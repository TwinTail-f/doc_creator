"""Юнит-тесты для autodoc/parser/fetchers/conan_fetcher.py — содержимое результата.

Эти тесты проверяют, что release_data, profile_data, errors и счётчики задач
доходят до ConanEnrichmentResult без искажений через ConanFetcher.fetch() —
сценарии, невидимые в чисто оркестрационных тестах test_conan_fetcher.py,
которые мокируют результат целиком.
"""

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


def _build_fake_result_cases() -> list:
    """Строит параметризованные кейсы для test_conan_fetcher_result_content_passes_through.

    Каждый кейс — это отдельное поле ConanEnrichmentResult, которое агрегатор
    мог бы заполнить (release_data, profile_data, errors, счётчики задач), и
    функция-проверка, читающая соответствующее значение из FetchResult.value.
    """
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    release_key = ("patchelf", "0.18.0", "tech")
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
    profile_entry = ProfileConanData(
        conan_settings={"os": "Linux", "arch": "x86_64", "compiler": "gcc"},
        exists=True,
        variants=[],
    )
    nested_errors = {
        "stunnel": {
            "5.71": {
                "tech": {"hw-linux-x86_64-gcc10_2": ["version range error: openssl/[>=1.0.0]"]}
            }
        }
    }

    return [
        pytest.param(
            ConanEnrichmentResult(release_data={release_key: release_entry}),
            lambda value: (
                release_key in value.release_data
                and value.release_data[release_key].base_ref
                == "patchelf/0.18.0@platform-2.0/tech"
            ),
            id="release_data-key-and-base_ref",
        ),
        pytest.param(
            ConanEnrichmentResult(profile_data={id(pb): profile_entry}),
            lambda value: (
                id(pb) in value.profile_data
                and value.profile_data[id(pb)].conan_settings["os"] == "Linux"
                and value.profile_data[id(pb)].exists is True
            ),
            id="profile_data-keyed-by-object-identity",
        ),
        pytest.param(
            ConanEnrichmentResult(errors=nested_errors),
            lambda value: (
                value.errors == nested_errors
                and "version range"
                in value.errors["stunnel"]["5.71"]["tech"]["hw-linux-x86_64-gcc10_2"][0]
            ),
            id="nested-errors-structure-preserved",
        ),
        pytest.param(
            ConanEnrichmentResult(total_tasks=3, succeeded=2, failed=1),
            lambda value: (value.total_tasks, value.succeeded, value.failed) == (3, 2, 1),
            id="task-counters",
        ),
    ]


@pytest.mark.contract
@pytest.mark.parametrize("fake_result, check", _build_fake_result_cases())
def test_conan_fetcher_result_content_passes_through(
    mocker: MockerFixture,
    fake_result: ConanEnrichmentResult,
    check,
) -> None:
    """Содержимое, возвращённое ConanResultAggregator.aggregate(), доходит до FetchResult.value без искажений.

    Покрывает поля, невидимые в чисто оркестрационных тестах test_conan_fetcher.py,
    которые мокируют результат целиком: ключи release_data/profile_data,
    вложенную структуру errors и счётчики задач.
    """
    _, _, _, _, mock_agg_cls = _patch_full_fetch_pipeline(mocker)
    mock_agg_cls.return_value.aggregate.return_value = fake_result

    ctx = _make_mock_ctx(mocker)
    fetcher = ConanFetcher()
    fetcher.configure(ctx)
    result: FetchResult[ConanEnrichmentResult] = fetcher.fetch([mocker.MagicMock()])

    assert isinstance(result.value, ConanEnrichmentResult)
    assert check(result.value)
