"""
Стратегии публикации одностраничной документации релиза.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.confluence.confluence_client import ConfluenceClient
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.base_transformer import BaseDataTransformer
from autodoc.publisher.transformers.combined_transformer import FullCombinedTransformer
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer
from autodoc.publisher.transformers.release_transformer import (
    FullReleaseTransformer,
    MinimalReleaseTransformer,
)


class ReleasePageStrategy(
    BasePublishStrategy,
    strategy_type='full_release',
    transformer_cls=FullReleaseTransformer,  # 3.7 transformer_cls в объявлении
):
    """
    Публикует документацию релиза на одной странице Confluence.

    Используется для всех одностраничных типов:
    ``full_release``, ``minimal_release``, ``profile_centric``, ``full_combined``.
    Тип документа определяется трансформером, передаваемым через Registry.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        transformer: BaseDataTransformer,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        template_name: str,
        parent_id: Optional[str] = None,
        data_dir: Optional[Path] = None,  # 3.9
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence.
            document_builder: Рендерер шаблонов.
            transformer: Трансформер данных.
            parsed_data: Данные парсера.
            space: Ключ Space.
            page_title: Заголовок целевой страницы.
            template_name: Имя файла шаблона.
            parent_id: ID родительской страницы.
            data_dir: Рабочая директория (для чтения passport_pages.json).
        """
        # 3.10 Убрана бессодержательная проверка if not all([...]).
        #      Pydantic и аннотации типов уже не допускают None для обязательных аргументов.
        if not space:
            raise ValueError('space не может быть пустым')
        if not page_title:
            raise ValueError('page_title не может быть пустым')
        if not template_name:
            raise ValueError('template_name не может быть пустым')

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._transformer = transformer
        self._page_title = page_title
        self._template_name = template_name
        self._parent_id = parent_id
        # 3.9 путь к passport_pages.json из data_dir, а не hardcoded Path('data')
        self._passport_pages_file = (
            (data_dir / 'passport_pages.json') if data_dir else Path('data') / 'passport_pages.json'
        )

    def execute(self) -> PublishReport:
        """Публикует страницу релиза."""
        logger.info('ReleasePageStrategy: публикация страницы %r', self._page_title)
        errors: List[str] = []
        details: List[Dict[str, Any]] = []

        try:
            passport_pages = self._load_passport_pages()
            view_model = self._transformer.transform(self._data)
            if not view_model:
                raise ValueError('Трансформер вернул пустой результат')

            view_model['space'] = self._space
            self._inject_passport_links(view_model, passport_pages)

            html_body = self._builder.build(self._template_name, view_model)
            result = self._client.publish_page(
                space=self._space,
                parent_id=self._parent_id or '',
                title=self._page_title,
                body_html=html_body,
            )

            details.append({
                'page_title': self._page_title,
                'page_id': result['id'],
                'version': result['version'],
                'status': result['status'],
                'template': self._template_name,
            })
            logger.info(
                'ReleasePageStrategy: %r %s (ID: %s)',
                self._page_title, result['status'], result['id'],
            )
            return PublishReport(success=True, pages_published=1, details=details)

        except Exception as e:
            error_msg = str(e)
            errors.append(error_msg)
            logger.error('ReleasePageStrategy: ошибка — %s', error_msg)
            return PublishReport(success=False, pages_published=0, errors=errors, details=details)

    def _load_passport_pages(self) -> Dict[str, Any]:
        if self._passport_pages_file.exists():
            try:
                return json.loads(self._passport_pages_file.read_text(encoding='utf-8'))
            except Exception as e:
                logger.debug('ReleasePageStrategy: не удалось загрузить passport_pages: %s', e)
        return {}

    @staticmethod
    def _inject_passport_links(
        view_model: Dict[str, Any],
        passport_pages: Dict[str, Any],
    ) -> None:
        if not passport_pages or 'components' not in view_model:
            return
        for comp in view_model.get('components', []):
            comp_name = comp.get('name')
            if not comp_name or comp_name not in passport_pages:
                continue
            release_versions = {rel.get('version') for rel in comp.get('releases', [])}
            comp['passport_versions'] = {
                v: info
                for v, info in passport_pages[comp_name].items()
                if v in release_versions
            }


# 3.7 Подклассы-алиасы вместо прямой записи в _registry/_transformer_map снаружи.
# Каждый объявляет свой strategy_type и transformer_cls через __init_subclass__.

class MinimalReleaseStrategy(
    ReleasePageStrategy,
    strategy_type='minimal_release',
    transformer_cls=MinimalReleaseTransformer,
):
    pass


class ProfileCentricStrategy(
    ReleasePageStrategy,
    strategy_type='profile_centric',
    transformer_cls=ProfileCentricTransformer,
):
    pass


class FullCombinedStrategy(
    ReleasePageStrategy,
    strategy_type='full_combined',
    transformer_cls=FullCombinedTransformer,
):
    pass
