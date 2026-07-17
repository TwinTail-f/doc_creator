"""Тесты для autodoc/cli/helpers.py.

Хелперы вызываются напрямую (без CliRunner), чтобы регрессии в них
обнаруживались сразу в источнике, а не только опосредованно — через падение
теста команды с непонятной причиной. Часть этой логики уже косвенно
покрыта тестами уровня команд в этом пакете.
"""

import json
from pathlib import Path

import click
import pytest
from pydantic import ValidationError as PydanticValidationError

from autodoc.cli.context import CliCtx
from autodoc.cli.helpers import (
    cli_error_boundary,
    load_parsed_data,
    make_publisher,
    print_publish_result,
)
from autodoc.exceptions import ConfigError, DocGeneratorError, PublishError, ValidationError
from tests.unit.cli.conftest import (
    make_confluence_config,
    make_parsed_result,
    make_publish_report,
    write_confluence_config,
    write_parsed_data,
)


@pytest.mark.infrastructure
def test_cli_error_boundary_no_exception_completes_normally() -> None:
    """Если внутри блока with исключение не возникает, выполнение завершается штатно."""
    entered = False
    with cli_error_boundary("Test Panel"):
        entered = True

    assert entered is True


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    "exc_cls",
    [ConfigError, DocGeneratorError, PublishError],
)
def test_cli_error_boundary_catches_domain_exceptions_as_system_exit(exc_cls: type) -> None:
    """ConfigError, DocGeneratorError и PublishError перехватываются и превращаются в SystemExit(1)."""
    with pytest.raises(SystemExit) as exc_info:
        with cli_error_boundary("Test Panel"):
            raise exc_cls("boom")

    assert exc_info.value.code == 1


@pytest.mark.infrastructure
@pytest.mark.parametrize("exc_cls", [ValueError, RuntimeError])
def test_cli_error_boundary_catches_unrelated_exceptions_as_system_exit(exc_cls: type) -> None:
    """Исключение, не входящее в (ConfigError, DocGeneratorError, PublishError), тоже
    перехватывается — пользователь никогда не видит «сырой» трейсбек — и превращается
    в SystemExit(1)."""
    with pytest.raises(SystemExit) as exc_info:
        with cli_error_boundary("Test Panel"):
            raise exc_cls("not a domain error")

    assert exc_info.value.code == 1


@pytest.mark.business_logic
def test_load_parsed_data_missing_file_raises_doc_generator_error_mentioning_parse(
    tmp_path: Path,
) -> None:
    """Отсутствующий parsed_data.json приводит к DocGeneratorError с упоминанием команды parse."""
    with pytest.raises(DocGeneratorError) as exc_info:
        load_parsed_data(tmp_path)

    assert "parse" in str(exc_info.value).lower()


@pytest.mark.business_logic
def test_load_parsed_data_empty_file_raises_validation_error_mentioning_interruption(
    tmp_path: Path,
) -> None:
    """Пустой или состоящий из пробелов parsed_data.json приводит к ValidationError с упоминанием прерывания."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "parsed_data.json").write_text("   \n", encoding="utf-8")

    with pytest.raises(ValidationError) as exc_info:
        load_parsed_data(tmp_path)

    assert "прерв" in str(exc_info.value).lower() or "interrupt" in str(exc_info.value).lower()


@pytest.mark.business_logic
def test_load_parsed_data_schema_violation_raises_validation_error_mentioning_parse(
    tmp_path: Path,
) -> None:
    """Синтаксически корректный JSON, не соответствующий схеме ParsedResult, приводит к ValidationError."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Отсутствует обязательное поле `generated_at`.
    (data_dir / "parsed_data.json").write_text(
        json.dumps({"platform_version": "2.0"}), encoding="utf-8"
    )

    with pytest.raises(ValidationError) as exc_info:
        load_parsed_data(tmp_path)

    assert "parse" in str(exc_info.value).lower()


@pytest.mark.business_logic
def test_load_parsed_data_valid_file_returns_matching_parsed_result(tmp_path: Path) -> None:
    """Валидный, соответствующий схеме JSON возвращает ParsedResult, совпадающий с записанными данными."""
    parsed_result = make_parsed_result(platform_version="3.1")
    write_parsed_data(tmp_path, parsed_result)

    loaded = load_parsed_data(tmp_path)

    assert loaded == parsed_result


