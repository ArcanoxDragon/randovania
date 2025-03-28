from __future__ import annotations

from typing import TYPE_CHECKING

import randovania.game.data
import randovania.game.development_state
import randovania.game.generator
import randovania.game.gui
import randovania.game.hints
import randovania.game.layout
import randovania.game.web_info
from randovania.games.dread.layout.dread_configuration import DreadConfiguration
from randovania.games.dread.layout.dread_cosmetic_patches import DreadCosmeticPatches
from randovania.games.dread.layout.preset_describer import DreadPresetDescriber

if TYPE_CHECKING:
    from randovania.exporter.game_exporter import GameExporter
    from randovania.exporter.patch_data_factory import PatchDataFactory
    from randovania.interface_common.options import PerGameOptions


def _options() -> type[PerGameOptions]:
    from randovania.games.dread.exporter.options import DreadPerGameOptions

    return DreadPerGameOptions


def _gui() -> randovania.game.gui.GameGui:
    from randovania.games.dread import gui
    from randovania.games.dread.layout import progressive_items
    from randovania.gui.game_details.hint_details_tab import HintDetailsTab

    return randovania.game.gui.GameGui(
        tab_provider=gui.dread_preset_tabs,
        cosmetic_dialog=gui.DreadCosmeticPatchesDialog,
        export_dialog=gui.DreadGameExportDialog,
        progressive_item_gui_tuples=progressive_items.tuples(),
        spoiler_visualizer=(HintDetailsTab, gui.DreadTeleporterDetailsTab),
        game_tab=gui.DreadGameTabWidget,
    )


def _patch_data_factory() -> type[PatchDataFactory]:
    from randovania.games.dread.exporter.patch_data_factory import DreadPatchDataFactory

    return DreadPatchDataFactory


def _exporter() -> GameExporter:
    from randovania.games.dread.exporter.game_exporter import DreadGameExporter

    return DreadGameExporter()


def _generator() -> randovania.game.generator.GameGenerator:
    from randovania.games.dread.generator.base_patches_factory import DreadBasePatchesFactory
    from randovania.games.dread.generator.bootstrap import DreadBootstrap
    from randovania.games.dread.generator.pool_creator import pool_creator
    from randovania.generator.filler.weights import ActionWeights

    return randovania.game.generator.GameGenerator(
        pickup_pool_creator=pool_creator,
        base_patches_factory=DreadBasePatchesFactory(),
        bootstrap=DreadBootstrap(),
        action_weights=ActionWeights(),
    )


def _hints() -> randovania.game.hints.GameHints:
    from randovania.games.dread.generator.hint_distributor import DreadHintDistributor

    return randovania.game.hints.GameHints(
        hint_distributor=DreadHintDistributor(),
        specific_pickup_hints={},  # TODO: DNA
    )


def _hash_words() -> list[str]:
    from randovania.games.dread.hash_words import HASH_WORDS

    return HASH_WORDS


game_data: randovania.game.data.GameData = randovania.game.data.GameData(
    short_name="Dread",
    long_name="Metroid Dread",
    development_state=randovania.game.development_state.DevelopmentState.STABLE,
    presets=[
        {"path": "starter_preset.rdvpreset"},
        {"path": "april_fools_2023.rdvpreset"},
    ],
    faq=[
        (
            "What Switch Emulators does Randovania support?",
            "Randovania only officially supports Ryujinx as an emulator, "
            "with no plans to support additional emulators.",
        ),
        (
            "Why does this missile door not open after I shoot a missile at it?",
            "Shoot another missile at the door. In the process of making certain missile doors possible to open from "
            "both sides, this issue shows up.",
        ),
        (
            "Using an Energy Recharge Station heals me to 299, but my energy maximum is 249. Which one is correct?",
            "The 299 is a display error. You can always see the correct value in the inventory screen.",
        ),
        (
            "Why is this pickup not animating, or displaying visual effects?",
            "While progressive pickups update to have the correct model, "
            "due to limitations these models are not animated or have any additional effects.",
        ),
        (
            "Can I use other mods?",
            "Depending on which files the other mods change, it can go from simple to impossible.\n\n"
            "* If a Lua file is modified, very likely it's not compatible.\n"
            "* If a PKG file is modified, it'll have to be combined with the one from Randovania.\n"
            "* Other mods likely work fine.\n\n"
            "When reporting issues, your first step is always to reproduce the issue without mods, "
            "**no matter how simple** the mod is.",
        ),
        (
            "I picked up the Speed Booster / Phantom Cloak / Storm Missile but can't use them!",
            "Press ZL + ZR + D-Pad Up to fix the issue."
            " Check the entry 'Crashing after suit upgrade' in 'Known Crashes' tab"
            " for important rules of when to use this button combination.\n\n"
            "You can also save and reload your game.",
        ),
        (
            "I entered the arena for Golzuna/Experiment Z-57 but it isn't there!",
            "Golzuna and Experiment Z-57 will not appear unless the X have been released from Elun.\n\n"
            "To activate the fight against Experiment Z-57, you must use the Morph Ball Launcher to enter the arena.",
        ),
        (
            "I opened the Wide Beam door in Dairon's Teleport to Cataris, but it won't let me through!",
            "Unlocking this door before turning on the power will render it unopenable.\n\n"
            "To fix this, simply save and reload the game.",
        ),
        (
            "I received a Beam/Missile upgrade from an E.M.M.I., and now my arm cannon doesn't work!",
            "Reload from checkpoint immediately to fix the issue. "
            "Your checkpoint was saved after killing the E.M.M.I., so you will not lose progress.",
        ),
    ],
    web_info=randovania.game.web_info.GameWebInfo(
        what_can_randomize=[
            "All items",
            "Elevator and shuttle destinations",
            "Starting locations",
            "Door locks",
            "A new goal has been added (DNA Hunt)",
        ],
        need_to_play=[
            "A modded Switch with Atmosphere and SimpleModManager; or Ryujinx",
            "A dumped RomFS of your original game. Either version 1.0.0 or 2.1.0",
        ],
    ),
    hash_words=_hash_words(),
    layout=randovania.game.layout.GameLayout(
        configuration=DreadConfiguration, cosmetic_patches=DreadCosmeticPatches, preset_describer=DreadPresetDescriber()
    ),
    options=_options,
    gui=_gui,
    generator=_generator,
    hints=_hints,
    patch_data_factory=_patch_data_factory,
    exporter=_exporter,
    multiple_start_nodes_per_area=True,
    defaults_available_in_game_sessions=True,
)
