"""
Юнит-тесты для autodoc/parser/conan/task_builder.py.

Охватывает ConanTaskBuilder.build() — перебор задач, заполнение полей
и нормализацию строк опций. Без ввода/вывода и вызовов subprocess.
"""

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.parser.conan.models.conan_task import ConanTask
from autodoc.parser.conan.conan_task_builder import ConanTaskBuilder

# ---------------------------------------------------------------------------
# Локальные вспомогательные функции / фикстуры
# ---------------------------------------------------------------------------


def make_release(
    version: str = "1.0",
    channel: str = "tech",
    profiles: tuple[str, ...] = ("hw-linux-x86_64",),
    opts: dict[str, str] | None = None,
) -> Release:
    """Создаёт Release с заданными профилями и внутренними наборами опций."""
    r = Release(
        version=version,
        platform="2.0",
        channel=channel,
        profile_builds=[ProfileBuild(profile_name=p) for p in profiles],
    )
    if opts:
        r._build_option_sets_internal = opts
    return r


def make_component(
    name: str = "mylib", releases: list[Release] | None = None
) -> Component:
    """Создаёт Component с необязательным списком релизов."""
    return Component(name=name, releases=releases or [])


ART_URL: str = "https://art.example.com"
PLATFORM: str = "2.0"


# ---------------------------------------------------------------------------
# Один компонент × один релиз × два профиля → две задачи
# ---------------------------------------------------------------------------


def test_task_builder_produces_one_task_per_profile() -> None:
    """Один компонент × один релиз × два профиля → две задачи."""
    release = make_release(profiles=("hw-linux-x86_64", "hw-linux-armv8"))
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


# ---------------------------------------------------------------------------
# Релиз без настроенных опций → одна задача с option_id '1'
# ---------------------------------------------------------------------------


def test_task_builder_uses_default_empty_option_set() -> None:
    """Релиз без настроенных опций → одна задача с option_id '1'."""
    release = make_release()
    # _build_option_sets_internal пуст по умолчанию
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    assert tasks[0].option_id == "1"


# ---------------------------------------------------------------------------
# Один профиль × два набора опций → две задачи
# ---------------------------------------------------------------------------


def test_task_builder_multiplies_tasks_by_option_sets() -> None:
    """Один профиль × два набора опций → две задачи."""
    opts = {"1": "shared=True", "2": "shared=False"}
    release = make_release(opts=opts)
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


# ---------------------------------------------------------------------------
# Первый элемент --requires= в cmd содержит имя компонента
# ---------------------------------------------------------------------------


def test_task_builder_cmd_contains_requires_flag() -> None:
    """Первый элемент --requires= в cmd должен содержать имя компонента."""
    release = make_release()
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, "Expected at least one --requires= flag in cmd"
    assert "mylib" in requires_flags[0]


# ---------------------------------------------------------------------------
# Голое 'shared=True' дополняется префиксом '*:'
# ---------------------------------------------------------------------------


def test_task_builder_normalizes_bare_option() -> None:
    """Голое 'shared=True' должно быть дополнено префиксом '*:' в cmd."""
    release = make_release(opts={"1": "shared=True"})
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    # cmd содержит [..., "-o", "*:shared=True", ...]
    assert "-o" in cmd
    o_index = cmd.index("-o")
    assert cmd[o_index + 1] == "*:shared=True"


# ---------------------------------------------------------------------------
# 'mylib:shared=True' расширяется до 'mylib/*:shared=True'
# ---------------------------------------------------------------------------


def test_task_builder_normalizes_package_qualified_option() -> None:
    """'mylib:shared=True' должно быть расширено до 'mylib/*:shared=True'."""
    release = make_release(opts={"1": "mylib:shared=True"})
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    assert "mylib/*:shared=True" in cmd


# ---------------------------------------------------------------------------
# 'mylib/*:shared=True' не должно быть дважды заменено символом подстановки
# ---------------------------------------------------------------------------


def test_task_builder_already_wildcarded_option_unchanged() -> None:
    """'mylib/*:shared=True' не должно быть дважды заменено символом подстановки."""
    release = make_release(opts={"1": "mylib/*:shared=True"})
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    assert "mylib/*:shared=True" in cmd
    # Убеждаемся, что дважды замаскированный вариант отсутствует
    assert "mylib/*/*:shared=True" not in cmd


# ---------------------------------------------------------------------------
# Пустой список компонентов → пустой список задач
# ---------------------------------------------------------------------------


def test_task_builder_empty_components_returns_empty() -> None:
    """Пустой список компонентов должен возвращать пустой список задач."""
    tasks = ConanTaskBuilder().build([], PLATFORM, ART_URL)

    assert tasks == []


