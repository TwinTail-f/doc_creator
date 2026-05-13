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


# ---------------------------------------------------------------------------
# Real-data tests: patchelf, nlohmann_json, sqlite3, two-profile
# ---------------------------------------------------------------------------

# NULL_PACKAGE_ID — SHA1 пустой строки (header-only компоненты)
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def test_aggregator_patchelf_tech_channel() -> None:
    """Aggregating a patchelf task (tech channel, empty options) produces correct release_data key."""
    pb = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    release = Release(
        version="0.18.0", platform="2.0", channel="tech", git_url="", profile_builds=[pb]
    )
    task = ConanTask(
        cmd=[],
        comp_name="patchelf",
        version="0.18.0",
        channel="tech",
        profile_name="crypto_alpine_gcc_x86_64.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )
    enrich = ConanEnrichData(
        base_ref="patchelf/0.18.0.39@platform-2.0/tech",
        rrev="c6c4fa5a8d6efc0263361c1979cfad8b",
        full_version="0.18.0.39",
        default_options=[],
        patches=[],
        dependencies=[],
        conan_settings={"os": "Linux", "os.distro": "alpine", "arch": "x86_64"},
        package_id="461534fe50686ce31d073dc24f005bd12e08c9fd",
        build_url="https://art.example.com/patchelf/package/461534fe",
        build_date="2026-05-07T09:00:00+00:00",
        conan_options={},
        option_id="1",
    )
    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={'graph': {'nodes': {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="https://art.example.com", target_platform="2.0"
    )

    key = ("patchelf", "0.18.0", "tech")
    assert key in result.release_data
    assert result.release_data[key].base_ref == "patchelf/0.18.0.39@platform-2.0/tech"
    pb_data = result.profile_data.get(id(pb))
    assert pb_data is not None
    assert pb_data.exists is True
    assert len(pb_data.variants) == 1
    assert pb_data.variants[0].package_id == "461534fe50686ce31d073dc24f005bd12e08c9fd"


def test_aggregator_nlohmann_json_null_package_id_stored() -> None:
    """Aggregating nlohmann_json stores NULL_PACKAGE_ID variant and marks profile as existing."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    release = Release(
        version="3.9.1", platform="2.0", channel="slow", git_url="", profile_builds=[pb]
    )
    task = ConanTask(
        cmd=[],
        comp_name="nlohmann_json",
        version="3.9.1",
        channel="slow",
        profile_name="hw-linux-x86_64-gcc10_2",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )
    enrich = ConanEnrichData(
        base_ref="nlohmann_json/3.9.1.188@platform-2.0/slow",
        rrev="da3ea1b7d1b27546b0",
        full_version="3.9.1.188",
        default_options=[],
        patches=[],
        dependencies=[],
        conan_settings={"os": "Linux", "arch": "x86_64"},
        package_id=NULL_PACKAGE_ID,
        build_url="",
        build_date="",
        conan_options={},
        option_id="1",
    )
    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={'graph': {'nodes': {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="https://art.example.com", target_platform="2.0"
    )

    pb_data = result.profile_data.get(id(pb))
    assert pb_data is not None
    assert pb_data.exists is True
    assert pb_data.variants[0].package_id == NULL_PACKAGE_ID


def test_aggregator_sqlite3_dependencies_in_release_data() -> None:
    """sqlite3 release_data entry stores the dependency list returned by the parser."""
    pb = ProfileBuild(profile_name="crypto_default_gcc_armv7hf.jinja")
    release = Release(
        version="3.51.2", platform="2.0", channel="fast", git_url="", profile_builds=[pb]
    )
    task = ConanTask(
        cmd=[],
        comp_name="sqlite3",
        version="3.51.2",
        channel="fast",
        profile_name="crypto_default_gcc_armv7hf.jinja",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )
    enrich = ConanEnrichData(
        base_ref="sqlite3/3.51.2.1263@platform-2.0/fast",
        rrev="4ce73a6492de83d8",
        full_version="3.51.2.1263",
        default_options=[],
        patches=[],
        dependencies=["tcl"],
        conan_settings={"os": "Linux", "arch": "armv7hf"},
        package_id="8c7b3c7905519eea8fda5ff9dde7fbefec90da76",
        build_url="",
        build_date="",
        conan_options={},
        option_id="1",
    )
    mock_parser = MagicMock(spec=ConanResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={'graph': {'nodes': {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="https://art.example.com", target_platform="2.0"
    )

    key = ("sqlite3", "3.51.2", "fast")
    assert key in result.release_data
    assert result.release_data[key].dependencies == ["tcl"]


def test_aggregator_two_profiles_same_release() -> None:
    """Two tasks for the same release (different profiles) → one release_data entry, two profile_data entries."""
    pb1 = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    pb2 = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    release = Release(
        version="0.18.0", platform="2.0", channel="tech", git_url="",
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
    raw = ConanRawResult(success=True, data={'graph': {'nodes': {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw, raw],
        art_base="https://art.example.com", target_platform="2.0",
    )

    # Exactly one entry in release_data for this release
    key = ("patchelf", "0.18.0", "tech")
    assert key in result.release_data
    assert len([k for k in result.release_data if k[0] == "patchelf"]) == 1

    # Two separate profile_data entries
    assert id(pb1) in result.profile_data
    assert id(pb2) in result.profile_data
