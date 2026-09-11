"""Тесты для autodoc/cli/commands/parse.py."""

from pathlib import Path

import pytest
from click.testing import CliRunner
from pytest_mock import MockerFixture

from autodoc.cli.app import cli
from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import NetworkError, ParsingError
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep
from tests.unit.cli.utils import (
    VALID_PARSER_CONFIG,
    make_parsed_result,
    write_parser_config,
)

_EXIT_SUCCESS: int = 0
_EXIT_FAILURE: int = 1


@pytest.mark.business_logic
def test_parse_happy_path_writes_parsed_data_and_constructs_parser(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
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


@pytest.mark.infrastructure
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
@pytest.mark.parametrize(
    ("flags", "expected_exclude"),
    [
        # --skip-conan — исключает только ConanEnrichStep
        pytest.param(["--skip-conan"], [ConanEnrichStep], id="skip-conan"),
        # --skip-validation — исключает только ArtifactoryValidationStep
        pytest.param(["--skip-validation"], [ArtifactoryValidationStep], id="skip-validation"),
        # оба флага сразу — исключаются оба шага
        pytest.param(
            ["--skip-conan", "--skip-validation"],
            [ConanEnrichStep, ArtifactoryValidationStep],
            id="both-skip-flags",
        ),
        # ни один флаг не передан — используется обычный конструктор, без исключений
        pytest.param([], None, id="no-skip-flags"),
    ],
)
def test_parse_skip_flags_control_step_exclusion(
    tmp_path: Path,
    configs_dir: Path,
    mocker: MockerFixture,
    flags: list[str],
    expected_exclude: list[type] | None,
) -> None:
    """
    Флаги --skip-conan/--skip-validation исключают соответствующие шаги пайплайна через
    parser.exclude(...); ComponentParser в любом случае создаётся обычным конструктором.
    """
    write_parser_config(configs_dir)
    parsed_result = make_parsed_result()
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.return_value = parsed_result

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse", *flags],
    )

    assert result.exit_code == _EXIT_SUCCESS, f"output: {result.output}\nexc: {result.exception}"
    mock_parser_cls.assert_called_once()
    if expected_exclude is None:
        mock_parser_cls.return_value.exclude.assert_not_called()
    else:
        assert mock_parser_cls.return_value.exclude.call_args_list == [
            mocker.call(step) for step in expected_exclude
        ]
        for excluded_step in expected_exclude:
            assert excluded_step.__name__ in result.output


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    ("exc_cls", "message"),
    [
        # NetworkError — сбой сети/TFS/Artifactory/Conan во время пайплайна
        pytest.param(NetworkError, "connection refused", id="network-error"),
        # ParsingError — ошибка разбора манифеста/JSON/YAML во время пайплайна
        pytest.param(ParsingError, "bad manifest", id="parsing-error"),
    ],
)
def test_parse_domain_error_during_parse_exits_nonzero_cleanly(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture, exc_cls: type, message: str
) -> None:
    """NetworkError/ParsingError, возникающая во время parser.parse(), завершает команду с кодом 1 и понятным сообщением."""
    write_parser_config(configs_dir)
    mock_parser_cls = mocker.patch("autodoc.cli.commands.parse.ComponentParser")
    mock_parser_cls.return_value.parse.side_effect = exc_cls(message)

    result = CliRunner().invoke(
        cli,
        ["--base-dir", str(tmp_path), "--configs-dir", str(configs_dir), "parse"],
    )

    assert result.exit_code == _EXIT_FAILURE
    assert "Traceback" not in result.output
    assert message in result.output


@pytest.mark.business_logic
@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        pytest.param(["--save-intermediate"], True, id="flag-present"),
        pytest.param([], False, id="flag-omitted"),
    ],
)
def test_parse_save_intermediate_is_forwarded_to_parser(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture, flags: list[str], expected: bool
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


@pytest.mark.infrastructure
def test_parse_creates_data_dir_when_missing(
    tmp_path: Path, configs_dir: Path, mocker: MockerFixture
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
