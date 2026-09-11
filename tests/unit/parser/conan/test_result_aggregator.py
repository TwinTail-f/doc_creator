"""
Юнит-тесты для autodoc/parser/conan/result_aggregator.py.

Охватывает ConanResultAggregator.aggregate() — успешный путь, пропуск
сбоев и структуру результата. Без subprocess и ввода/вывода.
"""

import logging
from unittest.mock import MagicMock

import pytest

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.conan2_result_parser import Conan2ResultParser
from autodoc.parser.conan.conan_enrich_data import ConanEnrichData
from autodoc.parser.conan.models.conan_raw_result import ConanRawResult
from autodoc.parser.conan.models.conan_task import ConanTask
from autodoc.parser.conan.result_aggregator import ConanResultAggregator


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


@pytest.mark.business_logic
def test_aggregator_populates_release_data_on_success() -> None:
    """Успешный сырой результат создаёт запись в ConanEnrichmentResult.release_data."""
    task = _make_task()
    enrich = _make_enrich()

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.return_value = enrich

    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="https://art.example.com", target_platform="2.0"
    )

    key = ("openssl", "3.0.0", "tech")
    assert key in result.release_data
    assert result.release_data[key].base_ref == "openssl/3.0.0@platform-2.0/tech"


@pytest.mark.business_logic
def test_aggregator_skips_parser_on_failed_raw_result() -> None:
    """Parser.parse() никогда не вызывается для сырых результатов с success=False."""
    task = _make_task()

    mock_parser = MagicMock(spec=Conan2ResultParser)
    raw = ConanRawResult(success=False, data=None, error="timeout")

    ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="", target_platform="2.0"
    )

    mock_parser.parse.assert_not_called()


@pytest.mark.business_logic
def test_aggregator_skips_none_raw_result_and_emits_warning(caplog) -> None:
    """Агрегатор пропускает None-результаты параллельных задач и пишет WARNING в лог."""
    task = _make_task()

    mock_parser = MagicMock(spec=Conan2ResultParser)
    with caplog.at_level(logging.WARNING):
        result = ConanResultAggregator(result_parser=mock_parser).aggregate(
            [task], [None], art_base="", target_platform="2.0"
        )

    mock_parser.parse.assert_not_called()
    assert ("openssl", "3.0.0", "tech") not in result.release_data

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "пуст" in m or "ошиб" in m or "отменен" in m or "отменён" in m for m in warning_messages
    ), "A WARNING must be logged when a None raw result is encountered"


@pytest.mark.business_logic
def test_aggregator_handles_parser_returning_none() -> None:
    """Когда парсер возвращает None (Binary: Missing), profile_data.exists == False."""
    task = _make_task()

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.return_value = None

    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="", target_platform="2.0"
    )

    pb_data = result.profile_data.get(id(task.pb))
    assert pb_data is not None
    assert pb_data.exists is False


@pytest.mark.business_logic
def test_aggregator_counts_totals_correctly() -> None:
    """Счётчики total_tasks и succeeded отражают количество задач и успехов."""
    task1 = _make_task(profile_name="hw-linux-x86_64")
    task2 = _make_task(profile_name="hw-linux-armv8")

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.return_value = _make_enrich()

    raw_ok = ConanRawResult(success=True, data={})
    raw_fail = ConanRawResult(success=False, data=None, error="err")

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw_ok, raw_fail], art_base="", target_platform="2.0"
    )

    assert result.total_tasks == 2
    assert result.succeeded == 1


@pytest.mark.business_logic
def test_aggregator_dependencies_flow_through_to_release_data() -> None:
    """Зависимости, возвращённые парсером, сохраняются в release_data под правильным ключом."""
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
    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task], [raw], art_base="", target_platform="2.0"
    )

    key = ("mylib", "2.0.0", "fast")
    assert key in result.release_data
    assert result.release_data[key].dependencies == ["depA", "depB"]


def _make_profile_task(release: Release, pb: ProfileBuild, profile_name: str) -> ConanTask:
    """
    Возвращает ConanTask (patchelf/0.18.0/tech, cmd=[]) для сценариев с несколькими
    профилями одного релиза, разделяющих один Release, но с разными ProfileBuild.
    """
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


@pytest.mark.business_logic
def test_aggregator_two_profiles_same_release() -> None:
    """Две задачи для одного релиза (разные профили) → одна запись release_data, две записи profile_data."""
    pb1 = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    pb2 = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    release = Release(
        version="0.18.0",
        platform="2.0",
        channel="tech",
        profile_builds=[pb1, pb2],
    )

    task1 = _make_profile_task(release, pb1, "crypto_alpine_gcc_x86_64.jinja")
    task2 = _make_profile_task(release, pb2, "hw-linux-armv7-gcc10_2")

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
    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.return_value = enrich
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})
    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2],
        [raw, raw],
        art_base="https://art.example.com",
        target_platform="2.0",
    )

    # Ровно одна запись release_data для этого релиза
    key = ("patchelf", "0.18.0", "tech")
    assert key in result.release_data
    assert len([k for k in result.release_data if k[0] == "patchelf"]) == 1

    # Две отдельные записи profile_data — по одной на профиль
    assert id(pb1) in result.profile_data
    assert id(pb2) in result.profile_data


