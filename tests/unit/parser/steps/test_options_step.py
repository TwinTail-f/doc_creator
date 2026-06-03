"""Юнит-тесты для autodoc/parser/steps/options_step.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.models.types import OptionsMap
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.options_step import OptionsResolveStep

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _make_release(version: str, channel: str) -> Release:
    """Create a minimal Release with given version and channel."""
    return Release(
        version=version,
        platform="2.0",
        channel=channel,
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )


def _make_component(name: str, releases: list[Release]) -> Component:
    """Create a minimal Component with given name and releases."""
    return Component(name=name, git_project="DEP", git_repo=name, releases=releases)


def _make_ctx_with_components(
    parser_config, tmp_path: Path, components: list[Component]
) -> PipelineContext:
    """Build a PipelineContext pre-populated with the given components."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.components = components
    return ctx


# ---------------------------------------------------------------------------
# Kept tests (unchanged)
# ---------------------------------------------------------------------------


@pytest.mark.infrastructure
def test_options_step_stores_options_map_in_intermediate(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ctx.intermediate['options_map'] is populated with the fetcher result."""
    expected: OptionsMap = {("comp", "1.0", "tech"): {"1": ""}}
    fake = make_fake_fetcher(value=expected)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.intermediate["options_map"] == expected


@pytest.mark.business_logic
def test_options_step_applies_options_to_components(
    parser_pipeline_context,
    manifest_component,
    make_fake_fetcher,
) -> None:
    """DataEnricher.apply_options is called: matching release gets non-empty build_option_sets."""
    parser_pipeline_context.components = [manifest_component]
    # Key must match the fixture: name="openssl", version="1.0.0", channel="tech"
    options_map: OptionsMap = {("openssl", "1.0.0", "tech"): {"1": "shared=True"}}
    fake = make_fake_fetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components[0].releases[0].build_option_sets != []


@pytest.mark.business_logic
def test_options_step_is_not_critical() -> None:
    """OptionsResolveStep is a non-critical pipeline step."""
    assert OptionsResolveStep.is_critical is False


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_options_step_sqlite3_twelve_options_applied(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """FakeFetcher returning 12 options for sqlite3/slow applies all 12 to build_option_sets."""
    sqlite3_opts: OptionsMap = {
        ("sqlite3", "3.34.1", "slow"): {
            "1": "",
            "2": "sqlite3:shared=True",
            "3": "sqlite3:enable_json1=True",
            "4": "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True",
            "5": "sqlite3:enable_json1=True, sqlite3:shared=True",
            "6": "sqlite3:shared=True, sqlite3:RTree_patch_enable=True",
            "7": "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True, sqlite3:shared=True",
            "8": "sqlite3:shared=True, sqlite3:strip_binary=True",
            "9": "sqlite3:enable_json1=True, sqlite3:shared=True, sqlite3:strip_binary=True",
            "10": "sqlite3:shared=True, sqlite3:RTree_patch_enable=True, sqlite3:strip_binary=True",
            "11": "sqlite3:enable_json1=True, sqlite3:RTree_patch_enable=True, sqlite3:shared=True, sqlite3:strip_binary=True",
            "12": "sqlite3:with_icu=True",
        }
    }
    comp = _make_component("sqlite3", [_make_release("3.34.1", "slow")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=sqlite3_opts)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 12
    # Options for ids 2–12 must be non-empty
    non_empty = [bs for bs in build_sets if bs.id != "1"]
    assert all(bs.options != "" for bs in non_empty)


@pytest.mark.integration
def test_options_step_patchelf_both_versions_get_options(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """FakeFetcher with options for two patchelf releases populates both build_option_sets."""
    options_map: OptionsMap = {
        ("patchelf", "0.16.1", "tech"): {"1": ""},
        ("patchelf", "0.18.0", "tech"): {"1": ""},
    }
    comp = _make_component(
        "patchelf",
        [
            _make_release("0.16.1", "tech"),
            _make_release("0.18.0", "tech"),
        ],
    )
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    for release in ctx.components[0].releases:
        assert release.build_option_sets != []


@pytest.mark.integration
def test_options_step_nlohmann_single_empty_option(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """FakeFetcher returning {'1': ''} gives release one build_option_set with empty options."""
    options_map: OptionsMap = {("nlohmann_json", "3.9.1", "slow"): {"1": ""}}
    comp = _make_component("nlohmann_json", [_make_release("3.9.1", "slow")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 1
    assert build_sets[0].options == ""
    assert build_sets[0].parsed_options == {}


@pytest.mark.infrastructure
def test_options_step_warnings_logged(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """Step does not raise when fetcher reports warnings; options_map is still stored in ctx."""
    options_map: OptionsMap = {("somelib", "1.0.0", "fast"): {"1": ""}}
    comp = _make_component("somelib", [_make_release("1.0.0", "fast")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=options_map, warnings=["repo not found"])
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)  # Must not raise

    assert "options_map" in ctx.intermediate


@pytest.mark.contract
def test_options_step_configure_called_before_fetch(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """FakeFetcher.configure_called is True after OptionsResolveStep.execute."""
    fake = make_fake_fetcher(value={})
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert fake.configure_called is True


# ---------------------------------------------------------------------------
# UC-M-2 + UC-O-3: Single fast-channel component with a named option
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_options_step_apr_single_shared_option(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """apr/fast gets exactly 1 build_option_set with 'apr:shared=True' (UC-M-2 / UC-O-3)."""
    options_map: OptionsMap = {("apr", "1.7.6", "fast"): {"1": "apr:shared=True"}}
    comp = _make_component("apr", [_make_release("1.7.6", "fast")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    step = OptionsResolveStep(fetcher=make_fake_fetcher(value=options_map))
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 1
    assert build_sets[0].options == "apr:shared=True"
    assert build_sets[0].parsed_options == {"shared": "True"}


# ---------------------------------------------------------------------------
# UC-M-5 + UC-O-1: External-project component (PRG_Quant) with empty option
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_options_step_libnetfilter_queue_single_empty_option(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """libnetfilter_queue/slow (PRG_Quant) gets 1 empty build_option_set (UC-M-5 / UC-O-1)."""
    options_map: OptionsMap = {("libnetfilter_queue", "1.0.5", "slow"): {"1": ""}}
    comp = _make_component("libnetfilter_queue", [_make_release("1.0.5", "slow")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    step = OptionsResolveStep(fetcher=make_fake_fetcher(value=options_map))
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 1
    assert build_sets[0].options == ""


# ---------------------------------------------------------------------------
# UC-M-4: Two-channel component — fast and slow get different option counts
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_options_step_sqlite3_fast_and_slow_get_different_option_counts(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """sqlite3 with both fast (5 options) and slow (12 options) releases — each gets its own set.

    Covers UC-M-4: standard component built in two channels with different option sets.
    """
    options_map: OptionsMap = {
        ("sqlite3", "3.51.2", "fast"): {str(i): f"opt{i}" for i in range(1, 6)},
        ("sqlite3", "3.34.1", "slow"): {str(i): f"opt{i}" for i in range(1, 13)},
    }
    comp = _make_component(
        "sqlite3",
        [_make_release("3.51.2", "fast"), _make_release("3.34.1", "slow")],
    )
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    step = OptionsResolveStep(fetcher=make_fake_fetcher(value=options_map))
    step.execute(ctx)

    releases = ctx.components[0].releases
    fast_rel = next(r for r in releases if r.channel == "fast")
    slow_rel = next(r for r in releases if r.channel == "slow")
    assert len(fast_rel.build_option_sets) == 5
    assert len(slow_rel.build_option_sets) == 12
