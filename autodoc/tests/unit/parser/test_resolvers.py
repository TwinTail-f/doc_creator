"""Тесты OptionsFetcher и DockerFetcher."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from autodoc.models.component import Component, ProfileBuild, Release
from autodoc.parser.fetchers.docker_fetcher import DockerLinksMap, DockerFetcher
from autodoc.parser.fetchers.options_fetcher import OptionsMap, OptionsFetcher
from autodoc.parser.parsers.docker_parser import DockerParser


def _make_component(name: str, version: str, channel: str, git_repo: str) -> Component:
    release = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="https://tfs.example.com/repo",
    )
    return Component(name=name, git_repo=git_repo, releases=[release])


def _make_sync_executor() -> MagicMock:
    """
    Возвращает мок ParallelExecutor, который выполняет задачи синхронно.

    Воспроизводит контракт ParallelExecutor.execute(fn, items, ...) → list,
    не запуская реальные потоки — достаточно для юнит-тестов.
    """
    mock_executor = MagicMock()
    mock_executor.execute.side_effect = lambda fn, items, **kw: [fn(item) for item in items]
    return mock_executor


class TestDockerParserAliases:
    def test_simple_name_generates_aliases(self) -> None:
        links: DockerLinksMap = {}
        DockerParser.add_aliases("settings/default_gcc.jinja", "registry/img:1", links)
        assert links.get("settings/default_gcc.jinja") == "registry/img:1"
        assert links.get("default_gcc.jinja") == "registry/img:1"
        assert links.get("default_gcc") == "registry/img:1"
        assert links.get("settings/default_gcc") == "registry/img:1"

    def test_flat_name_generates_two_aliases(self) -> None:
        links: DockerLinksMap = {}
        DockerParser.add_aliases("profile.jinja", "registry/img:2", links)
        assert links.get("profile.jinja") == "registry/img:2"
        assert links.get("profile") == "registry/img:2"

    def test_empty_name_does_nothing(self) -> None:
        links: DockerLinksMap = {}
        DockerParser.add_aliases("", "registry/img:3", links)
        assert links == {}


class TestDockerFetcherFetch:
    def test_valid_yaml_returns_docker_links(self) -> None:
        yaml_data = {
            "archs": {
                "linux_x86_64": {
                    "docker": "registry.example.com/builder:1.0",
                    "profile_host": "settings/gcc.jinja",
                },
            }
        }
        resolver = DockerFetcher.__new__(DockerFetcher)
        resolver._tfs = MagicMock()
        resolver._configured = True
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = yaml.dump(yaml_data)
        resolver._tfs.get_file_content.return_value = mock_resp

        url = "https://tfs.example.com/DEP/_git/profiles?path=/build.yaml&version=GBdevelop"
        result = resolver.fetch([url], "develop")

        assert "linux_x86_64" in result.value
        assert result.value["linux_x86_64"] == "registry.example.com/builder:1.0"
        assert "settings/gcc.jinja" in result.value
        assert "gcc" in result.value

    def test_url_without_git_segment_skipped(self) -> None:
        resolver = DockerFetcher.__new__(DockerFetcher)
        resolver._tfs = MagicMock()
        resolver._configured = True
        result = resolver.fetch(["https://example.com/no-git-here"], "develop")
        assert result.value == {}

    def test_http_error_response_skipped(self) -> None:
        resolver = DockerFetcher.__new__(DockerFetcher)
        resolver._tfs = MagicMock()
        resolver._configured = True
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        resolver._tfs.get_file_content.return_value = mock_resp
        url = "https://tfs.example.com/DEP/_git/profiles?path=/b.yaml&version=GBdevelop"
        result = resolver.fetch([url], "develop")
        assert result.value == {}


class TestOptionsFetcher:
    def _resolver_with_options(
        self, options_json, opt_path="/repo/conan/ci-2.0/options.json"
    ):
        resolver = OptionsFetcher.__new__(OptionsFetcher)
        resolver._base_url = "https://tfs.example.com/DEP"
        resolver._configured = True
        resolver._executor = _make_sync_executor()
        mock_tfs = MagicMock()
        mock_tfs.get_items.return_value = [{"path": opt_path, "isFolder": False}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = json.dumps(options_json)
        mock_tfs.get_file_content.return_value = mock_resp
        resolver._tfs = mock_tfs
        return resolver

    def test_returns_options_map(self) -> None:
        resolver = self._resolver_with_options({"1": "shared=True"})
        comp = _make_component("my_lib", "1.0.0", "stable", "my_lib_repo")
        result = resolver.fetch([comp])
        assert isinstance(result.value, dict)
        assert ("my_lib", "1.0.0", "stable") in result.value

    def test_does_not_mutate_components(self) -> None:
        """2.1/1.4 resolver.fetch() не мутирует компоненты."""
        resolver = self._resolver_with_options({"1": "opt=True"})
        comp = _make_component("my_lib", "1.0.0", "stable", "my_lib_repo")
        original_opts = list(comp.releases[0].build_option_sets)
        resolver.fetch([comp])
        assert comp.releases[0].build_option_sets == original_opts

    def test_component_without_git_repo_skipped(self) -> None:
        """1.3 git_repo берётся из Component — если пустой, компонент пропускается."""
        resolver = OptionsFetcher.__new__(OptionsFetcher)
        resolver._base_url = "https://tfs.example.com/DEP"
        resolver._configured = True
        resolver._executor = _make_sync_executor()
        resolver._tfs = MagicMock()
        comp = _make_component("no_repo_lib", "1.0.0", "stable", "")
        result = resolver.fetch([comp])
        assert result.value == {}
        resolver._tfs.get_items.assert_not_called()

    def test_default_options_when_no_files_found(self) -> None:
        resolver = OptionsFetcher.__new__(OptionsFetcher)
        resolver._base_url = "https://tfs.example.com/DEP"
        resolver._configured = True
        resolver._executor = _make_sync_executor()
        mock_tfs = MagicMock()
        mock_tfs.get_items.return_value = [{"path": "/other.txt", "isFolder": False}]
        resolver._tfs = mock_tfs
        comp = _make_component("lib", "1.0.0", "stable", "lib_repo")
        result = resolver.fetch([comp])
        assert result.value[("lib", "1.0.0", "stable")] == {"1": ""}