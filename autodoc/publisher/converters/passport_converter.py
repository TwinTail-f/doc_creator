"""Конвертер для паспорта одного компонента."""

from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.converters.base_data_converter import (
    BadgeClass,
    BaseDataConverter,
    _VariantOpts,
)

_TFS_BRANCH_PREFIX: str = "GBrelease_"
"""Префикс ветки TFS для релизных бранчей по соглашению об именовании."""


class PassportConverter(BaseDataConverter):
    """
    Конвертер для подробной документации (паспорта) конкретного компонента.

    Если компонент или версия не найдены — бросает ``ValueError`` (не возвращает ``None``).

    Формат view-model совместим с ``component_passport.jinja2``:
    - Верхнеуровневые ключи — ``component`` (карточка компонента) и
      ``releases`` (список каналов текущей версии, для группировки в
      шаблоне через Jinja2 ``groupby``).
    - Все поля профилей используют новые имена: ``docker_image``, ``exists``.
    """

    def __init__(self, component_name: str, release_version: str) -> None:
        """
        Args:
            component_name: Имя компонента, для которого формируется паспорт.
            release_version: Версия релиза компонента.
        """
        self._component_name: str = component_name
        self._release_version: str = release_version

    @classmethod
    def _classify_option_badge(cls, value: Any, default_value: Any, has_default: bool) -> str:
        """
        Определяет CSS-класс бейджа опции по признаку отличия от дефолта.

        Значения сравниваются через ``str()``, чтобы ``True`` и ``"True"``
        (булево и строковое представление, оба встречаются в разборе Conan)
        считались одним и тем же значением.

        Args:
            value: Текущее значение опции варианта сборки.
            default_value: Дефолтное значение этой опции у компонента.
            has_default: Найдено ли дефолтное значение для этой опции
                         (опции зависимостей вроде ``icu:shared`` могут
                         отсутствовать в ``default_options`` компонента).

        Returns:
            ``BadgeClass.DEFAULT`` (нейтральный), если значение совпадает с
            известным дефолтом. В остальных случаях — ``BadgeClass.NEUTRAL``
            (жёлтый): значение отличается от дефолта, либо дефолт для этой
            опции неизвестен.
        """
        if has_default and str(value) == str(default_value):
            return BadgeClass.DEFAULT.value
        return BadgeClass.NEUTRAL.value

    @staticmethod
    def _find_component(data: ParsedResult, component_name: str) -> Any:
        """
        Находит компонент по имени в данных парсера.

        Args:
            data: Полный набор данных парсера.
            component_name: Имя искомого компонента.

        Returns:
            Объект компонента.

        Raises:
            ValueError: Если компонент не найден.
        """
        comp = next((c for c in data.components if c.name == component_name), None)
        if not comp:
            raise ValueError(f"PassportConverter: компонент {component_name} не найден")
        return comp

    @staticmethod
    def _find_releases(component: Any, release_version: str) -> list[Any]:
        """
        Находит все релизы по версии внутри компонента.

        Один компонент может иметь несколько релизов с одинаковой версией,
        но разными каналами (например ``fast`` и ``slow``). Метод возвращает
        их все в порядке, в котором они хранятся в ``component.releases``
        (т.е. в том же порядке, что и в ``parsed_data``).

        Args:
            component: Объект компонента с атрибутом ``releases``.
            release_version: Строковое представление версии.

        Returns:
            Список объектов релиза (не менее одного).

        Raises:
            ValueError: Если ни одного релиза с такой версией не найдено.
        """
        releases = [r for r in component.releases if str(r.version) == str(release_version)]
        if not releases:
            raise ValueError(
                f"PassportConverter: версия {release_version} " f"для {component.name} не найдена"
            )
        return releases

    def _build_enriched_profile_builds(
        self,
        target_rel: Any,
        comp_name: str,
        pd_map: dict[str, Any],
        os_map: dict[str, dict],
        bos_map: dict[str, str],
        defaults_map: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Строит список обогащённых записей profile_builds для view-model паспорта.

        Для каждой записи ``ProfileBuild`` извлекает настройки профиля (conan_settings,
        docker_image) из ``pd_map`` и строит представления вариантов через
        ``_build_variant_view``.

        Args:
            target_rel: Объект Release.
            comp_name: Имя компонента-владельца.
            pd_map: Словарь ``{profile_name: ProfileDefinition}``.
            os_map: Словарь ``{options_ref_id: options_dict}`` (resolved опции).
            bos_map: Словарь ``{options_ref_id: install_options_str}`` (из таблицы конфигураций).
            defaults_map: Словарь ``{option_name: default_value}`` компонента,
                          для подсветки в UI отличий от дефолта.

        Returns:
            Список dict-записей, совместимых с шаблоном ``component_passport.jinja2``.
        """
        enriched_pbs = []
        for pb in sorted(target_rel.profile_builds, key=lambda p: p.profile_name):
            settings, docker_image = self._resolve_profile_meta(pd_map, pb.profile_name)
            enriched_pbs.append(
                {
                    "profile_name": pb.profile_name,
                    "conan_settings": settings,
                    "exists": pb.exists,
                    "docker_image": docker_image,
                    "variants": [
                        self._build_variant_view(
                            v,
                            comp_name,
                            _VariantOpts(
                                conan_options=os_map.get(v.options_ref, {}),
                                install_options_override=bos_map.get(v.options_ref, None),
                                default_options=defaults_map,
                            ),
                        )
                        for v in (pb.variants or [])
                    ],
                }
            )
        return enriched_pbs

    def convert(self, data: ParsedResult) -> dict[str, Any]:
        """
        Формирует паспорт для конкретного компонента и версии.

        Один компонент может публиковаться в нескольких каналах (например
        ``fast`` и ``slow``) с одинаковой версией. В этом случае метод
        возвращает ``releases`` — список словарей по каждому каналу в порядке
        их следования в ``parsed_data``.

        Args:
            data: Полный набор данных парсера.

        Returns:
            View-model словарь с полем ``releases`` (список каналов).

        Raises:
            ValueError: Если компонент или версия не найдены.
        """
        pd_map: dict[str, Any] = self._build_profile_definition_map(data)

        target_comp = self._find_component(data, self._component_name)
        # Все релизы с данной версией — сохраняем порядок из parsed_data
        target_releases = self._find_releases(target_comp, self._release_version)

        # Базовый URL репозитория вычисляется один раз: хранится на уровне компонента.
        # Ветка по стандартному соглашению TFS для релизных бранчей.
        raw_git_url: str = target_comp.git_url or ""
        git_repo_base_url: str = raw_git_url.split("?")[0] if "?" in raw_git_url else raw_git_url

        releases_list: list[dict[str, Any]] = []
        for target_rel in target_releases:
            # Resolved опции — для бейджей conan_options в UI
            os_map: dict[str, dict] = {os_.id: os_.options for os_ in target_rel.total_option_sets}
            # Строки из таблицы конфигураций — для команды conan install
            bos_map: dict[str, str] = {
                bos.id: self._build_install_options_from_string(bos.options)
                for bos in target_rel.build_option_sets
            }
            # {имя_опции: дефолт} — источник истины для подсветки отличий в UI паспорта.
            defaults_map: dict[str, Any] = {
                o.name: o.default_value for o in target_rel.default_options
            }
            enriched_pbs = self._build_enriched_profile_builds(
                target_rel, target_comp.name, pd_map, os_map, bos_map, defaults_map
            )
            git_branch_version: str = f"{_TFS_BRANCH_PREFIX}{target_rel.version}"

            releases_list.append(
                {
                    "version": target_rel.version,
                    "platform": target_rel.platform,
                    "channel": target_rel.channel,
                    "git_url": target_comp.git_url,
                    "git_repo_base_url": git_repo_base_url,
                    "git_branch_version": git_branch_version,
                    "conan_reference": target_rel.conan_reference,
                    "artifactory_url": target_rel.artifactory_url,
                    "is_header_only": target_comp.is_header_only,
                    "build_option_sets": [bos.model_dump() for bos in target_rel.build_option_sets],
                    "default_options": [o.model_dump() for o in target_rel.default_options],
                    "patches": target_rel.patches,
                    "dependencies": target_rel.dependencies,
                    "profile_builds": enriched_pbs,
                }
            )

        return {
            "platform_version": data.platform_version,
            "component": {
                "name": target_comp.name,
                "description": target_comp.description,
                "git_project": target_comp.git_project,
                "git_repo": target_comp.git_repo,
                # git_url вынесен на уровень компонента для использования в заголовке страницы
                "git_url": target_comp.git_url,
            },
            # data.releases — список каналов; порядок соответствует parsed_data
            "releases": releases_list,
        }
