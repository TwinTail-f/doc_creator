"""
Unit tests for autodoc/parser/conan/task_builder.py.

Covers ConanTaskBuilder.build() — task enumeration, field population,
and option-string normalization. No I/O; no subprocess calls.
"""

import pytest

from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.conan.task_builder import ConanTask, ConanTaskBuilder

# ---------------------------------------------------------------------------
# Local helpers / fixtures
# ---------------------------------------------------------------------------


def make_release(
    version: str = "1.0",
    channel: str = "tech",
    profiles: tuple[str, ...] = ("hw-linux-x86_64",),
    opts: dict[str, str] | None = None,
) -> Release:
    """Build a Release with the given profiles and internal option sets."""
    r = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="proj/_git/repo",
        profile_builds=[ProfileBuild(profile_name=p) for p in profiles],
    )
    if opts:
        r._build_option_sets_internal = opts
    return r


def make_component(
    name: str = "mylib", releases: list[Release] | None = None
) -> Component:
    """Build a Component with optional releases list."""
    return Component(name=name, releases=releases or [])


ART_URL: str = "https://art.example.com"
PLATFORM: str = "2.0"


# ---------------------------------------------------------------------------
# 1.1
# ---------------------------------------------------------------------------


def test_task_builder_produces_one_task_per_profile() -> None:
    """One component × one release × two profiles → two tasks."""
    release = make_release(profiles=("hw-linux-x86_64", "hw-linux-armv8"))
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


# ---------------------------------------------------------------------------
# 1.2
# ---------------------------------------------------------------------------


def test_task_builder_uses_default_empty_option_set() -> None:
    """Release with no options configured → one task with option_id '1'."""
    release = make_release()
    # _build_option_sets_internal is empty by default
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    assert tasks[0].option_id == "1"


# ---------------------------------------------------------------------------
# 1.3
# ---------------------------------------------------------------------------


def test_task_builder_multiplies_tasks_by_option_sets() -> None:
    """One profile × two option sets → two tasks."""
    opts = {"1": "shared=True", "2": "shared=False"}
    release = make_release(opts=opts)
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


# ---------------------------------------------------------------------------
# 1.4
# ---------------------------------------------------------------------------


def test_task_builder_cmd_contains_requires_flag() -> None:
    """The first --requires= element of cmd must contain the component name."""
    release = make_release()
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, "Expected at least one --requires= flag in cmd"
    assert "mylib" in requires_flags[0]


# ---------------------------------------------------------------------------
# 1.5
# ---------------------------------------------------------------------------


def test_task_builder_normalizes_bare_option() -> None:
    """Bare 'shared=True' must be prefixed with '*:' in the cmd."""
    release = make_release(opts={"1": "shared=True"})
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    # cmd contains [..., "-o", "*:shared=True", ...]
    assert "-o" in cmd
    o_index = cmd.index("-o")
    assert cmd[o_index + 1] == "*:shared=True"


# ---------------------------------------------------------------------------
# 1.6
# ---------------------------------------------------------------------------


def test_task_builder_normalizes_package_qualified_option() -> None:
    """'mylib:shared=True' must be expanded to 'mylib/*:shared=True'."""
    release = make_release(opts={"1": "mylib:shared=True"})
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    assert "mylib/*:shared=True" in cmd


# ---------------------------------------------------------------------------
# 1.7
# ---------------------------------------------------------------------------


def test_task_builder_already_wildcarded_option_unchanged() -> None:
    """'mylib/*:shared=True' must not be double-wildcarded."""
    release = make_release(opts={"1": "mylib/*:shared=True"})
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    assert "mylib/*:shared=True" in cmd
    # Ensure no double-wildcarded variant exists
    assert "mylib/*/*:shared=True" not in cmd


# ---------------------------------------------------------------------------
# 1.8
# ---------------------------------------------------------------------------


def test_task_builder_empty_components_returns_empty() -> None:
    """Empty component list must return empty task list."""
    tasks = ConanTaskBuilder().build([], PLATFORM, ART_URL)

    assert tasks == []


# ---------------------------------------------------------------------------
# 1.9
# ---------------------------------------------------------------------------


def test_task_builder_task_fields_populated() -> None:
    """All ConanTask scalar fields must match source model values."""
    release = make_release(
        version="3.2.1", channel="stable", profiles=("hw-linux-x86_64",)
    )
    comp = make_component(name="zlib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    task: ConanTask = tasks[0]
    assert task.comp_name == "zlib"
    assert task.version == "3.2.1"
    assert task.channel == "stable"
    assert task.profile_name == "hw-linux-x86_64"
    assert task.option_id == "1"
    assert task.target_platform == PLATFORM
