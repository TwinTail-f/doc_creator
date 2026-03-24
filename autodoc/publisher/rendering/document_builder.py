"""
Рендеринг Jinja2-шаблонов в HTML Confluence Storage Format.
"""
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader

from autodoc.infrastructure.logger import logger


class DocumentBuilder:
    """
    Рендерит Jinja2-шаблоны в HTML для публикации в Confluence.

    Инициализирует окружение Jinja2 из указанной директории шаблонов
    и предоставляет единственный публичный метод ``build``.
    """

    def __init__(self, templates_dir: Path) -> None:
        """
        Args:
            templates_dir: Путь к директории с ``.jinja2``-шаблонами.

        Raises:
            FileNotFoundError: Если директория шаблонов не существует.
        """
        if not templates_dir.exists():
            raise FileNotFoundError(
                f'Директория шаблонов не найдена: {templates_dir}'
            )

        self._env = Environment(loader=FileSystemLoader(str(templates_dir)))
        logger.info(f'DocumentBuilder инициализирован: {templates_dir}')

    def build(self, template_name: str, view_model: Dict[str, Any]) -> str:
        """
        Рендерит шаблон с переданными данными.

        Args:
            template_name: Имя файла шаблона (например ``'release_doc_full.jinja2'``).
            view_model: Словарь данных для передачи в шаблон (доступен как ``data``).

        Returns:
            HTML-строка в Confluence Storage Format.

        Raises:
            jinja2.TemplateNotFound: Если шаблон не найден.
            jinja2.TemplateError: Если рендеринг завершился с ошибкой.
        """
        logger.debug(f'DocumentBuilder: рендеринг шаблона "{template_name}"')
        try:
            template = self._env.get_template(template_name)
            html = template.render(data=view_model)
            logger.info(f'DocumentBuilder: шаблон "{template_name}" отрендерен')
            return html
        except Exception as e:
            logger.error(
                f'DocumentBuilder: ошибка рендеринга "{template_name}": {e}'
            )
            raise
