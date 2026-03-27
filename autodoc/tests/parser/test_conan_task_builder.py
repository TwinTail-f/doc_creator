"""Тесты ConanTaskBuilder."""

import pytest

from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.conan.task_builder import ConanTask, ConanTaskBuilder

def _make_release(version='1.0.0', channel='stable', profiles=None, options=None):
    release = Release(
        version=version,
        platform='2.0',
        channel=channel,
        git_url='https://tfs.example.com/repo',
        profile_builds=[ProfileBuild(profile_name=p) for p in (profiles or [])],
    )
    # 1.4 _conan_options_internal → _build_option_sets_internal
    release._build_option_sets_internal = options or {'1': ''}
    return release

def _make_component(name, releases):
    return Component(name=name, releases=releases)

class TestConanTaskBuilder:
    def setup_method(self):
        self.builder = ConanTaskBuilder()

    def test_one_release_two_profiles_generates_two_tasks(self) -> None:
        release = _make_release(profiles=['linux_x86_64', 'linux_aarch64'])
        comp = _make_component('my_lib', [release])
        tasks = self.builder.build([comp], '2.0', 'https://art.example.com')
        assert len(tasks) == 2
        assert {t.profile_name for t in tasks} == {'linux_x86_64', 'linux_aarch64'}

    def test_two_option_sets_generate_two_tasks_per_profile(self) -> None:
        release = _make_release(profiles=['linux_x86_64'], options={'1': 'shared=True', '2': 'shared=False'})
        comp = _make_component('my_lib', [release])
        tasks = self.builder.build([comp], '2.0', 'https://art.example.com')
        assert len(tasks) == 2

    def test_option_without_colon_gets_wildcard_prefix(self) -> None:
        release = _make_release(profiles=['p'], options={'1': 'shared=True'})
        comp = _make_component('lib', [release])
        tasks = self.builder.build([comp], '2.0', '')
        cmd = tasks[0].cmd
        opt_idx = cmd.index('-o')
        assert cmd[opt_idx + 1] == '*:shared=True'

    def test_option_with_pkg_colon_gets_wildcard_suffix(self) -> None:
        release = _make_release(profiles=['p'], options={'1': 'mylib:shared=True'})
        comp = _make_component('lib', [release])
        tasks = self.builder.build([comp], '2.0', '')
        cmd = tasks[0].cmd
        opt_idx = cmd.index('-o')
        assert cmd[opt_idx + 1] == 'mylib/*:shared=True'

    def test_multiple_options_in_string_all_added(self) -> None:
        release = _make_release(profiles=['p'], options={'1': 'opt_a=True,opt_b=False'})
        comp = _make_component('lib', [release])
        tasks = self.builder.build([comp], '2.0', '')
        cmd = tasks[0].cmd
        o_flags = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '-o']
        assert len(o_flags) == 2

    def test_no_profiles_generates_no_tasks(self) -> None:
        release = _make_release(profiles=[])
        comp = _make_component('lib', [release])
        assert self.builder.build([comp], '2.0', '') == []

    def test_empty_components_list(self) -> None:
        assert self.builder.build([], '2.0', 'https://art.example.com') == []
