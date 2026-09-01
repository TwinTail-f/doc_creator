"""
Реестр ID страниц паспортов — управляет файлом passport_pages.json.

Инкапсулирует весь файловый ввод-вывод, связанный с передачей данных
между стратегиями публикации. ``PassportsStrategy`` записывает карту ID,
``ReleasePageStrategy`` и ``ProfileCentricPageStrategy`` её читают.
"""

import json
from pathlib import Path
from typing import Any

from autodoc.common.logger import logger

_DEFAULT_DATA_DIR: Path = Path("data")
_REGISTRY_FILENAME: str = "passport_pages.json"


class PassportPageRegistry:
    """
    Владеет файлом ``passport_pages.json``.

    Схема файла::

        {
          "<имя_компонента>": {
            "<версия>": {
              "page_id": "...",
              "page_title": "...",
              "version": <int>
            }
          }
        }

    Файл сохраняется между запусками CLI, что позволяет публиковать паспорта
    и страницу релиза в отдельных командах.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """
        Args:
            data_dir: Директория для ``passport_pages.json``.
                      По умолчанию ``Path('data')``.
        """
        base = data_dir or _DEFAULT_DATA_DIR
        self._file: Path = base / _REGISTRY_FILENAME

    def save(self, pages_map: dict[str, Any]) -> None:
        """
        Сохраняет карту страниц паспортов на диск.

        При ошибке ввода-вывода не бросает исключение, чтобы не прерывать
        основной поток публикации.

        Args:
            pages_map: Карта вида ``{comp_name: {version: {page_id, page_title, version}}}``.
        """
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(pages_map, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(f"Сохранено {len(pages_map)} компонентов в {self._file}")
        except OSError as e:
            logger.warning(f"Не удалось сохранить файл: {e}")

    def upsert(self, pages_map: dict[str, Any]) -> None:
        """
        Объединяет переданную карту страниц с уже сохранённой на диске и сохраняет результат.

        Новые записи перезаписывают старые при совпадении компонента и версии.

        Args:
            pages_map: Карта вида ``{comp_name: {version: {page_id, page_title, version}}}``.
        """
        merged = self.load()
        for comp_name, versions in pages_map.items():
            merged.setdefault(comp_name, {}).update(versions)
        self.save(merged)

    def load(self) -> dict[str, Any]:
        """
        Загружает карту страниц паспортов с диска.

        При отсутствии файла или ошибке чтения/парсинга возвращает пустой
        словарь — штатная ситуация при первом запуске.

        Returns:
            Загруженная карта или пустой словарь.
        """
        if not self._file.exists():
            logger.debug(f"Файл не найден: {self._file}")
            return {}
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            logger.debug(f"Загружено {len(data)} компонентов")
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.debug(f"Не удалось загрузить файл: {e}")
            return {}
