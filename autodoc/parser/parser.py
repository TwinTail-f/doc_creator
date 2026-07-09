"""
Точка входа парсера компонентов платформы.
"""

import json
import shutil
from pathlib import Path

from typing import Self

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.exceptions import DocGeneratorError, ParsingError
from autodoc.common.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.clients.artifactory_client import ArtifactoryClient
from autodoc.parser.clients.tfs_client import TFSClient
from autodoc.parser.steps.base_parse_step import BaseParseStep
from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.docker_step import DockerResolveStep
from autodoc.parser.steps.finalize_step import FinalizeStep
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.steps.options_step import OptionsResolveStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep


class ComponentParser:
    """
    Верхний уровень бизнес-логики парсера компонентов платформы.

    Составляет пайплайн из шагов и управляет их выполнением.
    Не содержит деталей реализации отдельных шагов — только оркестрацию.
    """

    def __init__(
        self,
        config: ParserConfigSchema,
        data_dir: Path,
        steps: list[BaseParseStep] | None = None,
        tfs_client: TFSClient | None = None,
        artifactory_client: ArtifactoryClient | None = None,
    ) -> None:
        """
        Args:
            config: Валидированная конфигурация парсера.
            data_dir: Корневая директория для временных и промежуточных файлов.
            steps: Список шагов пайплайна. ``None`` → ``_default_pipeline()``.
            tfs_client: Готовый экземпляр ``TFSClient``. ``None`` → создаётся
                        из ``config`` при каждом вызове ``parse()``.
            artifactory_client: Готовый экземпляр ``ArtifactoryClient``. ``None`` →
                                создаётся из ``config`` при каждом вызове ``parse()``.
        """
        self._config = config
        self._data_dir = data_dir
        self._tmp_dir = data_dir / "tmp"
        self._intermediate_dir = data_dir / "intermediate"
        self._steps: list[BaseParseStep] = (
            steps if steps is not None else ComponentParser._default_pipeline()
        )
        self._tfs_client: TFSClient | None = tfs_client
        self._artifactory_client: ArtifactoryClient | None = artifactory_client

    @staticmethod
    def _default_pipeline() -> list[BaseParseStep]:
        """
        Возвращает стандартный набор шагов пайплайна.

        Клиенты (TFS, Artifactory) не создаются здесь — они внедряются в
        ``PipelineContext`` самим ``ComponentParser.parse()``.

        Returns:
            Список шагов пайплайна в порядке выполнения.
        """
        return [
            ManifestStep(),
            OptionsResolveStep(),
            ConanEnrichStep(),
            DockerResolveStep(),
            ArtifactoryValidationStep(),
            FinalizeStep(),
        ]

    @classmethod
    def with_steps_excluded(
        cls,
        config: ParserConfigSchema,
        data_dir: Path,
        exclude: list[type],
    ) -> Self:
        """
        Фабричный метод: создаёт парсер без указанных классов шагов.

        Args:
            config: Валидированная конфигурация парсера.
            data_dir: Корневая директория для временных и промежуточных файлов.
            exclude: Список классов шагов, которые нужно исключить из пайплайна.

        Returns:
            Экземпляр ``ComponentParser`` с отфильтрованным пайплайном.
        """
        steps = [
            step
            for step in ComponentParser._default_pipeline()
            if not isinstance(step, tuple(exclude))
        ]
        return ComponentParser(config, data_dir, steps=steps)

    def parse(self, save_intermediate: bool = False) -> ParsedResult:
        """
        Запускает пайплайн и возвращает валидированный результат.

        Критические шаги при ошибке останавливают пайплайн.
        Некритические — логируют и продолжают.
        Временная директория очищается в ``finally``.

        Клиенты (TFS, Artifactory) создаются в начале каждого вызова,
        если не были переданы в конструктор, и живут ровно столько,
        сколько выполняется ``parse()``.

        Args:
            save_intermediate: Сохранять ли JSON-снимок после каждого шага.

        Returns:
            ``ParsedResult`` с данными всех компонентов.

        Raises:
            ParsingError: Если критический шаг завершился с ошибкой.
        """
        tfs_client = self._tfs_client or TFSClient(self._config)
        artifactory_client = self._artifactory_client or ArtifactoryClient(self._config)

        ctx = PipelineContext(
            config=self._config,
            tmp_dir=self._tmp_dir,
            tfs_client=tfs_client,
            artifactory_client=artifactory_client,
        )

        if save_intermediate:
            self._intermediate_dir.mkdir(parents=True, exist_ok=True)

        try:
            for step_idx, step in enumerate(self._steps):
                logger.info(f"ComponentParser → [{step.name}]…")
                try:
                    step.execute(ctx)
                    logger.info(f"ComponentParser ✓ [{step.name}]")
                except DocGeneratorError as exc:
                    if step.is_critical:
                        logger.error(f"ComponentParser ✗ [{step.name}] — критическая ошибка: {exc}")
                        raise ParsingError(
                            f"Критический шаг {step.name} завершился с ошибкой: {exc}"
                        ) from exc
                    logger.warning(
                        f"ComponentParser ⚠ [{step.name}] — некритическая ошибка (продолжаем): {exc}"
                    )

                if save_intermediate:
                    self._save_intermediate(ctx, step, step_idx)

        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            logger.debug("временная директория очищена.")

        if ctx.result is None:
            raise ParsingError("ComponentParser: FinalizeStep не заполнил ctx.result.")

        return ctx.result

    def _save_intermediate(self, ctx: PipelineContext, step: BaseParseStep, step_idx: int) -> None:
        """Сохраняет снимок промежуточного состояния контекста в JSON-файл."""
        safe_name = step.name.lower().replace(" ", "_").replace("/", "_")
        filepath = self._intermediate_dir / f"{step_idx + 1:02d}_{safe_name}.json"

        snapshot = {"step": step.name, **ctx.to_snapshot_dict()}

        try:
            filepath.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            logger.debug(f"сохранён снимок → {filepath.name}")
        except OSError as e:
            logger.warning(f"не удалось сохранить снимок {filepath}: {e}")
