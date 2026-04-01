"""Стратегия публикации профиль-центричной документации в Confluence."""
from pathlib import Path
from typing import Any

from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.rendering.document_builder import DocumentBuilder
from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer

_DEFAULT_TEMPLATE: str = 'profile_centric.jinja2'


class ProfileCentricStrategy(BasePublishStrategy, strategy_type='profile_centric'):
    """
    Публикует профиль-центричную документацию релиза на одной странице Confluence.

    Реорганизует данные по схеме Профиль → Канал → Компонент.
    Ссылки на паспорта компонентов встраиваются непосредственно в view-model
    внутри ``ProfileCentricTransformer`` (поле ``passport_link`` на каждом
    компоненте) — отдельный шаг инжекции здесь не нужен.

    Трансформер строится фабрикой через ``_make_transformer``. Оба ключа
    ``include_passport_links`` и ``passport_page_pattern`` остаются в kwargs
    и попадают как в трансформер, так и в ``__init__`` стратегии.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        document_builder: DocumentBuilder,
        parsed_data: ParsedResult,
        space: str,
        page_title: str,
        transformer: ProfileCentricTransformer | None = None,
        template_name: str = _DEFAULT_TEMPLATE,
        parent_id: str | None = None,
        include_passport_links: bool = True,
        passport_page_pattern: str | None = None,
        data_dir: Path | None = None,
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence API.
            document_builder: Рендерер Jinja2-шаблонов.
            parsed_data: Данные парсера.
            space: Ключ Space в Confluence.
            page_title: Заголовок страницы.
            transformer: Готовый экземпляр ``ProfileCentricTransformer``.
                         Если ``None`` — создаётся из ``include_passport_links``
                         и ``passport_page_pattern``. Передача готового
                         экземпляра упрощает тестирование.
            template_name: Имя Jinja2-шаблона. По умолчанию ``profile_centric.jinja2``.
            parent_id: ID родительской страницы. Если ``None`` — без родителя.
            include_passport_links: Передаётся в ``ProfileCentricTransformer``;
                                    если ``True``, каждый компонент получает
                                    поле ``passport_link``.
            passport_page_pattern: Шаблон URL паспорта с плейсхолдерами
                                   ``{component_name}`` и ``{release_version}``.
            data_dir: Не используется в этой стратегии; принимается для
                      совместимости с единым интерфейсом ``DocumentPublisher``.

        Raises:
            ValueError: Если ``space`` или ``page_title`` пустые.
        """
        if not space:
            raise ValueError('space cannot be empty')
        if not page_title:
            raise ValueError('page_title cannot be empty')

        super().__init__(confluence_client, document_builder, parsed_data, space)
        self._page_title: str = page_title
        self._template_name: str = template_name
        self._parent_id: str | None = parent_id
        self._transformer: ProfileCentricTransformer = transformer or ProfileCentricTransformer(
            include_passport_links=include_passport_links,
            passport_page_pattern=passport_page_pattern,
        )

    @classmethod
    def _make_transformer(cls, kwargs: dict) -> ProfileCentricTransformer:
        """
        Строит ``ProfileCentricTransformer`` из kwargs перед вызовом ``__init__``.

        Оба ключа читаются через ``.get()`` — стратегия также принимает их
        в ``__init__`` и использует как fallback при создании трансформера.
        Это гарантирует, что caller-значение не теряется ни для трансформера,
        ни для стратегии (исправляет Bug B).

        Args:
            kwargs: Прямая ссылка на словарь аргументов из ``create()``.

        Returns:
            Готовый ``ProfileCentricTransformer``.
        """
        return ProfileCentricTransformer(
            include_passport_links=kwargs.get('include_passport_links', True),
            passport_page_pattern=kwargs.get('passport_page_pattern', None),
        )

    def execute(self) -> PublishReport:
        """
        Трансформирует данные, рендерит шаблон и публикует страницу.

        Если трансформер вернул пустой результат — публикация прерывается
        и возвращается отчёт с ошибкой. Любое другое исключение также
        перехватывается, логируется и отражается в ``PublishReport``.

        Returns:
            ``PublishReport`` с результатом публикации одной страницы.
        """
        logger.info('ProfileCentricStrategy: публикация %r', self._page_title)
        errors: list[str] = []
        details: list[dict[str, Any]] = []

        try:
            view_model = self._transformer.transform(self._data)
            if not view_model:
                raise ValueError('трансформер вернул пустой результат')

            view_model['space'] = self._space

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
                'ProfileCentricStrategy: %r %s (ID: %s)',
                self._page_title, result['status'], result['id'],
            )
            return PublishReport(success=True, pages_published=1, details=details)

        except Exception as e:
            errors.append(str(e))
            logger.error('ProfileCentricStrategy: ошибка публикации %r: %s', self._page_title, e)
            return PublishReport(
                success=False, pages_published=0, errors=errors, details=details
            )
