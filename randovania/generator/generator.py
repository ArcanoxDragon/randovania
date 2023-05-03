import asyncio
import dataclasses
from random import Random
from typing import Callable

import tenacity

from randovania.game_description.assignment import (PickupTarget, PickupTargetAssociation)
from randovania.game_description.game_description import GameDescription
from randovania.game_description.resources.location_category import LocationCategory
from randovania.game_description.resources.pickup_entry import PickupEntry
from randovania.game_description.world.pickup_node import PickupNode
from randovania.generator import dock_weakness_distributor
from randovania.generator.filler.filler_library import (
    UnableToGenerate, filter_unassigned_pickup_nodes)
from randovania.generator.filler.runner import (FillerResults, PlayerPool,
                                                run_filler)
from randovania.generator.hint_distributor import PreFillParams
from randovania.generator.pickup_pool import pool_creator
from randovania.layout import filtered_database
from randovania.layout.base.available_locations import RandomizationMode
from randovania.layout.base.base_configuration import BaseConfiguration
from randovania.layout.generator_parameters import GeneratorParameters
from randovania.layout.layout_description import LayoutDescription
from randovania.layout.preset import Preset
from randovania.resolver import resolver
from randovania.resolver.exceptions import (GenerationFailure,
                                            ImpossibleForSolver)
from randovania.layout.exceptions import InvalidConfiguration


def _validate_item_pool_size(item_pool: list[PickupEntry], game: GameDescription,
                             configuration: BaseConfiguration) -> None:
    min_starting_items = configuration.standard_pickup_configuration.minimum_random_starting_pickups
    if len(item_pool) > game.world_list.num_pickup_nodes + min_starting_items:
        raise InvalidConfiguration(
            "Item pool has {} items, which is more than {} (game) + {} (minimum starting items)".format(
                len(item_pool), game.world_list.num_pickup_nodes, min_starting_items))


async def create_player_pool(rng: Random, configuration: BaseConfiguration,
                             player_index: int, num_players: int, rng_required: bool = True) -> PlayerPool:
    game = filtered_database.game_description_for_layout(configuration).get_mutable()

    game_generator = game.game.generator
    game.resource_database = game_generator.bootstrap.patch_resource_database(game.resource_database, configuration)

    base_patches = game_generator.base_patches_factory.create_base_patches(configuration, rng, game,
                                                                           num_players > 1,
                                                                           player_index=player_index,
                                                                           rng_required=rng_required)

    base_patches = dock_weakness_distributor.distribute_pre_fill_weaknesses(base_patches)

    base_patches = await game_generator.hint_distributor.assign_pre_filler_hints(
        base_patches,
        PreFillParams(
            rng,
            configuration,
            game,
            num_players > 1,
        ),
        rng_required=rng_required
    )

    pool_results = pool_creator.calculate_pool_results(configuration,
                                                       game,
                                                       base_patches,
                                                       rng,
                                                       rng_required=rng_required)
    target_assignment = [
        (index, PickupTarget(pickup, player_index))
        for index, pickup in pool_results.assignment.items()
    ]
    patches = base_patches.assign_new_pickups(target_assignment).assign_extra_starting_pickups(pool_results.starting)

    return PlayerPool(
        game=game,
        game_generator=game_generator,
        configuration=configuration,
        patches=patches,
        pickups=pool_results.to_place,
    )


async def _create_pools_and_fill(rng: Random,
                                 presets: list[Preset],
                                 status_update: Callable[[str], None],
                                 ) -> FillerResults:
    """
    Runs the rng-dependant parts of the generation, with retries
    :param rng:
    :param presets:
    :param status_update:
    :return:
    """
    player_pools: list[PlayerPool] = []

    for player_index, player_preset in enumerate(presets):
        status_update(f"Creating item pool for player {player_index + 1}")
        player_pools.append(await create_player_pool(rng, player_preset.configuration, player_index, len(presets)))

    for player_pool in player_pools:
        _validate_item_pool_size(player_pool.pickups, player_pool.game, player_pool.configuration)

    return await run_filler(rng, player_pools, status_update)


