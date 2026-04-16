"""Трансформер для паспорта одного компонента."""

from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import BaseDataTransformer


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
        self._component_name = component_name
        self._release_version = release_version

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
        pd_map: dict[str, Any] = {pd.profile_name: pd for pd in data.profile_definitions}

        target_comp = next(
            (c for c in data.components if c.name == self._component_name), None
        )
        if not target_comp:
            raise ValueError(
                f"PassportTransformer: компонент {self._component_name} не найден"
            )

        target_rel = next(
            (
                r
                for r in target_comp.releases
                if str(r.version) == str(self._release_version)
            ),
            None,
        )
        if not target_rel:
            raise ValueError(
                f"PassportTransformer: версия {self._release_version} для {self._component_name} не найдена"
            )

        # Lookup resolved options by options_ref for this release
        os_map: dict[str, dict] = {
            os_.id: os_.options for os_ in target_rel.option_sets
        }

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
                            target_comp.name,
                            os_map.get(v.options_ref, {}),
                        )
                        for v in (pb.variants or [])
                    ],
                }
            )

        release_dict = {
            "version": target_rel.version,
            "platform": target_rel.platform,
            "channel": target_rel.channel,
            "git_url": target_rel.git_url,
            "conan_reference": target_rel.conan_reference,
            "artifactory_url": target_rel.artifactory_url,
            "is_header_only": target_rel.is_header_only,  # новое имя
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
