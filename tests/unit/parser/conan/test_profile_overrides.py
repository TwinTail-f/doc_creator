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
    """Экземпляр без переопределений (созданный без аргументов) имеет is_empty() == True."""
    assert ProfileSettingsOverrides().is_empty() is True


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


# ---------------------------------------------------------------------------
# Частичная порча списка overrides: один "битый" элемент не должен ломать
# разбор остальных, валидных элементов того же списка.
# ---------------------------------------------------------------------------


@pytest.mark.business_logic
def test_profile_overrides_non_dict_entry_skipped_others_resolved(tmp_path: Path) -> None:
    """Элемент overrides, не являющийся объектом (например строка), пропускается — остальные записи разрешаются."""
    data = {
        "overrides": [
            "this-is-not-a-dict",
            {
                "profiles": ["good-profile.jinja"],
                "settings": {"os": "Linux"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("good-profile.jinja") == {"os": "Linux"}


@pytest.mark.business_logic
def test_profile_overrides_singular_profile_key_typo_skipped_others_resolved(tmp_path: Path) -> None:
    """Запись с опечаткой 'profile' вместо 'profiles' пропускается — остальные записи разрешаются."""
    data = {
        "overrides": [
            {
                "profile": ["typo-profile.jinja"],
                "settings": {"os": "Linux"},
            },
            {
                "profiles": ["good-profile.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("typo-profile.jinja") == {}
    assert overrides.resolve("good-profile.jinja") == {"compiler": "gcc"}


@pytest.mark.business_logic
def test_profile_overrides_profiles_non_list_skipped_others_resolved(tmp_path: Path) -> None:
    """Запись, у которой 'profiles' — не список (а строка), пропускается — остальные записи разрешаются."""
    data = {
        "overrides": [
            {
                "profiles": "crypto_default.jinja",
                "settings": {"os": "Linux"},
            },
            {
                "profiles": ["good-profile.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("crypto_default.jinja") == {}
    assert overrides.resolve("good-profile.jinja") == {"compiler": "gcc"}


@pytest.mark.business_logic
def test_profile_overrides_empty_profiles_list_skipped_others_resolved(tmp_path: Path) -> None:
    """Запись с пустым списком 'profiles' пропускается — остальные записи разрешаются."""
    data = {
        "overrides": [
            {
                "profiles": [],
                "settings": {"os": "Linux"},
            },
            {
                "profiles": ["good-profile.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("good-profile.jinja") == {"compiler": "gcc"}


@pytest.mark.business_logic
def test_profile_overrides_missing_settings_skipped_others_resolved(tmp_path: Path) -> None:
    """Запись без ключа 'settings' пропускается — остальные записи разрешаются."""
    data = {
        "overrides": [
            {
                "profiles": ["no-settings-profile.jinja"],
            },
            {
                "profiles": ["good-profile.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("no-settings-profile.jinja") == {}
    assert overrides.resolve("good-profile.jinja") == {"compiler": "gcc"}


@pytest.mark.business_logic
def test_profile_overrides_empty_settings_dict_skipped_others_resolved(tmp_path: Path) -> None:
    """Запись с пустым словарём 'settings' пропускается (не только отсутствующим) — остальные записи разрешаются."""
    data = {
        "overrides": [
            {
                "profiles": ["empty-settings-profile.jinja"],
                "settings": {},
            },
            {
                "profiles": ["good-profile.jinja"],
                "settings": {"compiler": "gcc"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("empty-settings-profile.jinja") == {}
    assert overrides.resolve("good-profile.jinja") == {"compiler": "gcc"}


@pytest.mark.business_logic
def test_profile_overrides_non_string_profile_name_skipped_siblings_resolved(tmp_path: Path) -> None:
    """Не-строковое имя профиля внутри списка пропускается — соседние валидные имена той же записи разрешаются."""
    data = {
        "overrides": [
            {
                "profiles": [123, "good-profile.jinja", None],
                "settings": {"os": "Linux"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("good-profile.jinja") == {"os": "Linux"}


@pytest.mark.business_logic
def test_profile_overrides_blank_profile_name_skipped_siblings_resolved(tmp_path: Path) -> None:
    """Пустое/состоящее из пробелов имя профиля пропускается — соседние валидные имена той же записи разрешаются."""
    data = {
        "overrides": [
            {
                "profiles": ["   ", "good-profile.jinja"],
                "settings": {"os": "Linux"},
            },
        ]
    }
    path = _write_json(tmp_path, data)
    overrides = ProfileSettingsOverrides.from_file(path)

    assert overrides.resolve("good-profile.jinja") == {"os": "Linux"}


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


# ---------------------------------------------------------------------------
# Форма всего файла: валидный JSON, но не той формы, которую ожидает
# _parse() (не dict, без секции "overrides", "overrides" не список).
# ---------------------------------------------------------------------------


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
