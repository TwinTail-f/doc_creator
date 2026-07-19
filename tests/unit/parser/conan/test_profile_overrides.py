"""
Юнит-тесты для autodoc/parser/conan/profile_overrides.py.

Охватывает ProfileSettingsOverrides: from_file(), resolve(), is_empty(),
empty() и поведение слияния нескольких записей.
"""

import json
from pathlib import Path
from typing import Callable

import pytest
import yaml

from autodoc.parser.conan.profile_overrides import ProfileSettingsOverrides

_SINGLE_OVERRIDE: dict = {
    "overrides": [
        {
            "profiles": ["crypto_default.jinja"],
            "settings": {"os": "Linux"},
        }
    ]
}


def _write_json(tmp_path: Path, content: dict) -> Path:
    """
    Записывает словарь как JSON во временный файл и возвращает путь.

    Args:
        tmp_path: Временная директория для размещения файла.
        content: Содержимое, которое будет сериализовано в JSON.

    Returns:
        Путь к созданному файлу overrides.json.
    """
    p = tmp_path / "overrides.json"
    p.write_text(json.dumps(content), encoding="utf-8")
    return p


def _write_yaml(tmp_path: Path, content: dict) -> Path:
    """
    Записывает словарь как YAML во временный файл и возвращает путь.

    Args:
        tmp_path: Временная директория для размещения файла.
        content: Содержимое, которое будет сериализовано в YAML.

    Returns:
        Путь к созданному файлу overrides.yaml.
    """
    p = tmp_path / "overrides.yaml"
    p.write_text(yaml.safe_dump(content), encoding="utf-8")
    return p


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "write_fixture",
    [
        pytest.param(_write_json, id="json"),
        pytest.param(_write_yaml, id="yaml"),
    ],
)
def test_profile_overrides_from_file_loads_correctly(
    tmp_path: Path,
    write_fixture: Callable[[Path, dict], Path],
) -> None:
    """from_file() с корректным JSON- или YAML-файлом правильно разрешает точное имя профиля."""
    path = write_fixture(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("crypto_default.jinja") == {"os": "Linux"}


@pytest.mark.business_logic
def test_profile_overrides_from_file_missing_file_returns_empty() -> None:
    """from_file() с несуществующим путём возвращает пустой экземпляр."""
    overrides = ProfileSettingsOverrides.from_file(Path("/nonexistent/path.json"))

    assert overrides.is_empty() is True


@pytest.mark.business_logic
def test_profile_overrides_from_file_invalid_json_returns_empty(tmp_path: Path) -> None:
    """from_file() с некорректным JSON возвращает пустой экземпляр."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_bytes(b"not-json")

    overrides = ProfileSettingsOverrides.from_file(bad_file)

    assert overrides.is_empty() is True


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


@pytest.mark.business_logic
def test_profile_overrides_resolve_no_match_returns_empty_dict(tmp_path: Path) -> None:
    """resolve() с неизвестным именем профиля возвращает пустой словарь."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    result = overrides.resolve("unknown-profile.jinja")

    assert result == {}


@pytest.mark.business_logic
def test_profile_overrides_empty_instance_is_empty() -> None:
    """Экземпляр без переопределений (созданный без аргументов) имеет is_empty() == True."""
    assert ProfileSettingsOverrides().is_empty() is True


@pytest.mark.business_logic
def test_profile_overrides_non_empty_is_not_empty(tmp_path: Path) -> None:
    """is_empty() возвращает False, если переопределения загружены из корректного файла."""
    path = _write_json(tmp_path, _SINGLE_OVERRIDE)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.is_empty() is False


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


@pytest.mark.business_logic
@pytest.mark.parametrize(
    "data, bad_profile_name, expected_good_settings",
    [
        # элемент overrides не является объектом (например строка)
        pytest.param(
            {
                "overrides": [
                    "this-is-not-a-dict",
                    {"profiles": ["good-profile.jinja"], "settings": {"os": "Linux"}},
                ]
            },
            None,
            {"os": "Linux"},
            id="non-dict-entry",
        ),
        # опечатка 'profile' вместо 'profiles'
        pytest.param(
            {
                "overrides": [
                    {"profile": ["typo-profile.jinja"], "settings": {"os": "Linux"}},
                    {"profiles": ["good-profile.jinja"], "settings": {"compiler": "gcc"}},
                ]
            },
            "typo-profile.jinja",
            {"compiler": "gcc"},
            id="singular-profile-key-typo",
        ),
        # 'profiles' — не список, а строка
        pytest.param(
            {
                "overrides": [
                    {"profiles": "crypto_default.jinja", "settings": {"os": "Linux"}},
                    {"profiles": ["good-profile.jinja"], "settings": {"compiler": "gcc"}},
                ]
            },
            "crypto_default.jinja",
            {"compiler": "gcc"},
            id="profiles-non-list",
        ),
        # пустой список 'profiles'
        pytest.param(
            {
                "overrides": [
                    {"profiles": [], "settings": {"os": "Linux"}},
                    {"profiles": ["good-profile.jinja"], "settings": {"compiler": "gcc"}},
                ]
            },
            None,
            {"compiler": "gcc"},
            id="empty-profiles-list",
        ),
        # ключ 'settings' отсутствует
        pytest.param(
            {
                "overrides": [
                    {"profiles": ["no-settings-profile.jinja"]},
                    {"profiles": ["good-profile.jinja"], "settings": {"compiler": "gcc"}},
                ]
            },
            "no-settings-profile.jinja",
            {"compiler": "gcc"},
            id="missing-settings",
        ),
        # пустой словарь 'settings' (не только отсутствующий)
        pytest.param(
            {
                "overrides": [
                    {"profiles": ["empty-settings-profile.jinja"], "settings": {}},
                    {"profiles": ["good-profile.jinja"], "settings": {"compiler": "gcc"}},
                ]
            },
            "empty-settings-profile.jinja",
            {"compiler": "gcc"},
            id="empty-settings-dict",
        ),
        # не-строковое имя профиля внутри списка 'profiles'
        pytest.param(
            {
                "overrides": [
                    {
                        "profiles": [123, "good-profile.jinja", None],
                        "settings": {"os": "Linux"},
                    },
                ]
            },
            None,
            {"os": "Linux"},
            id="non-string-profile-in-list",
        ),
        # пустое/состоящее из пробелов имя профиля внутри списка 'profiles'
        pytest.param(
            {
                "overrides": [
                    {
                        "profiles": ["   ", "good-profile.jinja"],
                        "settings": {"os": "Linux"},
                    },
                ]
            },
            None,
            {"os": "Linux"},
            id="blank-profile-in-list",
        ),
    ],
)
def test_profile_overrides_malformed_entry_skipped_others_resolved(
    tmp_path: Path,
    data: dict,
    bad_profile_name: str | None,
    expected_good_settings: dict,
) -> None:
    """При различных дефектах отдельной записи overrides или отдельного имени
    профиля внутри неё (не-объект, опечатка в ключе, 'profiles' не список,
    пустой список профилей, отсутствующий или пустой 'settings', не-строковое
    или пустое/пробельное имя профиля в списке) дефектная часть пропускается,
    а остальные записи по-прежнему разрешаются корректно."""
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    if bad_profile_name is not None:
        assert overrides.resolve(bad_profile_name) == {}
    assert overrides.resolve("good-profile.jinja") == expected_good_settings


@pytest.mark.business_logic
def test_profile_overrides_partial_corruption_final_state_correct(tmp_path: Path) -> None:
    """Список из трёх записей с одной битой: обе валидные записи разрешаются, is_empty() возвращает False."""
    data = {
        "overrides": [
            {
                "profile": ["broken-entry.jinja"],
                "settings": {"os": "Linux"},
            },
            {
                "profiles": ["profile-one.jinja"],
                "settings": {"compiler": "gcc"},
            },
            {
                "profiles": ["profile-two.jinja"],
                "settings": {"compiler": "clang"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("profile-one.jinja") == {"compiler": "gcc"}
    assert overrides.resolve("profile-two.jinja") == {"compiler": "clang"}
    assert overrides.is_empty() is False


@pytest.mark.business_logic
def test_profile_overrides_raw_not_a_dict_returns_empty(tmp_path: Path) -> None:
    """Если содержимое файла — валидный JSON, но не объект (например список) — возвращается пустой экземпляр."""
    path = _write_json(tmp_path, ["not", "a", "dict"])  # type: ignore[arg-type]

    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.is_empty() is True


@pytest.mark.business_logic
def test_profile_overrides_missing_overrides_key_returns_empty(tmp_path: Path) -> None:
    """Если в валидном JSON-объекте отсутствует секция 'overrides' — возвращается пустой экземпляр."""
    path = _write_json(tmp_path, {"something_else": True})

    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.is_empty() is True


@pytest.mark.business_logic
def test_profile_overrides_overrides_key_not_a_list_returns_empty(tmp_path: Path) -> None:
    """Если 'overrides' присутствует, но не является списком (например объектом) — возвращается пустой экземпляр."""
    path = _write_json(tmp_path, {"overrides": {"not": "a list"}})

    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.is_empty() is True
