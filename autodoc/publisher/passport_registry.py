"""
Реестр ID страниц паспортов — управляет файлом passport_pages.json.

Инкапсулирует весь файловый ввод-вывод, связанный с передачей данных
между стратегиями публикации. ``PassportsStrategy`` записывает карту ID,
``ReleasePageStrategy`` и ``ProfileCentricStrategy`` её читают.
"""
import json
from pathlib import Path
from typing import Any

from autodoc.infrastructure.logger import logger

_DEFAULT_DATA_DIR: Path = Path('data')
_REGISTRY_FILENAME: str = 'passport_pages.json'


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
        base = data_dir if data_dir is not None else _DEFAULT_DATA_DIR
        self._file: Path = base / _REGISTRY_FILENAME

    def save(self, pages_map: dict[str, Any]) -> None:
        """
        Сохраняет карту страниц паспортов на диск.

        Создаёт родительскую директорию при необходимости.
        При ошибке ввода-вывода логирует предупреждение и не бросает исключение,
        чтобы не прерывать основной поток публикации.

        Args:
            pages_map: Карта вида ``{comp_name: {version: {page_id, page_title, version}}}``.
        """
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(pages_map, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            logger.debug(
                'PassportPageRegistry: сохранено %d компонентов в %s',
                len(pages_map), self._file,
            )
        except OSError as e:
            logger.warning('PassportPageRegistry: не удалось сохранить файл: %s', e)

    def load(self) -> dict[str, Any]:
        """
        Загружает карту страниц паспортов с диска.

        При отсутствии файла или ошибке чтения/парсинга возвращает пустой
        словарь и логирует отладочное сообщение — это штатная ситуация
        при первом запуске без предварительной публикации паспортов.

        Returns:
            Загруженная карта или пустой словарь.
        """
        if not self._file.exists():
            logger.debug('PassportPageRegistry: файл не найден: %s', self._file)
            return {}
        try:
            data = json.loads(self._file.read_text(encoding='utf-8'))
            logger.debug('PassportPageRegistry: загружено %d компонентов', len(data))
            return data
        except (OSError, json.JSONDecodeError) as e:
            logger.debug('PassportPageRegistry: не удалось загрузить файл: %s', e)
            return {}

    @staticmethod
    def inject_links(
        view_model: dict[str, Any],
        passport_pages: dict[str, Any],
    ) -> None:
        """
        Вставляет ссылки на страницы паспортов в view-model релиза.

        Мутирует ``view_model`` на месте. Для каждого компонента из
        ``view_model['components']`` добавляет ключ ``passport_versions``,
        который содержит только те версии, что присутствуют в релизах
        данного компонента.

        Если ``view_model`` не содержит ключ ``'components'`` (например,
        в профиль-центричном виде) — ничего не делает.

        Args:
            view_model: Словарь, созданный трансформером. Изменяется на месте.
            passport_pages: Карта, загруженная через ``PassportPageRegistry.load()``.
        """
        if not passport_pages or 'components' not in view_model:
            return

        for comp in view_model.get('components', []):
            comp_name = comp.get('name')
            if not comp_name or comp_name not in passport_pages:
                continue
            release_versions = {rel.get('version') for rel in comp.get('releases', [])}
            comp['passport_versions'] = {
                v: info
                for v, info in passport_pages[comp_name].items()
                if v in release_versions
            }