@pytest.mark.business_logic
def test_aggregator_merges_dependencies_across_profiles_of_same_release() -> None:
    """Зависимости с разных профилей одного релиза объединяются в одну запись release_data."""
    pb1 = ProfileBuild(profile_name="crypto_alpine_gcc_x86_64.jinja")
    pb2 = ProfileBuild(profile_name="hw-linux-armv7-gcc10_2")
    release = Release(
        version="0.18.0",
        platform="2.0",
        channel="tech",
        profile_builds=[pb1, pb2],
    )

    task1 = _make_profile_task(release, pb1, "crypto_alpine_gcc_x86_64.jinja")
    task2 = _make_profile_task(release, pb2, "hw-linux-armv7-gcc10_2")

    def _enrich(deps: list[str]) -> ConanEnrichData:
        return ConanEnrichData(
            base_ref="patchelf/0.18.0.39@platform-2.0/tech",
            rrev="c6c4fa5a8d6efc0263361c1979cfad8b",
            full_version="0.18.0.39",
            default_options=[],
            patches=[],
            dependencies=deps,
            conan_settings={"os": "Linux", "arch": "x86_64"},
            package_id="461534fe50686ce31d073dc24f005bd12e08c9fd",
            build_url="",
            build_date="",
            conan_options={},
            option_id="1",
        )

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.side_effect = [_enrich(["depA"]), _enrich(["depB"])]
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2],
        [raw, raw],
        art_base="https://art.example.com",
        target_platform="2.0",
    )

    key = ("patchelf", "0.18.0", "tech")
    assert key in result.release_data
    assert result.release_data[key].dependencies == ["depA", "depB"]


@pytest.mark.business_logic
def test_aggregator_records_version_range_error_message() -> None:
    """Агрегатор сохраняет полный текст ошибки неразрешённого version range в result.errors."""
    # Синтетический, но реалистичный по форме текст ошибки — сознательно не
    # копия вывода конкретной версии conan. conan меняет точную формулировку
    # между версиями, а тест обязан оставаться валидным при любой из них:
    # он проверяет, что аггрегатор сохраняет ошибку с этими двумя маркерами
    # (см. assert ниже), а не то, что conan выводит именно эти слова.
    error_msg = "ERROR: stunnel/[~5.77]: Version range could not be resolved: not resolved"
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

    aggregator = ConanResultAggregator(result_parser=Conan2ResultParser())
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


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "raw, expected_status",
    [
        # raw is None -> задача не вернула результат (worker упал/отменён)
        pytest.param(None, "FAILED", id="raw-none-failed"),
        # успешный разбор без binary=Missing -> SUCCESS
        pytest.param(
            ConanRawResult(success=True, data={"graph": {"nodes": {}}}),
            "SUCCESS",
            id="success",
        ),
        # binary=Missing в узле графа -> BINARY_MISSING, несмотря на success=True
        pytest.param(
            ConanRawResult(
                success=True,
                data={
                    "graph": {
                        "nodes": {
                            "0": {"name": "openssl", "binary": "Missing"},
                        }
                    }
                },
            ),
            "BINARY_MISSING",
            id="binary-missing",
        ),
        # success=True, но данные графа отсутствуют (пустой ответ conan) ->
        # _extract_binary_status возвращает "" -> SUCCESS
        pytest.param(
            ConanRawResult(success=True, data=None),
            "SUCCESS",
            id="success-empty-data",
        ),
    ],
)
def test_build_execution_report_maps_raw_result_to_status(
    raw: ConanRawResult | None, expected_status: str
) -> None:
    """
    build_execution_report сопоставляет сырой результат одному из четырёх статусов:
    отсутствующий результат -> FAILED, успешный разбор без Missing -> SUCCESS,
    узел с binary=Missing в графе -> BINARY_MISSING, успешный разбор с отсутствующими
    данными графа (data=None) -> SUCCESS (_extract_binary_status возвращает "").
    """
    task = _make_task()
    report = ConanResultAggregator().build_execution_report([task], [raw])

    assert len(report) == 1
    profile_report = report[0].profiles[task.profile_name]
    assert len(profile_report.commands) == 1
    assert profile_report.commands[0].status == expected_status


@pytest.mark.business_logic
def test_build_execution_report_failed_raw_result_has_error_message() -> None:
    """build_execution_report сохраняет текст ошибки исполнения (success=False) в записи FAILED."""
    task = _make_task()
    raw = ConanRawResult(success=False, data=None, error="conan: command not found")

    report = ConanResultAggregator().build_execution_report([task], [raw])

    record = report[0].profiles[task.profile_name].commands[0]
    assert record.status == "FAILED"
    assert record.error == "conan: command not found"


