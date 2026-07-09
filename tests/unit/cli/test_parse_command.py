"""Тесты для autodoc/cli/commands/parse.py.

Команда `parse` проверяется целиком через CliRunner. ComponentParser
подменяется на уровне CLI — поведение его внутреннего пайплайна покрыто
в другом месте набора тестов.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from autodoc.cli.app import cli
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import NetworkError, ParsingError
from autodoc.models.parsed_result import ParsedResult
from tests.unit.cli.conftest import (
    VALID_PARSER_CONFIG,
    make_parsed_result,
    write_parser_config,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1


@pytest.mark.business_logic
def test_parse_happy_path_writes_parsed_data_and_constructs_parser(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Успешный сценарий сохраняет parsed_data.json и создаёт ComponentParser с загруженным конфигом."""
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"

    output_file = tmp_path / "data" / "parsed_data.json"
    assert output_file.exists()
    round_tripped = ParsedResult.model_validate_json(output_file.read_text(encoding="utf-8"))
    assert round_tripped == parsed_result

    mock_parser_cls.assert_called_once()
    called_config, called_data_dir = mock_parser_cls.call_args.args
    assert called_config == ParserConfigSchema(**VALID_PARSER_CONFIG)
    assert called_data_dir == tmp_path / "data"


@pytest.mark.contract
def test_parse_config_load_failure_exits_nonzero_with_clean_message(
    tmp_path: Path, configs_dir: Path
) -> None:
    """Отсутствующий или некорректный конфиг парсера завершает команду с кодом 1 и понятным сообщением, без трейсбека."""
    # configs_dir остаётся пустым — файл parser_config.* отсутствует, поэтому
    # ConfigManager.load_parser_config возвращает None.
    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert 'File "' not in result.output


@pytest.mark.business_logic
def test_parse_skip_conan_excludes_conan_enrich_step(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """--skip-conan исключает ConanEnrichStep из пайплайна парсинга."""
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.with_steps_excluded.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "parse", "--skip-conan",
        ],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_parser_cls.assert_not_called()
    mock_parser_cls.with_steps_excluded.assert_called_once()
    _, _, exclude = mock_parser_cls.with_steps_excluded.call_args.args
    assert exclude == [mocker.ANY]
    assert "ConanEnrichStep" in result.output


@pytest.mark.business_logic
def test_parse_skip_validation_excludes_artifactory_validation_step(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """--skip-validation исключает ArtifactoryValidationStep из пайплайна парсинга."""
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.with_steps_excluded.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "parse", "--skip-validation",
        ],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_parser_cls.assert_not_called()
    mock_parser_cls.with_steps_excluded.assert_called_once()
    assert "ArtifactoryValidationStep" in result.output


@pytest.mark.business_logic
def test_parse_both_skip_flags_exclude_both_step_classes(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Совместное указание --skip-conan и --skip-validation исключает оба соответствующих шага сразу."""
    from autodoc.parser.steps.conan_step import ConanEnrichStep
    from autodoc.parser.steps.validation_step import ArtifactoryValidationStep

    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.with_steps_excluded.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        [
            "--base-dir", str(tmp_path),
            "--configs-dir", str(configs_dir),
            "parse", "--skip-conan", "--skip-validation",
        ],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    _, _, exclude = mock_parser_cls.with_steps_excluded.call_args.args
    assert set(exclude) == {ConanEnrichStep, ArtifactoryValidationStep}


@pytest.mark.business_logic
def test_parse_neither_skip_flag_uses_plain_constructor(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Без флагов пропуска шагов используется обычный конструктор ComponentParser(...)."""
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_parser_cls.assert_called_once()
    mock_parser_cls.with_steps_excluded.assert_not_called()


@pytest.mark.business_logic
def test_parse_network_error_during_parse_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """NetworkError, возникающая во время parser.parse(), завершает команду с кодом 1 и понятным сообщением."""
    write_parser_config(configs_dir)
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.side_effect = NetworkError("connection refused")

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "connection refused" in result.output


@pytest.mark.business_logic
def test_parse_parsing_error_during_parse_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """ParsingError, возникающая во время parser.parse(), завершает команду с кодом 1 и понятным сообщением."""
    write_parser_config(configs_dir)
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.side_effect = ParsingError("bad manifest")

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert "bad manifest" in result.output


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        pytest.param(["--save-intermediate"], True, id="flag-present"),
        pytest.param([], False, id="flag-omitted"),
    ],
)
@pytest.mark.business_logic
def test_parse_save_intermediate_is_forwarded_to_parser(
    tmp_path: Path, configs_dir: Path, mocker, flags: list[str], expected: bool
) -> None:
    """--save-intermediate передаётся в parser.parse(save_intermediate=...) в заданном виде."""
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse", *flags],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_parser_cls.return_value.parse.assert_called_once_with(save_intermediate=expected)


@pytest.mark.business_logic
def test_parse_creates_data_dir_when_missing(
    tmp_path: Path, configs_dir: Path, mocker
) -> None:
    """Директория data/ создаётся автоматически, даже если её не было до запуска команды."""
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.return_value = parsed_result

    data_dir = tmp_path / "data"
    assert not data_dir.exists()

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    assert data_dir.exists()
