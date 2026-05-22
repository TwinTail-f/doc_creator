"""
Парсер опций Conan: разбор JSON-файлов options.json.
Не имеет доступа к TFS и не выполняет сетевых вызовов.
"""

import json
from typing import Any

from autodoc.common.logger import logger

_CI_DIR_V2: str = "/ci-2.0/"
_CI_DIR_V1_6: str = "/ci-1.6/"

_CI_PRIORITY: tuple[str, ...] = (_CI_DIR_V2, _CI_DIR_V1_6)


class OptionsParser:
    """Статические методы для разбора options.json файлов Conan."""

    @staticmethod
    def select_ci_prefix(options_paths: list[str]) -> str:
        """Возвращает первый подходящий CI-префикс или пустую строку."""
        for prefix in _CI_PRIORITY:
            if any(prefix in p for p in options_paths):
                return prefix
        return ""

    @staticmethod
    def parse_file(
        text: str,
        opt_path: str,
        ci_prefix: str,
    ) -> tuple[str | None, dict[str, str]]:
        """
        Разбирает текст JSON-файла опций.

        Returns:
            Кортеж ``(имя_канала_или_None, очищенные_опции)``
        """
        try:
            parsed: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка чтения {opt_path}: {e}")
            return None, {}

        cleaned: dict[str, str] = {
            str(k): (v.strip() if isinstance(v, str) else "")
            for k, v in parsed.items()
            if isinstance(v, (str, type(None)))
        }

        tail = opt_path.split(ci_prefix)[1]
        parts = tail.split("/")
        channel_name: str | None = parts[0] if len(parts) > 1 else None

        return channel_name, cleaned

    @staticmethod
    def pick_options(repo_data: dict, channel: str) -> dict[str, str]:
        """Выбирает набор опций для заданного канала."""
        channels = repo_data.get("channels", {})
        if channel and channel in channels:
            return channels[channel]
        global_opts = repo_data.get("global", {})
        if global_opts:
            return global_opts
        return {"1": ""}
