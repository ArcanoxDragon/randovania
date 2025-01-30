import dataclasses
from typing import Self

from frozendict import frozendict

from randovania.bitpacking.json_dataclass import JsonDataclass
from randovania.bitpacking.type_enforcement import DataclassPostInitTypeCheck
from randovania.game.game_enum import RandovaniaGame
from randovania.game_description.hint_features import PickupHintFeature
from randovania.game_description.resources.location_category import LocationCategory

# how to order json-encoded fields
BASE_METADATA_STORAGE_ORDER = -20
ADDITIONAL_RESOURCES_STORAGE_ORDER = -10
OTHER_METADATA_STORAGE_ORDER = 0
GENERATOR_PARAMS_STORAGE_ORDER = 10
EXTRA_DICT_STORAGE_ORDER = 20


@dataclasses.dataclass(frozen=True, kw_only=True)
class BasePickupDefinition(JsonDataclass, DataclassPostInitTypeCheck):
    game: RandovaniaGame = dataclasses.field(metadata={"init_from_extra": True})
    """The game this pickup comes from."""

    name: str = dataclasses.field(metadata={"init_from_extra": True})
    """The name of the pickup."""

    gui_category: PickupHintFeature = dataclasses.field(metadata={"init_from_extra": True})
    """
    Used in the GUI for visually grouping pickups with the same precise category.
    """

    hint_features: frozenset[PickupHintFeature] = dataclasses.field(metadata={"init_from_extra": True})
    """Defines which features this pickup can be referred to with by hints."""

    model_name: str = dataclasses.field(metadata={"storage_order": BASE_METADATA_STORAGE_ORDER})
    """The name of the model that should be used by default for this pickup."""

    offworld_models: frozendict[RandovaniaGame, str] = dataclasses.field(
        metadata={"storage_order": BASE_METADATA_STORAGE_ORDER}
    )
    """A dictionary defining the name of the model for other games if this pickup is in their world."""

    preferred_location_category: LocationCategory = dataclasses.field(
        metadata={"storage_order": BASE_METADATA_STORAGE_ORDER}
    )
    """
    The category for the preferred location. Used to determine where to place this Pickup when Major/Minor placement
    is enabled, and for when this pickup is referenced by a major/minor hint.
    """

    additional_resources: frozendict[str, int] = dataclasses.field(
        default_factory=frozendict,
        metadata={"exclude_if_default": True, "storage_order": ADDITIONAL_RESOURCES_STORAGE_ORDER},
    )
    """Defines item resources (as short names) which all will be additionally provided when the pickup is collected."""

    index_age_impact: float = dataclasses.field(
        default=1.0, metadata={"exclude_if_default": True, "storage_order": GENERATOR_PARAMS_STORAGE_ORDER}
    )
    """
    During generation, determines by how much to increase all reachable location's age before this pickup is placed.
    The older a location is, the less likely it is for future pickups to be placed there.
    """

    probability_offset: float = dataclasses.field(
        default=0.0, metadata={"exclude_if_default": True, "storage_order": GENERATOR_PARAMS_STORAGE_ORDER}
    )
    """During generation, determines how much the weight when placing the pickup will be offset."""

    probability_multiplier: float = dataclasses.field(
        default=1.0, metadata={"exclude_if_default": True, "storage_order": GENERATOR_PARAMS_STORAGE_ORDER}
    )
    """During generation, determines by how much the weight when placing the pickup will be multiplied."""

    description: str | None = dataclasses.field(
        default=None, metadata={"exclude_if_default": True, "storage_order": EXTRA_DICT_STORAGE_ORDER - 1}
    )
    """An extra description of the pickup. Will be used in the GUI for more info."""

    extra: frozendict = dataclasses.field(
        default_factory=frozendict, metadata={"exclude_if_default": True, "storage_order": EXTRA_DICT_STORAGE_ORDER}
    )
    """
    A dictionary that can contain any arbitrary game-specific extra information.
    Developers can use the game-specific however they need to.
    """

    @classmethod
    def from_json_with_categories(
        cls,
        name: str,
        game: RandovaniaGame,
        pickup_categories: dict[str, PickupHintFeature],
        value: dict,
    ) -> Self:
        gui_category = pickup_categories[value["gui_category"]]
        features = frozenset(pickup_categories[category] for category in value["hint_features"])
        return cls.from_json(
            value,
            game=game,
            name=name,
            gui_category=gui_category,
            hint_features=features,
        )

    @property
    def as_json(self) -> dict:
        return {
            "gui_category": self.gui_category.name,
            "hint_features": sorted(feature.name for feature in self.hint_features),
            **super().as_json,
        }
