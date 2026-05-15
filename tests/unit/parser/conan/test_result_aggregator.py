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
from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.conan.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.result_aggregator import ConanResultAggregator
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.parser.conan.models.conan_task import ConanTask
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
    release = Release(version=version, platform="2.0", channel=channel)
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


def test_aggregator_skips_none_raw_result_and_emits_warning(caplog) -> None:
    """Aggregator skips None raw results and emits a WARNING log entry.

    A None result indicates a crashed or cancelled parallel task.
    Silent skipping without a warning would hide threading failures.
    """
    import logging

    task = _make_task()

    mock_parser = MagicMock(spec=ConanResultParser)
    with caplog.at_level(logging.WARNING):
        result = ConanResultAggregator(result_parser=mock_parser).aggregate(
            [task], [None], art_base="", target_platform="2.0"
        )

    mock_parser.parse.assert_not_called()
    assert ("openssl", "3.0.0", "tech") not in result.release_data

    warning_messages = [
        r.message for r in caplog.records if r.levelno == logging.WARNING
    ]
    assert any(
        "None" in m or "crashed" in m or "cancelled" in m for m in warning_messages
    ), "A WARNING must be logged when a None raw result is encountered"


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


def test_aggregator_dependencies_flow_through_to_release_data() -> None:
    """Dependencies returned by the parser are stored in release_data for the correct key.

    Uses pre-built mock data — no real fixture JSON is parsed here.
    Verifies the aggregator's own responsibility of routing parsed deps into
    release_data, which was the only aggregator behaviour covered exclusively
    by the deleted test_aggregator_sqlite3_dependencies_in_release_data.
    """
    task = _make_task(comp_name="mylib", version="2.0.0", channel="fast")
    enrich = ConanEnrichData(
        base_ref="mylib/2.0.0@platform-2.0/fast",
        rrev="abc123",
        full_version="2.0.0",
        default_options=[],
        patches=[],
        dependencies=["depA", "depB"],
        conan_settings={"os": "Linux", "arch": "x86_64"},
        package_id="deadbeef" * 5,
        build_url="",
        build_date="",
        conan_options={},
        option_id="1",
    )
    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="", target_platform="2.0"
    )

    key = ("mylib", "2.0.0", "fast")
    assert key in result.release_data
    assert result.release_data[key].dependencies == ["depA", "depB"]


# ---------------------------------------------------------------------------
# Real-data tests: patchelf, nlohmann_json, sqlite3, two-profile
# ---------------------------------------------------------------------------

# NULL_PACKAGE_ID — SHA1 пустой строки (header-only компоненты)
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def test_aggregator_two_profiles_same_release() -> None:
    """Two tasks for the same release (different profiles) → one release_data entry, two profile_data entries."""
    pb1 = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    pb2 = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    release = Release(
        version="0.18.0",
        platform="2.0",
        channel="tech",
        profile_builds=[pb1, pb2],
    )

    def _task(pb: ProfileBuild, profile_name: str) -> ConanTask:
        return ConanTask(
            cmd=[],
            comp_name="patchelf",
            version="0.18.0",
            channel="tech",
            profile_name=profile_name,
            option_id="1",
            option_str="",
            target_platform="2.0",
            artifactory_base_url="https://art.example.com",
            release=release,
            pb=pb,
        )

    task1 = _task(pb1, "crypto_alpine_gcc_x86_64.jinja")
    task2 = _task(pb2, "hw-linux-armv7-gcc10_2")

    enrich = ConanEnrichData(
        base_ref="patchelf/0.18.0.39@platform-2.0/tech",
        rrev="c6c4fa5a8d6efc0263361c1979cfad8b",
        full_version="0.18.0.39",
        default_options=[],
        patches=[],
        dependencies=[],
        conan_settings={"os": "Linux", "arch": "x86_64"},
        package_id="461534fe50686ce31d073dc24f005bd12e08c9fd",
        build_url="",
        build_date="",
        conan_options={},
        option_id="1",
    )
    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2],
        [raw, raw],
        art_base="https://art.example.com",
        target_platform="2.0",
    )

    # Exactly one entry in release_data for this release
    key = ("patchelf", "0.18.0", "tech")
    assert key in result.release_data
    assert len([k for k in result.release_data if k[0] == "patchelf"]) == 1

    # Two separate profile_data entries
    assert id(pb1) in result.profile_data
    assert id(pb2) in result.profile_data


# ---------------------------------------------------------------------------
# UC-G-7 — Version-range error message is preserved in aggregation result
# ---------------------------------------------------------------------------


def test_aggregator_records_version_range_error_message() -> None:
    """Aggregator records the full version-range-not-resolved error from a failed ConanRawResult.

    Simulates what happens when the runner returns success=False for a stunnel-like
    version range that could not be resolved. The error text must survive aggregation
    and appear in result.errors under the expected nested key path.
    """
    error_msg = (
        "ERROR: Package 'stunnel/[~5.77,include_prerelease]@platform-2.0/fast' not resolved: "
        "Version range '~5.77,include_prerelease' from requirement "
        "'stunnel/[~5.77,include_prerelease]@platform-2.0/fast' required by 'None' "
        "could not be resolved. Required by 'cli'"
    )
    release = Release(version="5.77", platform="2.0", channel="fast")
    pb = ProfileBuild(profile_name="crypto_default_gcc_x86_64.jinja")
    task = ConanTask(
        cmd=["conan", "graph", "info", "--requires=stunnel/[~5.77]@platform-2.0/fast"],
        comp_name="stunnel",
        version="5.77",
        channel="fast",
        profile_name="crypto_default_gcc_x86_64.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )
    raw = ConanRawResult(success=False, data=None, error=error_msg)

    aggregator = ConanResultAggregator(result_parser=ConanResultParser())
    result = aggregator.aggregate([task], [raw], art_base="", target_platform="2.0")

    assert (
        "stunnel" in result.errors
    ), f"Expected 'stunnel' in errors keys, got: {list(result.errors.keys())}"
    stunnel_errors = result.errors["stunnel"]
    version_errors = stunnel_errors.get("5.77", {})
    channel_errors = version_errors.get("fast", {})
    profile_errors = channel_errors.get("crypto_default_gcc_x86_64.jinja", [])
    assert any(
        "not resolved" in str(e) or "Version range" in str(e) for e in profile_errors
    ), f"Error message not found in profile_errors: {profile_errors}"
