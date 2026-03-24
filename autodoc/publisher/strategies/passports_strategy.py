"""
Стратегия публикации коллекции паспортов компонентов.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.confluence.confluence_client import ConfluenceClient
from autodoc.publisher.page_manager.hierarchy_manager import PageHierarchyManager
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.passport_transformer import PassportTransformer

_DEFAULT_PASSPORT_TEMPLATE = 'component_passport.jinja2'


class PassportsStrategy(BasePublishStrategy, strategy_type='passports'):
    """
    Публикует паспорта компонентов с иерархией страниц Confluence.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        root_page_id: str,
        template_name: str = _DEFAULT_PASSPORT_TEMPLATE,
        data_dir: Optional[Path] = None,  # 3.9
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence.
            document_builder: Рендерер шаблонов.
            parsed_data: Данные парсера.
            space: Ключ Space.
            root_page_id: ID корневой страницы иерархии паспортов.
            template_name: Имя шаблона паспорта.
            data_dir: Рабочая директория (для сохранения passport_pages.json).
        """
        # 3.10 Конкретные проверки с внятными сообщениями вместо if not all([...])
        if not space:
            raise ValueError('space не может быть пустым')
        if not root_page_id:
            raise ValueError('root_page_id не может быть пустым')

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._root_page_id = root_page_id
        self._template_name = template_name
        self._hierarchy = PageHierarchyManager(confluence_client)
        # 3.9 путь из data_dir, а не hardcoded
        self._passport_pages_file = (
            (data_dir / 'passport_pages.json') if data_dir else Path('data') / 'passport_pages.json'
        )

    def execute(self) -> PublishReport:
        """Публикует паспорта для всех компонентов и релизов."""
        logger.info('PassportsStrategy: начало публикации паспортов')
        errors: List[str] = []
        details: List[Dict[str, Any]] = []
        pages_published = 0

        for comp in self._data.components:
            if not comp.releases:
                errors.append('Нет релизов для компонента "%s"' % comp.name)
                continue

            for release in comp.releases:
                try:
                    page_id, version, status = self._publish_passport(
                        comp.name, release.version
                    )
                    pages_published += 1
                    details.append({
                        'component_name': comp.name,
                        'release_version': release.version,
                        'page_title': self._page_title(comp.name, release.version),
                        'page_id': page_id,
                        'version': version,
                        'status': status,
                    })
                except Exception as e:
                    msg = 'Ошибка паспорта %s v%s: %s' % (comp.name, release.version, e)
                    errors.append(msg)
                    logger.error('PassportsStrategy: %s', msg)

        passport_pages_map = self._build_pages_map(details)
        self._save_passport_pages(passport_pages_map)

        logger.info(
            'PassportsStrategy: опубликовано %d паспортов, ошибок: %d',
            pages_published, len(errors),
        )
        return PublishReport(
            success=len(errors) == 0,
            pages_published=pages_published,
            errors=errors,
            details=details,
        )

    # ------------------------------------------------------------------

    def _publish_passport(self, comp_name: str, release_version: str) -> tuple:
        version_page_id = self._hierarchy.ensure_hierarchy_exists(
            space=self._space,
            root_parent_id=self._root_page_id,
            component_name=comp_name,
            release_version=release_version,
        )

        page_title = self._page_title(comp_name, release_version)

        legacy_body = ''
        try:
            legacy_body = self._client.get_page_body(
                space=self._space, title=page_title
            )
        except Exception as e:
            logger.warning(
                'PassportsStrategy: не удалось получить legacy для %r: %s', page_title, e
            )

        # 3.2 ValueError если компонент/версия не найдены
        transformer = PassportTransformer(comp_name, release_version)
        view_model = transformer.transform(self._data)

        legacy_contents: Dict[str, str] = {}
        if legacy_body:
            from autodoc.publisher.transformers.legacy_extractor import LegacyContentExtractor
            all_legacy = LegacyContentExtractor.extract_platform_versions(legacy_body)
            platform_version = view_model.get('platform_version', '')
            legacy_contents = {
                k: v for k, v in all_legacy.items()
                if 'Платформа %s' % platform_version not in k
                and not k.endswith(str(platform_version))
            }

        view_model['target_platform'] = (
            'Платформа %s' % view_model.get('platform_version', '')
        )
        view_model['legacy_contents'] = legacy_contents

        html_body = self._builder.build(self._template_name, view_model)
        result = self._client.publish_page(
            space=self._space,
            parent_id=version_page_id,
            title=page_title,
            body_html=html_body,
        )
        return result['id'], result['version'], result['status']

    @staticmethod
    def _page_title(comp_name: str, release_version: str) -> str:
        return 'Документация %s %s' % (comp_name, release_version)

    @staticmethod
    def _build_pages_map(details: List[Dict[str, Any]]) -> Dict[str, Any]:
        pages_map: Dict[str, Any] = {}
        for d in details:
            pages_map.setdefault(d['component_name'], {})[str(d['release_version'])] = {
                'page_id': d['page_id'],
                'page_title': d['page_title'],
                'version': d['version'],
            }
        return pages_map

    def _save_passport_pages(self, pages_map: Dict[str, Any]) -> None:
        try:
            self._passport_pages_file.parent.mkdir(parents=True, exist_ok=True)
            self._passport_pages_file.write_text(
                json.dumps(pages_map, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
        except OSError as e:
            logger.warning(
                'PassportsStrategy: не удалось сохранить passport_pages: %s', e
            )
