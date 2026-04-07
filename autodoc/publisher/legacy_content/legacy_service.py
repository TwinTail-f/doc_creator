"""Высокоуровневый сервис для извлечения и слияния legacy-контента."""

from autodoc.infrastructure.logger import logger
from autodoc.publisher.legacy_content.legacy_extractor import LegacyContentExtractor
from autodoc.publisher.legacy_content.legacy_merger import LegacyContentMerger

_PLATFORM_LABEL_PREFIX: str = "Платформа "


class LegacyContentService:
    """
    Координирует извлечение и фильтрацию legacy-контента из Confluence.

    Стратегии обращаются к этому сервису вместо прямых вызовов
    ``LegacyContentExtractor`` и ``LegacyContentMerger``.
    Все методы статические.
    """

    @staticmethod
    def extract_for_platform(
        existing_html: str,
        current_platform_version: str,
    ) -> dict[str, str]:
        """
        Извлекает все legacy-секции платформ, кроме текущей.

        Использует ``LegacyContentExtractor.extract_platform_versions`` для
        получения всех секций, затем исключает ту, что соответствует текущей
        версии платформы. Проверка двойная: по полному имени вида
        ``'Платформа 2.2'`` и по суффиксу строки версии ``'2.2'``.

        Args:
            existing_html: Текущее тело страницы (Confluence Storage Format).
            current_platform_version: Версия платформы, которая заменяется,
                например ``'2.2'``. Секции, содержащие эту строку, исключаются.

        Returns:
            Словарь ``{имя_платформы: html_контент}`` для всех ДРУГИХ платформ.
            Пустой словарь, если ``existing_html`` пуст.
        """
        if not existing_html:
            return {}

        all_sections = LegacyContentExtractor.extract_platform_versions(existing_html)
        current_label = _PLATFORM_LABEL_PREFIX + current_platform_version
        filtered = {
            k: v for k, v in all_sections.items()
            if current_label not in k and not k.endswith(current_platform_version)
        }

        logger.debug(f"{len(all_sections)} секций всего, {len(filtered)} после фильтрации платформы {current_platform_version}")
        return filtered

    @staticmethod
    def merge(
        new_html: str,
        legacy_contents: dict[str, str],
        current_platform: str,
    ) -> str:
        """
        Объединяет новый HTML с legacy-секциями платформ.

        Делегирует в ``LegacyContentMerger.merge_by_tabs()``. Если шаблон
        сам обрабатывает вкладки, ``new_html`` возвращается без изменений.

        Args:
            new_html: Свежеотрендеренный HTML.
            legacy_contents: Секции старых платформ для сохранения.
            current_platform: Отображаемое имя вкладки текущей платформы.

        Returns:
            Финальный HTML, готовый для публикации в Confluence.
        """
        return LegacyContentMerger.merge_by_tabs(new_html, legacy_contents, current_platform)
