"""
Фикстуры и константы, используемые только тестами tests/unit/publisher/converters/*.

Перенесены сюда из tests/unit/publisher/conftest.py (см. план рефакторинга,
п. 1.2): publisher_header_only_component и publisher_two_profile_parsed_result
использовались только в converters/*; CI_BUILD_URL и COMPONENT_NAME —
аналогично. publisher_conan_variant — отдельный случай (см. п. 1.4 плана):
это независимая локальная копия только для test_base_data_converter.py,
не связанная с цепочкой publisher_profile_build → publisher_release →
publisher_component из общего publisher/conftest.py.
"""

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.options import TotalOptionsSet
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.models.release import Release

CI_BUILD_URL: str = "https://ci.example.com/build/42"
COMPONENT_NAME: str = "openssl"


@pytest.fixture
def publisher_conan_variant() -> ConanVariant:
    """Один ConanVariant с заполненными полями (только для test_base_data_converter.py)."""
    return ConanVariant(
        package_id="abc123",
        build_url=CI_BUILD_URL,
        build_date="2024-01-15",
        options_ref="opt-set-1",
    )


@pytest.fixture
def publisher_header_only_component(publisher_release: Release) -> Component:
    """
    Component с is_header_only=True (поле теперь на Component, а не на Release).

    profile_builds сохраняются на вложенном release, чтобы проверить, что
    FullReleaseConverter скрывает их в view model.
    """
    return Component(
        name="eigen",
        description="Header-only linear algebra library",
        git_project="DEP_Components",
        git_repo="contrib_eigen",
        git_url="https://tfs.example.com/DEP_Components/_git/contrib_eigen",
        is_header_only=True,
        releases=[publisher_release],
    )


@pytest.fixture
def publisher_two_profile_parsed_result(
    publisher_profile_definition: ProfileDefinition,
) -> ParsedResult:
    """
    ParsedResult с одним компонентом ('mylib') и двумя сборками профилей:
    hw-linux-x86_64-gcc10 и hw-linux-arm64-gcc10.

    Используется для проверки, что profile_builds сортируются по алфавиту
    по profile_name.
    """
    pd_arm = ProfileDefinition(
        profile_name="hw-linux-arm64-gcc10",
        conan_settings={
            "os": "Linux",
            "arch": "armv8",
            "compiler": "gcc",
            "compiler.version": "10",
        },
        docker_image="registry.example.com/arm64:latest",
    )
    total_opts = TotalOptionsSet(id="opt-1", options={"shared": "True"})
    variant_x86 = ConanVariant(
        package_id="pka",
        build_url="https://ci/a",
        build_date="2024-01-01",
        options_ref="opt-1",
    )
    variant_arm = ConanVariant(
        package_id="pkb",
        build_url="https://ci/b",
        build_date="2024-01-02",
        options_ref="opt-1",
    )
    pb_x86 = ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10",
        exists=True,
        variants=[variant_x86],
    )
    pb_arm = ProfileBuild(
        profile_name="hw-linux-arm64-gcc10",
        exists=True,
        variants=[variant_arm],
    )
    rel = Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        conan_reference="mylib/1.0.0@platform/2.0-tech",
        artifactory_url="https://art/mylib",
        profile_builds=[pb_x86, pb_arm],
        total_option_sets=[total_opts],
    )
    comp = Component(
        name="mylib",
        description="My library",
        git_project="DEP",
        git_repo="mylib",
        git_url="https://tfs.example.com/DEP/_git/mylib",
        is_header_only=False,
        releases=[rel],
    )
    return ParsedResult(
        generated_at="2024-01-15T12:00:00",
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition, pd_arm],
        components=[comp],
    )
