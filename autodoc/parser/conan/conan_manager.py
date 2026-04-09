"""
Менеджер Conan: параллельное выполнение задач и возврат результата для обогащения.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from autodoc.config.schemas import ParserConfigSchema
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component
from autodoc.parser.conan.conan_result import ConanRawResult
from autodoc.parser.conan.conan_runner import BaseConanRunner, Conan2Runner
from autodoc.parser.conan.result_parser import ConanEnrichData, ConanResultParser
from autodoc.parser.conan.task_builder import ConanTask, ConanTaskBuilder
from autodoc.models.conan_result import (
    ConanEnrichmentResult,
    ConanCommandRecord,
    ConanComponentReport,
    ConanProfileReport,
    ProfileConanData,
    ReleaseConanData,
    _ErrorLog,
)

_DEFAULT_MAX_WORKERS: int = 64


class ConanManager:
    """
    Управляет выполнением ``conan graph info`` и возвращает ``ConanEnrichmentResult``.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        """
        Инициализирует менеджер с runner, task builder и result parser.

        Args:
            config: Валидированная конфигурация парсера. Используется для
                    настройки таймаута команды Conan.
        """
        self._runner: BaseConanRunner = Conan2Runner(
            timeout=config.conan_command_timeout
        )
        self._task_builder = ConanTaskBuilder()
        self._result_parser = ConanResultParser()

    def clean_cache(self) -> None:
        """Очищает локальный кэш Conan."""
        self._runner.clean_cache()

    def enrich_components(
        self,
        components: list[Component],
        target_platform: str,
        artifactory_base_url: str,
    ) -> ConanEnrichmentResult:
        """
        Выполняет Conan graph info для всех компонентов.

        Возвращает ``ConanEnrichmentResult`` — не мутирует входные модели.

        Args:
            components: Список компонентов.
            target_platform: Целевая платформа.
            artifactory_base_url: Базовый URL Artifactory.

        Returns:
            ``ConanEnrichmentResult`` с данными для обогащения.
        """
        tasks = self._task_builder.build(
            components, target_platform, artifactory_base_url
        )

        if not tasks:
            logger.info("Нет задач для выполнения.")
            return ConanEnrichmentResult()

        logger.info(
            f"сформировано {len(tasks)} задач, запуск в {_DEFAULT_MAX_WORKERS} потоках…"
        )

        raw_results = self._run_tasks_parallel(tasks)
        result = self._build_enrichment_result(
            tasks, raw_results, artifactory_base_url, target_platform
        )
        result.execution_report = self._build_execution_report(tasks, raw_results)
        return result

    def _run_tasks_parallel(
        self, tasks: list[ConanTask]
    ) -> list[ConanRawResult | None]:
        """
        Выполняет задачи Conan параллельно через ``ThreadPoolExecutor``.

        Логирует прогресс каждые 50 задач и по завершении.

        Args:
            tasks: Список задач для выполнения.

        Returns:
            Список сырых результатов ``ConanRawResult`` в том же порядке,
            что и входные задачи.
        """
        results: list[ConanRawResult | None] = [None] * len(tasks)

        with ThreadPoolExecutor(max_workers=_DEFAULT_MAX_WORKERS) as executor:
            future_to_idx = {
                executor.submit(self._runner.run, task): idx
                for idx, task in enumerate(tasks)
            }

            completed = 0
            total = len(tasks)
            for future in as_completed(future_to_idx):
                completed += 1
                if completed % 50 == 0 or completed == total:
                    logger.info(f"Прогресс {completed}/{total} задач…")

                idx = future_to_idx[future]
                results[idx] = future.result()

        return results

    def _build_execution_report(
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
        # (comp, version, channel) → ConanComponentReport
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
                # Check whether the binary was actually found — conan exits 0 even
                # when the binary is Missing, so we need to inspect the JSON.
                binary_status = self._extract_binary_status(raw.data, task.comp_name)
                if binary_status == "Missing":
                    record = ConanCommandRecord(
                        command=" ".join(task.cmd),
                        status="BINARY_MISSING",
                        error="WARNING: Binary not found (Missing) for this profile.",
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

    def _build_enrichment_result(
        self,
        tasks: list[ConanTask],
        raw_results: list[ConanRawResult | None],
        art_base: str,
        target_platform: str,
    ) -> ConanEnrichmentResult:
        """Собирает ConanEnrichmentResult из сырых результатов без мутации моделей."""
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
                    # Command exited 0 but the binary is Missing for this profile —
                    # treat as a failed lookup so the profile is excluded.
                    agg.errors.append(
                        {" ".join(task.cmd): "Binary not found (Missing) for this profile."}
                    )
            else:
                agg.errors.append({" ".join(task.cmd): raw.error})

        result = ConanEnrichmentResult(
            total_tasks=len(tasks),
            succeeded=sum(1 for r in raw_results if r and r.success),
        )
        result.failed = result.total_tasks - result.succeeded

        visited_pbs: set = set()
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
                result.release_data[release_key] = ReleaseConanData(
                    base_ref=fe.base_ref,
                    rrev=fe.rrev,
                    full_version=fe.full_version,
                    default_options=fe.default_options,
                    patches=fe.patches,
                    dependencies=fe.dependencies,
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


    @staticmethod
    def _extract_binary_status(data: dict | None, comp_name: str) -> str:
        """
        Извлекает поле ``binary`` целевого узла из JSON-ответа ``conan graph info``.

        Conan завершается с кодом 0 даже когда бинарный пакет отсутствует,
        помечая узел полем ``"binary": "Missing"``. Этот метод используется
        для диагностического отчёта, чтобы правильно пометить такие вызовы
        статусом ``BINARY_MISSING`` вместо ``SUCCESS``.

        Args:
            data: Разобранный JSON-ответ ``conan graph info``. Может быть ``None``.
            comp_name: Имя компонента — используется для поиска нужного узла.

        Returns:
            Строка статуса (например ``"Missing"``, ``"Download"``, ``"Cache"``)
            или пустая строка, если узел не найден или данные недоступны.
        """
        if not data:
            return ""
        nodes = data.get("graph", {}).get("nodes", {})
        target = next(
            (n for n in nodes.values() if n.get("name") == comp_name), None
        )
        return target.get("binary", "") if target else ""


class _ProfileBuildAggregator:
    """Внутренний агрегатор результатов по одному ProfileBuild."""

    __slots__ = (
        "any_success",
        "unique_variants",
        "first_enrich",
        "conan_settings",
        "errors",
    )

    def __init__(self) -> None:
        self.any_success = False
        self.conan_settings: dict[str, Any] = {}
        self.unique_variants: dict[str, dict[str, Any]] = {}
        self.first_enrich: ConanEnrichData | None = None
        self.errors: list[dict[str, Any]] = []

    def apply_enrich(self, enrich: ConanEnrichData) -> None:
        """
        Применяет данные одной завершённой задачи к агрегатору.

        Обновляет настройки Conan, фиксирует первый успешный EnrichData при
        наличии base_ref и добавляет вариант сборки в ``unique_variants``.

        Args:
            enrich: Структурированные данные из разобранного ответа Conan.
        """
        self.any_success = True
        self.conan_settings = enrich.conan_settings

        if self.first_enrich is None and enrich.base_ref:
            self.first_enrich = enrich

        if enrich.package_id and enrich.package_id not in self.unique_variants:
            self.unique_variants[enrich.package_id] = {
                "package_id": enrich.package_id,
                "build_url": enrich.build_url,
                "build_date": enrich.build_date,
                "conan_options": enrich.conan_options,
            }


def _record_error(errors: _ErrorLog, task: ConanTask, task_errors: list[dict]) -> None:
    """
    Добавляет запись об ошибке в структурированный лог ошибок.

    Гарантирует наличие всех промежуточных ключей в словаре с помощью
    ``setdefault``.

    Args:
        errors: Вложенный словарь ошибок ``{comp: {version: {channel: {profile: [errs]}}}}``.
        task: Задача, при выполнении которой возникли ошибки.
        task_errors: Список записей об ошибках для данной задачи.
    """
    n, v, ch, pr = task.comp_name, task.version, task.channel, task.profile_name
    errors.setdefault(n, {}).setdefault(v, {}).setdefault(ch, {})[pr] = task_errors
