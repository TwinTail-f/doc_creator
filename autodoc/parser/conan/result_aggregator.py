"""
Агрегатор результатов Conan graph info.

Принимает сырые результаты параллельного выполнения команд и собирает
``ConanEnrichmentResult``, готовый для передачи в ``DataEnricher``.

Выделен из ``ConanManager`` в отдельный слой, чтобы каждый этап пайплайна
имел единственную ответственность:
- ``ConanFetcher``          — сбор сырых данных (запуск subprocess в параллель);
- ``ConanResultParser``     — парсинг одного JSON-ответа;
- ``ConanResultAggregator`` — агрегация N результатов → ``ConanEnrichmentResult``.
"""

from typing import Any

from autodoc.models.conan_enrichment_result import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
    _ErrorLog,
)
from autodoc.models.conan_raw_result import ConanCommandRecord, ConanRawResult
from autodoc.models.conan_report import ConanComponentReport, ConanProfileReport
from autodoc.models.conan_variant import ConanVariant
from autodoc.models.options import TotalOptionsSet
from autodoc.parser.conan.result_parser import ConanResultParser
from autodoc.parser.conan.conan_task import ConanTask
from autodoc.parser.conan.conan_enrich_data import ConanEnrichData


class ConanResultAggregator:
    """
    Агрегирует список сырых результатов ``conan graph info`` в ``ConanEnrichmentResult``.

    Чистый класс без I/O — только трансформация данных.
    Легко тестируется без запуска Conan или параллельного исполнителя.
    """

    def __init__(self, result_parser: ConanResultParser | None = None) -> None:
        """
        Args:
            result_parser: Парсер одного JSON-ответа. Если не передан — создаётся
                           экземпляр по умолчанию.
        """
        self._result_parser = result_parser or ConanResultParser()

    def aggregate(
        self,
        tasks: list[ConanTask],
        raw_results: list[ConanRawResult | None],
        art_base: str,
        target_platform: str,
    ) -> ConanEnrichmentResult:
        """
        Собирает ``ConanEnrichmentResult`` из сырых результатов параллельного выполнения.

        Не мутирует переданные модели — только формирует структуру данных
        для последующей передачи в ``DataEnricher.apply_conan_results()``.

        Args:
            tasks: Список задач в том же порядке, что и ``raw_results``.
            raw_results: Сырые результаты параллельного выполнения.
            art_base: Базовый URL Artifactory (без завершающего слэша).
            target_platform: Целевая платформа (используется в URL пакета).

        Returns:
            ``ConanEnrichmentResult`` с заполненными ``release_data`` и
            ``profile_data``.
        """
        pb_agg: dict[int, _ProfileBuildAggregator] = {
            id(task.pb): _ProfileBuildAggregator() for task in tasks
        }

        for task, raw in zip(tasks, raw_results):
            if raw is None:
                continue
            agg = pb_agg[id(task.pb)]
            if raw.success and raw.data:
                enrich = self._result_parser.parse(raw.data, task)
                if enrich:
                    agg.apply_enrich(enrich)
                else:
                    # Команда завершилась с кодом 0, но бинарный пакет отсутствует
                    # (Binary: Missing) — профиль считается недоступным.
                    agg.errors.append(
                        {
                            " ".join(
                                task.cmd
                            ): "Бинарный пакет не найден (Missing) для этого профиля."
                        }
                    )
            else:
                agg.errors.append({" ".join(task.cmd): raw.error})

        result = ConanEnrichmentResult(
            total_tasks=len(tasks),
            succeeded=sum(1 for r in raw_results if r and r.success),
        )
        result.failed = result.total_tasks - result.succeeded

        release_deps: dict[tuple[str, str, str], set[str]] = {}
        release_patches: dict[tuple[str, str, str], set[str]] = {}

        release_resolved_options: dict[
            tuple[str, str, str], dict[str, dict[str, Any]]
        ] = {}

        for task in tasks:
            release_key_pre: tuple[str, str, str] = (
                task.comp_name,
                task.version,
                task.channel,
            )
            release_deps.setdefault(release_key_pre, set()).update(
                pb_agg[id(task.pb)].all_dependencies
            )
            release_patches.setdefault(release_key_pre, set()).update(
                pb_agg[id(task.pb)].all_patches
            )
            merged_opts = release_resolved_options.setdefault(release_key_pre, {})
            for opt_id, opts in pb_agg[id(task.pb)].resolved_options_by_id.items():
                if opt_id not in merged_opts:
                    merged_opts[opt_id] = opts

        visited_pbs: set[int] = set()
        for task in tasks:
            pb_id = id(task.pb)
            if pb_id in visited_pbs:
                continue
            visited_pbs.add(pb_id)

            agg = pb_agg[pb_id]
            release_key: tuple[str, str, str] = (
                task.comp_name,
                task.version,
                task.channel,
            )

            if agg.first_enrich and release_key not in result.release_data:
                fe = agg.first_enrich
                art_url = ""
                if art_base:
                    art_url = (
                        f"{art_base}/platform-{target_platform}"
                        f"/{task.comp_name}/{fe.full_version}/{task.channel}/{fe.rrev}"
                    )

                total_options = [
                    TotalOptionsSet(id=opt_id, options=opts)
                    for opt_id, opts in release_resolved_options.get(
                        release_key, {}
                    ).items()
                ]
                result.release_data[release_key] = ReleaseConanData(
                    base_ref=fe.base_ref,
                    rrev=fe.rrev,
                    full_version=fe.full_version,
                    default_options=fe.default_options,
                    total_options=total_options,
                    patches=sorted(release_patches.get(release_key, set())),
                    dependencies=sorted(release_deps.get(release_key, set())),
                    artifactory_url=art_url,
                )

            result.profile_data[pb_id] = ProfileConanData(
                conan_settings=agg.conan_settings,
                exists=agg.any_success,
                variants=list(agg.unique_variants.values()),
            )

            if not agg.any_success:
                _record_error(result.errors, task, agg.errors)

        return result

    def build_execution_report(
        self,
        tasks: list[ConanTask],
        raw_results: list[ConanRawResult | None],
    ) -> list[ConanComponentReport]:
        """
        Строит диагностический отчёт по каждому вызову ``conan graph info``.

        Группирует записи по ключу (component, version, channel) → profile_name.
        Порядок компонентов соответствует порядку задач.

        Args:
            tasks: Список задач в том же порядке, что и ``raw_results``.
            raw_results: Сырые результаты параллельного выполнения.

        Returns:
            Список ``ConanComponentReport``, упорядоченный по компонентам.
        """
        comp_map: dict[tuple[str, str, str], ConanComponentReport] = {}

        for task, raw in zip(tasks, raw_results):
            key = (task.comp_name, task.version, task.channel)
            comp_report = comp_map.setdefault(
                key,
                ConanComponentReport(
                    component=task.comp_name,
                    version=task.version,
                    channel=task.channel,
                ),
            )

            profile_report = comp_report.profiles.setdefault(
                task.profile_name,
                ConanProfileReport(profile_name=task.profile_name),
            )

            if raw is None:
                record = ConanCommandRecord(
                    command=" ".join(task.cmd),
                    status="FAILED",
                    error="Результат не получен (внутренняя ошибка).",
                )
            elif raw.success:
                binary_status = self._extract_binary_status(raw.data, task.comp_name)
                if binary_status == "Missing":
                    record = ConanCommandRecord(
                        command=" ".join(task.cmd),
                        status="BINARY_MISSING",
                        error="ПРЕДУПРЕЖДЕНИЕ: Бинарный пакет не найден (Missing) для этого профиля.",
                    )
                else:
                    record = ConanCommandRecord(
                        command=" ".join(task.cmd),
                        status="SUCCESS",
                    )
            else:
                record = ConanCommandRecord(
                    command=" ".join(task.cmd),
                    status="FAILED",
                    error=raw.error,
                )

            profile_report.commands.append(record)

        return list(comp_map.values())

    def _extract_binary_status(self, data: dict[str, Any] | None, comp_name: str) -> str:
        """
        Извлекает поле ``binary`` целевого узла из JSON-ответа ``conan graph info``.

        Conan завершается с кодом 0 даже когда бинарный пакет отсутствует,
        помечая узел полем ``"binary": "Missing"``.

        Args:
            data: Разобранный JSON-ответ. Может быть ``None``.
            comp_name: Имя компонента — используется для поиска нужного узла.

        Returns:
            Строка статуса (например ``"Missing"``, ``"Download"``, ``"Cache"``)
            или пустая строка, если узел не найден или данные недоступны.
        """
        if not data:
            return ""
        nodes = data.get("graph", {}).get("nodes", {})
        target = next((n for n in nodes.values() if n.get("name") == comp_name), None)
        return target.get("binary", "") if target else ""


