"""Трансформер для паспорта одного компонента."""
from typing import Any, Dict

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
    - Поле ``svace_report`` включено в каждый релиз.
    """

    def __init__(self, component_name: str, release_version: str) -> None:
        self._component_name = component_name
        self._release_version = release_version

    def transform(self, data: ParsedResult) -> Dict[str, Any]:
        """
        Формирует паспорт для конкретного компонента и версии.

        Args:
            data: Полный набор данных парсера.

        Returns:
            View-model словарь.

        Raises:
            ValueError: Если компонент или версия не найдены.
        """
        profile_settings: Dict[str, Dict[str, Any]] = {}
        for comp in data.components:
            for rel in comp.releases:
                for pb in rel.profile_builds:
                    if pb.conan_settings and pb.profile_name not in profile_settings:
                        profile_settings[pb.profile_name] = dict(pb.conan_settings)

        target_comp = next(
            (c for c in data.components if c.name == self._component_name), None
        )
        if not target_comp:
            raise ValueError(
                'PassportTransformer: компонент "%s" не найден' % self._component_name
            )

        target_rel = next(
            (r for r in target_comp.releases
             if str(r.version) == str(self._release_version)),
            None,
        )
        if not target_rel:
            raise ValueError(
                'PassportTransformer: версия %s для "%s" не найдена'
                % (self._release_version, self._component_name)
            )

        enriched_pbs = []
        for pb in target_rel.profile_builds:
            settings = dict(pb.conan_settings) if pb.conan_settings else {}
            if not settings and pb.profile_name in profile_settings:
                settings = profile_settings[pb.profile_name]

            enriched_pbs.append({
                'profile_name': pb.profile_name,
                'conan_settings': settings,
                'exists': pb.exists,
                'docker_image': pb.docker_image,   # новое имя
                'variants': [v.model_dump() for v in (pb.variants or [])],
            })

        release_dict = {
            'version': target_rel.version,
            'platform': target_rel.platform,
            'channel': target_rel.channel,
            'git_url': target_rel.git_url,
            'conan_reference': target_rel.conan_reference,
            'artifactory_url': target_rel.artifactory_url,
            'is_header_only': target_rel.is_header_only,       # новое имя
            'build_option_sets': target_rel.build_option_sets,
            'default_options': [o.model_dump() for o in target_rel.default_options],
            'patches': target_rel.patches,
            'dependencies': target_rel.dependencies,
            'profile_builds': enriched_pbs,
            # svace_report — поле для шаблона (component_passport.jinja2)
            'svace_report': {
                'profile': target_rel.svace_report.profile,
                'report_url': target_rel.svace_report.report_url,
            },
        }

        return {
            'platform_version': data.platform_version,
            'generated_at': data.generated_at,
            'component': {
                'name': target_comp.name,
                'description': target_comp.description,
                'git_project': target_comp.git_project,
                'git_repo': target_comp.git_repo,
                # data.component.releases — список из одного элемента,
                # чтобы шаблон мог groupby('channel') без изменений
                'releases': [release_dict],
            },
            # data.release — для обратной совместимости и прямого доступа
            'release': release_dict,
            'legacy_contents': {},
        }
