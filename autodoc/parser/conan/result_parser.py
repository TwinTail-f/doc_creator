"""
Парсер JSON-ответа команды ``conan graph info``.
"""

import datetime
from pathlib import Path
from typing import Any

from autodoc.models.component import DefaultOptionsSet
from autodoc.parser.conan.task_builder import ConanTask
from autodoc.parser.conan.types import ConanEnrichData


class ConanResultParser:
    """
    Парсит JSON-ответ ``conan graph info`` в структурированные данные.

    Чистый класс без I/O — только преобразование данных.
    """

    def parse(
        self,
        conan_json: dict[str, Any],
        task: ConanTask,
    ) -> ConanEnrichData | None:
        """
        Извлекает данные о компоненте из JSON-графа зависимостей Conan.

        Args:
            conan_json: Разобранный JSON-ответ ``conan graph info``.
            task: Задача, для которой был получен ответ.

        Returns:
            ``ConanEnrichData`` если нода компонента найдена, иначе ``None``.
        """
        nodes: dict[str, Any] = conan_json.get("graph", {}).get("nodes", {})
        target_node = next(
            (n for n in nodes.values() if n.get("name") == task.comp_name),
            None,
        )
        if target_node is None:
            return None

        # Conan завершается с кодом 0 даже при отсутствии бинарного пакета —
        # проверяем поле binary явно. "Missing" означает, что собранного пакета
        # для этого профиля нет; считаем это неудачей и исключаем профиль.
        binary_status: str = target_node.get("binary", "")
        if binary_status == "Missing":
            return None

        base_ref, rrev, full_version = self._extract_ref_info(target_node, task.version)
        default_options = self._extract_default_options(target_node)
        patches = self._extract_patches(target_node)
        dependencies = self._extract_dependencies(nodes, task.comp_name)

        info_dict: dict[str, Any] = target_node.get("info", {})
        conan_settings: dict[str, Any] = info_dict.get(
            "settings", target_node.get("settings", {})
        )
        package_id = target_node.get("package_id", "")
        build_url = (
            self._build_artifactory_url(task, full_version, rrev, package_id)
            if package_id
            else ""
        )
        build_date = self._extract_build_date(target_node)

        # Поле "options" содержит финально разрешённые опции после применения
        # дефолтов и пользовательских переопределений — они попадают в TotalOptionsSet.
        conan_options: dict[str, Any] = info_dict.get(
            "options", target_node.get("options", {})
        )

        return ConanEnrichData(
            base_ref=base_ref,
            rrev=rrev,
            full_version=full_version,
            default_options=default_options,
            patches=patches,
            dependencies=dependencies,
            conan_settings=conan_settings,
            package_id=package_id,
            build_url=build_url,
            build_date=build_date,
            conan_options=conan_options,
            option_id=task.option_id,
        )

    def _extract_ref_info(self, 
        node: dict[str, Any],
        fallback_version: str,
    ) -> tuple[str, str, str]:
        """
        Извлекает base_ref, rrev и полную версию из узла графа Conan.

        Conan сериализует ссылку в двух полях: ``ref`` (полная ссылка, включая ``#rrev``)
        и ``rrev`` (отдельным полем). Метод поддерживает оба варианта.

        Args:
            node: Словарь узла из JSON-ответа ``conan graph info``.
            fallback_version: Версия из задачи — используется, если ref отсутствует.

        Returns:
            Кортеж ``(base_ref, rrev, full_version)``:
            - ``base_ref`` — ссылка без ``#rrev`` (например ``name/ver@user/channel``);
            - ``rrev`` — recipe revision;
            - ``full_version`` — версия компонента, извлечённая из ref или fallback.
        """
        full_ref: str = node.get("ref", "")
        rrev: str = node.get("rrev", "")
        full_version = fallback_version

        if not full_ref:
            return "", rrev, full_version

        base_ref = full_ref.split("#")[0]
        if not rrev and "#" in full_ref:
            rrev = full_ref.split("#")[1]
        if "@" in base_ref and "/" in base_ref.split("@")[0]:
            full_version = base_ref.split("@")[0].split("/")[1]

        return base_ref, rrev, full_version

    def _extract_default_options(self, node: dict[str, Any]) -> list[DefaultOptionsSet]:
        """Извлекает поле default_options → list[DefaultOptionsSet]."""
        opt_defs: dict[str, Any] = node.get("options_definitions", {}) or {}
        def_opts: dict[str, Any] = node.get("default_options", {}) or {}
        result: list[DefaultOptionsSet] = []

        for opt_name, opt_val in def_opts.items():
            opt_type = "string"
            definition = opt_defs.get(opt_name)
            if isinstance(definition, list) and len(definition) >= 2:
                if "ANY" in definition:
                    opt_type = "ANY"
                elif set(definition).issubset(
                    {"True", "False", True, False, "None", None}
                ):
                    opt_type = "bool"
                else:
                    opt_type = "enum"
            result.append(
                DefaultOptionsSet(name=opt_name, type=opt_type, default_value=opt_val)
            )

        return result

    def _extract_patches(self, node: dict[str, Any]) -> list[str]:
        """Извлекает имена всех патч-файлов из conandata -> patches.

        Обходит **все** ключи словаря patches (версии, строки вроде "all",
        "KasperskyOS" и т.п.) и собирает имена файлов без учёта ключа.
        Дубликаты удаляются с сохранением порядка первого вхождения.
        """
        patches_dict: dict[str, Any] = node.get("conandata", {}).get("patches", {})
        if not isinstance(patches_dict, dict):
            return []

        extracted: list[str] = []
        for patch_list in patches_dict.values():
            if not isinstance(patch_list, list):
                continue
            for p in patch_list:
                if not isinstance(p, dict):
                    continue
                patch_file = p.get("patch_file", "")
                if patch_file:
                    extracted.append(Path(patch_file).name)

        return list(dict.fromkeys(extracted))

    def _extract_dependencies(self, nodes: dict[str, Any], comp_name: str) -> list[str]:
        """Собирает имена всех пакетов из графа зависимостей, кроме самого
        компонента и виртуальной ноды conanfile.

        Обходит все узлы графа (включая транзитивные зависимости), а не только
        прямые зависимости целевого узла.
        """
        deps: list[str] = []
        for node in nodes.values():
            name: str = node.get("name", "")
            if not name or name == comp_name or name == "conanfile":
                continue
            ref: str = node.get("ref", "")
            if ref:
                dep_name = ref.split("/")[0]
                if dep_name and dep_name != comp_name:
                    deps.append(dep_name)
        return sorted(set(deps))

    def _build_artifactory_url(self, 
        task: ConanTask, full_version: str, rrev: str, package_id: str = ""
    ) -> str:
        """
        Строит URL пакета в Artifactory для данного варианта сборки.

        Возвращает пустую строку, если ``task.artifactory_base_url`` не задан
        или ``rrev`` пуст — в этих случаях URL сформировать невозможно.

        Args:
            task: Задача Conan с метаданными компонента и URL Artifactory.
            full_version: Полная версия компонента (из ref или fallback).
            rrev: Recipe revision.
            package_id: Идентификатор конкретного бинарного пакета.
                        Если задан — добавляется суффикс ``/package/<id>``.

        Returns:
            Полный URL пакета в Artifactory или пустая строка.
        """
        if not task.artifactory_base_url or not rrev:
            return ""
        url = (
            f"{task.artifactory_base_url}/platform-{task.target_platform}"
            f"/{task.comp_name}/{full_version}/{task.channel}/{rrev}"
        )
        if package_id:
            url += f"/package/{package_id}"
        return url

    def _extract_build_date(self, node: dict[str, Any]) -> str:
        """
        Извлекает дату сборки пакета из поля ``prev_timestamp`` узла.

        ``prev_timestamp`` — POSIX-время последнего изменения recipe revision в Artifactory.
        Конвертируется в ISO 8601 UTC строку. При любой ошибке конвертации (невалидное
        значение, переполнение) возвращает пустую строку — это не критично для пайплайна.

        Args:
            node: Словарь узла из JSON-ответа ``conan graph info``.

        Returns:
            Дата в формате ISO 8601 (UTC) или пустая строка, если поле отсутствует или
            содержит невалидное значение.
        """
        prev_timestamp = node.get("prev_timestamp")
        if not prev_timestamp:
            return ""
        try:
            return datetime.datetime.fromtimestamp(
                float(prev_timestamp), datetime.timezone.utc
            ).isoformat()
        except (ValueError, OSError, OverflowError):
            return ""