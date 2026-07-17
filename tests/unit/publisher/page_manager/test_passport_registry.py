"""Юнит-тесты для PassportPageRegistry.

Покрывает:
- save() записывает JSON в data_dir/passport_pages.json.
- save() создаёт родительскую директорию, если её не существует.
- save() производит валидный JSON, проходящий полный цикл через load().
- save() при OSError не бросает исключение — только логирует.
- load() возвращает {} при отсутствии файла.
- load() возвращает словарь при валидном файле.
- load() возвращает {} при некорректном JSON.
- load() возвращает {} при OSError из read_text.
- inject_links() добавляет passport_versions по ключу версии.
- inject_links() включает только версии, присутствующие среди релизов компонента.
- inject_links() ничего не делает, если у view_model отсутствует ключ 'components'.
- inject_links() ничего не делает, если passport_pages пуст.
- inject_links_for_profiles() выставляет passport_link найденным записям компонентов.
- inject_links_for_profiles() оставляет passport_link равным None для неизвестных компонентов.
- inject_links_for_profiles() ничего не делает, если у view_model отсутствует ключ 'profiles'.
- inject_links_for_profiles() ничего не делает, если passport_pages пуст.
"""
import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.publisher.page_manager.passport_link_injector import (
    inject_links,
    inject_links_for_profiles,
)
from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry

_PAGES_MAP: dict[str, Any] = {
    "openssl": {"1.0.0": {"page_id": "p1", "page_title": "openssl 1.0.0", "version": 1}}
}

_REGISTRY_FILE: str = "passport_pages.json"

SPACE: str = "TEST"
PAGE_ID: str = "p-001"


def _make_registry(data_dir: Path) -> PassportPageRegistry:
    """Создаёт PassportPageRegistry с заданной директорией данных.

    Args:
        data_dir: Директория, в которой будет храниться реестр.

    Returns:
        Новый экземпляр PassportPageRegistry.
    """
    return PassportPageRegistry(data_dir=data_dir)


@pytest.mark.infrastructure
def test_save_creates_file_in_data_dir(tmp_path: Path) -> None:
    """save() записывает passport_pages.json в data_dir."""
    registry = _make_registry(tmp_path)

    registry.save(_PAGES_MAP)

    assert (tmp_path / _REGISTRY_FILE).exists()


@pytest.mark.infrastructure
def test_save_creates_parent_directory_if_missing(tmp_path: Path) -> None:
    """save() создаёт data_dir, если она ещё не существует."""
    data_dir = tmp_path / "new_subdir"
    registry = _make_registry(data_dir)

    registry.save(_PAGES_MAP)

    assert data_dir.exists()


@pytest.mark.infrastructure
def test_save_writes_valid_json(tmp_path: Path) -> None:
    """save() записывает содержимое, которое парсится как валидный JSON."""
    registry = _make_registry(tmp_path)

    registry.save(_PAGES_MAP)

    raw = (tmp_path / _REGISTRY_FILE).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert parsed == _PAGES_MAP


@pytest.mark.infrastructure
def test_save_on_os_error_does_not_raise(tmp_path: Path, mocker: pytest.MonkeyPatch) -> None:
    """save() поглощает OSError и не пробрасывает исключение наружу."""
    registry = _make_registry(tmp_path)
    mocker.patch("pathlib.Path.write_text", side_effect=OSError("disk full"))

    # Не должно бросать исключение
    registry.save(_PAGES_MAP)


@pytest.mark.infrastructure
def test_load_returns_empty_dict_if_file_missing(tmp_path: Path) -> None:
    """load() возвращает {}, если passport_pages.json не существует."""
    registry = _make_registry(tmp_path)

    result = registry.load()

    assert result == {}


@pytest.mark.infrastructure
def test_load_returns_dict_on_valid_file(tmp_path: Path) -> None:
    """load() десериализует и возвращает сохранённый словарь."""
    (tmp_path / _REGISTRY_FILE).write_text(
        json.dumps(_PAGES_MAP, ensure_ascii=False), encoding="utf-8"
    )
    registry = _make_registry(tmp_path)

    result = registry.load()

    assert result == _PAGES_MAP


@pytest.mark.infrastructure
def test_load_returns_empty_dict_on_invalid_json(tmp_path: Path) -> None:
    """load() возвращает {}, если файл содержит некорректный JSON."""
    (tmp_path / _REGISTRY_FILE).write_text("not valid json", encoding="utf-8")
    registry = _make_registry(tmp_path)

    result = registry.load()

    assert result == {}


@pytest.mark.infrastructure
def test_load_returns_empty_dict_on_os_error(tmp_path: Path, mocker: pytest.MonkeyPatch) -> None:
    """load() возвращает {}, если read_text бросает OSError."""
    (tmp_path / _REGISTRY_FILE).write_text("{}", encoding="utf-8")
    registry = _make_registry(tmp_path)
    mocker.patch("pathlib.Path.read_text", side_effect=OSError("permission denied"))

    result = registry.load()

    assert result == {}