# ---------------------------------------------------------------------------
# Все скалярные поля ConanTask совпадают со значениями исходной модели
# ---------------------------------------------------------------------------


def test_task_builder_task_fields_populated() -> None:
    """Все скалярные поля ConanTask должны совпадать со значениями исходной модели."""
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


# ---------------------------------------------------------------------------
# BL-TB-04 — package key without wildcard is normalized to pkg/*:opt
# ---------------------------------------------------------------------------


def test_option_normalization_package_key_gets_wildcard() -> None:
    """BL-TB-04: Option with bare package name is normalized to wildcard form.

    Business Rule:
        An option like ``"mylib:shared=True"`` (without wildcard) must be
        normalized to ``"mylib/*:shared=True"`` because Conan 2 requires the
        ``pkg/*:key=val`` notation when targeting all variants of a package.

    Preconditions:
        - One component ``mylib`` with one release.
        - Option set: ``{"1": "mylib:shared=True"}`` (no wildcard).

    Steps:
        1. Build tasks with ``ConanTaskBuilder().build([comp], ...)``
        2. Inspect the ``cmd`` of the single resulting task.

    Expected Result:
        - ``cmd`` contains the flag ``"-o"`` followed by ``"mylib/*:shared=True"``.
        - The bare form ``"mylib:shared=True"`` does NOT appear as a separate
          argument.
    """
    release = make_release(opts={"1": "mylib:shared=True"})
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    cmd = tasks[0].cmd

    # Normalized wildcard form must be present
    assert any("mylib/*:shared=True" in arg for arg in cmd), (
        f"Expected 'mylib/*:shared=True' in command, got: {cmd}"
    )
    # Bare non-wildcard form must NOT appear as a standalone argument
    assert not any(arg == "mylib:shared=True" for arg in cmd), (
        f"Unexpected bare 'mylib:shared=True' found in command: {cmd}"
    )


# ---------------------------------------------------------------------------
# BL-TB-05 — already-wildcarded option is not double-wildcarded
# ---------------------------------------------------------------------------


def test_option_normalization_already_wildcarded_is_idempotent() -> None:
    """BL-TB-05: An already-wildcarded option is not modified a second time.

    Business Rule:
        An option that already contains ``/*:`` (e.g. ``"mylib/*:shared=True"``)
        must pass through the normalizer unchanged.  The normalizer must NOT
        produce a double-wildcard form such as ``"mylib/*/*:shared=True"``.

    Preconditions:
        - Option set: ``{"1": "mylib/*:shared=True"}`` (wildcard already present).

    Steps:
        1. Build tasks with ``ConanTaskBuilder().build([comp], ...)``
        2. Inspect the ``cmd`` of the single resulting task.

    Expected Result:
        - ``cmd`` contains ``"mylib/*:shared=True"`` exactly once.
        - ``cmd`` does NOT contain any string with ``"mylib/*/*"``.
    """
    release = make_release(opts={"1": "mylib/*:shared=True"})
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    cmd = tasks[0].cmd

    # Double-wildcard must not appear
    assert not any("mylib/*/*" in arg for arg in cmd), (
        f"Double wildcard detected in command: {cmd}"
    )
    # Correct single-wildcard form must be present
    assert any("mylib/*:shared=True" in arg for arg in cmd), (
        f"Expected 'mylib/*:shared=True' in command, got: {cmd}"
    )


# ---------------------------------------------------------------------------
# BL-TB-06 — release with no option sets produces exactly one default task
# ---------------------------------------------------------------------------


def test_no_option_sets_produces_one_default_task() -> None:
    """BL-TB-06: A release with no option sets still produces exactly one task.

    Business Rule:
        When ``release._build_option_sets_internal`` is empty (or None), the
        builder must fall back to a single default option set ``{"1": ""}`` so
        that the Conan graph is queried at least once.  Zero tasks would mean
        the component is silently skipped.

    Preconditions:
        - One component with one release.
        - One profile: ``"hw-linux-x86_64"``.
        - No option sets (``opts=None``).

    Steps:
        1. Build tasks with ``ConanTaskBuilder().build([comp], ...)``
        2. Inspect the resulting task list.

    Expected Result:
        - Exactly one ``ConanTask`` is returned.
        - ``task.option_id == "1"`` (default identifier).
        - ``task.option_str == ""`` (empty option string; no ``-o`` flags).
    """
    release = make_release(
        profiles=("hw-linux-x86_64",),
        opts=None,  # No option sets configured
    )
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1, (
        f"Expected exactly 1 task for a release with no option sets, got {len(tasks)}"
    )
    assert tasks[0].option_id == "1", (
        f"Default option_id should be '1', got '{tasks[0].option_id}'"
    )
    assert tasks[0].option_str == "", (
        f"Default option_str should be empty, got '{tasks[0].option_str}'"
    )