@pytest.mark.business_logic
def test_build_final_result_deduplicates_by_profile_build_identity() -> None:
    """
    Две задачи с одним и тем же объектом ProfileBuild (task.pb) учитываются в
    result.profile_data только один раз — запись профиля не задваивается для
    повторяющегося ProfileBuild, даже если у задач разные option_id.
    """
    pb = ProfileBuild(profile_name="hw-linux-x86_64")
    release = Release(version="3.0.0", platform="2.0", channel="tech", profile_builds=[pb])
    task1 = ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name="openssl",
        version="3.0.0",
        channel="tech",
        profile_name="hw-linux-x86_64",
        option_id="1",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="",
        release=release,
        pb=pb,
    )
    task2 = ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name="openssl",
        version="3.0.0",
        channel="tech",
        profile_name="hw-linux-x86_64",
        option_id="2",
        option_str="",
        target_platform="2.0",
        artifactory_base_url="",
        release=release,
        pb=pb,
    )

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.return_value = _make_enrich()
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw, raw], art_base="", target_platform="2.0"
    )

    # Один и тот же ProfileBuild -> одна запись profile_data, а не две.
    assert len(result.profile_data) == 1
    assert id(pb) in result.profile_data


def _make_repeated_task(release: Release, pb: ProfileBuild, option_id: str = "1") -> ConanTask:
    """
    Возвращает ConanTask, разделяющий один и тот же Release/ProfileBuild с другими
    задачами того же релиза (для сценариев с несколькими результатами на один ProfileBuild).
    """
    return ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name="openssl",
        version="3.0.0",
        channel="tech",
        profile_name=pb.profile_name,
        option_id=option_id,
        option_str="",
        target_platform="2.0",
        artifactory_base_url="",
        release=release,
        pb=pb,
    )


@pytest.mark.business_logic
def test_aggregator_keeps_first_release_data_rrev_for_repeated_profile_build() -> None:
    """
    release_data сохраняет base_ref/rrev первого успешного результата ProfileBuild
    и не перезаписывает их последующими результатами того же релиза.
    """
    release = Release(version="3.0.0", platform="2.0", channel="tech")
    pb = ProfileBuild(profile_name="hw-linux-x86_64")
    task1 = _make_repeated_task(release, pb, option_id="1")
    task2 = _make_repeated_task(release, pb, option_id="2")

    first = _make_enrich(comp_name="openssl", version="3.0.0")
    first.rrev = "first-rrev"
    second = _make_enrich(comp_name="openssl", version="3.0.0")
    second.rrev = "different-rrev"

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.side_effect = [first, second]
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw, raw], art_base="", target_platform="2.0"
    )

    key = ("openssl", "3.0.0", "tech")
    assert result.release_data[key].rrev == "first-rrev"


@pytest.mark.business_logic
def test_aggregator_total_options_keeps_first_resolved_options_for_repeated_option_id() -> None:
    """
    total_options в release_data хранит resolved-опции только первого результата
    для повторяющегося option_id — второй результат с тем же option_id их не переопределяет.
    """
    release = Release(version="3.0.0", platform="2.0", channel="tech")
    pb = ProfileBuild(profile_name="hw-linux-x86_64")
    task1 = _make_repeated_task(release, pb, option_id="1")
    task2 = _make_repeated_task(release, pb, option_id="2")

    first = _make_enrich()
    first.option_id = "opt-1"
    first.conan_options = {"shared": "True"}
    second = _make_enrich()
    second.option_id = "opt-1"
    second.conan_options = {"shared": "False"}

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.side_effect = [first, second]
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw, raw], art_base="", target_platform="2.0"
    )

    key = ("openssl", "3.0.0", "tech")
    total_options = result.release_data[key].total_options
    assert len(total_options) == 1
    assert total_options[0].id == "opt-1"
    assert total_options[0].options == {"shared": "True"}


@pytest.mark.business_logic
def test_aggregator_profile_data_does_not_duplicate_variant_for_repeated_package_id() -> None:
    """
    profile_data.variants не задваивает вариант сборки, когда два результата
    одного ProfileBuild возвращают один и тот же package_id.
    """
    release = Release(version="3.0.0", platform="2.0", channel="tech")
    pb = ProfileBuild(profile_name="hw-linux-x86_64")
    task1 = _make_repeated_task(release, pb, option_id="1")
    task2 = _make_repeated_task(release, pb, option_id="2")

    first = _make_enrich()
    first.package_id = "deadbeef" * 5
    second = _make_enrich()
    second.package_id = "deadbeef" * 5

    mock_parser = MagicMock(spec=Conan2ResultParser)
    mock_parser.parse.side_effect = [first, second]
    raw = ConanRawResult(success=True, data={"graph": {"nodes": {}}})

    result = ConanResultAggregator(result_parser=mock_parser).aggregate(
        [task1, task2], [raw, raw], art_base="", target_platform="2.0"
    )

    assert len(result.profile_data[id(pb)].variants) == 1
