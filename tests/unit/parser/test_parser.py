"""Юнит-тесты для autodoc/parser/parser.py (ComponentParser)."""

import pytest
from pytest_mock import MockerFixture

from autodoc.exceptions import ParsingError
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.parser import ComponentParser
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.docker_step import DockerResolveStep
from autodoc.parser.steps.finalize_step import FinalizeStep
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.steps.options_step import OptionsResolveStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep
from tests.unit.parser.conftest import CallbackStep, FailingStep, FakeTFSClient, FinalizeOnlyStep


@pytest.mark.business_logic
def test_component_parser_parse_returns_parsed_result(
    parser_config,
    tmp_path,
) -> None:
    """Успешный путь: parse() возвращает ParsedResult, когда FinalizeOnlyStep заполняет ctx.result."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[CallbackStep(is_critical=True), FinalizeOnlyStep()],
    )
    result = parser.parse()
    assert isinstance(result, ParsedResult)


@pytest.mark.business_logic
def test_component_parser_non_critical_step_failure_continues(
    parser_config,
    tmp_path,
) -> None:
    """Сбой некритичного шага поглощается, и пайплайн продолжает работу до завершения."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FailingStep(ParsingError("non-critical boom")), FinalizeOnlyStep()],
    )
    result = parser.parse()  # не должно вызывать исключений
    assert isinstance(result, ParsedResult)


@pytest.mark.infrastructure
def test_component_parser_cleans_up_tmp_dir_on_success(
    parser_config,
    tmp_path,
) -> None:
    """tmp_dir удаляется после успешного парсинга (блок finally)."""
    data_dir = tmp_path / "workspace"
    data_dir.mkdir()
    tmp_dir = data_dir / "tmp"
    tmp_dir.mkdir()
    parser = ComponentParser(
        config=parser_config,
        data_dir=data_dir,
        steps=[FinalizeOnlyStep()],
    )
    parser.parse()
    assert not tmp_dir.exists()


@pytest.mark.infrastructure
def test_component_parser_cleans_up_tmp_dir_on_failure(
    parser_config,
    tmp_path,
) -> None:
    """tmp_dir удаляется даже когда критичный шаг вызывает исключение (блок finally)."""
    data_dir = tmp_path / "workspace"
    data_dir.mkdir()
    tmp_dir = data_dir / "tmp"
    tmp_dir.mkdir()
    parser = ComponentParser(
        config=parser_config,
        data_dir=data_dir,
        steps=[FailingStep(ParsingError("boom"), is_critical=True)],
    )
    with pytest.raises(ParsingError):
        parser.parse()
    assert not tmp_dir.exists()


@pytest.mark.business_logic
def test_component_parser_raises_if_result_not_set(
    parser_config,
    tmp_path,
) -> None:
    """Если ни один шаг не заполняет ctx.result, parse() вызывает ParsingError после завершения всех шагов."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[CallbackStep(is_critical=True)],
    )
    with pytest.raises(ParsingError):
        parser.parse()


@pytest.mark.infrastructure
def test_component_parser_uses_injected_tfs_client(
    mocker: MockerFixture,
    parser_config,
    tmp_path,
) -> None:
    """Когда tfs_client передаётся через конструктор, TFSClient.__init__ никогда не вызывается."""
    mock_tfs_init = mocker.patch(
        "autodoc.parser.parser.TFSClient.__init__",
        return_value=None,
    )
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FinalizeOnlyStep()],
        tfs_client=FakeTFSClient(),
    )
    parser.parse()
    mock_tfs_init.assert_not_called()


@pytest.mark.infrastructure
def test_component_parser_save_intermediate_writes_files(
    parser_config,
    tmp_path,
) -> None:
    """parse(save_intermediate=True) записывает хотя бы один JSON-файл в директорию intermediate."""
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FinalizeOnlyStep()],
    )
    parser.parse(save_intermediate=True)
    intermediate_dir = tmp_path / "intermediate"
    json_files = list(intermediate_dir.glob("*.json"))
    assert len(json_files) == 1


@pytest.mark.infrastructure
def test_component_parser_save_intermediate_oserror_logged_not_raised(
    mocker: MockerFixture,
    parser_config,
    tmp_path,
) -> None:
    """OSError при записи снимка перехватывается и логируется, не прерывая parse()."""
    mock_write_text = mocker.patch(
        "pathlib.Path.write_text",
        side_effect=OSError("disk full"),
    )
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FinalizeOnlyStep()],
    )
    result = parser.parse(save_intermediate=True)  # не должно вызывать исключений
    assert isinstance(result, ParsedResult)
    mock_write_text.assert_called()


@pytest.mark.business_logic
def test_component_parser_default_pipeline_step_order(
    parser_config,
    tmp_path,
) -> None:
    """_default_pipeline() возвращает шаги в задокументированном порядке: Manifest→Options→Conan→Docker→Validation→Finalize."""
    parser = ComponentParser(config=parser_config, data_dir=tmp_path)
    expected_order = [
        ManifestStep,
        OptionsResolveStep,
        ConanEnrichStep,
        DockerResolveStep,
        ArtifactoryValidationStep,
        FinalizeStep,
    ]
    assert [type(s) for s in parser._steps] == expected_order


@pytest.mark.infrastructure
def test_component_parser_uses_injected_artifactory_client(
    mocker: MockerFixture,
    parser_config,
    tmp_path,
) -> None:
    """Когда artifactory_client передаётся через конструктор, ArtifactoryClient.__init__ никогда не вызывается."""
    mock_artifactory_init = mocker.patch(
        "autodoc.parser.parser.ArtifactoryClient.__init__",
        return_value=None,
    )
    parser = ComponentParser(
        config=parser_config,
        data_dir=tmp_path,
        steps=[FinalizeOnlyStep()],
        artifactory_client=mocker.MagicMock(),
    )
    parser.parse()
    mock_artifactory_init.assert_not_called()
