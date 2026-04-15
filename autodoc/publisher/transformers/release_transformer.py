"""Трансформеры для документации релизов: полный вид."""

from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import (
    BaseDataTransformer,
    PassportLinkMixin,
    _DEFAULT_PASSPORT_PATTERN,
)


class BaseReleaseTransformer(PassportLinkMixin, BaseDataTransformer):
    """
    Базовый класс трансформеров документации релиза.

    Наследует ``_passport_link()`` из ``PassportLinkMixin``.
    Конкретные виды реализуют ``transform()``.
    """

    def __init__(
        self,
        include_passport_links: bool = True,
        passport_page_pattern: str | None = None,
    ) -> None:
        """
        Args:
            include_passport_links: Добавлять ли ссылки на паспорта компонентов.
            passport_page_pattern: Шаблон URL паспорта с плейсхолдерами
                ``{component_name}`` и ``{release_version}``.
                По умолчанию используется ``_DEFAULT_PASSPORT_PATTERN``.
        """
        self._include_passport_links: bool = include_passport_links
        self._pattern: str = passport_page_pattern or _DEFAULT_PASSPORT_PATTERN


class FullReleaseTransformer(BaseReleaseTransformer):
    """
    Трансформер для полного вида документации релиза.

    Включает все компоненты со всеми профилями, вариантами и зависимостями.
    Опционально добавляет ссылки на паспорта компонентов.
    """

    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Возвращает полный вид с вариантами и всеми деталями.

        Args:
            data: Данные парсера.

        Returns:
            Словарь view-model для шаблона полного релиза.
        """
        logger.debug("Трансформация в полный вид")
        return {
            "platform_version": data.platform_version,
            "include_passport_links": self._include_passport_links,
            "components": [
                {
                    "name": comp.name,
                    "description": comp.description,
                    "releases": [
                        {
                            "version": rel.version,
                            "channel": rel.channel,
                            "conan_reference": rel.conan_reference,
                            "artifactory_url": rel.artifactory_url,
                            "is_header_only": rel.is_header_only,
                            "profile_builds": [
                                {
                                    "profile_name": pb.profile_name,
                                    "conan_settings": pb.conan_settings,
                                    "docker_image": pb.docker_image,
                                }
                                for pb in rel.profile_builds
                            ],
                        }
                        for rel in comp.releases
                    ],
                }
                for comp in data.components
            ],
        }
