"""
Public API for the legacy_content subsystem.

External callers (strategies, publisher) should import exclusively from this
module. Internal modules (legacy_extractor, legacy_merger, _html_utils) are
implementation details and subject to change.
"""
from autodoc.common.logger import logger
from autodoc.publisher.legacy_content.legacy_extractor import extract_platform_versions


def extract_for_platform(
    existing_html: str,
    current_platform_version: str,
) -> dict[str, str]:
    """
    Извлекает все legacy-секции платформ, кроме текущей.

    Использует ``extract_platform_versions`` для
    получения всех секций, затем исключает ту, что соответствует текущей
    версии платформы по суффиксу строки версии (например ``'2.2'``).

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
        if not (
            k == current_platform_version or k.endswith(f" {current_platform_version}")
        )
    }

    logger.debug(
        f"{len(all_sections)} секций всего, {len(filtered)} после фильтрации "
        f"платформы {current_platform_version}"
    )
    return filtered
