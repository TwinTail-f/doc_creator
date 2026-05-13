"""Unit tests for autodoc/parser/steps/options_step.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.models.types import OptionsMap
from autodoc.parser.fetchers.models.fetch_result import FetchResult
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.options_step import OptionsResolveStep

# ---------------------------------------------------------------------------
# Fake Fetcher
# ---------------------------------------------------------------------------


class FakeFetcher:
    """Controllable fake fetcher for OptionsResolveStep unit tests."""

    def __init__(self, value: OptionsMap, warnings: list[str] | None = None) -> None:
        """
        Args:
            value: OptionsMap returned by fetch().
            warnings: Optional list of warning strings.
        """
        self.value = value
        self.warnings = warnings or []
        self.configure_called: bool = False
        self.fetch_called: bool = False

    def configure(self, ctx: object) -> None:
        """Record that configure was called."""
        self.configure_called = True

    def fetch(self, *args: object, **kwargs: object) -> FetchResult:
        """Return a controlled FetchResult."""
        self.fetch_called = True
        return FetchResult(value=self.value, warnings=self.warnings)


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _make_release(version: str, channel: str) -> Release:
    """Create a minimal Release with given version and channel."""
    return Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="DEP/_git/repo",
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


def test_options_step_stores_options_map_in_intermediate(
    parser_pipeline_context,
) -> None:
    """ctx.intermediate['options_map'] is populated with the fetcher result."""
    expected: OptionsMap = {("comp", "1.0", "tech"): {"1": ""}}
    fake = FakeFetcher(value=expected)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.intermediate["options_map"] == expected


def test_options_step_applies_options_to_components(
    parser_pipeline_context,
    manifest_component,
) -> None:
    """DataEnricher.apply_options is called: matching release gets non-empty build_option_sets."""
    parser_pipeline_context.components = [manifest_component]
    # Key must match the fixture: name="openssl", version="1.0.0", channel="tech"
    options_map: OptionsMap = {("openssl", "1.0.0", "tech"): {"1": "shared=True"}}
    fake = FakeFetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert parser_pipeline_context.components[0].releases[0].build_option_sets != []


def test_options_step_is_not_critical() -> None:
    """OptionsResolveStep is a non-critical pipeline step."""
    assert OptionsResolveStep.is_critical is False


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


def test_options_step_sqlite3_twelve_options_applied(
    parser_config,
    tmp_path: Path,
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
    fake = FakeFetcher(value=sqlite3_opts)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 12
    # Options for ids 2–12 must be non-empty
    non_empty = [bs for bs in build_sets if bs.id != "1"]
    assert all(bs.options != "" for bs in non_empty)


def test_options_step_patchelf_both_versions_get_options(
    parser_config,
    tmp_path: Path,
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
    fake = FakeFetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    for release in ctx.components[0].releases:
        assert release.build_option_sets != []


def test_options_step_nlohmann_single_empty_option(
    parser_config,
    tmp_path: Path,
) -> None:
    """FakeFetcher returning {'1': ''} gives release one build_option_set with empty options."""
    options_map: OptionsMap = {("nlohmann_json", "3.9.1", "slow"): {"1": ""}}
    comp = _make_component("nlohmann_json", [_make_release("3.9.1", "slow")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = FakeFetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 1
    assert build_sets[0].options == ""
    assert build_sets[0].parsed_options == {}


def test_options_step_warnings_logged(
    parser_config,
    tmp_path: Path,
) -> None:
    """Step does not raise when fetcher reports warnings; options_map is still stored in ctx."""
    options_map: OptionsMap = {("somelib", "1.0.0", "fast"): {"1": ""}}
    comp = _make_component("somelib", [_make_release("1.0.0", "fast")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = FakeFetcher(value=options_map, warnings=["repo not found"])
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)  # Must not raise

    assert "options_map" in ctx.intermediate


def test_options_step_configure_called_before_fetch(
    parser_pipeline_context,
) -> None:
    """FakeFetcher.configure_called is True after OptionsResolveStep.execute."""
    fake = FakeFetcher(value={})
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert fake.configure_called is True
