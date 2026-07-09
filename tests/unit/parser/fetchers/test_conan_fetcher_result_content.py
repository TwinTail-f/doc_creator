"""Юнит-тесты для autodoc/parser/fetchers/conan_fetcher.py — содержимое результата.

Эти тесты проверяют, что release_data, profile_data, errors и счётчики задач
доходят до ConanEnrichmentResult без искажений через ConanFetcher.fetch() —
сценарии, невидимые в чисто оркестрационных тестах test_conan_fetcher.py,
которые мокируют результат целиком.
"""

from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from autodoc.parser.conan.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ReleaseConanData,
    ProfileConanData,
)
from autodoc.models.conan_variant import ProfileBuild
from autodoc.parser.fetchers.conan_fetcher import ConanFetcher
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from tests.unit.parser.fetchers.conftest import _make_mock_ctx, _patch_full_fetch_pipeline


@pytest.mark.contract
def test_fetch_result_release_data_has_correct_key_and_base_ref(
    mocker: MockerFixture,
) -> None:
    """Ключ (name, version, channel) и base_ref в release_data сохраняются без изменений."""
    expected_key = ("patchelf", "0.18.0", "tech")
    release_entry = ReleaseConanData(
        base_ref="patchelf/0.18.0@platform-2.0/tech",
        rrev="deadbeef",
        full_version="0.18.0",
        default_options=[],
        total_options=[],
        patches=[],
        dependencies=[],
        artifactory_url="https://art.example.com/patchelf",
    )
    fake_result = ConanEnrichmentResult(
        release_data={expected_key: release_entry},
        profile_data={},
        errors={},
    )

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert isinstance(result.value, ConanEnrichmentResult)
    assert expected_key in result.value.release_data
    assert result.value.release_data[expected_key].base_ref == "patchelf/0.18.0@platform-2.0/tech"


@pytest.mark.contract
def test_fetch_result_profile_data_keyed_by_object_identity(
    mocker: MockerFixture,
) -> None:
    """Ключом profile_data является id(pb); соответствующая запись ProfileConanData сохраняется."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    profile_entry = ProfileConanData(
        conan_settings={"os": "Linux", "arch": "x86_64", "compiler": "gcc"},
        exists=True,
        variants=[],
    )
    fake_result = ConanEnrichmentResult(
        release_data={},
        profile_data={id(pb): profile_entry},
        errors={},
    )

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert id(pb) in result.value.profile_data
    assert result.value.profile_data[id(pb)].conan_settings["os"] == "Linux"
    assert result.value.profile_data[id(pb)].exists is True


@pytest.mark.contract
def test_fetch_result_nested_errors_structure_preserved(
    mocker: MockerFixture,
) -> None:
    """Вложенная структура errors {component: {version: {channel: {profile: [msgs]}}}} не теряется."""
    expected_errors = {
        "stunnel": {
            "5.71": {
                "tech": {"hw-linux-x86_64-gcc10_2": ["version range error: openssl/[>=1.0.0]"]}
            }
        }
    }
    fake_result = ConanEnrichmentResult(errors=expected_errors)

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert result.value.errors == expected_errors
    error_msg = result.value.errors["stunnel"]["5.71"]["tech"]["hw-linux-x86_64-gcc10_2"][0]
    assert "version range" in error_msg


@pytest.mark.contract
def test_fetch_task_counters_reflected_in_result(
    mocker: MockerFixture,
) -> None:
    """Счётчики задач агрегатора (total/succeeded/failed) присутствуют в FetchResult.value."""
    fake_result = ConanEnrichmentResult(
        total_tasks=3,
        succeeded=2,
        failed=1,
    )

    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert result.value.total_tasks == 3
    assert result.value.succeeded == 2
    assert result.value.failed == 1
