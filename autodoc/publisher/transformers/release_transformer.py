"""
Трансформеры для документации релизов: полный и минимальный вид.
"""
from typing import Any, Dict, Optional

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import BaseDataTransformer

_DEFAULT_PASSPORT_PATTERN = '/wiki/spaces/DOC/pages/{component_name}+{release_version}'


class BaseReleaseTransformer(BaseDataTransformer):
    """
    Базовый класс трансформеров документации релиза.

    Содержит общий конструктор и вспомогательный метод формирования
    ссылки на паспорт компонента. Конкретные виды реализуют ``transform()``.
    """

    def __init__(
        self,
        include_passport_links: bool = True,
        passport_page_pattern: Optional[str] = None,
    ) -> None:
        """
        Args:
            include_passport_links: Добавлять ли ссылки на паспорта компонентов.
            passport_page_pattern: Шаблон URL паспорта с плейсхолдерами
                ``{component_name}`` и ``{release_version}``.
        """
        self._include_passport_links = include_passport_links
        self._pattern = passport_page_pattern or _DEFAULT_PASSPORT_PATTERN

    def _passport_link(self, comp_name: str, version: str) -> Optional[str]:
        """
        Формирует ссылку на паспорт компонента.

        Args:
            comp_name: Имя компонента.
            version: Версия релиза.

        Returns:
            URL паспорта или ``None``, если ссылки отключены.
        """
        if not self._include_passport_links:
            return None
        return self._pattern.format(
            component_name=comp_name.replace(' ', '+'),
            release_version=version.replace(' ', '+'),
        )


class FullReleaseTransformer(BaseReleaseTransformer):
    """
    Трансформер для полного вида документации релиза.

    Включает все компоненты со всеми профилями, вариантами и зависимостями.
    Опционально добавляет ссылки на паспорта компонентов.
    """

    def transform(self, data: ParsedResult) -> Dict[str, Any]:
        """
        Возвращает полный вид с вариантами и всеми деталями.

        Args:
            data: Данные парсера.

        Returns:
            Словарь view-model для шаблона полного релиза.
        """
        logger.debug('трансформация в полный вид')
        return {
            'platform_version': data.platform_version,
            'generated_at': data.generated_at,
            'include_passport_links': self._include_passport_links,
            'components': [
                {
                    'name': comp.name,
                    'description': comp.description,
                    'git_project': comp.git_project,
                    'git_repo': comp.git_repo,
                    'passport_link': self._passport_link(
                        comp.name, comp.releases[0].version
                    ) if comp.releases else None,
                    'releases': [
                        {
                            'version': rel.version,
                            'platform': rel.platform,
                            'channel': rel.channel,
                            'git_url': rel.git_url,
                            'conan_reference': rel.conan_reference,
                            'artifactory_url': rel.artifactory_url,
                            'is_header_only': rel.is_header_only,
                            'build_option_sets': rel.build_option_sets,
                            'default_options': rel.default_options,
                            'patches': rel.patches,
                            'dependencies': rel.dependencies,
                            'profile_builds': [
                                {
                                    'profile_name': pb.profile_name,
                                    'conan_settings': pb.conan_settings,
                                    'docker_image': pb.docker_image,
                                    'variants': [v.model_dump() for v in pb.variants],
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


class MinimalReleaseTransformer(BaseReleaseTransformer):
    """
    Трансформер для минимального вида документации релиза.

    Возвращает данные без вариантов для облегчённого отображения.
    """

    def transform(self, data: ParsedResult) -> Dict[str, Any]:
        """
        Возвращает минимальный вид без вариантов сборки.

        Args:
            data: Данные парсера.

        Returns:
            Словарь view-model для минимального шаблона.
        """
        logger.debug('трансформация в минимальный вид')
        return {
            'platform_version': data.platform_version,
            'generated_at': data.generated_at,
            'include_passport_links': self._include_passport_links,
            'components': [
                {
                    'name': comp.name,
                    'description': comp.description,
                    'git_project': comp.git_project,
                    'git_repo': comp.git_repo,
                    'passport_link': self._passport_link(
                        comp.name, comp.releases[0].version
                    ) if comp.releases else None,
                    'releases': [
                        {
                            'version': rel.version,
                            'platform': rel.platform,
                            'channel': rel.channel,
                            'git_url': rel.git_url,
                            'conan_reference': rel.conan_reference,
                            'artifactory_url': rel.artifactory_url,
                            'is_header_only': rel.is_header_only,
                            'build_option_sets': rel.build_option_sets,
                            'dependencies': rel.dependencies,
                            'profile_builds': [
                                {
                                    'profile_name': pb.profile_name,
                                    'conan_settings': pb.conan_settings,
                                    'docker_image': pb.docker_image,
                                    # variants намеренно опущены в минимальном виде
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
