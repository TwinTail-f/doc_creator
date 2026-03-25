"""
Менеджер Conan: параллельное выполнение задач и возврат результата для обогащения.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from autodoc.config.schemas import ParserConfigSchema
from autodoc.infrastructure.logger import logger
from autodoc.models.component import Component
from autodoc.parser.conan.conan_runner import BaseConanRunner, Conan2Runner, ConanRawResult
from autodoc.parser.conan.result_parser import ConanEnrichData, ConanResultParser
from autodoc.parser.conan.task_builder import ConanTask, ConanTaskBuilder
from autodoc.parser.conan.types import (
    ConanEnrichmentResult,
    ProfileConanData,
    ReleaseConanData,
    _ErrorLog,
)

_DEFAULT_MAX_WORKERS = 8


@dataclass
class _ReleaseUpdates:
    """
    Промежуточные данные обогащения одного Release, собранные из ответов Conan.

    Заменяет неструктурированный ``Dict[str, Any]`` в ``_PbAgg``.
    """

    base_ref: str
    rrev: str
    full_version: str
    default_options: list
    patches: list
    dependencies: list


class ConanManager:
    """
    Управляет выполнением ``conan graph info`` и возвращает ``ConanEnrichmentResult``.

    Не мутирует модели — мутацию выполняет ``DataEnricher.apply_conan_results()``.
    """

    def __init__(self, config: ParserConfigSchema) -> None:
        self._runner: BaseConanRunner = Conan2Runner(timeout=config.conan_command_timeout)
        self._task_builder = ConanTaskBuilder()
        self._result_parser = ConanResultParser()
        self._cache: Dict[str, ConanRawResult] = {}

    def clean_cache(self) -> None:
        """Очищает локальный кэш Conan и внутренний кэш менеджера."""
        self._runner.clean_cache()
        self._cache.clear()
        logger.debug('внутренний кеш сброшен.')

    def enrich_components(
        self,
        components: List[Component],
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
        tasks = self._task_builder.build(components, target_platform, artifactory_base_url)

        if not tasks:
            logger.info('нет задач для выполнения.')
            return ConanEnrichmentResult()

        logger.info(
            'ConanManager: сформировано %d задач, запуск в %d потоках…',
            len(tasks), _DEFAULT_MAX_WORKERS,
        )

        raw_results = self._run_tasks_parallel(tasks)
        return self._build_enrichment_result(tasks, raw_results, artifactory_base_url, target_platform)

    # ------------------------------------------------------------------

    def _run_tasks_parallel(self, tasks: List[ConanTask]) -> List[Optional[ConanRawResult]]:
        results: List[Optional[ConanRawResult]] = [None] * len(tasks)
        tasks_to_run: List[Tuple[int, ConanTask]] = []

        for idx, task in enumerate(tasks):
            cache_key = ' '.join(task.cmd)
            if cache_key in self._cache:
                results[idx] = self._cache[cache_key]
            else:
                tasks_to_run.append((idx, task))

        if not tasks_to_run:
            return results

        with ThreadPoolExecutor(max_workers=_DEFAULT_MAX_WORKERS) as executor:
            future_to_idx = {
                executor.submit(self._runner.run, task): idx
                for idx, task in tasks_to_run
            }

            completed = 0
            total = len(tasks_to_run)
            for future in as_completed(future_to_idx):
                completed += 1
                if completed % 50 == 0 or completed == total:
                    logger.info('прогресс %d/%d задач…', completed, total)

                idx = future_to_idx[future]
                raw = future.result()
                results[idx] = raw
                if raw.success:
                    self._cache[' '.join(raw.task.cmd)] = raw

        return results

    def _build_enrichment_result(
        self,
        tasks: List[ConanTask],
        raw_results: List[Optional[ConanRawResult]],
        art_base: str,
        target_platform: str,
    ) -> ConanEnrichmentResult:
        """Собирает ConanEnrichmentResult из сырых результатов без мутации моделей."""
        pb_agg: Dict[int, _PbAgg] = {id(task.pb): _PbAgg() for task in tasks}

        for task, raw in zip(tasks, raw_results):
            if raw is None:
                continue
            agg = pb_agg[id(task.pb)]
            if raw.success and raw.data:
                enrich = self._result_parser.parse(raw.data, task)
                if enrich:
                    agg.apply_enrich(enrich)
            else:
                agg.errors.append({' '.join(task.cmd): raw.error})

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
            release_key: Tuple[str, str, str] = (task.comp_name, task.version, task.channel)

            if agg.release_updates and release_key not in result.release_data:
                upd = agg.release_updates
                art_url = ''
                if art_base:
                    art_url = '%s/platform-%s/%s/%s/%s/%s' % (
                        art_base, target_platform,
                        task.comp_name, upd.full_version,
                        task.channel, upd.rrev,
                    )
                result.release_data[release_key] = ReleaseConanData(
                    base_ref=upd.base_ref,
                    rrev=upd.rrev,
                    full_version=upd.full_version,
                    default_options=upd.default_options,
                    patches=upd.patches,
                    dependencies=upd.dependencies,
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


class _PbAgg:
    """Внутренний агрегатор результатов по одному ProfileBuild."""

    __slots__ = ('any_success', 'unique_variants', 'release_updates', 'conan_settings', 'errors')

    def __init__(self) -> None:
        self.any_success = False
        self.conan_settings: Dict[str, Any] = {}
        self.unique_variants: Dict[str, Dict[str, Any]] = {}
        self.release_updates: Optional[_ReleaseUpdates] = None  # 3.14 датакласс вместо Dict
        self.errors: List[Dict] = []

    def apply_enrich(self, enrich: ConanEnrichData) -> None:
        self.any_success = True
        self.conan_settings = enrich.conan_settings

        if self.release_updates is None and enrich.base_ref:
            # 3.14 Строго типизированный датакласс вместо Dict[str, Any]
            self.release_updates = _ReleaseUpdates(
                base_ref=enrich.base_ref,
                rrev=enrich.rrev,
                full_version=enrich.full_version,
                default_options=enrich.default_options,
                patches=enrich.patches,
                dependencies=enrich.dependencies,
            )

        if enrich.package_id and enrich.package_id not in self.unique_variants:
            self.unique_variants[enrich.package_id] = {
                'package_id': enrich.package_id,
                'build_url': enrich.build_url,
                'build_date': enrich.build_date,
                'conan_options': enrich.conan_options,
            }


def _record_error(errors: _ErrorLog, task: ConanTask, task_errors: List[Dict]) -> None:
    n, v, ch, pr = task.comp_name, task.version, task.channel, task.profile_name
    errors.setdefault(n, {}).setdefault(v, {}).setdefault(ch, {})[pr] = task_errors
