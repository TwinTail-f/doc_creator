"""Юнит-тесты для autodoc/parser/steps/options_step.py."""

import json
from pathlib import Path

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release
from autodoc.models.types import OptionsMap
from autodoc.parser.fetchers.options_fetcher import OptionsFetcher
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.options_step import OptionsResolveStep
from tests.unit.parser.conftest import RESOURCES_DIR


def _make_release(version: str, channel: str) -> Release:
    """Строит минимальный Release с заданными версией и каналом."""
    return Release(
        version=version,
        platform="2.0",
        channel=channel,
        profile_builds=[ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")],
    )


def _make_component(name: str, releases: list[Release]) -> Component:
    """Строит минимальный Component с заданным именем и списком релизов."""
    return Component(name=name, git_project="DEP", git_repo=name, releases=releases)


def _make_ctx_with_components(
    parser_config, tmp_path: Path, components: list[Component]
) -> PipelineContext:
    """
    Строит PipelineContext, предзаполненный переданными компонентами.

    Args:
        parser_config: Схема конфигурации парсера.
        tmp_path: Временная директория пайплайна.
        components: Компоненты, которыми нужно заполнить ctx.components.

    Returns:
        Готовый к использованию PipelineContext.
    """
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.components = components
    return ctx


@pytest.mark.business_logic
def test_options_step_stores_options_map_in_intermediate(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """ctx.intermediate['options_map'] заполняется результатом fetcher."""
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
    """Совпавший по ключу релиз получает непустой build_option_sets после применения опций."""
    parser_pipeline_context.components = [manifest_component]
    # Ключ должен совпадать с фикстурой: name="openssl", version="1.0.0", channel="tech"
    options_map: OptionsMap = {("openssl", "1.0.0", "tech"): {"1": "shared=True"}}
    fake = make_fake_fetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    build_sets = parser_pipeline_context.components[0].releases[0].build_option_sets
    assert len(build_sets) == 1
    assert build_sets[0].options == "shared=True"


@pytest.mark.contract
def test_options_step_default_fetcher_is_options_fetcher() -> None:
    """При отсутствии аргумента fetcher OptionsResolveStep создаёт реальный OptionsFetcher."""
    step = OptionsResolveStep()
    assert isinstance(step._fetcher, OptionsFetcher)


@pytest.mark.business_logic
def test_options_step_component_not_in_options_map_left_untouched(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """Релиз, отсутствующий в options_map целиком, не получает build_option_sets."""
    options_map: OptionsMap = {("other_lib", "1.0.0", "fast"): {"1": ""}}
    comp = _make_component("somelib", [_make_release("1.0.0", "fast")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    assert ctx.components[0].releases[0].build_option_sets == []


@pytest.mark.business_logic
def test_options_step_sqlite3_twelve_options_applied(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """FakeFetcher с 12 опциями для sqlite3/slow применяет все 12 к build_option_sets."""
    sqlite3_opts: OptionsMap = {
        ("sqlite3", "3.34.1", "slow"): json.loads(
            (RESOURCES_DIR / "options" / "sqlite3_slow_options.json").read_text()
        )
    }
    comp = _make_component("sqlite3", [_make_release("3.34.1", "slow")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=sqlite3_opts)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 12
    # Опции для id 2–12 не должны быть пустыми
    non_empty = [bs for bs in build_sets if bs.id != "1"]
    assert all(bs.options != "" for bs in non_empty)


@pytest.mark.business_logic
def test_options_step_patchelf_both_versions_get_options(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """FakeFetcher с опциями для двух релизов patchelf заполняет build_option_sets у обоих."""
    patchelf_opts = json.loads((RESOURCES_DIR / "options" / "patchelf_options.json").read_text())
    options_map: OptionsMap = {
        ("patchelf", "0.16.1", "tech"): patchelf_opts,
        ("patchelf", "0.18.0", "tech"): patchelf_opts,
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
        assert len(release.build_option_sets) == 1


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "comp_name, version, channel, option_str, expected_parsed",
    [
        # nlohmann_json/slow — единственная опция пустая, parsed_options пуст
        pytest.param("nlohmann_json", "3.9.1", "slow", "", {}, id="nlohmann-empty-option"),
        # apr/fast — единственная опция содержит shared=True
        pytest.param(
            "apr", "1.7.6", "fast", "apr:shared=True", {"shared": "True"}, id="apr-shared-option"
        ),
        # libnetfilter_queue/slow (PRG_Quant) — единственная опция пустая
        pytest.param(
            "libnetfilter_queue", "1.0.5", "slow", "", {}, id="libnetfilter-queue-empty-option"
        ),
    ],
)
def test_options_step_single_release_single_option_applied(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
    comp_name: str,
    version: str,
    channel: str,
    option_str: str,
    expected_parsed: dict[str, str],
) -> None:
    """Релиз с единственной опцией в options_map получает ровно один build_option_set с этой опцией."""
    options_map: OptionsMap = {(comp_name, version, channel): {"1": option_str}}
    comp = _make_component(comp_name, [_make_release(version, channel)])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=options_map)
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)

    build_sets = ctx.components[0].releases[0].build_option_sets
    assert len(build_sets) == 1
    assert build_sets[0].options == option_str
    assert build_sets[0].parsed_options == expected_parsed


@pytest.mark.infrastructure
def test_options_step_warnings_logged(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """Шаг не бросает исключение при предупреждениях fetcher; options_map всё равно сохраняется в ctx."""
    options_map: OptionsMap = {("somelib", "1.0.0", "fast"): {"1": ""}}
    comp = _make_component("somelib", [_make_release("1.0.0", "fast")])
    ctx = _make_ctx_with_components(parser_config, tmp_path, [comp])
    fake = make_fake_fetcher(value=options_map, warnings=["repo not found"])
    step = OptionsResolveStep(fetcher=fake)
    step.execute(ctx)  # Не должно бросать исключение

    assert "options_map" in ctx.intermediate


@pytest.mark.contract
def test_options_step_configure_called_before_fetch(
    parser_pipeline_context,
    make_fake_fetcher,
) -> None:
    """FakeFetcher.configure_called равен True после OptionsResolveStep.execute."""
    fake = make_fake_fetcher(value={})
    step = OptionsResolveStep(fetcher=fake)
    step.execute(parser_pipeline_context)
    assert fake.configure_called is True


@pytest.mark.business_logic
def test_options_step_sqlite3_fast_and_slow_get_different_option_counts(
    parser_config,
    tmp_path: Path,
    make_fake_fetcher,
) -> None:
    """sqlite3 с релизами fast (5 опций) и slow (12 опций) — каждый получает свой набор опций."""
    fast_opts = json.loads((RESOURCES_DIR / "options" / "sqlite3_fast_options.json").read_text())
    slow_opts = json.loads((RESOURCES_DIR / "options" / "sqlite3_slow_options.json").read_text())
    options_map: OptionsMap = {
        ("sqlite3", "3.51.2", "fast"): fast_opts,
        ("sqlite3", "3.34.1", "slow"): slow_opts,
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
    assert len(fast_rel.build_option_sets) == len(fast_opts) == 5
    assert len(slow_rel.build_option_sets) == len(slow_opts) == 12
