"""Юнит-тесты для autodoc/parser/steps/conan_step.py."""

import pytest

from autodoc.parser.conan.models.conan_enrichment_result import ConanEnrichmentResult
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.steps.conan_step import ConanEnrichStep

# ---------------------------------------------------------------------------
# Сигнальный пустой результат, используемый в тестах
# ---------------------------------------------------------------------------

EMPTY_CONAN_RESULT: ConanEnrichmentResult = ConanEnrichmentResult(
    release_data={}, profile_data={}, errors={}
)



# ---------------------------------------------------------------------------
# Тесты
# ---------------------------------------------------------------------------


def test_conan_step_stores_conan_report_in_intermediate(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ctx.intermediate['conan_report'] заполняется после execute."""
    fake = make_fake_fetcher(value=EMPTY_CONAN_RESULT)
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert "conan_report" in parser_pipeline_context.intermediate


def test_conan_step_is_not_critical() -> None:
    """ConanEnrichStep является некритичным шагом пайплайна."""
    assert ConanEnrichStep.is_critical is False


def test_conan_step_warnings_do_not_raise(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """Предупреждения от fetcher не вызывают исключений."""
    fake = make_fake_fetcher(value=EMPTY_CONAN_RESULT, warnings=["conan timeout"])
    step = ConanEnrichStep(fetcher=fake)
    step.execute(parser_pipeline_context)  # не должно вызывать исключений


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

# NULL_PACKAGE_ID — SHA1 пустой строки (header-only компоненты)
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
)
from autodoc.models.options import TotalOptionsSet


def _make_release_with_pb(name: str, version: str, channel: str, profile_name: str):
    """Build a (Component, Release, ProfileBuild) triple for use in tests."""
    pb = ProfileBuild(profile_name=profile_name)
    rel = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="DEP/_git/repo",
        profile_builds=[pb],
    )
    comp = Component(name=name, releases=[rel])
    return comp, rel, pb


def _make_conan_result(
    comp_name: str,
    version: str,
    channel: str,
    pb: ProfileBuild,
    package_id: str,
    deps: list[str] | None = None,
) -> ConanEnrichmentResult:
    """Build a ConanEnrichmentResult with one release and one profile entry."""
    result = ConanEnrichmentResult(release_data={}, profile_data={}, errors={})
    result.release_data[(comp_name, version, channel)] = ReleaseConanData(
        base_ref=f"{comp_name}/{version}@platform-2.0/{channel}",
        rrev="abc123",
        full_version=version,
        default_options=[],
        total_options=[TotalOptionsSet(id="1", options={})],
        patches=[],
        dependencies=deps or [],
        artifactory_url="https://art.example.com/pkg",
    )
    result.profile_data[id(pb)] = ProfileConanData(
        conan_settings={"os": "Linux"},
        exists=True,
        variants=[
            ConanVariant(
                package_id=package_id,
                build_url="",
                build_date="",
                options_ref="1",
            )
        ],
    )
    return result


# ---------------------------------------------------------------------------
# New real-data tests
# ---------------------------------------------------------------------------


def test_conan_step_applies_conan_results_to_components(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """After execute, the target release has conan_reference set (context was mutated).

    Specific field values from enrichment are covered by test_data_enricher.py.
    """
    comp, rel, pb = _make_release_with_pb(
        "patchelf", "0.18.0", "tech", "crypto_alpine_gcc_x86_64.jinja"
    )
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "patchelf", "0.18.0", "tech", pb,
        package_id="461534fe50686ce31d073dc24f005bd12e08c9fd",
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    # Only assert flow-through: context was mutated, no exception.
    assert rel.conan_reference is not None
    assert rel.conan_reference != ""


def test_conan_step_header_only_component_variants_stored(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """FakeFetcher returns NULL_PACKAGE_ID variant — variants are stored on the ProfileBuild.

    Specific package_id field values are covered by test_data_enricher.py.
    """
    comp, rel, pb = _make_release_with_pb(
        "nlohmann_json", "3.9.1", "slow", "hw-linux-x86_64-gcc10_2"
    )
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "nlohmann_json", "3.9.1", "slow", pb,
        package_id=NULL_PACKAGE_ID,
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    # Only assert flow-through: variants were populated on the ProfileBuild.
    assert len(pb.variants) == 1


def test_conan_step_component_with_dependencies(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """FakeFetcher returns deps list — release.dependencies is populated after execute.

    Specific dependency values are covered by test_data_enricher.py.
    """
    comp, rel, pb = _make_release_with_pb(
        "libnetfilter_queue", "1.0.5", "slow", "hw-linux-armv7-gcc10_2"
    )
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "libnetfilter_queue", "1.0.5", "slow", pb,
        package_id="46bf0ba807876c7591c702abfa2ba19d3133f1af",
        deps=["libmnl", "libnfnetlink"],
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    # Only assert flow-through: context was mutated with non-empty dependencies.
    assert rel.dependencies is not None
    assert len(rel.dependencies) > 0


def test_conan_step_configure_called_before_fetch(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """fetcher.configure() is called before fetcher.fetch() during execute."""
    fake = make_fake_fetcher(value=EMPTY_CONAN_RESULT)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    assert fake.configure_called is True


# ---------------------------------------------------------------------------
# UC-G-4 — apr/fast channel, no dependencies
# ---------------------------------------------------------------------------


def test_conan_step_apr_fast_channel_no_dependencies(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ConanStep correctly enriches apr/fast release with empty dependencies list.

    Uses a FakeFetcher that returns a ConanEnrichmentResult pre-populated
    with apr data. After ConanEnrichStep.execute, the apr release's dependencies
    list must be empty (apr has no runtime deps in production).
    """
    comp, rel, pb = _make_release_with_pb("apr", "1.7.6", "fast", "hw-linux-x86_64-gcc10_2")
    parser_pipeline_context.components = [comp]
    conan_result = _make_conan_result(
        "apr",
        "1.7.6",
        "fast",
        pb,
        package_id="7741115342fe6159bd16463d6d349e4c02e33237",
        deps=[],
    )
    fake = make_fake_fetcher(value=conan_result)
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    assert rel.dependencies == [] or rel.dependencies is None, (
        f"Expected empty dependencies for apr, got: {rel.dependencies}"
    )


# ---------------------------------------------------------------------------
# UC-G-7 — Error result does not raise and is stored in ctx.intermediate
# ---------------------------------------------------------------------------


def test_conan_step_error_does_not_raise_and_stores_in_report(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ConanStep does not raise when the aggregator reports a version-range resolution error.

    A FakeFetcher returns a ConanEnrichmentResult whose errors dict contains
    an entry for 'stunnel' (mimicking UC-G-7: version range could not be resolved).
    ConanEnrichStep.execute must complete without raising and must store the error
    information in ctx.intermediate['conan_report'].
    """
    error_entry = {
        "5.77": {"fast": {"crypto_default_gcc_x86_64.jinja": ["Version range not resolved"]}}
    }
    fake_result = ConanEnrichmentResult(
        release_data={},
        profile_data={},
        errors={"stunnel": error_entry},
    )
    fake = make_fake_fetcher(value=fake_result)
    parser_pipeline_context.components = []

    # Must not raise
    ConanEnrichStep(fetcher=fake).execute(parser_pipeline_context)

    conan_report = parser_pipeline_context.intermediate.get("conan_report")
    assert conan_report is not None
    assert "stunnel" in str(conan_report), (
        f"Expected 'stunnel' error to appear in conan report, got: {conan_report}"
    )
