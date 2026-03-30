"""Тесты ManifestFetcher и read_properties."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autodoc.models.component import Component
from autodoc.parser.fetchers.manifest_fetcher import ManifestFetcher
from autodoc.parser.fetchers.properties_reader import read_properties
from autodoc.parser.parsers.manifest_parser import ManifestParser

# 4.2 Используем новое имя поля
MINIMAL_CONFIG_DATA = {
    'platform_version': '2.0',
    'platform_branch_name': 'develop',
    'tfs_username': 'robot',
    'tfs_token': 'secret',
    'tfs_dep_components_url': 'https://tfs.example.com/DEP',
    'manifests_remotes_path': '/remotes/manifests',
}

def _make_config():
    from autodoc.config.schemas import ParserConfigSchema
    return ParserConfigSchema(**MINIMAL_CONFIG_DATA)

def _write_properties(tmp_path: Path, filename: str, content: str) -> Path:
    p = tmp_path / filename
    p.write_text(content, encoding='utf-8')
    return p

SAMPLE_PROPERTIES = """\
name=crypto_lib
description=Crypto library
tfs_git_project=DEP_Components
git_repo_name=crypto_lib
versions.component=1.2.3
versions.platform=2.0-stable
integration-profiles-develop-1.2.3-2.0-stable=linux_x86_64,linux_aarch64
svace-profiles-1.2.3-2.0=linux_x86_64
"""

class TestReadProperties:
    def test_reads_simple_key_value(self, tmp_path: Path) -> None:
        p = _write_properties(tmp_path, 'test.properties', 'key=value\nfoo=bar\n')
        assert read_properties(p) == {'key': 'value', 'foo': 'bar'}

    def test_ignores_comments_and_empty_lines(self, tmp_path: Path) -> None:
        p = _write_properties(tmp_path, 'test.properties', '# comment\n\nkey=value\n')
        assert read_properties(p) == {'key': 'value'}

    def test_multiline_continuation(self, tmp_path: Path) -> None:
        p = _write_properties(tmp_path, 'test.properties', 'key=first\\\nsecond\\\nthird\n')
        assert read_properties(p)['key'] == 'firstsecondthird'

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        p = _write_properties(tmp_path, 'test.properties', '  key  =  value  \n')
        assert read_properties(p) == {'key': 'value'}

    def test_raises_os_error_for_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(OSError):
            read_properties(tmp_path / 'nonexistent.properties')

class TestManifestFetcher:
    def _make_parser_with_mock(self, tmp_path: Path, content: str):
        def fake_download(items_url, remote_path, branch, output_dir):
            _write_properties(Path(output_dir), 'comp.properties', content)

        parser = ManifestFetcher.__new__(ManifestFetcher)
        parser._tfs = MagicMock()
        parser._tfs.download_properties.side_effect = fake_download
        parser._base_url = 'https://tfs.example.com/DEP'
        parser._manifests_remotes_path = '/remotes/manifests'
        parser._platform_branch_name = 'develop'
        parser._platform_version = '2.0'
        parser._configured = True
        return parser

    def test_returns_component_list(self, tmp_path: Path) -> None:
        parser = self._make_parser_with_mock(tmp_path, SAMPLE_PROPERTIES)
        result = parser.fetch(tmp_path / 'manifests', excluded=[])
        assert len(result.value) == 1
        assert isinstance(result.value[0], Component)
        assert result.value[0].name == 'crypto_lib'

    def test_release_fields_populated(self, tmp_path: Path) -> None:
        parser = self._make_parser_with_mock(tmp_path, SAMPLE_PROPERTIES)
        result = parser.fetch(tmp_path / 'manifests', excluded=[])
        release = result.value[0].releases[0]
        assert release.version == '1.2.3'
        assert release.channel == 'stable'

    def test_git_repo_on_component_not_release(self, tmp_path: Path) -> None:
        """1.3 git_repo/git_project должны быть на Component, не на Release."""
        parser = self._make_parser_with_mock(tmp_path, SAMPLE_PROPERTIES)
        result = parser.fetch(tmp_path / 'manifests', excluded=[])
        comp = result.value[0]
        # На компоненте — есть
        assert comp.git_repo == 'crypto_lib'
        assert comp.git_project == 'DEP_Components'
        # На релизе — нет таких атрибутов
        assert not hasattr(comp.releases[0], 'git_repo')

    def test_profile_builds_populated(self, tmp_path: Path) -> None:
        parser = self._make_parser_with_mock(tmp_path, SAMPLE_PROPERTIES)
        result = parser.fetch(tmp_path / 'manifests', excluded=[])
        profiles = result.value[0].releases[0].profile_builds
        assert len(profiles) == 2
        assert {p.profile_name for p in profiles} == {'linux_x86_64', 'linux_aarch64'}

    def test_excluded_component_skipped(self, tmp_path: Path) -> None:
        parser = self._make_parser_with_mock(tmp_path, SAMPLE_PROPERTIES)
        assert parser.fetch(tmp_path / 'manifests', excluded=['crypto_lib']).value == []

    def test_component_without_name_skipped(self, tmp_path: Path) -> None:
        parser = self._make_parser_with_mock(tmp_path, 'description=No name\n')
        assert parser.fetch(tmp_path / 'manifests', excluded=[]).value == []

    def test_raises_parsing_error_if_no_files(self, tmp_path: Path) -> None:
        from autodoc.exceptions import ParsingError
        parser = ManifestFetcher.__new__(ManifestFetcher)
        parser._tfs = MagicMock()
        parser._tfs.download_properties.return_value = None
        parser._base_url = 'https://tfs.example.com/DEP'
        parser._manifests_remotes_path = '/remotes/manifests'
        parser._platform_branch_name = 'develop'
        parser._platform_version = '2.0'
        parser._configured = True
        with pytest.raises(ParsingError, match='.properties'):
            parser.fetch(tmp_path / 'empty', excluded=[])


class TestManifestParser:
    """Тесты ManifestParser напрямую — без TFS, без моков сети."""

    def test_parse_returns_component(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, 'c.properties', SAMPLE_PROPERTIES)
        parser = ManifestParser(target_platform='2.0')
        components, warnings = parser.parse(list(tmp_path.glob('*.properties')), excluded=[])
        assert len(components) == 1
        assert components[0].name == 'crypto_lib'
        assert warnings == []

    def test_parse_excluded_returns_empty(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, 'c.properties', SAMPLE_PROPERTIES)
        parser = ManifestParser(target_platform='2.0')
        components, _ = parser.parse(list(tmp_path.glob('*.properties')), excluded=['crypto_lib'])
        assert components == []

    def test_parse_no_name_skipped(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, 'c.properties', 'description=No name\n')
        parser = ManifestParser(target_platform='2.0')
        components, _ = parser.parse(list(tmp_path.glob('*.properties')), excluded=[])
        assert components == []

    def test_release_fields_correct(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, 'c.properties', SAMPLE_PROPERTIES)
        parser = ManifestParser(target_platform='2.0')
        components, _ = parser.parse(list(tmp_path.glob('*.properties')), excluded=[])
        release = components[0].releases[0]
        assert release.version == '1.2.3'
        assert release.channel == 'stable'
        assert len(release.profile_builds) == 2
