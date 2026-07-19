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
"""
import json
from pathlib import Path
from typing import Any

import pytest

from autodoc.publisher.page_manager.passport_registry import PassportPageRegistry

_PAGES_MAP: dict[str, Any] = {
    "openssl": {"1.0.0": {"page_id": "p1", "page_title": "openssl 1.0.0", "version": 1}}
}

_REGISTRY_FILE: str = "passport_pages.json"


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

