"""Трансформеры для документации релизов: полный вид."""

from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import (
    BaseDataTransformer,
    PassportLinkMixin,
    _DEFAULT_PASSPORT_PATTERN,
    _VariantOpts,
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
        self._pattern: str | None = passport_page_pattern or _DEFAULT_PASSPORT_PATTERN


class FullReleaseTransformer(BaseReleaseTransformer):
    """
    Трансформер для полного вида документации релиза.

    Включает все компоненты со всеми профилями, вариантами и зависимостями.
    Опционально добавляет ссылки на паспорта компонентов.
    """

    def _build_release_view(
        self,
        rel: Any,
        comp_name: str,
        pd_map: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Формирует view-model одного релиза, включая варианты сборки.

        Args:
            rel: Объект Release.
            comp_name: Имя компонента-владельца (для квалификации опций).
            pd_map: Словарь ``{profile_name: ProfileDefinition}``.

        Returns:
            Словарь с полными данными релиза для шаблона.
        """
        os_map: dict[str, dict] = {os_.id: os_.options for os_ in rel.total_option_sets}
        return {
            "version": rel.version,
            "channel": rel.channel,
            "conan_reference": rel.conan_reference,
            "artifactory_url": rel.artifactory_url,
            "is_header_only": rel.is_header_only,
            "profile_builds": [
                {
                    "profile_name": pb.profile_name,
                    "conan_settings": (
                        dict(pd_map[pb.profile_name].conan_settings)
                        if pb.profile_name in pd_map
                        else {}
                    ),
                    "docker_image": (
                        pd_map[pb.profile_name].docker_image
                        if pb.profile_name in pd_map
                        else ""
                    ),
                    "exists": pb.exists,
                    "variants": [
                        self._build_variant_view(
                            v,
                            comp_name,
                            _VariantOpts(conan_options=os_map.get(v.options_ref, {})),
                        )
                        for v in pb.variants
                    ],
                }
                for pb in rel.profile_builds
            ],
        }

    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Возвращает полный вид с вариантами и всеми деталями.

        Args:
            data: Данные парсера.

        Returns:
            Словарь view-model для шаблона полного релиза.
        """
        logger.debug("Трансформация в полный вид")
        pd_map: dict[str, Any] = {
            pd.profile_name: pd for pd in data.profile_definitions
        }
        return {
            "platform_version": data.platform_version,
            "include_passport_links": self._include_passport_links,
            "components": [
                {
                    "name": comp.name,
                    "description": comp.description,
                    "releases": [
                        self._build_release_view(rel, comp.name, pd_map)
                        for rel in comp.releases
                    ],
                }
                for comp in data.components
            ],
        }
