"""
Трансформер для профиль-центричного вида документации.
"""
from typing import Any, Dict, List, Optional

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import BaseDataTransformer

_DEFAULT_PASSPORT_PATTERN = '/wiki/spaces/DOC/pages/{component_name}+{release_version}'


class ProfileCentricTransformer(BaseDataTransformer):
    """
    Трансформер для профиль-центричного вида.

    Перестраивает иерархию ``Компонент → Релиз → Профиль``
    в ``Профиль → Канал → Компонент`` для удобного анализа по профилям.
    """

    def __init__(
        self,
        include_passport_links: bool = True,
        passport_page_pattern: Optional[str] = None,
    ) -> None:
        """
        Args:
            include_passport_links: Добавлять ли ссылки на паспорта.
            passport_page_pattern: Шаблон URL паспорта.
        """
        self._include_passport_links = include_passport_links
        self._pattern = passport_page_pattern or _DEFAULT_PASSPORT_PATTERN

    def _passport_link(self, comp_name: str, version: str) -> Optional[str]:
        if not self._include_passport_links:
            return None
        return self._pattern.format(
            component_name=comp_name.replace(' ', '+'),
            release_version=version.replace(' ', '+'),
        )

    def transform(self, data: ParsedResult) -> Dict[str, Any]:
        """
        Возвращает профиль-центричный вид данных.

        Args:
            data: Данные парсера.

        Returns:
            Словарь с профилями как верхним уровнем иерархии.
        """
        logger.debug('трансформация в профиль-центричный вид')

        # Собираем агрегированные настройки и docker URL по профилям
        profile_meta: Dict[str, Dict[str, Any]] = {}
        for comp in data.components:
            for rel in comp.releases:
                for pb in rel.profile_builds:
                    if pb.profile_name not in profile_meta:
                        profile_meta[pb.profile_name] = {'settings': {}, 'docker_url': ''}
                    if pb.conan_settings:
                        profile_meta[pb.profile_name]['settings'].update(pb.conan_settings)
                    if pb.docker_image:
                        profile_meta[pb.profile_name]['docker_url'] = pb.docker_image

        profiles: List[Dict[str, Any]] = []
        for profile_name in sorted(profile_meta):
            settings = profile_meta[profile_name]['settings']
            entry: Dict[str, Any] = {
                'profile_name': profile_name,
                'os': settings.get('os', 'Unknown'),
                'arch': settings.get('arch', '—'),
                'compiler': settings.get('compiler', '—'),
                'compiler_version': settings.get('compiler.version', '—'),
                'docker_url': profile_meta[profile_name]['docker_url'],
                'include_passport_links': self._include_passport_links,
                'channels': {},
            }

            for comp in data.components:
                for rel in comp.releases:
                    if not any(pb.profile_name == profile_name for pb in rel.profile_builds):
                        continue
                    if rel.channel not in entry['channels']:
                        entry['channels'][rel.channel] = []
                    entry['channels'][rel.channel].append({
                        'name': comp.name,
                        'version': rel.version,
                        'passport_link': self._passport_link(comp.name, rel.version),
                        'git': f'{comp.git_project}/{comp.git_repo}',
                        'reference': rel.conan_reference or '—',
                        'url': rel.artifactory_url or '—',
                        'is_header_only': rel.is_header_only,
                    })

            for channel in entry['channels']:
                entry['channels'][channel].sort(key=lambda x: x['name'])

            profiles.append(entry)

        return {
            'platform_version': data.platform_version,
            'generated_at': data.generated_at,
            'include_passport_links': self._include_passport_links,
            'profiles': profiles,
        }
