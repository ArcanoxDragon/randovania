from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, call

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from randovania.gui.game_details.game_details_window import GameDetailsWindow
from randovania.gui.game_details.pickup_details_tab import PickupDetailsTab
from randovania.interface_common.players_configuration import PlayersConfiguration
from randovania.layout.generator_parameters import GeneratorParameters
from randovania.layout.layout_description import LayoutDescription


async def test_export_iso(skip_qtbot, mocker):
    # Setup
    mock_execute_dialog = mocker.patch(
        "randovania.gui.lib.async_dialog.execute_dialog",
        new_callable=AsyncMock,
        return_value=QtWidgets.QDialog.DialogCode.Accepted,
    )

    options = MagicMock()
    options.output_directory = None

    window_manager = MagicMock()

    window = GameDetailsWindow(window_manager, options)
    skip_qtbot.addWidget(window)
    window.layout_description = MagicMock()
    window._player_names = {}
    game = window.layout_description.get_preset.return_value.game
    game.exporter.can_start_new_export = False
    window.layout_description.all_games = [game]
    configuration = window.layout_description.get_preset.return_value.configuration
    patch_data = game.patch_data_factory.return_value.create_data.return_value

    players_config = PlayersConfiguration(
        player_index=window.current_player_index,
        player_names=window._player_names,
    )

    # Run
    await window._export_iso()

    # Assert
    game.patch_data_factory.assert_called_once_with(
        window.layout_description, players_config, options.generic_per_game_options.return_value.cosmetic_patches
    )
    game.gui.export_dialog.assert_called_once_with(
        options,
        configuration,
        window.layout_description.shareable_word_hash,
        window.layout_description.has_spoiler,
        [game],
    )
    mock_execute_dialog.assert_awaited_once_with(game.gui.export_dialog.return_value)
    game.exporter.export_game.assert_called_once_with(
        patch_data,
        game.gui.export_dialog.return_value.get_game_export_params.return_value,
        progress_update=ANY,
    )


def test_update_layout_description_no_spoiler(skip_qtbot, mocker):
    # Setup
    mock_describer = mocker.patch("randovania.layout.preset_describer.describe", return_value=["a", "b", "c", "d"])
    mock_merge = mocker.patch("randovania.layout.preset_describer.merge_categories", return_value="<description>")

    options = MagicMock()
    description = MagicMock(spec=LayoutDescription)
    description.world_count = 1
    description.shareable_hash = "12345"
    description.shareable_word_hash = "Some Hash Words"
    description.randovania_version_text = "v1.2.4"
    description.permalink.as_base64_str = "<permalink>"
    description.generator_parameters = MagicMock(spec=GeneratorParameters)
    description.has_spoiler = False

    preset = description.get_preset.return_value
    preset.game.data.layout.get_ingame_hash.return_value = "<image>"
    preset.name = "CustomPreset"

    window = GameDetailsWindow(None, options)
    skip_qtbot.addWidget(window)

    # Run
    window.update_layout_description(description)

    # Assert
    mock_describer.assert_called_once_with(preset)
    mock_merge.assert_has_calls(
        [
            call(["a", "c"]),
            call(["b", "d"]),
        ]
    )
    assert window.layout_title_label.text() == (
        """
        <p>
            Generated with Randovania v1.2.4<br />
            Seed Hash: Some Hash Words (12345)<br/>
            In-game Hash: <image><br/>
            Preset Name: CustomPreset
        </p>
        """
    )


@pytest.mark.parametrize("twice", [False, True])
def test_update_layout_description_actual_seed(skip_qtbot, test_files_dir, twice: bool):
    description = LayoutDescription.from_file(test_files_dir.joinpath("log_files", "seed_a.rdvgame"))

    # Run
    window = GameDetailsWindow(None, MagicMock())
    skip_qtbot.addWidget(window)
    window.update_layout_description(description)
    if twice:
        window.update_layout_description(description)

    # Assert
    pickup_details_tab = window._game_details_tabs[0]
    assert isinstance(pickup_details_tab, PickupDetailsTab)
    assert len(pickup_details_tab.pickup_spoiler_buttons) == 119
    assert pickup_details_tab.pickup_spoiler_show_all_button.text() == "Show All"
    skip_qtbot.mouseClick(pickup_details_tab.pickup_spoiler_show_all_button, QtCore.Qt.MouseButton.LeftButton)
    assert pickup_details_tab.pickup_spoiler_show_all_button.text() == "Hide All"


def test_update_layout_description_prime1_crazy(skip_qtbot, test_files_dir):
    description = LayoutDescription.from_file(test_files_dir.joinpath("log_files", "prime1_crazy_seed.rdvgame"))

    # Run
    window = GameDetailsWindow(None, MagicMock())
    skip_qtbot.addWidget(window)
    window.update_layout_description(description)

    # Assert
    pickup_details_tab = window._game_details_tabs[0]
    assert isinstance(pickup_details_tab, PickupDetailsTab)
    assert len(pickup_details_tab.pickup_spoiler_buttons) == 293


@pytest.mark.parametrize("has_validator", [False, True])
def test_close_event(skip_qtbot, has_validator):
    window = GameDetailsWindow(None, MagicMock())
    skip_qtbot.addWidget(window)

    validator = MagicMock()
    if has_validator:
        window.validator_widget = validator

    # Run
    window.closeEvent(QtGui.QCloseEvent())

    # Assert
    if has_validator:
        validator.stop_validator.assert_called_once_with()
