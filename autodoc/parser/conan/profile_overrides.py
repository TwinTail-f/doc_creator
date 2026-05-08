"""
Загрузчик и резолвер переопределений настроек профилей Conan.

Используется как костыль для профилей, чьи Jinja-шаблоны читают
env-переменные (например ``KOS_SDK_VER`` → ``compiler.toolchain_config_id``).
Вместо задания env-переменных пользователь описывает нужные ``-s`` настройки
в файле ``profile_settings_overrides.json``.

Пример конфига — ``configs/profile_settings_overrides.json.example``.
"""

import json
from pathlib import Path
from typing import Any, Self

from autodoc.common.logger import logger


class ProfileSettingsOverrides:
    """
    Хранит и резолвит переопределения настроек (-s) для профилей Conan.

    Загружается один раз из JSON-файла. Метод ``resolve()`` возвращает
    словарь ``{setting_key: value}`` для заданного имени профиля.

    Attributes:
        _mapping: Словарь ``{profile_name: {setting_key: value}}``,
                  построенный из секций ``overrides`` конфига.
    """

    def __init__(self, mapping: dict[str, dict[str, str]]) -> None:
        """
        Args:
            mapping: Готовый словарь ``{profile_name: {setting: value}}``.
                     Обычно строится через ``ProfileSettingsOverrides.from_file()``.
        """
        self._mapping = mapping

    # ------------------------------------------------------------------
    # Фабричные методы
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls) -> Self:
        """Возвращает пустой экземпляр (костыль отключён)."""
        return cls({})

    @classmethod
    def from_file(cls, path: str | Path) -> Self:
        """
        Загружает переопределения из JSON-файла.

        Формат файла::

            {
              "overrides": [
                {
                  "profiles": ["profile1.jinja", "profile2.jinja"],
                  "settings": {
                    "compiler.toolchain_config_id": "kos-kisg-3.1.0.130"
                  }
                }
              ]
            }

        Если файл не найден или содержит ошибки — логирует предупреждение
        и возвращает пустой экземпляр, не прерывая работу пайплайна.

        Args:
            path: Путь к JSON-файлу с переопределениями.

        Returns:
            Заполненный экземпляр ``ProfileSettingsOverrides``.
        """
        p = Path(path)
        if not p.exists():
            logger.warning(
                f"profile_settings_overrides: файл не найден: {p}. "
                "Переопределения настроек профилей не будут применены."
            )
            return cls.empty()

        try:
            with p.open("r", encoding="utf-8") as f:
                raw: Any = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                f"profile_settings_overrides: не удалось прочитать {p}: {e}. "
                "Переопределения не будут применены."
            )
            return cls.empty()

        return cls._parse(raw, source=str(p))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        """
        Строит экземпляр из уже загруженного словаря (например из ``ConfigManager``).

        Args:
            raw: Содержимое конфига в виде словаря.

        Returns:
            Заполненный экземпляр ``ProfileSettingsOverrides``.
        """
        return cls._parse(raw, source="<dict>")

    # ------------------------------------------------------------------
    # Основной метод
    # ------------------------------------------------------------------

    def resolve(self, profile_name: str) -> dict[str, str]:
        """
        Возвращает словарь настроек для заданного профиля.

        Поиск ведётся сначала по полному имени профиля, затем по basename
        (имя файла без пути). Если профиль не описан в конфиге — возвращает
        пустой словарь и команда остаётся неизменной.

        Args:
            profile_name: Имя профиля как оно передаётся в ``-pr=``.

        Returns:
            Словарь ``{setting_key: value}`` или ``{}``.
        """
        # Точное совпадение
        if profile_name in self._mapping:
            return dict(self._mapping[profile_name])

        # Совпадение по basename (на случай если в профилях указан полный путь)
        basename = Path(profile_name).name
        if basename != profile_name and basename in self._mapping:
            return dict(self._mapping[basename])

        return {}

    def is_empty(self) -> bool:
        """Возвращает ``True``, если переопределения не заданы."""
        return not self._mapping

    # ------------------------------------------------------------------
    # Приватные методы
    # ------------------------------------------------------------------

    @classmethod
    def _parse(cls, raw: Any, source: str) -> Self:
        """
        Разбирает содержимое конфига в плоский словарь ``{profile: {setting: value}}``.

        Args:
            raw: Данные конфига (ожидается dict с ключом ``overrides``).
            source: Строковое описание источника для сообщений лога.

        Returns:
            Заполненный экземпляр.
        """
        if not isinstance(raw, dict):
            logger.warning(
                f"profile_settings_overrides ({source}): ожидался объект, "
                f"получен {type(raw).__name__}. Переопределения не будут применены."
            )
            return cls.empty()

        overrides_list = raw.get("overrides")
        if not overrides_list:
            logger.debug(
                f"profile_settings_overrides ({source}): секция \"overrides\" пуста или отсутствует."
            )
            return cls.empty()

        if not isinstance(overrides_list, list):
            logger.warning(
                f"profile_settings_overrides ({source}): \"overrides\" должен быть списком. "
                "Переопределения не будут применены."
            )
            return cls.empty()

        mapping: dict[str, dict[str, str]] = {}
        for idx, entry in enumerate(overrides_list):
            if not isinstance(entry, dict):
                logger.warning(
                    f"profile_settings_overrides ({source}): запись [{idx}] не является объектом, пропускается."
                )
                continue

            profiles = entry.get("profiles", [])
            settings = entry.get("settings", {})

            if not isinstance(profiles, list) or not profiles:
                logger.warning(
                    f"profile_settings_overrides ({source}): запись [{idx}] не содержит список \"profiles\", пропускается."
                )
                continue

            if not isinstance(settings, dict) or not settings:
                logger.warning(
                    f"profile_settings_overrides ({source}): запись [{idx}] не содержит \"settings\", пропускается."
                )
                continue

            for profile in profiles:
                if not isinstance(profile, str) or not profile.strip():
                    logger.warning(
                        f"profile_settings_overrides ({source}): запись [{idx}] содержит невалидный профиль: {profile}, пропускается."
                    )
                    continue

                profile = profile.strip()
                if profile in mapping:
                    # Мёржим: последующие записи дополняют/перезаписывают предыдущие
                    mapping[profile].update(settings)
                    logger.debug(
                        f"profile_settings_overrides: профиль \"{profile}\" уже описан, настройки объединены."
                    )
                else:
                    mapping[profile] = dict(settings)

        logger.info(
            f"profile_settings_overrides ({source}): загружено {len(mapping)} профиля(-ей) с переопределениями."
        )
        return cls(mapping)
