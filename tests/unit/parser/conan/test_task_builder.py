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
from autodoc.parser.conan.conan_task_builder import ConanTaskBuilder
from autodoc.parser.conan.models.conan_task import ConanTask
from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides

ART_URL: str = "https://art.example.com"
PLATFORM: str = "2.0"


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


def _make_component_with_releases(
    name: str = "mylib", releases: list[Release] | None = None
) -> Component:
    """Создаёт Component с необязательным списком релизов."""
    return Component(name=name, releases=releases or [])


@pytest.mark.business_logic
def test_task_builder_produces_one_task_per_profile() -> None:
    """Один компонент × один релиз × два профиля → две задачи."""
    release = make_release(profiles=("hw-linux-x86_64", "hw-linux-armv8"))
    comp = _make_component_with_releases(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


@pytest.mark.business_logic
def test_task_builder_multiplies_tasks_by_option_sets() -> None:
    """Один профиль × два набора опций → две задачи."""
    opts = {"1": "shared=True", "2": "shared=False"}
    release = make_release(opts=opts)
    comp = _make_component_with_releases(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert len(tasks) == 2


@pytest.mark.business_logic
def test_task_builder_cmd_contains_requires_flag() -> None:
    """Первый элемент --requires= в cmd должен содержать имя компонента."""
    release = make_release()
    comp = _make_component_with_releases(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, "Expected at least one --requires= flag in cmd"
    assert "mylib" in requires_flags[0]


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "raw_option, expected_normalized",
    [
        # голая опция без имени пакета получает префикс '*:'
        pytest.param("shared=True", "*:shared=True", id="bare-option-gets-wildcard-prefix"),
        # опция с именем пакета без подстановочного знака нормализуется в 'pkg/*:...'
        pytest.param("mylib:shared=True", "mylib/*:shared=True", id="package-key-gets-wildcard"),
        # уже подставленная опция не изменяется повторно (без двойной подстановки)
        pytest.param(
            "mylib/*:shared=True", "mylib/*:shared=True", id="already-wildcarded-is-idempotent"
        ),
    ],
)
def test_task_builder_normalizes_option_to_wildcard_form(
    raw_option: str, expected_normalized: str
) -> None:
    """
    _normalize_option() приводит одиночную опцию к форме 'pkg/*:key=val'; уже
    нормализованная опция не подставляется повторно (без двойного '/*/*').
    """
    release = make_release(opts={"1": raw_option})
    comp = _make_component_with_releases(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    cmd = tasks[0].cmd
    assert cmd.count("-o") == 1
    o_index = cmd.index("-o")
    assert cmd[o_index + 1] == expected_normalized


@pytest.mark.business_logic
def test_task_builder_empty_components_returns_empty() -> None:
    """Пустой список компонентов должен возвращать пустой список задач."""
    tasks = ConanTaskBuilder().build([], PLATFORM, ART_URL)

    assert tasks == []


@pytest.mark.business_logic
def test_task_builder_task_fields_populated() -> None:
    """Все скалярные поля ConanTask должны совпадать со значениями исходной модели."""
    release = make_release(version="3.2.1", channel="stable", profiles=("hw-linux-x86_64",))
    comp = _make_component_with_releases(name="zlib", releases=[release])

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
def test_no_option_sets_produces_one_default_task() -> None:
    """Релиз без наборов опций всё равно даёт ровно одну задачу с дефолтным option_id '1' и пустым option_str."""
    release = make_release(
        profiles=("hw-linux-x86_64",),
        opts=None,  # наборы опций не заданы
    )
    comp = _make_component_with_releases(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL)

    assert (
        len(tasks) == 1
    ), f"Expected exactly 1 task for a release with no option sets, got {len(tasks)}"
    assert tasks[0].option_id == "1", f"Default option_id should be '1', got '{tasks[0].option_id}'"
    assert (
        tasks[0].option_str == ""
    ), f"Default option_str should be empty, got '{tasks[0].option_str}'"


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "version, exact_range_components, expected_substring, forbidden_substrings",
    [
        # версии с буквенным суффиксом (например '8.4p1') всегда используют точный
        # диапазон [>=X <X+1], а не '~'
        pytest.param("8.4p1", None, "[>=8.4 <8.5]", ["~"], id="lettered-version-uses-exact-range"),
        # версия без числового префикса (например 'latest') подставляется как есть,
        # без диапазона '~' или '[>=X <Y]'
        pytest.param(
            "latest",
            None,
            "mylib/latest@platform-2.0/tech",
            ["~", "["],
            id="non-numeric-prefix-used-as-is",
        ),
        # exact_range_components заставляет использовать точный диапазон даже для
        # чисто числовой версии
        pytest.param(
            "3.34.1",
            ["mylib"],
            "[>=3.34.1 <3.34.2]",
            ["~"],
            id="exact-range-components-forces-exact-range",
        ),
        # для многосегментной версии ('20.11.10') точный диапазон увеличивает только
        # последний числовой сегмент
        pytest.param(
            "20.11.10",
            ["mylib"],
            "[>=20.11.10 <20.11.11]",
            ["~"],
            id="exact-range-increments-only-last-segment",
        ),
        # зеркальный кейс: чисто числовая версия без exact_range_components -> дефолтная
        # ветка '~' (недостающий кейс, добавлен при рефакторинге)
        pytest.param(
            "3.34.1",
            None,
            "[~3.34.1,include_prerelease]",
            ["[>="],
            id="numeric-version-without-exact-range-uses-tilde",
        ),
    ],
)
def test_task_builder_requires_flag_version_formatting(
    version: str,
    exact_range_components: list[str] | None,
    expected_substring: str,
    forbidden_substrings: list[str],
) -> None:
    """
    --requires= формирует диапазон версии в зависимости от формата версии и наличия
    компонента в exact_range_components: буквенный суффикс версии или явный
    exact_range_components всегда дают точный диапазон [>=X <Y]; версия без числового
    префикса подставляется как есть; чисто числовая версия без exact_range_components
    использует стандартный оператор Conan 2 '~'.
    """
    release = make_release(version=version)
    comp = _make_component_with_releases(name="mylib", releases=[release])

    tasks = ConanTaskBuilder().build(
        [comp], PLATFORM, ART_URL, exact_range_components=exact_range_components
    )

    requires_flags = [arg for arg in tasks[0].cmd if arg.startswith("--requires=")]
    assert requires_flags, f"Expected a --requires= flag, got: {tasks[0].cmd}"
    assert expected_substring in requires_flags[0]
    for forbidden in forbidden_substrings:
        assert forbidden not in requires_flags[0]


@pytest.mark.business_logic
def test_task_builder_applies_profile_overrides_as_settings_flags() -> None:
    """Непустые ProfileSettingsOverrides.resolve() добавляют в cmd соответствующие флаги -s."""
    overrides = ProfileSettingsOverrides(
        mapping={"kos_profile.jinja": {"compiler.toolchain_config_id": "kos-kisg-3.1.0.130"}}
    )
    release = make_release(profiles=("kos_profile.jinja",))
    comp = _make_component_with_releases(releases=[release])

    tasks = ConanTaskBuilder().build([comp], PLATFORM, ART_URL, profile_overrides=overrides)

    cmd = tasks[0].cmd
    assert "-s" in cmd
    s_index = cmd.index("-s")
    assert cmd[s_index + 1] == "compiler.toolchain_config_id=kos-kisg-3.1.0.130"
