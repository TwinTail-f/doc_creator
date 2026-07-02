"""
Публичный API подсистемы legacy_content.

Внешние вызывающие (стратегии, паблишер) должны импортировать исключительно из этого
модуля. Внутренние модули (legacy_extractor, _html_utils) являются
деталями реализации и могут меняться.
"""

from autodoc.common.logger import logger
from autodoc.publisher.legacy_content.legacy_extractor import extract_platform_versions


def extract_for_platform(
    existing_html: str,
    current_platform_version: str,
) -> dict[str, str]:
    """
    Извлекает legacy-секции всех платформ, кроме указанной текущей.

    Args:
        existing_html: Текущее тело страницы (Confluence Storage Format).
        current_platform_version: Версия платформы, которая заменяется,
            например ``'2.2'``. Секции, чьё имя заканчивается на эту строку,
            исключаются.

    Returns:
        Словарь ``{имя_платформы: html_контент}`` для всех ДРУГИХ платформ.
        Пустой словарь, если ``existing_html`` пуст.
    """
    if not existing_html:
        return {}

    all_sections = extract_platform_versions(existing_html)
    filtered = {
        k: v
        for k, v in all_sections.items()
        if not (k == current_platform_version or k.endswith(f" {current_platform_version}"))
    }

    logger.debug(
        f"{len(all_sections)} секций всего, {len(filtered)} после фильтрации "
        f"платформы {current_platform_version}"
    )
    return filtered
