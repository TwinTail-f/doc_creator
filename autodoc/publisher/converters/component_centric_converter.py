"""Конвертер для полного вида документации релиза, сгруппированного по компонентам."""

from typing import Any

from autodoc.common.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.base_data_converter import _VariantOpts
from autodoc.publisher.converters.base_release_converter import BaseReleaseConverter


class ComponentCentricConverter(BaseReleaseConverter):
    """
    Конвертер для полного вида документации релиза: иерархия
    ``Компонент → Релиз → Профиль сборки → Вариант``.

    Название и структура — прямая пара к ``ProfileCentricConverter``, который
    строит ту же исходную выборку данных релиза в другой иерархии
    (``Профиль → Канал → Компонент``). Обе формы существуют ровно потому, что
    одни и те же данные релиза читают по-разному: «что входит в этот
    компонент» (эта форма) и «что входит в этот профиль сборки»
    (``ProfileCentricConverter``). Включает все компоненты со всеми
    профилями, вариантами и зависимостями. Опционально добавляет ссылки на
    паспорта компонентов через ``enrich_with_passport_links()``.
    """

    def _build_profile_build_entry(
        self,
        pb: Any,
        pd_map: dict[str, Any],
        os_map: dict[str, dict],
        comp_name: str,
    ) -> dict[str, Any]:
        """
        Строит одну запись ``profile_builds`` для view-model релиза.

        Args:
            pb: Объект ``ProfileBuild``.
            pd_map: Словарь ``{profile_name: ProfileDefinition}``.
            os_map: Словарь ``{options_ref_id: options_dict}``.
            comp_name: Имя компонента-владельца.

        Returns:
            Словарь с полями ``profile_name``, ``conan_settings``, ``docker_image``,
            ``exists``, ``variants``.
        """
        conan_settings, docker_image = self._resolve_profile_meta(pd_map, pb.profile_name)
        return {
            "profile_name": pb.profile_name,
            "conan_settings": conan_settings,
            "docker_image": docker_image,
            "exists": pb.exists,
            "variants": [
                self._build_variant_view(
                    v, comp_name, _VariantOpts(conan_options=os_map.get(v.options_ref, {}))
                )
                for v in pb.variants
            ],
        }

    def _build_release_view(
        self,
        rel: Any,
        comp_name: str,
        pd_map: dict[str, Any],
        comp_is_header_only: bool = False,
    ) -> dict[str, Any]:
        """
        Формирует view-model одного релиза, включая варианты сборки.

        Args:
            rel: Объект Release.
            comp_name: Имя компонента-владельца (для квалификации опций).
            pd_map: Словарь ``{profile_name: ProfileDefinition}``.
            comp_is_header_only: Флаг header-only с уровня компонента.

        Returns:
            Словарь с полными данными релиза для шаблона.
        """
        os_map: dict[str, dict] = {os_.id: os_.options for os_ in rel.total_option_sets}
        profile_builds: list[dict] = (
            []
            if comp_is_header_only
            else [
                self._build_profile_build_entry(pb, pd_map, os_map, comp_name)
                for pb in rel.profile_builds
            ]
        )
        return {
            "version": rel.version,
            "channel": rel.channel,
            "conan_reference": rel.conan_reference,
            "artifactory_url": rel.artifactory_url,
            "is_header_only": comp_is_header_only,
            "profile_builds": profile_builds,
        }

    def convert(self, data: ParsedResult) -> dict[str, Any]:
        """
        Возвращает полный вид с вариантами и всеми деталями.

        Args:
            data: Данные парсера.

        Returns:
            Словарь view-model для шаблона полного релиза.
        """
        logger.debug("Конвертация в полный вид")
        pd_map: dict[str, Any] = self._build_profile_definition_map(data)
        components_sorted = sorted(data.components, key=lambda comp: comp.name)
        return {
            **self._base_view_model(data),
            "components": [
                {
                    "name": comp.name,
                    "description": comp.description,
                    "releases": [
                        self._build_release_view(rel, comp.name, pd_map, comp.is_header_only)
                        for rel in comp.releases
                    ],
                }
                for comp in components_sorted
            ],
        }

    def enrich_with_passport_links(
        self,
        view_model: dict[str, Any],
        passport_pages: dict[str, Any],
    ) -> None:
        """
        Вставляет ссылки на страницы паспортов во view-model полного вида релиза.

        Для каждого компонента добавляет ключ ``passport_versions`` с теми
        версиями, что присутствуют в реестре. Не изменяет view-model, если
        ссылки на паспорта отключены (``include_passport_links=False``),
        реестр пуст или ключ ``'components'`` отсутствует.

        Args:
            view_model: Словарь, созданный ``convert()``. Изменяется на месте.
            passport_pages: Карта, загруженная через ``PassportPageRegistry.load()``.
        """
        if not self._include_passport_links or not passport_pages or "components" not in view_model:
            return

        space = view_model.get("space", "")

        for comp in view_model.get("components", []):
            comp_name = comp.get("name")
            if comp_name not in passport_pages:
                continue
            release_versions = {rel.get("version") for rel in comp.get("releases", [])}
            comp["passport_versions"] = {
                version: {**entry, "url": self._build_passport_url(space, entry.get("page_id", ""))}
                for version in release_versions
                if (entry := self._lookup_passport_entry(passport_pages, comp_name, version))
                is not None
            }
