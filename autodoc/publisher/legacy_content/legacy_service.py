"""Утилиты для извлечения и слияния legacy-контента платформ."""

from autodoc.infrastructure.logger import logger
from autodoc.publisher.legacy_content.legacy_extractor import LegacyContentExtractor

_PLATFORM_LABEL_PREFIX: str = "Платформа "


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
        k: v
        for k, v in all_sections.items()
        if current_label not in k and not k.endswith(current_platform_version)
    }

    logger.debug(
        f"{len(all_sections)} секций всего, {len(filtered)} после фильтрации платформы {current_platform_version}"
    )
    return filtered