@pytest.mark.infrastructure
def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    """Значение, сохранённое через save(), корректно возвращается через load()."""
    pages_map: dict[str, Any] = {
        "openssl": {"1.0.0": {"page_id": "p1", "page_title": "T", "version": 1}}
    }
    registry = _make_registry(tmp_path)

    registry.save(pages_map)
    loaded = registry.load()

    assert loaded == pages_map


@pytest.mark.business_logic
def test_inject_links_adds_passport_versions_to_component(tmp_path: Path) -> None:
    """inject_links() выставляет passport_versions найденному компоненту."""
    view_model: dict[str, Any] = {
        "components": [{"name": "openssl", "releases": [{"version": "1.0.0"}]}]
    }
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    inject_links(view_model, passport_pages)

    assert view_model["components"][0]["passport_versions"]["1.0.0"]["page_id"] == PAGE_ID


@pytest.mark.business_logic
def test_inject_links_skips_versions_not_in_releases(tmp_path: Path) -> None:
    """inject_links() включает только версии, присутствующие среди релизов компонента."""
    view_model: dict[str, Any] = {
        "components": [{"name": "openssl", "releases": [{"version": "1.0.0"}]}]
    }
    passport_pages: dict[str, Any] = {
        "openssl": {
            "1.0.0": {"page_id": "p1"},
            "2.0.0": {"page_id": "p2"},
        }
    }

    inject_links(view_model, passport_pages)

    passport_versions = view_model["components"][0]["passport_versions"]
    assert "1.0.0" in passport_versions
    assert "2.0.0" not in passport_versions


@pytest.mark.contract
def test_inject_links_noop_if_no_components_key() -> None:
    """inject_links() ничего не делает и не бросает исключение при отсутствии ключа 'components'."""
    view_model: dict[str, Any] = {"other_key": "value"}
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    inject_links(view_model, passport_pages)

    assert "components" not in view_model


@pytest.mark.contract
def test_inject_links_noop_if_passport_pages_empty() -> None:
    """inject_links() ничего не делает, если passport_pages пуст."""
    view_model: dict[str, Any] = {
        "components": [{"name": "openssl", "releases": [{"version": "1.0.0"}]}]
    }

    inject_links(view_model, {})

    assert "passport_versions" not in view_model["components"][0]


def _make_profile_view_model(comp_name: str, version: str, space: str = SPACE) -> dict[str, Any]:
    """Строит минимальную профиль-центричную view-model для тестов inject_links_for_profiles.

    Args:
        comp_name: Имя компонента в единственном канале 'tech'.
        version: Версия компонента.
        space: Ключ Space в Confluence.

    Returns:
        Словарь view-model с одним профилем и одним компонентом в канале 'tech'.
    """
    return {
        "space": space,
        "profiles": [
            {"channels": {"tech": [{"name": comp_name, "version": version, "passport_link": None}]}}
        ],
    }


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_passport_link() -> None:
    """inject_links_for_profiles() выставляет passport_link на ожидаемый путь в Confluence."""
    view_model = _make_profile_view_model("openssl", "1.0.0")
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] == f"/spaces/{SPACE}/pages/{PAGE_ID}"


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_none_if_comp_missing() -> None:
    """inject_links_for_profiles() выставляет passport_link=None, если компонент не найден в реестре."""
    view_model = _make_profile_view_model("unknown_lib", "1.0.0")
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] is None


@pytest.mark.business_logic
def test_inject_links_for_profiles_sets_none_if_page_id_missing() -> None:
    """inject_links_for_profiles() выставляет passport_link=None, если найденная запись реестра лишена page_id."""
    view_model = _make_profile_view_model("openssl", "1.0.0")
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": None}}}

    inject_links_for_profiles(view_model, passport_pages)

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] is None


@pytest.mark.contract
def test_inject_links_for_profiles_noop_if_no_profiles_key() -> None:
    """inject_links_for_profiles() не бросает исключение при отсутствии ключа 'profiles'."""
    view_model: dict[str, Any] = {"space": SPACE, "components": []}
    passport_pages: dict[str, Any] = {"openssl": {"1.0.0": {"page_id": PAGE_ID}}}

    inject_links_for_profiles(view_model, passport_pages)

    assert "profiles" not in view_model


@pytest.mark.contract
def test_inject_links_for_profiles_noop_if_empty_passport_pages() -> None:
    """inject_links_for_profiles() ничего не делает, если passport_pages пуст."""
    view_model = _make_profile_view_model("openssl", "1.0.0")
    original_link = view_model["profiles"][0]["channels"]["tech"][0]["passport_link"]

    inject_links_for_profiles(view_model, {})

    comp = view_model["profiles"][0]["channels"]["tech"][0]
    assert comp["passport_link"] == original_link
