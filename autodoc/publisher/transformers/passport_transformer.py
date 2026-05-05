"""Трансформер для паспорта одного компонента."""

from typing import Any

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import (
    BaseDataTransformer,
    _VariantOpts,
)


class PassportTransformer(BaseDataTransformer):
    """
    Трансформер для подробной документации (паспорта) конкретного компонента.

    Если компонент или версия не найдены — бросает ``ValueError`` (не возвращает ``None``).

    Формат view-model совместим с ``component_passport.jinja2``:
    - ``data.component.releases`` — список из одного релиза, чтобы шаблон мог
      группировать по каналам через Jinja2 ``groupby``.
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
            raise ValueError(
                f"PassportTransformer: компонент {component_name} не найден"
            )
        return comp

    @staticmethod
    def _find_release(component: Any, release_version: str) -> Any:
        """
        Находит релиз по версии внутри компонента.

        Args:
            component: Объект компонента с атрибутом ``releases``.
            release_version: Строковое представление версии.

        Returns:
            Объект релиза.

        Raises:
            ValueError: Если версия не найдена.
        """
        rel = next(
            (r for r in component.releases if str(r.version) == str(release_version)),
            None,
        )
        if not rel:
            raise ValueError(
                f"PassportTransformer: версия {release_version} "
                f"для {component.name} не найдена"
            )
        return rel

    def _build_enriched_profile_builds(
        self,
        target_rel: Any,
        comp_name: str,
        pd_map: dict[str, Any],
        os_map: dict[str, dict],
        bos_map: dict[str, str],
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

        Returns:
            Список dict-записей, совместимых с шаблоном ``component_passport.jinja2``.
        """
        enriched_pbs = []
        for pb in target_rel.profile_builds:
            pd = pd_map.get(pb.profile_name)
            settings = dict(pd.conan_settings) if pd else {}
            docker_image = pd.docker_image if pd else ""
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
                                install_options_override=bos_map.get(
                                    v.options_ref, None
                                ),
                            ),
                        )
                        for v in (pb.variants or [])
                    ],
                }
            )
        return enriched_pbs

    def transform(self, data: ParsedResult) -> dict[str, Any]:
        """
        Формирует паспорт для конкретного компонента и версии.

        Args:
            data: Полный набор данных парсера.

        Returns:
            View-model словарь.

        Raises:
            ValueError: Если компонент или версия не найдены.
        """
        pd_map: dict[str, Any] = {
            pd.profile_name: pd for pd in data.profile_definitions
        }

        target_comp = self._find_component(data, self._component_name)
        target_rel = self._find_release(target_comp, self._release_version)

        # Resolved опции — для бейджей conan_options в UI
        os_map: dict[str, dict] = {
            os_.id: os_.options for os_ in target_rel.total_option_sets
        }
        # Строки из таблицы конфигураций — для команды conan install
        bos_map: dict[str, str] = {
            bos.id: self._build_install_options_from_string(bos.options)
            for bos in target_rel.build_option_sets
        }

        enriched_pbs = self._build_enriched_profile_builds(
            target_rel, target_comp.name, pd_map, os_map, bos_map
        )

        # Базовый URL репозитория (без query-параметров) — для построения ссылок на патчи.
        # Ветка вида GBrelease_{version} — стандартное соглашение TFS для бранчей релизов.
        _raw_git_url: str = target_rel.git_url or ""
        git_repo_base_url: str = (
            _raw_git_url.split("?")[0] if "?" in _raw_git_url else _raw_git_url
        )
        git_branch_version: str = f"GBrelease_{target_rel.version}"

        release_dict = {
            "version": target_rel.version,
            "platform": target_rel.platform,
            "channel": target_rel.channel,
            "git_url": target_rel.git_url,
            "git_repo_base_url": git_repo_base_url,
            "git_branch_version": git_branch_version,
            "conan_reference": target_rel.conan_reference,
            "artifactory_url": target_rel.artifactory_url,
            "is_header_only": target_rel.is_header_only,
            "build_option_sets": [
                bos.model_dump() for bos in target_rel.build_option_sets
            ],
            "default_options": [o.model_dump() for o in target_rel.default_options],
            "patches": target_rel.patches,
            "dependencies": target_rel.dependencies,
            "profile_builds": enriched_pbs,
        }

        return {
            "platform_version": data.platform_version,
            "component": {
                "name": target_comp.name,
                "description": target_comp.description,
                "git_project": target_comp.git_project,
                "git_repo": target_comp.git_repo,
            },
            # data.release — единственная точка доступа к данным релиза в шаблоне
            "release": release_dict,
            "legacy_contents": {},
        }
