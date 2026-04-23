"""
Тесты доменных моделей: Component, Release, ParsedResult.
"""

import json

import pytest

from autodoc.models.component import (
    ConanInputOptions,
    ConanVariant,
    Component,
    DefaultOptionsSet,
    TotalOptionsSet,
    ProfileBuild,
    ProfileDefinition,
    Release,
)
from autodoc.models.parsed_result import ParsedResult


class TestComponentCreation:
    """Тесты создания Component с вложенными объектами."""

    def test_minimal_component(self) -> None:
        comp = Component(name="crypto_lib")
        assert comp.name == "crypto_lib"
        assert comp.releases == []

    def test_component_with_full_release(self) -> None:

        variant = ConanVariant(
            package_id="abc123",
            build_url="https://art.example.com/pkg",
            build_date="2026-01-15",
            options_ref="1",
        )

        profile = ProfileBuild(
            profile_name="linux_x86_64",
            exists=True,
            variants=[variant],
        )
        release = Release(
            version="1.2.3",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com/repo",
            conan_reference="crypto_lib/1.2.3@platform/stable",
            profile_builds=[profile],
        )
        comp = Component(
            name="crypto_lib",
            description="Криптографическая библиотека",
            git_project="DEP_Components",
            git_repo="crypto_lib",
            releases=[release],
        )

        assert len(comp.releases) == 1
        assert comp.releases[0].version == "1.2.3"
        pb = comp.releases[0].profile_builds[0]
        assert pb.profile_name == "linux_x86_64"
        assert pb.exists is True  # 1.2
        assert pb.variants[0].package_id == "abc123"

    def test_release_has_no_git_repo_field(self) -> None:
        """1.3 Release не должен иметь git_repo/git_project."""
        release = Release(
            version="1.0.0",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com/repo",
        )
        assert not hasattr(release, "git_repo")
        assert not hasattr(release, "git_project")

    def test_conan_variant_has_no_option_set_fields(self) -> None:
        """1.1 ConanVariant не должен иметь option_set_id/option_set_str."""
        variant = ConanVariant(package_id="abc", build_url="", build_date="")
        assert not hasattr(variant, "option_set_id")
        assert not hasattr(variant, "option_set_str")

    def test_option_definition_type_literal(self) -> None:
        """1.6 OptionType ограничивает допустимые значения type."""
        opt = DefaultOptionsSet(name="shared", type="bool", default_value=False)
        assert opt.type == "bool"

    def test_component_extra_fields_ignored(self) -> None:
        """1.7 extra='allow' убран — лишние поля игнорируются (Pydantic v2 default)."""
        comp = Component(name="lib", unknown_field="value")
        assert not hasattr(comp, "unknown_field")


class TestPrivateAttribute:
    """Тест: _build_option_sets_internal не попадает в сериализацию."""

    def test_internal_options_excluded_from_dump(self) -> None:
        """_build_option_sets_internal не должен присутствовать в model_dump()."""
        release = Release(
            version="1.0.0",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com/repo",
        )
        release._build_option_sets_internal = {"opt1": "val1"}

        dumped = release.model_dump()
        assert "_build_option_sets_internal" not in dumped
        assert "build_option_sets_internal" not in dumped

    def test_internal_options_accessible_via_attribute(self) -> None:
        release = Release(
            version="1.0.0",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com/repo",
        )
        release._build_option_sets_internal = {"key": "value"}
        assert release._build_option_sets_internal == {"key": "value"}


class TestReleaseFieldNames:
    """1.4, 1.5 Проверка переименованных полей Release."""

    def test_build_option_sets_field_exists(self) -> None:
        """1.4 conan_options → build_option_sets."""
        release = Release(
            version="1.0.0",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com",
            build_option_sets=[ConanInputOptions(id="1", options="shared=True")],
        )
        assert release.build_option_sets == [
            ConanInputOptions(id="1", options="shared=True")
        ]

    def test_is_header_only_field_exists(self) -> None:
        """1.5 is_header_only_component → is_header_only."""
        release = Release(
            version="1.0.0",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com",
            is_header_only=True,
        )
        assert release.is_header_only is True