@pytest.mark.business_logic
def test_load_parsed_data_bad_encoding_raises_validation_error_mentioning_utf8(
    tmp_path: Path,
) -> None:
    """parsed_data.json с содержимым не в кодировке UTF-8 приводит к ValidationError,
    а не к необработанному UnicodeDecodeError — файл считается повреждённым."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Байтовая последовательность, невалидная как UTF-8.
    (data_dir / "parsed_data.json").write_bytes(b"\xff\xfe\x00\x01broken")

    with pytest.raises(ValidationError) as exc_info:
        load_parsed_data(tmp_path)

    assert "utf-8" in str(exc_info.value).lower() or "кодировк" in str(exc_info.value).lower()


@pytest.mark.infrastructure
def test_load_parsed_data_oserror_on_read_raises_doc_generator_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OSError при чтении существующего parsed_data.json (например нет прав доступа)
    оборачивается в DocGeneratorError, а не пробрасывается как есть."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "parsed_data.json").write_text("{}", encoding="utf-8")

    import autodoc.cli.helpers as helpers_module

    def _raise_oserror(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(helpers_module.Path, "read_text", _raise_oserror)

    with pytest.raises(DocGeneratorError) as exc_info:
        load_parsed_data(tmp_path)

    assert "parsed_data.json" in str(exc_info.value)


@pytest.mark.business_logic
def test_make_publisher_missing_config_raises_config_error(tmp_path: Path) -> None:
    """Незагрузившийся конфиг Confluence (возвращающий None) приводит к ConfigError."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    cli_ctx = CliCtx(tmp_path, configs_dir, verbose=False)

    with pytest.raises(ConfigError):
        make_publisher(cli_ctx)


@pytest.mark.business_logic
def test_make_publisher_valid_config_returns_publisher_and_config(tmp_path: Path) -> None:
    """Валидный конфиг Confluence возвращает кортеж (DocumentPublisher, conf_config)."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    write_confluence_config(configs_dir)
    cli_ctx = CliCtx(tmp_path, configs_dir, verbose=False)

    publisher, conf_config = make_publisher(cli_ctx)

    assert publisher is not None
    assert conf_config == make_confluence_config()


@pytest.mark.business_logic
def test_make_publisher_forwards_config_file_argument(tmp_path: Path, mocker) -> None:
    """Параметр config_file передаётся в config_manager.load_confluence_config без изменений."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    cli_ctx = CliCtx(tmp_path, configs_dir, verbose=False)
    mock_load = mocker.patch.object(
        cli_ctx.config_manager,
        "load_confluence_config",
        return_value=make_confluence_config(),
    )

    make_publisher(cli_ctx, config_file="custom_confluence.yaml")

    mock_load.assert_called_once_with("custom_confluence.yaml")


@pytest.mark.business_logic
def test_print_publish_result_success_with_pages_does_not_exit(capsys: pytest.CaptureFixture) -> None:
    """При success=True и pages_published>0 SystemExit не возникает, в вывод попадает маркер успеха."""
    report = make_publish_report(success=True, pages_published=5)

    print_publish_result(report)

    output = capsys.readouterr().out
    assert "успешно" in output.lower()


@pytest.mark.business_logic
def test_print_publish_result_failure_exits_and_prints_every_error(
    capsys: pytest.CaptureFixture,
) -> None:
    """При success=False возникает SystemExit(1), а в вывод попадает каждая запись из result.errors."""
    report = make_publish_report(
        success=False, pages_published=0, errors=["first failure", "second failure"]
    )

    with pytest.raises(SystemExit) as exc_info:
        print_publish_result(report)

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert "first failure" in output
    assert "second failure" in output


@pytest.mark.business_logic
def test_print_publish_result_success_with_zero_pages_exits_without_error_branch(
    capsys: pytest.CaptureFixture,
) -> None:
    """При success=True и pages_published=0 SystemExit(1) возникает через отдельную ветку, а не через ветку с сообщением об ошибках."""
    report = make_publish_report(success=True, pages_published=0)

    with pytest.raises(SystemExit) as exc_info:
        print_publish_result(report)

    assert exc_info.value.code == 1
    output = capsys.readouterr().out
    assert "завершена с ошибками" not in output