def _distribute_remaining_items(rng: Random,
                                filler_results: FillerResults,
                                presets: list[Preset]
                                ) -> FillerResults:
    major_pickup_nodes: list[tuple[int, PickupNode]] = []
    minor_pickup_nodes: list[tuple[int, PickupNode]] = []
    avoid_majors_pickup_nodes: set[tuple[int, PickupNode]] = set()
    all_remaining_pickups: list[PickupTarget] = []
    remaining_major_pickups: list[PickupTarget] = []

    assignments: dict[int, list[PickupTargetAssociation]] = {}

    modes = [preset.configuration.available_locations.randomization_mode for preset in presets]

    for player, filler_result in filler_results.player_results.items():
        split_major = modes[player] is RandomizationMode.MAJOR_MINOR_SPLIT
        minor_only_indices = presets[player].configuration.available_locations.minor_only_indices
        for pickup_node in filter_unassigned_pickup_nodes(filler_result.game.world_list.iterate_nodes(),
                                                          filler_result.patches.pickup_assignment):
            if split_major and pickup_node.location_category == LocationCategory.MAJOR:
                major_pickup_nodes.append((player, pickup_node))
            else:
                minor_pickup_nodes.append((player, pickup_node))
                if pickup_node.pickup_index in minor_only_indices:
                    avoid_majors_pickup_nodes.add((player, pickup_node))

        for pickup in filler_result.unassigned_pickups:
            target = PickupTarget(pickup, player)
            if split_major and pickup.generator_params.preferred_location_category == LocationCategory.MAJOR:
                remaining_major_pickups.append(target)
            else:
                all_remaining_pickups.append(target)

        assignments[player] = []

    def assign_pickup(node_player: int, node: PickupNode, pickup_target: PickupTarget):
        assignments[node_player].append((node.pickup_index, pickup_target))

    def assign_while_both_non_empty(nodes: list[tuple[int, PickupNode]], pickups: list[PickupTarget]):
        rng.shuffle(nodes)
        rng.shuffle(pickups)

        while nodes and pickups:
            node_player, node = nodes.pop()
            pickup = pickups.pop()
            assign_pickup(node_player, node, pickup)

    # distribute major pickups
    assign_while_both_non_empty(major_pickup_nodes, remaining_major_pickups)

    # distribute minor pickups (and full randomization)
    assign_while_both_non_empty(minor_pickup_nodes, all_remaining_pickups)

    # spill-over from one pool into the other
    unassigned_pickup_nodes = [*major_pickup_nodes, *minor_pickup_nodes]
    all_remaining_pickups.extend(remaining_major_pickups)
    rng.shuffle(unassigned_pickup_nodes)
    rng.shuffle(all_remaining_pickups)

    # after shuffling, sort both lists such that locations marked as "no majors" come first and major items come last
    # this will attempt to prevent majors from being assigned to locations marked as "no majors", but allows for such
    # assignments to happen if there aren't enough remaining locations
    unassigned_pickup_nodes.sort(key=lambda n: 0 if n in avoid_majors_pickup_nodes else 1)
    all_remaining_pickups.sort(
        key=lambda t: 1 if t.pickup.generator_params.preferred_location_category == LocationCategory.MAJOR else 0)

    if len(all_remaining_pickups) > len(unassigned_pickup_nodes):
        raise InvalidConfiguration(
            "Received {} remaining pickups, but there's only {} unassigned locations.".format(
                len(all_remaining_pickups),
                len(unassigned_pickup_nodes)
            ))

    for (node_player, node), pickup in zip(unassigned_pickup_nodes, all_remaining_pickups):
        assign_pickup(node_player, node, pickup)

    return dataclasses.replace(
        filler_results,
        player_results={
            player: dataclasses.replace(
                result,
                patches=result.patches.assign_new_pickups(assignments[player])
            ) for player, result in filler_results.player_results.items()
        }
    )


async def _create_description(generator_params: GeneratorParameters,
                              status_update: Callable[[str], None],
                              attempts: int,
                              ) -> LayoutDescription:
    """
    :param generator_params:
    :param status_update:
    :return:
    """
    rng = generator_params.create_rng()

    presets = [
        generator_params.get_preset(i)
        for i in range(generator_params.player_count)
    ]

    retrying = tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(attempts),
        retry=tenacity.retry_if_exception_type(UnableToGenerate),
        reraise=True
    )

    filler_results = await retrying(_create_pools_and_fill, rng, presets, status_update)

    filler_results = _distribute_remaining_items(rng, filler_results, presets)
    filler_results = await dock_weakness_distributor.distribute_post_fill_weaknesses(rng, filler_results, status_update)

    return LayoutDescription.create_new(
        generator_parameters=generator_params,
        all_patches={
            player: result.patches
            for player, result in filler_results.player_results.items()
        },
        item_order=filler_results.action_log,
    )


async def generate_and_validate_description(generator_params: GeneratorParameters,
                                            status_update: Callable[[str], None] | None,
                                            validate_after_generation: bool,
                                            timeout: int | None = 600,
                                            attempts: int = 15,
                                            ) -> LayoutDescription:
    """
    Creates a LayoutDescription for the given Permalink.
    :param generator_params:
    :param status_update:
    :param validate_after_generation:
    :param timeout: Abort generation after this many seconds.
    :param attempts: Attempt this many generations.
    :return:
    """
    if status_update is None:
        status_update = id

    try:
        result = await _create_description(
            generator_params=generator_params,
            status_update=status_update,
            attempts=attempts,
        )
    except UnableToGenerate as e:
        raise GenerationFailure("Could not generate a game with the given settings",
                                generator_params=generator_params, source=e) from e

    if validate_after_generation and generator_params.player_count == 1:
        final_state_async = resolver.resolve(
            configuration=generator_params.get_preset(0).configuration,
            patches=result.all_patches[0],
            status_update=status_update,
        )
        try:
            final_state_by_resolve = await asyncio.wait_for(final_state_async, timeout)
        except asyncio.TimeoutError as e:
            raise ImpossibleForSolver("Timeout reached when validating possibility",
                                      generator_params=generator_params, layout=result) from e

        if final_state_by_resolve is None:
            raise ImpossibleForSolver("Generated game was considered impossible by the solver",
                                      generator_params=generator_params, layout=result)

    return result
