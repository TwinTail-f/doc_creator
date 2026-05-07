"""
Юнит-тесты для autodoc/parser/conan/result_aggregator.py.

Охватывает ConanResultAggregator.aggregate() — успешный путь, пропуск
сбоев и структуру результата. Без subprocess и ввода/вывода.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.result_aggregator import ConanResultAggregator
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.models.conan_task import ConanTask
from autodoc.parser.conan.conan_enrich_data import ConanEnrichData

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _make_task(
    comp_name: str = "openssl",
    version: str = "3.0.0",
    channel: str = "tech",
    profile_name: str = "hw-linux-x86_64",
) -> ConanTask:
    """Возвращает минимальный ConanTask для тестов агрегации."""
    release = Release(version=version, platform="2.0", channel=channel, git_url="")
    pb = ProfileBuild(profile_name=profile_name)
    return ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name=comp_name,
        version=version,
        channel=channel,
        profile_name=profile_name,
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


def _make_enrich(
    comp_name: str = "openssl",
    version: str = "3.0.0",
    channel: str = "tech",
) -> ConanEnrichData:
    """Возвращает минимальный ConanEnrichData для мокирования парсера."""
    return ConanEnrichData(
        base_ref=f"{comp_name}/{version}@platform-2.0/{channel}",
        rrev="abc123",
        full_version=version,
        default_options=[],
        patches=[],
        dependencies=[],
        conan_settings={"os": "Linux", "arch": "x86_64"},
        package_id="deadbeef00000000000000000000000000000000",
        build_url="https://art.example.com/openssl",
        build_date="2024-01-01T00:00:00",
        conan_options={},
        option_id="1",
    )


# ---------------------------------------------------------------------------
# Успешный сырой результат → release_data заполнен
# ---------------------------------------------------------------------------


def test_aggregator_populates_release_data_on_success() -> None:
    """Успешный сырой результат создаёт запись в ConanEnrichmentResult.release_data."""
    task = _make_task()
    enrich = _make_enrich()

    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = enrich

    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="https://art.example.com", target_platform="2.0"
    )

    key = ("openssl", "3.0.0", "tech")
    assert key in result.release_data
    assert result.release_data[key].base_ref == "openssl/3.0.0@platform-2.0/tech"


# ---------------------------------------------------------------------------
# Неуспешный сырой результат пропускает вызов парсера
# ---------------------------------------------------------------------------


def test_aggregator_skips_parser_on_failed_raw_result() -> None:
    """Parser.parse() никогда не вызывается для сырых результатов с success=False."""
    task = _make_task()

    mock_parser = MagicMock(spec=ConanResultParser)
    raw = ConanRawResult(success=False, data=None, error="timeout")

    ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="", target_platform="2.0"
    )

    mock_parser.parse.assert_not_called()


# ---------------------------------------------------------------------------
# None в сыром результате пропускается корректно
# ---------------------------------------------------------------------------


def test_aggregator_skips_none_raw_result() -> None:
    """Запись None в raw_results не вызывает исключения и оставляет release_data пустым."""
    task = _make_task()

    mock_parser = MagicMock(spec=ConanResultParser)
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [None], art_base="", target_platform="2.0"
    )

    mock_parser.parse.assert_not_called()
    assert ("openssl", "3.0.0", "tech") not in result.release_data


# ---------------------------------------------------------------------------
# Парсер вернул None (Binary: Missing) → profile_data с exists=False
# ---------------------------------------------------------------------------


def test_aggregator_handles_parser_returning_none() -> None:
    """Когда парсер возвращает None (Binary: Missing), profile_data.exists == False."""
    task = _make_task()

    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = None

    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="", target_platform="2.0"
    )

    pb_data = result.profile_data.get(id(task.pb))
    assert pb_data is not None
    assert pb_data.exists is False


# ---------------------------------------------------------------------------
# Счётчики задач и сырых результатов отслеживаются
# ---------------------------------------------------------------------------


def test_aggregator_counts_totals_correctly() -> None:
    """Счётчики total_tasks и succeeded отражают количество задач и успехов."""
    task1 = _make_task(profile_name="hw-linux-x86_64")
    task2 = _make_task(profile_name="hw-linux-armv8")

    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = _make_enrich()

    raw_ok = ConanRawResult(success=True, data={})
    raw_fail = ConanRawResult(success=False, data=None, error="err")

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw_ok, raw_fail], art_base="", target_platform="2.0"
    )

    assert result.total_tasks == 2
    assert result.succeeded == 1
