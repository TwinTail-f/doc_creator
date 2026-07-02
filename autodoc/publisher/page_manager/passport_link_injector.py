"""Вставка ссылок на страницы паспортов компонентов в view-model."""

from typing import Any


def _lookup_passport_entry(
    passport_pages: dict[str, Any],
    comp_name: str,
    version: str,
) -> dict[str, Any] | None:
    """Возвращает запись реестра паспортов для компонента и версии или None.

    Args:
        passport_pages: Реестр страниц паспортов.
        comp_name: Имя компонента.
        version: Версия компонента.

    Returns:
        Запись реестра или None, если компонент или версия не найдены.
    """
    return passport_pages.get(comp_name, {}).get(version)


def _build_passport_url(space: str, page_id: str) -> str:
    """
    Строит относительный URL страницы паспорта в Confluence.

    Args:
        space: Ключ Space в Confluence.
        page_id: ID страницы паспорта.

    Returns:
        Относительный путь вида ``/spaces/{space}/pages/{page_id}``.
    """
    return f"/spaces/{space}/pages/{page_id}"


def inject_links_for_profiles(
    view_model: dict[str, Any],
    passport_pages: dict[str, Any],
) -> None:
    """
    Вставляет ссылки на страницы паспортов в view-model профиль-центричного вида.

    Для компонентов, отсутствующих в реестре, поле ``passport_link``
    остаётся ``None``.

    Args:
        view_model: Словарь, созданный ``ProfileCentricConverter``.
                    Изменяется на месте. Должен содержать ключ ``'space'``.
        passport_pages: Карта, загруженная через ``PassportPageRegistry.load()``.
    """
    if not passport_pages or "profiles" not in view_model:
        return

    space = view_model.get("space", "")

    for profile in view_model.get("profiles", []):
        for channel_comps in profile.get("channels", {}).values():
            for comp in channel_comps:
                comp_name = comp.get("name")
                version = str(comp.get("version", ""))
                info = (
                    _lookup_passport_entry(passport_pages, comp_name, version)
                    if comp_name
                    else None
                )
                if not info:
                    comp["passport_link"] = None
                    continue
                page_id = info.get("page_id")
                comp["passport_link"] = _build_passport_url(space, page_id) if page_id else None


def inject_links(
    view_model: dict[str, Any],
    passport_pages: dict[str, Any],
) -> None:
    """
    Вставляет ссылки на страницы паспортов в view-model релиза.

    Для каждого компонента добавляет ключ ``passport_versions`` с теми
    версиями, что присутствуют в реестре. Не изменяет view-model,
    если ключ ``'components'`` отсутствует или реестр пуст.

    Args:
        view_model: Словарь, созданный трансформером. Изменяется на месте.
        passport_pages: Карта, загруженная через ``PassportPageRegistry.load()``.
    """
    if not passport_pages or "components" not in view_model:
        return

    space = view_model.get("space", "")

    for comp in view_model.get("components", []):
        comp_name = comp.get("name")
        if not comp_name or comp_name not in passport_pages:
            continue
        release_versions = {rel.get("version") for rel in comp.get("releases", [])}
        comp["passport_versions"] = {
            version: {**entry, "url": _build_passport_url(space, entry.get("page_id", ""))}
            for version in release_versions
            if (entry := _lookup_passport_entry(passport_pages, comp_name, version)) is not None
        }
