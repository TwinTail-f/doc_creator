"""
Юнит-тесты для autodoc/parser/conan/profile_overrides.py.

Охватывает ProfileSettingsOverrides: from_file(), resolve(), is_empty(),
empty() и поведение слияния нескольких записей.
"""

import json
from pathlib import Path

import pytest

from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

_SINGLE_OVERRIDE: dict = {
    "overrides": [
        {
            "profiles": ["crypto_default.jinja"],
            "settings": {"os": "Linux"},
        }
    ]
}


def _write_json(tmp_path: Path, content: dict) -> Path:
    """Записывает словарь как JSON во временный файл и возвращает путь."""
    p = tmp_path / "overrides.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# from_file с корректным JSON
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_from_file_loads_correctly(tmp_path: Path) -> None:
    """from_file() с корректным JSON-файлом правильно разрешает точное имя профиля."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("crypto_default.jinja") == {"os": "Linux"}


# ---------------------------------------------------------------------------
# from_file с несуществующим путём
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_from_file_missing_file_returns_empty() -> None:
    """from_file() с несуществующим путём возвращает пустой экземпляр."""
    overrides = ProfileSettingsOverrides.from_file(Path("/nonexistent/path.json"))

    assert overrides.is_empty() is True


# ---------------------------------------------------------------------------
# from_file с некорректным JSON
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_from_file_invalid_json_returns_empty(tmp_path: Path) -> None:
    """from_file() с некорректным JSON возвращает пустой экземпляр."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_bytes(b"not-json")

    overrides = ProfileSettingsOverrides.from_file(bad_file)

    assert overrides.is_empty() is True


# ---------------------------------------------------------------------------
# resolve: точное совпадение имени
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_resolve_exact_match(tmp_path: Path) -> None:
    """resolve() с точным именем профиля из конфига возвращает настройки."""
    data = {
        "overrides": [
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"compiler": "gcc"},
            }
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("hw-linux-x86_64.jinja")

    assert result == {"compiler": "gcc"}


# ---------------------------------------------------------------------------
# resolve: сопоставление по basename при полном пути
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_resolve_basename_fallback(tmp_path: Path) -> None:
    """resolve() использует сопоставление по basename, когда полный путь используется как имя профиля.

    Исходный код выполняет поиск по basename (Path.name) в качестве вторичного шага.
    Профиль, хранящийся как 'hw-linux-x86_64.jinja', должен находиться при запросе
    через '/some/path/to/hw-linux-x86_64.jinja'.
    """
    data = {
        "overrides": [
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"compiler": "gcc"},
            }
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    # Используем полный путь, basename которого совпадает с именем сохранённого профиля
    result = overrides.resolve("/some/path/to/hw-linux-x86_64.jinja")

    assert result == {"compiler": "gcc"}


# ---------------------------------------------------------------------------
# resolve: неизвестное имя профиля
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_resolve_no_match_returns_empty_dict(tmp_path: Path) -> None:
    """resolve() с неизвестным именем профиля возвращает пустой словарь."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("unknown-profile.jinja")

    assert result == {}


# ---------------------------------------------------------------------------
# empty(): экземпляр с is_empty() == True
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_empty_instance_is_empty() -> None:
    """ProfileSettingsOverrides.empty() создаёт экземпляр, для которого is_empty() возвращает True."""
    assert ProfileSettingsOverrides.empty().is_empty() is True


# ---------------------------------------------------------------------------
# is_empty() при загруженных переопределениях
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_non_empty_is_not_empty(tmp_path: Path) -> None:
    """is_empty() возвращает False, если переопределения загружены из корректного файла."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.is_empty() is False


# ---------------------------------------------------------------------------
# Слияние нескольких записей для одного профиля
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_multiple_entries_merged(tmp_path: Path) -> None:
    """Две записи для одного имени профиля объединяются в единый словарь настроек."""
    data = {
        "overrides": [
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"os": "Linux"},
            },
            {
                "profiles": ["hw-linux-x86_64.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("hw-linux-x86_64.jinja")

    assert result.get("os") == "Linux"
    assert result.get("compiler") == "gcc"
