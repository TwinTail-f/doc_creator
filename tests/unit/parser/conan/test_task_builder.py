"""
Юнит-тесты для autodoc/parser/conan/conan_task_builder.py.

Охватывает ConanTaskBuilder.build() — перебор задач, заполнение полей
и нормализацию строк опций. Без ввода/вывода и вызовов subprocess.
"""

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.options import ConanInputOptions
from autodoc.models.release import Release
from autodoc.parser.conan.models.conan_task import ConanTask
from autodoc.parser.conan.conan_task_builder import ConanTaskBuilder
from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides


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
        r.build_option_sets = [
            ConanInputOptions(id=option_id, options=option_str)
            for option_id, option_str in opts.items()
        ]
    return r


def make_component(name: str = "mylib", releases: list[Release] | None = None) -> Component:
    """Создаёт Component с необязательным списком релизов."""
    return Component(name=name, releases=releases or [])


ART_URL: str = "https://art.example.com"
PLATFORM: str = "2.0"


@pytest.mark.business_logic
def test_task_builder_produces_one_task_per_profile() -> None:
    """Один компонент × один релиз × два профиля → две задачи."""
    release = make_release(profiles=("hw-linux-x86_64", "hw-linux-armv8"))
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


@pytest.mark.business_logic
def test_task_builder_multiplies_tasks_by_option_sets() -> None:
    """Один профиль × два набора опций → две задачи."""
    opts = {"1": "shared=True", "2": "shared=False"}
    release = make_release(opts=opts)
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


@pytest.mark.business_logic
def test_task_builder_cmd_contains_requires_flag() -> None:
    """Первый элемент --requires= в cmd должен содержать имя компонента."""
    release = make_release()
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, "Expected at least one --requires= flag in cmd"
    assert "mylib" in requires_flags[0]


@pytest.mark.business_logic
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


@pytest.mark.business_logic
def test_task_builder_empty_components_returns_empty() -> None:
    """Пустой список компонентов должен возвращать пустой список задач."""
    tasks = ConanTaskBuilder().build([], PLATFORM, ART_URL)

    assert tasks == []


@pytest.mark.business_logic
def test_task_builder_task_fields_populated() -> None:
    """Все скалярные поля ConanTask должны совпадать со значениями исходной модели."""
    release = make_release(version="3.2.1", channel="stable", profiles=("hw-linux-x86_64",))
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


@pytest.mark.business_logic
def test_option_normalization_package_key_gets_wildcard() -> None:
    """Опция с именем пакета без подстановочного знака ('mylib:shared=True') нормализуется в 'mylib/*:shared=True'."""
    release = make_release(opts={"1": "mylib:shared=True"})
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    cmd = tasks[0].cmd

    # Нормализованная форма с подстановочным знаком должна присутствовать
    assert any(
        "mylib/*:shared=True" in arg for arg in cmd
    ), f"Expected 'mylib/*:shared=True' in command, got: {cmd}"
    # Голая форма без подстановочного знака не должна встречаться как отдельный аргумент
    assert not any(
        arg == "mylib:shared=True" for arg in cmd
    ), f"Unexpected bare 'mylib:shared=True' found in command: {cmd}"


@pytest.mark.business_logic
def test_option_normalization_already_wildcarded_is_idempotent() -> None:
    """Уже подставленная опция ('mylib/*:shared=True') не изменяется повторно (без двойной подстановки)."""
    release = make_release(opts={"1": "mylib/*:shared=True"})
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 1
    cmd = tasks[0].cmd

    # Двойной подстановочный знак не должен встречаться
    assert not any("mylib/*/*" in arg for arg in cmd), f"Double wildcard detected in command: {cmd}"
    # Корректная форма с одним подстановочным знаком должна присутствовать
    assert any(
        "mylib/*:shared=True" in arg for arg in cmd
    ), f"Expected 'mylib/*:shared=True' in command, got: {cmd}"


@pytest.mark.business_logic
def test_no_option_sets_produces_one_default_task() -> None:
    """Релиз без наборов опций всё равно даёт ровно одну задачу с дефолтным option_id '1' и пустым option_str."""
    release = make_release(
        profiles=("hw-linux-x86_64",),
        opts=None,  # наборы опций не заданы
    )
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert (
        len(tasks) == 1
    ), f"Expected exactly 1 task for a release with no option sets, got {len(tasks)}"
    assert tasks[0].option_id == "1", f"Default option_id should be '1', got '{tasks[0].option_id}'"
    assert (
        tasks[0].option_str == ""
    ), f"Default option_str should be empty, got '{tasks[0].option_str}'"


@pytest.mark.business_logic
def test_task_builder_lettered_version_uses_exact_range() -> None:
    """Версии с буквенным суффиксом (например '8.4p1') используют точный диапазон [>=X <X+1], а не '~'."""
    release = make_release(version="8.4p1")
    comp = make_component(name="openssh", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, f"Expected a --requires= flag, got: {tasks[0].cmd}"
    assert "[>=8.4 <8.5]" in requires_flags[0]
    assert "~" not in requires_flags[0]


@pytest.mark.business_logic
def test_task_builder_version_without_numeric_prefix_used_as_is() -> None:
    """Версия без числового префикса (например 'latest') подставляется в --requires
    как есть, без диапазона версий '~' или '[>=X <Y]', так как _format_reference
    не может вычислить upper_bound из нечислового значения."""
    release = make_release(version="latest")
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, f"Expected a --requires= flag, got: {tasks[0].cmd}"
    assert "mylib/latest@platform-2.0/tech" in requires_flags[0]
    assert "~" not in requires_flags[0]
    assert "[" not in requires_flags[0]


@pytest.mark.business_logic
def test_task_builder_exact_range_components_forces_exact_range_for_numeric_version() -> None:
    """exact_range_components заставляет использовать точный диапазон даже для чисто числовой версии."""
    release = make_release(version="3.34.1")
    comp = make_component(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build(
        [comp], PLATFORM, ART_URL, exact_range_components=["mylib"]
    )

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, f"Expected a --requires= flag, got: {tasks[0].cmd}"
    assert "[>=3.34.1 <3.34.2]" in requires_flags[0]
    assert "~" not in requires_flags[0]


@pytest.mark.business_logic
def test_task_builder_calc_upper_bound_multi_segment() -> None:
    """_calc_upper_bound увеличивает только последний числовой сегмент многосегментной версии."""
    assert ConanTaskBuilder._calc_upper_bound("20.11.10") == "20.11.11"


@pytest.mark.business_logic
def test_task_builder_applies_profile_overrides_as_settings_flags() -> None:
    """Непустые ProfileSettingsOverrides.resolve() добавляют в cmd соответствующие флаги -s."""
    overrides = ProfileSettingsOverrides(
        mapping={"kos_profile.jinja": {"compiler.toolchain_config_id": "kos-kisg-3.1.0.130"}}
    )
    release = make_release(profiles=("kos_profile.jinja",))
    comp = make_component(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL, profile_overrides=overrides)

    cmd = tasks[0].cmd
    assert "-s" in cmd
    s_index = cmd.index("-s")
    assert cmd[s_index + 1] == "compiler.toolchain_config_id=kos-kisg-3.1.0.130"
