"""
Специфичные для паблишера фикстуры и заглушки.
"""

import random
from datetime import datetime, timedelta
from typing import Any

import pytest

from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.options import ConanInputOptions, TotalOptionsSet
from autodoc.models.parsed_result import ParsedResult, ProfileDefinition
from autodoc.models.release import Release
from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.clients.models.page_result import PageResult


def _random_generated_at() -> str:
    """Возвращает случайную дату/время в ISO 8601 (без привязки к конкретному дню)."""
    start = datetime(2020, 1, 1)
    random_offset = timedelta(seconds=random.randint(0, int(timedelta(days=365 * 5).total_seconds())))
    return (start + random_offset).isoformat()


class FakeConfluenceClient:
    """
    Тестовая заглушка ConfluenceClient с предсказуемым поведением.

    Вызовы publish_page, resolve_existing_page_id, create_page и get_page_body
    фиксируются в self.calls для последующей проверки (find_page и get_page —
    нет). Возвращаемые значения publish_page/create_page — экземпляры PageResult
    (соответствуют контракту настоящего ConfluenceClient), настраиваются
    через self.publish_responses / self.create_responses.
    find_page/resolve_existing_page_id работают через self._pages
    (title -> ConfluencePage), заполняемый через register_page().
    По умолчанию возвращает page_id='page-001', version=1, status='updated'.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.publish_responses: list[PageResult] = []
        self.create_responses: list[PageResult] = []
        self._page_bodies: dict[str, str] = {}
        self._pages: dict[str, ConfluencePage] = {}

    def register_page(
        self,
        title: str,
        page_id: str,
        version: int = 1,
        ancestor_ids: tuple[str, ...] = (),
        body_html: str = "",
    ) -> None:
        """Регистрирует заранее существующую страницу, чтобы её находили find_page/resolve_existing_page_id."""
        self._pages[title] = ConfluencePage(
            id=page_id,
            title=title,
            version=version,
            ancestor_ids=ancestor_ids,
            body_html=body_html,
        )

    def _default_publish_response(self, title: str, status: str = "updated") -> PageResult:
        return PageResult(id="page-001", version=1, status=status, message="")

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> PageResult:
        """Записывает вызов; возвращает следующий ответ из publish_responses или значение по умолчанию."""
        self.calls.append(
            {
                "method": "publish_page",
                "space": space,
                "parent_id": parent_id,
                "title": title,
                "body_html": body_html,
            }
        )
        if self.publish_responses:
            return self.publish_responses.pop(0)
        return self._default_publish_response(title)

    def resolve_existing_page_id(
        self,
        space: str,
        parent_id: str,
        title: str,
    ) -> str | None:
        """Возвращает ID заранее зарегистрированной (через register_page) страницы или None."""
        self.calls.append(
            {
                "method": "resolve_existing_page_id",
                "space": space,
                "parent_id": parent_id,
                "title": title,
            }
        )
        page = self._pages.get(title)
        return page.id if page else None

    def create_page(
        self,
        space: str,
        parent_id: str | None,
        title: str,
        body_html: str,
    ) -> PageResult:
        """Записывает вызов; возвращает следующий ответ из create_responses или значение по умолчанию."""
        self.calls.append(
            {
                "method": "create_page",
                "space": space,
                "parent_id": parent_id,
                "title": title,
                "body_html": body_html,
            }
        )
        if self.create_responses:
            return self.create_responses.pop(0)
        return self._default_publish_response(title, status="created")

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str = "",
    ) -> ConfluencePage | None:
        """Возвращает заранее зарегистрированную ConfluencePage для этого заголовка или None."""
        return self._pages.get(title)

    def get_page(self, page_id: str, expand: str = "") -> ConfluencePage:
        """Возвращает заглушку ConfluencePage по ID."""
        return ConfluencePage(id=page_id, title="stub", version=1)

    def get_page_body(self, space: str, title: str, parent_id: str | None = None) -> str:
        """Возвращает тело страницы из _page_bodies или пустую строку."""
        self.calls.append(
            {"method": "get_page_body", "space": space, "title": title, "parent_id": parent_id}
        )
        return self._page_bodies.get(title, "")


@pytest.fixture
def minimal_confluence_config(valid_confluence_config: dict) -> dict:
    """Минимальный валидный словарь, совместимый со схемой ConfluenceConfigSchema."""
    return valid_confluence_config


@pytest.fixture
def publisher_confluence_client() -> FakeConfluenceClient:
    """Свежий FakeConfluenceClient для каждого теста."""
    return FakeConfluenceClient()


@pytest.fixture
def publisher_profile_build() -> ProfileBuild:
    """ProfileBuild для профиля 'hw-linux-x86_64-gcc10' с одним вариантом."""
    variant = ConanVariant(
        package_id="abc123",
        build_url="https://ci.example.com/build/42",
        build_date="2024-01-15",
        options_ref="opt-set-1",
    )
    return ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10",
        exists=True,
        variants=[variant],
    )


@pytest.fixture
def publisher_release(publisher_profile_build: ProfileBuild) -> Release:
    """Release '1.0.0' для платформы 2.0 с одним ProfileBuild."""
    total_opts = TotalOptionsSet(id="opt-set-1", options={"shared": "True", "fPIC": "True"})
    build_opts = ConanInputOptions(
        id="opt-set-1",
        options="openssl/*:shared=True, openssl/*:fPIC=True",
    )
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        conan_reference="openssl/1.0.0@platform/2.0-tech",
        artifactory_url="https://art.example.com/conan/openssl/1.0.0",
        profile_builds=[publisher_profile_build],
        total_option_sets=[total_opts],
        build_option_sets=[build_opts],
    )


@pytest.fixture
def publisher_component(publisher_release: Release) -> Component:
    """Component 'openssl' с одним Release."""
    return Component(
        name="openssl",
        description="OpenSSL TLS/SSL library",
        git_project="DEP_Components",
        git_repo="contrib_openssl",
        git_url="https://tfs.example.com/DEP_Components/_git/contrib_openssl",
        is_header_only=False,
        releases=[publisher_release],
    )


@pytest.fixture
def publisher_profile_definition() -> ProfileDefinition:
    """ProfileDefinition для профиля 'hw-linux-x86_64-gcc10'."""
    return ProfileDefinition(
        profile_name="hw-linux-x86_64-gcc10",
        conan_settings={
            "os": "Linux",
            "arch": "x86_64",
            "compiler": "gcc",
            "compiler.version": "10",
        },
        docker_image="registry.example.com/build/linux-gcc10:latest",
    )


@pytest.fixture
def publisher_parsed_result(
    publisher_component: Component,
    publisher_profile_definition: ProfileDefinition,
) -> ParsedResult:
    """Минимальный ParsedResult с одним компонентом и одним профилем."""
    return ParsedResult(
        generated_at=_random_generated_at(),
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[publisher_component],
    )


@pytest.fixture
def publisher_multi_channel_result(
    publisher_profile_definition: ProfileDefinition,
) -> ParsedResult:
    """
    ParsedResult с двумя компонентами и двумя каналами для тестов ProfileCentricConverter.

    - comp_alpha (is_header_only=False): релизы в каналах 'fast' и 'stable'
    - comp_beta  (is_header_only=True):  один релиз в канале 'fast'
    """
    total_opts = TotalOptionsSet(id="opt-1", options={"shared": "False"})
    variant = ConanVariant(
        package_id="pkx",
        build_url="https://ci/x",
        build_date="2024-01-01",
        options_ref="opt-1",
    )
    pb = ProfileBuild(
        profile_name="hw-linux-x86_64-gcc10",
        exists=True,
        variants=[variant],
    )
    rel_fast = Release(
        version="2.0.0",
        platform="2.0",
        channel="fast",
        conan_reference="alpha/2.0.0@platform/2.0-fast",
        artifactory_url="https://art/alpha",
        profile_builds=[pb],
        total_option_sets=[total_opts],
    )
    rel_stable = Release(
        version="2.0.0",
        platform="2.0",
        channel="stable",
        conan_reference="alpha/2.0.0@platform/2.0-stable",
        artifactory_url="https://art/alpha-stable",
        profile_builds=[
            ProfileBuild(
                profile_name="hw-linux-x86_64-gcc10",
                exists=True,
                variants=[
                    ConanVariant(
                        package_id="pky",
                        build_url="https://ci/y",
                        build_date="2024-01-02",
                        options_ref="opt-1",
                    )
                ],
            )
        ],
        total_option_sets=[total_opts],
    )
    comp_alpha = Component(
        name="alpha",
        description="Alpha lib",
        git_project="DEP",
        git_repo="alpha",
        git_url="https://tfs.example.com/DEP/_git/alpha",
        is_header_only=False,
        releases=[rel_fast, rel_stable],
    )
    comp_beta = Component(
        name="beta",
        description="Beta lib — header-only",
        git_project="DEP",
        git_repo="beta",
        git_url="https://tfs.example.com/DEP/_git/beta",
        is_header_only=True,
        releases=[
            Release(
                version="1.0.0",
                platform="2.0",
                channel="fast",
                conan_reference="beta/1.0.0@platform/2.0-fast",
                artifactory_url="https://art/beta",
                profile_builds=[],
                total_option_sets=[],
            )
        ],
    )
    return ParsedResult(
        generated_at=_random_generated_at(),
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[comp_alpha, comp_beta],
    )


@pytest.fixture
def publisher_multi_component_result(
    publisher_profile_definition: ProfileDefinition,
) -> ParsedResult:
    """ParsedResult с двумя компонентами и несколькими релизами — для стратегий."""
    total_opts = TotalOptionsSet(id="opt-1", options={"shared": "True"})
    rel1 = Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        conan_reference="openssl/1.0.0@platform/2.0-tech",
        artifactory_url="https://art.example.com/openssl",
        profile_builds=[
            ProfileBuild(
                profile_name="hw-linux-x86_64-gcc10",
                exists=True,
                variants=[
                    ConanVariant(
                        package_id="p1",
                        build_url="https://ci/1",
                        build_date="2024-01-01",
                        options_ref="opt-1",
                    )
                ],
            )
        ],
        total_option_sets=[total_opts],
    )
    rel2 = Release(
        version="2.0.0",
        platform="2.0",
        channel="stable",
        conan_reference="openssl/2.0.0@platform/2.0-stable",
        artifactory_url="https://art.example.com/openssl2",
        profile_builds=[],
        total_option_sets=[],
    )
    comp1 = Component(
        name="openssl",
        description="TLS library",
        git_project="DEP",
        git_repo="contrib_openssl",
        git_url="https://tfs.example.com/repo1",
        is_header_only=False,
        releases=[rel1, rel2],
    )
    comp2 = Component(
        name="zlib",
        description="Compression library",
        git_project="DEP",
        git_repo="contrib_zlib",
        git_url="https://tfs.example.com/repo2",
        is_header_only=False,
        releases=[
            Release(
                version="1.2.11",
                platform="2.0",
                channel="tech",
                conan_reference="zlib/1.2.11@platform/2.0-tech",
                artifactory_url="https://art.example.com/zlib",
                profile_builds=[
                    ProfileBuild(
                        profile_name="hw-linux-x86_64-gcc10",
                        exists=True,
                        variants=[],
                    )
                ],
                total_option_sets=[],
            )
        ],
    )
    return ParsedResult(
        generated_at=_random_generated_at(),
        platform_version="2.0",
        profile_definitions=[publisher_profile_definition],
        components=[comp1, comp2],
    )
