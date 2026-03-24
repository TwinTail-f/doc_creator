"""
Трансформер для комбинированного вида: компоненты + профили на одной странице.
"""
from typing import Any, Dict, List, Optional

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.transformers.base_transformer import BaseDataTransformer
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer
from autodoc.publisher.transformers.release_transformer import FullReleaseTransformer


class FullCombinedTransformer(BaseDataTransformer):
    """
    Трансформер для полного комбинированного вида.

    Объединяет полную документацию компонентов и профиль-центричный вид
    в одном документе для всестороннего анализа.
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
        self._component_transformer = FullReleaseTransformer(
            include_passport_links, passport_page_pattern
        )
        self._profile_transformer = ProfileCentricTransformer(
            include_passport_links, passport_page_pattern
        )

    def transform(self, data: ParsedResult) -> Dict[str, Any]:
        """
        Объединяет компонентный и профильный виды в один документ.

        Args:
            data: Данные парсера.

        Returns:
            Словарь с секциями ``components`` и ``profiles``.
        """
        logger.info('FullCombinedTransformer: трансформация в комбинированный вид')

        components_data = self._component_transformer.transform(data)
        profiles_data = self._profile_transformer.transform(data)

        sections: List[Dict[str, Any]] = [
            {
                'section_type': 'components',
                'title': 'Component Documentation',
                'content': components_data,
            },
            {
                'section_type': 'profiles',
                'title': 'Profile-Centric View',
                'content': profiles_data,
            },
        ]

        return {
            'sections': sections,
            'generated_at': data.generated_at,
            'platform_version': data.platform_version,
            'component_count': len(data.components),
            'profile_count': len(profiles_data.get('profiles', [])),
            'include_passport_links': self._include_passport_links,
        }