class TestParsedResult:
    """Тесты сериализации / десериализации ParsedResult."""

    def _make_result(self) -> ParsedResult:
        release = Release(
            version="2.0.0",
            platform="develop",
            channel="stable",
            git_url="https://tfs.example.com/repo",
        )
        comp = Component(name="my_lib", releases=[release])
        return ParsedResult(
            generated_at="2026-03-19T10:00:00",
            platform_version="2.0",
            components=[comp],
        )

    def test_serializes_to_json(self) -> None:
        result = self._make_result()
        data = json.loads(result.model_dump_json())
        assert data["platform_version"] == "2.0"
        assert len(data["components"]) == 1

    def test_roundtrip_json(self) -> None:
        result = self._make_result()
        restored = ParsedResult.model_validate_json(result.model_dump_json())
        assert restored.components[0].releases[0].version == "2.0.0"


class TestProfileDefinitionAndOptionSet:
    def test_profile_definition_creation(self) -> None:
        pd = ProfileDefinition(
            profile_name="linux_x86_64",
            conan_settings={"os": "Linux", "arch": "x86_64"},
            docker_image="registry.example.com/builder:latest",
        )
        assert pd.profile_name == "linux_x86_64"
        assert pd.conan_settings["os"] == "Linux"

    def test_option_set_creation(self) -> None:
        os_ = TotalOptionsSet(id="1", options={"shared": "True"})
        assert os_.id == "1"
        assert os_.options["shared"] == "True"

    def test_release_has_option_sets_field(self) -> None:
        release = Release(
            version="1.0.0",
            platform="develop",
            channel="stable",
            git_url="https://example.com",
            total_option_sets=[TotalOptionsSet(id="1", options={"shared": "True"})],
        )
        assert len(release.total_option_sets) == 1
        assert release.total_option_sets[0].id == "1"

    def test_parsed_result_has_profile_definitions(self) -> None:
        result = ParsedResult(
            generated_at="2026-01-01T00:00:00",
            platform_version="2.0",
            profile_definitions=[ProfileDefinition(profile_name="linux_x86_64")],
            components=[],
        )
        assert len(result.profile_definitions) == 1


class TestFinalizeStepHeaderOnly:
    """Tests for the updated _compute_header_only_flags logic."""

    def _make_profile_def(
        self, name: str, settings: dict | None = None
    ) -> ProfileDefinition:
        return ProfileDefinition(profile_name=name, conan_settings=settings or {})

    def test_header_only_when_no_settings_and_empty_options(self) -> None:
        from autodoc.models.component import (
            TotalOptionsSet,
            ConanVariant,
            ProfileBuild,
            Release,
            Component,
        )
        from autodoc.parser.steps.finalize_step import FinalizeStep

        variant = ConanVariant(package_id="p1", options_ref="1")
        pb = ProfileBuild(profile_name="linux_x86_64", exists=True, variants=[variant])
        release = Release(
            version="1.0.0",
            platform="dev",
            channel="stable",
            git_url="https://example.com",
            total_option_sets=[TotalOptionsSet(id="1", options={})],  # empty options
            profile_builds=[pb],
        )
        comp = Component(name="hdr_lib", releases=[release])
        pd = self._make_profile_def("linux_x86_64", settings={})  # empty settings

        FinalizeStep._compute_header_only_flags([comp], [pd])
        assert release.is_header_only is True

    def test_not_header_only_when_settings_present(self) -> None:
        from autodoc.models.component import (
            TotalOptionsSet,
            ConanVariant,
            ProfileBuild,
            Release,
            Component,
        )
        from autodoc.parser.steps.finalize_step import FinalizeStep

        variant = ConanVariant(package_id="p1", options_ref="1")
        pb = ProfileBuild(profile_name="linux_x86_64", exists=True, variants=[variant])
        release = Release(
            version="1.0.0",
            platform="dev",
            channel="stable",
            git_url="https://example.com",
            total_option_sets=[TotalOptionsSet(id="1", options={})],
            profile_builds=[pb],
        )
        comp = Component(name="bin_lib", releases=[release])
        pd = self._make_profile_def(
            "linux_x86_64", settings={"os": "Linux"}
        )  # non-empty

        FinalizeStep._compute_header_only_flags([comp], [pd])
        assert release.is_header_only is False
