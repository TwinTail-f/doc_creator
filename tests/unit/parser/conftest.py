"""
Общие тестовые фикстуры и заглушки для autodoc/tests/unit/parser/.

FakeTFSClient — заглушка-пустышка для реального TFSClient. Отдельные тестовые
модули наследуются от него и переопределяют только нужные методы, делая
тестовую поверхность минимальной и явной.
"""

from pathlib import Path
import shutil

import pytest
import requests

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.conan_variant import ConanVariant, ProfileBuild
from autodoc.models.release import Release


# Фикстуры конфигурации / путей
@pytest.fixture
def parser_config(valid_parser_config: dict) -> ParserConfigSchema:
    """Минимальная корректная ParserConfigSchema для юнит-тестов (без реальных сетевых вызовов)."""
    return ParserConfigSchema(**valid_parser_config)


@pytest.fixture
def resources_dir() -> Path:
    """Путь к общим тестовым ресурсам в tests/unit/parser/resources/."""
    return Path(__file__).parent / "resources"


@pytest.fixture
def real_manifests_dir(resources_dir: Path) -> Path:
    """Path to real .properties files under tests/unit/parser/resources/manifests/."""
    return resources_dir / "manifests"


# Фикстуры Component / Release (общие для steps/, enrichment/, test_pipeline.py)
@pytest.fixture
def manifest_release() -> Release:
    """Release для openssl 1.0.0 на платформе 2.0 / канал 'tech'."""
    pb = ProfileBuild(profile_name="hw-linux-x86_64-gcc10_2")
    return Release(
        version="1.0.0",
        platform="2.0",
        channel="tech",
        profile_builds=[pb],
    )


@pytest.fixture
def manifest_component(manifest_release: Release) -> Component:
    """Component с именем 'openssl', оборачивающий manifest_release."""
    return Component(name="openssl", releases=[manifest_release])


class FakeTFSClient:
    """
    Заглушка-пустышка для TFSClient.

    Каждый метод возвращает безопасное пустое значение по умолчанию, чтобы
    подклассам нужно было переопределять только один-два метода, нужных для теста.

    Сигнатуры методов зеркалируют реальный TFSClient, поэтому код с проверкой
    типов может использовать FakeTFSClient как замену в тестах.

    Ответ ``get_file_content`` настраивается через конструктор (``content``,
    ``status_code``, ``exception``), а список ``get_items`` — через ``items``:
    для простых сценариев не нужно писать отдельный подкласс, достаточно
    ``FakeTFSClient(content=..., status_code=...)``,
    ``FakeTFSClient(exception=...)`` для имитации сетевого сбоя или
    ``FakeTFSClient(items=[...])`` для настройки списка элементов.
    Значения хранятся как атрибуты класса, поэтому подклассы с собственным
    ``__init__`` (не вызывающим ``super().__init__()``) по-прежнему получают
    безопасные значения по умолчанию.
    """

    _content: bytes = b""
    _status_code: int = 200
    _exception: Exception | None = None
    _items: list = []

    def __init__(
        self,
        content: bytes = b"",
        status_code: int = 200,
        exception: Exception | None = None,
        items: list | None = None,
    ) -> None:
        """
        Args:
            content: Байты, возвращаемые как тело ответа get_file_content.
            status_code: HTTP-код статуса ответа get_file_content.
            exception: Если задано, get_file_content поднимает это исключение
                вместо возврата ответа (имитация сетевого сбоя).
            items: Список item-словарей, возвращаемых get_items. По умолчанию
                пустой список.
        """
        self._content = content
        self._status_code = status_code
        self._exception = exception
        self._items = items if items is not None else []

    def get_file_content(
        self,
        items_url: str,
        path: str,
        branch: str,
        version_type=None,
    ) -> requests.Response:
        """Возвращает ответ с настроенными в конструкторе content/status_code (по умолчанию — пустой 200)
        либо поднимает настроенное в конструкторе исключение.

        Собирается как настоящий ``requests.Response`` (а не MagicMock), чтобы
        ``raise_for_status()`` реально поднимал ``HTTPError`` при status_code >= 400 —
        как это делает реальный TFSClient.
        """
        if self._exception is not None:
            raise self._exception
        resp = requests.Response()
        resp.status_code = self._status_code
        resp._content = self._content
        return resp

    def get_items(
        self,
        items_url: str,
        branch: str,
        recursion=None,
        version_type=None,
    ) -> list:
        """Возвращает список элементов, настроенный в конструкторе (по умолчанию — пустой)."""
        return self._items

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Ничего не делает по умолчанию (файлы не записываются)."""


#: SHA-1 пустой строки — сигнальный package_id Conan для header-only пакетов.
NULL_PACKAGE_ID: str = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def make_component(
    name: str = "mylib",
    version: str = "1.0",
    channel: str = "fast",
    profiles: list[str] | None = None,
    git_url: str = "",
    is_header_only: bool = False,
) -> Component:
    """Фабрика Component, создающая один Release с запрошенными профилями.

    Отражает перенос полей ``git_url`` и ``is_header_only`` из ``Release``
    в ``Component``, произведённый в рамках рефакторинга DE/FS.

    Args:
        name: Имя компонента, используется и как имя пакета Conan, и как
            поле ``Component.name``.
        version: Строка версии релиза (например, ``"1.0"``).
        channel: Имя канала Conan (например, ``"fast"``).
        profiles: Список имён профилей, привязываемых к релизу. По умолчанию
            ``["hw-linux-x86_64"]``.
        git_url: URL git-репозитория — теперь хранится на ``Component``, а не на ``Release``.
        is_header_only: Флаг header-only — теперь хранится на ``Component``.

    Returns:
        Полностью собранный ``Component`` с одним ``Release`` и одним
        ``ProfileBuild`` на каждый элемент ``profiles``.
    """
    profile_names = profiles or ["hw-linux-x86_64"]
    pbs = [ProfileBuild(profile_name=p) for p in profile_names]
    release = Release(
        version=version,
        platform="2.2",
        channel=channel,
        conan_reference="",
        artifactory_url="",
        profile_builds=pbs,
    )
    return Component(
        name=name,
        description="",
        git_project="Proj",
        git_repo="repo",
        git_url=git_url,
        is_header_only=is_header_only,
        releases=[release],
    )


def make_conan_variant(
    package_id: str = "abc123",
    options_ref: str = "1",
) -> ConanVariant:
    """Минимальная фабрика ``ConanVariant`` с разумными значениями по умолчанию.

    Args:
        package_id: Хеш пакета Conan (используйте ``NULL_PACKAGE_ID`` для
            сценариев header-only).
        options_ref: Строка-идентификатор, ссылающаяся на ``TotalOptionsSet``.

    Returns:
        Экземпляр ``ConanVariant``, готовый к использованию в тестах обогащения.
    """
    return ConanVariant(
        package_id=package_id,
        build_url="http://art/pkg",
        build_date="2024-01-01",
        options_ref=options_ref,
    )


class CopyingAllFakeTFSClient(FakeTFSClient):
    """Копирует все .properties-файлы из исходной директории в output_dir при вызове download_properties."""

    def __init__(self, source_dir: Path) -> None:
        """
        Args:
            source_dir: Директория с .properties-файлами для копирования.
        """
        self._source_dir = source_dir

    def download_properties(
        self,
        items_url: str,
        remote_path: str,
        branch: str,
        output_dir: str,
        version_type=None,
    ) -> None:
        """Копирует все .properties-файлы из source_dir в output_dir."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for f in self._source_dir.glob("*.properties"):
            shutil.copy(f, out / f.name)
