from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from randovania.game.game_enum import RandovaniaGame
from randovania.games.common.prime_family.gui.export_validator import is_prime1_iso_validator, is_prime2_iso_validator
from randovania.games.prime1.exporter.options import PrimePerGameOptions
from randovania.games.prime2.exporter.export_params import EchoesGameExportParams
from randovania.games.prime2.exporter.options import EchoesPerGameOptions
from randovania.games.prime2.gui.generated.echoes_game_export_dialog_ui import Ui_EchoesGameExportDialog
from randovania.games.prime2.layout.echoes_configuration import EchoesConfiguration
from randovania.gui.dialog.game_export_dialog import (
    GameExportDialog,
    add_field_validation,
    output_file_validator,
    prompt_for_input_file,
    prompt_for_output_file,
    spoiler_path_for,
    update_validation,
)
from randovania.interface_common import game_workdir

if TYPE_CHECKING:
    from PySide6.QtWidgets import QLineEdit, QPushButton

    from randovania.exporter.game_exporter import GameExportParams
    from randovania.interface_common.options import Options, PerGameOptions
    from randovania.patching.patchers.exceptions import UnableToExportError

_VALID_GAME_TEXT = "(internal game copy)"


def has_internal_copy(contents_file_path: Path) -> bool:
    result = game_workdir.discover_game(contents_file_path)
    if result is not None:
        game_id, _ = result
        if game_id.startswith("G2M"):
            return True
    return False


def delete_internal_copy(internal_copies_path: Path) -> None:
    internal_copies_path = internal_copies_path.joinpath("prime2")
    if internal_copies_path.exists():
        shutil.rmtree(internal_copies_path)


def check_extracted_game(input_file_edit: QLineEdit, input_file_button: QPushButton, contents_file_path: Path) -> bool:
    prompt_input_file = not has_internal_copy(contents_file_path)
    input_file_edit.setEnabled(prompt_input_file)

    if prompt_input_file:
        input_file_button.setText("Select File")
    else:
        input_file_button.setText("Delete internal copy")
        input_file_edit.setText(_VALID_GAME_TEXT)

    return prompt_input_file


def echoes_input_validator(input_file: Path | None, prompt_input_file: bool, input_file_edit: QLineEdit) -> bool:
    if prompt_input_file:
        return is_prime2_iso_validator(input_file)
    else:
        return input_file_edit.text() != _VALID_GAME_TEXT


