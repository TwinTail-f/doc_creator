"""Тесты ConanResultParser."""

from unittest.mock import MagicMock

import pytest

from autodoc.models.component import ProfileBuild, Release
from autodoc.parser.conan.result_parser import ConanEnrichData, ConanResultParser
from autodoc.parser.conan.task_builder import ConanTask


def _make_task(comp_name="my_lib", version="1.0.0", channel="stable") -> ConanTask:
    release = Release(
        version=version,
        platform="2.0",
        channel=channel,
        git_url="https://tfs.example.com",
    )
    pb = ProfileBuild(profile_name="linux_x86_64")
    return ConanTask(
        cmd=["conan", "graph", "info"],
        comp_name=comp_name,
        version=version,
        channel=channel,
        profile_name="linux_x86_64",
        option_id="1",
        option_str="shared=True",
        target_platform="2.0",
        artifactory_base_url="https://art.example.com",
        release=release,
        pb=pb,
    )


def _make_conan_graph(
    comp_name="my_lib",
    version="1.0.0",
    channel="stable",
    package_id="abc123",
    include_patches=False,
    include_deps=False,
):
    ref = "%s/%s@platform-2.0/%s#rev001" % (comp_name, version, channel)
    node = {
        "name": comp_name,
        "ref": ref,
        "rrev": "rev001",
        "package_id": package_id,
        "default_options": {"shared": "False"},
        "options_definitions": {"shared": ["True", "False"]},
        "info": {
            "settings": {"os": "Linux", "arch": "x86_64"},
            "options": {"shared": "True"},
        },
        "prev_timestamp": None,
    }
    if include_patches:
        node["conandata"] = {
            "patches": {"1.0": [{"patch_file": "patches/fix_build.patch"}]}
        }
    if include_deps:
        node["dependencies"] = {
            "1": {"ref": "zlib/1.2.13@platform-2.0/stable"},
            "2": {"ref": "openssl/3.0.0@platform-2.0/stable"},
        }
    return {"graph": {"nodes": {"0": node}}}


class TestConanResultParser:
    def setup_method(self):
        self.parser = ConanResultParser()

    def test_valid_json_returns_enrich_data(self) -> None:
        result = self.parser.parse(_make_conan_graph(), _make_task())
        assert result is not None
        assert isinstance(result, ConanEnrichData)

    def test_missing_target_node_returns_none(self) -> None:
        result = self.parser.parse(
            _make_conan_graph(comp_name="other_lib"), _make_task()
        )
        assert result is None

    def test_empty_graph_returns_none(self) -> None:
        result = self.parser.parse({"graph": {"nodes": {}}}, _make_task())
        assert result is None

    def test_ref_fields_extracted(self) -> None:
        result = self.parser.parse(_make_conan_graph(), _make_task())
        assert result.base_ref == "my_lib/1.0.0@platform-2.0/stable"
        assert result.rrev == "rev001"

    def test_patches_extracted(self) -> None:
        result = self.parser.parse(
            _make_conan_graph(include_patches=True), _make_task()
        )
        assert "fix_build.patch" in result.patches

    def test_dependencies_extracted(self) -> None:
        result = self.parser.parse(_make_conan_graph(include_deps=True), _make_task())
        assert "zlib" in result.dependencies
        assert "my_lib" not in result.dependencies

    def test_conan_settings_extracted(self) -> None:
        result = self.parser.parse(_make_conan_graph(), _make_task())
        assert result.conan_settings.get("os") == "Linux"

    def test_enrich_data_has_no_option_set_fields(self) -> None:
        """3.3 ConanEnrichData больше не содержит option_set_id/str — удалены как артефакты пайплайна."""
        result = self.parser.parse(_make_conan_graph(), _make_task())
        assert result is not None
        assert not hasattr(result, "option_set_id")
        assert not hasattr(result, "option_set_str")

    def test_default_options_type_detection(self) -> None:
        result = self.parser.parse(_make_conan_graph(), _make_task())
        shared_opt = next(
            (o for o in result.default_options if o.name == "shared"), None
        )
        assert shared_opt is not None
        assert shared_opt.type == "bool"
