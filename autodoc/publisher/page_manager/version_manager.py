"""
Вспомогательные утилиты для работы с версиями страниц Confluence.
"""
from typing import Any

from autodoc.infrastructure.logger import logger

class PageVersionManager:
    """
    Утилиты для работы с версионированием страниц Confluence.

    Все методы статические — состояние не хранится.
    """

    @staticmethod
    def get_next_version(current_version: int) -> int:
        """
        Вычисляет следующий номер версии.

        Args:
            current_version: Текущая версия страницы.

        Returns:
            ``current_version + 1``.
        """
        return current_version + 1

    @staticmethod
    def extract_version_from_response(response: dict[str, Any]) -> int:
        """
        Извлекает номер версии из ответа Confluence API.

        Args:
            response: Словарь ответа от метода ``get_page``.

        Returns:
            Номер версии или ``0`` если извлечь не удалось.
        """
        try:
            return int(response.get('version', {}).get('number', 0))
        except (ValueError, TypeError, KeyError):
            logger.warning(
                f'PageVersionManager: не удалось извлечь версию из ответа: {response}'
            )
            return 0

    @staticmethod
    def log_version_update(
        page_title: str,
        old_version: int,
        new_version: int,
    ) -> None:
        """
        Логирует обновление версии страницы.

        Args:
            page_title: Заголовок обновлённой страницы.
            old_version: Предыдущая версия.
            new_version: Новая версия.
        """
        logger.info(
            f'PageVersionManager: "{page_title}" '
            f'v{old_version} → v{new_version}'
        )