class EchoesGameExportDialog(GameExportDialog[EchoesConfiguration], Ui_EchoesGameExportDialog):
    _prompt_input_file: bool
    _use_prime_models: bool

    @classmethod
    def game_enum(cls) -> RandovaniaGame:
        return RandovaniaGame.METROID_PRIME_ECHOES

    def __init__(
        self,
        options: Options,
        configuration: EchoesConfiguration,
        word_hash: str,
        spoiler: bool,
        games: list[RandovaniaGame],
    ):
        super().__init__(options, configuration, word_hash, spoiler, games)

        self.default_output_name = f"Echoes Randomizer - {word_hash}"
        self._prompt_input_file = check_extracted_game(
            self.input_file_edit, self.input_file_button, self._contents_file_path
        )

        per_game = options.per_game_options(EchoesPerGameOptions)

        # Input
        self.input_file_button.clicked.connect(self._on_input_file_button)

        # Output
        self.output_file_button.clicked.connect(self._on_output_file_button)

        # Prime input
        self.prime_file_button.clicked.connect(self._on_prime_file_button)

        if RandovaniaGame.METROID_PRIME in games:
            self._use_prime_models = RandovaniaGame.METROID_PRIME in per_game.use_external_models
            self.prime_models_check.setChecked(self._use_prime_models)
            self._on_prime_models_check()
            self.prime_models_check.clicked.connect(self._on_prime_models_check)

            prime_options = options.per_game_options(PrimePerGameOptions)
            if prime_options.input_path is not None:
                self.prime_file_edit.setText(str(prime_options.input_path))

        else:
            self._use_prime_models = False
            self.prime_models_check.hide()
            self.prime_file_edit.hide()
            self.prime_file_label.hide()
            self.prime_file_button.hide()

        if self._prompt_input_file and per_game.input_path is not None:
            self.input_file_edit.setText(str(per_game.input_path))

        if per_game.output_directory is not None:
            output_path = per_game.output_directory.joinpath(f"{self.default_output_name}.iso")
            self.output_file_edit.setText(str(output_path))

        add_field_validation(
            accept_button=self.accept_button,
            fields={
                self.input_file_edit: lambda: echoes_input_validator(
                    self.input_file, self._prompt_input_file, self.input_file_edit
                ),
                self.output_file_edit: lambda: output_file_validator(self.output_file),
                self.prime_file_edit: lambda: self._use_prime_models
                and is_prime1_iso_validator(self.prime_file, iso_required=True),
            },
        )

    def update_per_game_options(self, per_game: PerGameOptions) -> PerGameOptions:
        assert isinstance(per_game, EchoesPerGameOptions)

        per_game_changes: dict = {}
        if self._prompt_input_file:
            per_game_changes["input_path"] = self.input_file

        use_external_models = per_game.use_external_models.copy()
        if not self.prime_models_check.isHidden():
            if self._use_prime_models:
                use_external_models.add(RandovaniaGame.METROID_PRIME)
            else:
                use_external_models.discard(RandovaniaGame.METROID_PRIME)

        return dataclasses.replace(
            per_game,
            output_directory=self.output_file.parent,
            use_external_models=use_external_models,
            **per_game_changes,
        )

    def save_options(self) -> None:
        super().save_options()
        if not self._use_prime_models:
            return

        with self._options as options:
            from randovania.games.prime1.exporter.options import PrimePerGameOptions

            options.set_per_game_options(
                dataclasses.replace(
                    options.per_game_options(PrimePerGameOptions),
                    input_path=self.prime_file,
                ),
            )

    # Getters
    @property
    def input_file(self) -> Path | None:
        if self._prompt_input_file:
            return Path(self.input_file_edit.text())
        return None

    @property
    def output_file(self) -> Path:
        return Path(self.output_file_edit.text())

    @property
    def prime_file(self) -> Path | None:
        return Path(self.prime_file_edit.text()) if self.prime_file_edit.text() else None

    @property
    def auto_save_spoiler(self) -> bool:
        return self.auto_save_spoiler_check.isChecked()

    # Checks

    # Input file
    def _on_input_file_button(self) -> None:
        if self._prompt_input_file:
            input_file = prompt_for_input_file(self, self.input_file_edit, ["iso"])
            if input_file is not None:
                self.input_file_edit.setText(str(input_file.absolute()))
        else:
            delete_internal_copy(self._options.internal_copies_path)
            self.input_file_edit.setText("")
            self._prompt_input_file = check_extracted_game(
                self.input_file_edit, self.input_file_button, self._contents_file_path
            )

    # Output File
    def _on_output_file_button(self) -> None:
        output_file = prompt_for_output_file(self, ["iso"], f"{self.default_output_name}.iso", self.output_file_edit)
        if output_file is not None:
            self.output_file_edit.setText(str(output_file))

    # Prime input
    def _on_prime_file_button(self) -> None:
        prime_file = prompt_for_input_file(self, self.prime_file_edit, ["iso"])
        if prime_file is not None:
            self.prime_file_edit.setText(str(prime_file.absolute()))

    def _on_prime_models_check(self) -> None:
        use_prime_models = self.prime_models_check.isChecked()
        self._use_prime_models = use_prime_models
        self.prime_file_edit.setEnabled(use_prime_models)
        self.prime_file_label.setEnabled(use_prime_models)
        self.prime_file_button.setEnabled(use_prime_models)
        update_validation(self.prime_file_edit)

    @property
    def _contents_file_path(self) -> Path:
        return self._options.internal_copies_path.joinpath("prime2", "contents")

    def get_game_export_params(self) -> GameExportParams:
        spoiler_output = spoiler_path_for(self.auto_save_spoiler, self.output_file)
        backup_files_path = self._options.internal_copies_path.joinpath("prime2", "vanilla")
        asset_cache_path = self._options.internal_copies_path.joinpath("prime2", "prime1_models")

        return EchoesGameExportParams(
            spoiler_output=spoiler_output,
            input_path=self.input_file,
            output_path=self.output_file,
            contents_files_path=self._contents_file_path,
            backup_files_path=backup_files_path,
            asset_cache_path=asset_cache_path,
            prime_path=self.prime_file,
            use_prime_models=self._use_prime_models,
        )

    async def handle_unable_to_export(self, error: UnableToExportError) -> None:
        delete_internal_copy(self._options.internal_copies_path)

        await super().handle_unable_to_export(error)
