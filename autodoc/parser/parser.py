"""
Точка входа парсера компонентов платформы.
"""

import json
import shutil
from pathlib import Path

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import DocGeneratorError, ParsingError
from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.clients.artifactory_client import ArtifactoryClient
from autodoc.parser.clients.tfs_client import TFSClient
from autodoc.parser.steps.base import BaseParseStep, PipelineContext
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.docker_step import DockerResolveStep
from autodoc.parser.steps.finalize_step import FinalizeStep
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.steps.options_step import OptionsResolveStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep


def default_pipeline() -> list[BaseParseStep]:
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


def _serialize_intermediate(intermediate: dict) -> dict:
    """Конвертирует intermediate-данные в JSON-совместимый вид.

    Tuple-ключи (например в options_map) преобразуются в строки вида
    "comp::version::channel", чтобы json.dumps не падал с TypeError.
    docker_links пропускается — он большой и не нужен в снимке.
    """
    result = {}
    for k, v in intermediate.items():
        if k == "docker_links":
            continue
        if isinstance(v, dict):
            result[k] = {
                "::".join(ik) if isinstance(ik, tuple) else ik: iv
                for ik, iv in v.items()
            }
        else:
            result[k] = v
    return result


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
            steps: Список шагов пайплайна. ``None`` → ``default_pipeline()``.
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
            steps if steps is not None else default_pipeline()
        )
        self._tfs_client = tfs_client
        self._artifactory_client = artifactory_client

    @classmethod
    def with_steps_excluded(
        cls,
        config: ParserConfigSchema,
        data_dir: Path,
        exclude: list[type],
    ) -> "ComponentParser":
        """
        Фабричный метод: создаёт парсер без указанных классов шагов.

        Args:
            config: Валидированная конфигурация парсера.
            data_dir: Корневая директория для временных и промежуточных файлов.
            exclude: Список классов шагов, которые нужно исключить из пайплайна.

        Returns:
            Экземпляр ``ComponentParser`` с отфильтрованным пайплайном.
        """
        steps = [s for s in default_pipeline() if not isinstance(s, tuple(exclude))]
        return cls(config, data_dir, steps=steps)

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
            for step in self._steps:
                logger.info(f"ComponentParser → [{step.name}]…")
                try:
                    step.execute(ctx)
                    logger.info(f"ComponentParser ✓ [{step.name}]")
                except DocGeneratorError as exc:
                    if step.is_critical:
                        logger.error(
                            f"ComponentParser ✗ [{step.name}] — критическая ошибка: {exc}"
                        )
                        raise ParsingError(
                            f"Критический шаг {step.name!r} завершился с ошибкой: {exc}"
                        ) from exc
                    logger.warning(
                        f"ComponentParser ⚠ [{step.name}] — некритическая ошибка (продолжаем): {exc}"
                    )

                if save_intermediate:
                    self._save_intermediate(ctx, step.name)

        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            logger.debug("временная директория очищена.")

        if ctx.result is None:
            raise ParsingError("ComponentParser: FinalizeStep не заполнил ctx.result.")

        return ctx.result

    def _save_intermediate(self, ctx: PipelineContext, step_name: str) -> None:
        """Сохраняет снимок промежуточного состояния контекста в JSON-файл."""
        step_idx = next(
            (i for i, s in enumerate(self._steps) if s.name == step_name), -1
        )
        if step_idx == -1:
            logger.warning(
                f"шаг {step_name!r} не найден в списке шагов, снимок пропущен"
            )
            return

        safe_name = step_name.lower().replace(" ", "_").replace("/", "_")
        filepath = self._intermediate_dir / f"{step_idx + 1:02d}_{safe_name}.json"

        snapshot = {
            "step": step_name,
            "components_count": len(ctx.components),
            "intermediate_keys": list(ctx.intermediate.keys()),
            "components": [c.model_dump() for c in ctx.components],
            "intermediate": _serialize_intermediate(ctx.intermediate),
            "docker_links_count": len(ctx.intermediate.get("docker_links", {})),
        }

        try:
            filepath.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            logger.debug(f"сохранён снимок → {filepath.name}")
        except OSError as e:
            logger.warning(f"не удалось сохранить снимок {filepath}: {e}")