class _ProfileBuildAggregator:
    """Внутренний агрегатор результатов по одному ProfileBuild."""

    __slots__ = (
        "any_success",
        "unique_variants",
        "first_enrich",
        "conan_settings",
        "errors",
        "resolved_options_by_id",
        "all_dependencies",
        "all_patches",
    )

    def __init__(self) -> None:
        """
        Инициализирует пустой агрегатор для одного ``ProfileBuild``.

        Attributes собираются постепенно через ``apply_enrich()``:
            any_success: Флаг — хотя бы один вызов conan для данного ProfileBuild успешен.
            conan_settings: Настройки Conan из последнего успешного вызова.
            unique_variants: Уникальные варианты сборки (package_id → ConanVariant).
            first_enrich: Первый успешный EnrichData с непустым base_ref.
            errors: Список записей об ошибках (команда → сообщение).
            resolved_options_by_id: option_id → resolved-словарь опций Conan.
            all_dependencies: Объединение зависимостей всех успешных задач.
            all_patches: Объединение патчей всех успешных задач.
        """
        self.any_success: bool = False
        self.conan_settings: dict[str, Any] = {}
        self.unique_variants: dict[str, ConanVariant] = {}
        self.first_enrich: ConanEnrichData | None = None
        self.errors: list[dict[str, Any]] = []
        self.resolved_options_by_id: dict[str, dict[str, Any]] = {}
        self.all_dependencies: set[str] = set()
        self.all_patches: set[str] = set()

    def apply_enrich(self, enrich: ConanEnrichData) -> None:
        """
        Применяет данные одной завершённой задачи к агрегатору.

        Обновляет настройки Conan, фиксирует первый успешный EnrichData при
        наличии base_ref, сохраняет resolved-опции (из поля ``options`` conan
        graph info) по ``option_id`` и добавляет вариант сборки в
        ``unique_variants``.

        Args:
            enrich: Структурированные данные из разобранного ответа Conan.
        """
        self.any_success = True
        self.conan_settings = enrich.conan_settings

        if self.first_enrich is None and enrich.base_ref:
            self.first_enrich = enrich

        if enrich.option_id and enrich.option_id not in self.resolved_options_by_id:
            self.resolved_options_by_id[enrich.option_id] = enrich.conan_options

        self.all_dependencies.update(enrich.dependencies)
        self.all_patches.update(enrich.patches)

        if enrich.package_id and enrich.package_id not in self.unique_variants:
            self.unique_variants[enrich.package_id] = ConanVariant(
                package_id=enrich.package_id,
                build_url=enrich.build_url,
                build_date=enrich.build_date,
                options_ref=enrich.option_id,
            )


def _record_error(errors: _ErrorLog, task: ConanTask, task_errors: list[dict]) -> None:
    """
    Добавляет запись об ошибке в структурированный лог ошибок.

    Args:
        errors: Вложенный словарь ошибок ``{comp: {version: {channel: {profile: [errs]}}}}``.
        task: Задача, при выполнении которой возникли ошибки.
        task_errors: Список записей об ошибках для данной задачи.
    """
    n, v, ch, pr = task.comp_name, task.version, task.channel, task.profile_name
    errors.setdefault(n, {}).setdefault(v, {}).setdefault(ch, {})[pr] = task_errors
