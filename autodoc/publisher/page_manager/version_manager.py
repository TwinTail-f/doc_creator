"""Вспомогательные утилиты для работы с версиями страниц Confluence."""

from typing import Any

from autodoc.infrastructure.logger import logger

_FALLBACK_VERSION: int = 0


class PageVersionManager:
    """
    Утилиты для работы с версионированием страниц Confluence.

    Инкапсулирует извлечение, инкремент и логирование версий страниц.
    Все методы статические — объект не хранит состояния.
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

        Ответ Confluence содержит структуру ``{"version": {"number": <int>}}``.
        При любой ошибке парсинга (отсутствующий ключ, некорректный тип)
        возвращает ``_FALLBACK_VERSION`` (0), что позволяет вызывающему коду
        безопасно продолжить работу: ``get_next_version(0)`` даёт версию 1.

        Args:
            response: Словарь ответа от метода ``get_page``.

        Returns:
            Номер версии или ``0`` если извлечь не удалось.
        """
        try:
            return int(response.get("version", {}).get("number", _FALLBACK_VERSION))
        except (ValueError, TypeError, AttributeError):
            logger.warning(f"Не удалось извлечь версию из ответа: {response}")
            return _FALLBACK_VERSION

    @staticmethod
    def log_version_update(
        page_title: str,
        old_version: int,
        new_version: int,
    ) -> None:
        """
        Логирует обновление версии страницы на уровне INFO.

        Args:
            page_title: Заголовок обновлённой страницы.
            old_version: Предыдущая версия.
            new_version: Новая версия.
        """
        logger.info(f'"{page_title}" v{old_version} → v{new_version}')
