"""
Точка входа парсера компонентов платформы.
"""
import json
import shutil
from pathlib import Path

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import ParsingError
from autodoc.infrastructure.logger import logger
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.steps.base import BaseParseStep, PipelineContext
from autodoc.parser.steps.conan_step import ConanEnrichStep
from autodoc.parser.steps.docker_step import DockerResolveStep
from autodoc.parser.steps.finalize_step import FinalizeStep
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.steps.options_step import OptionsResolveStep
from autodoc.parser.steps.validation_step import ArtifactoryValidationStep

def default_pipeline() -> list[BaseParseStep]:
    """Возвращает стандартный набор шагов пайплайна в порядке выполнения."""
    return [
        ManifestStep(),
        OptionsResolveStep(),
        ConanEnrichStep(),
        DockerResolveStep(),
        ArtifactoryValidationStep(),
        FinalizeStep(),
    ]

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
        steps: list[BaseParseStep | None] = None,  # 3.6 явный тип
    ) -> None:
        """
        Args:
            config: Валидированная конфигурация парсера.
            data_dir: Корневая директория для временных и промежуточных файлов.
            steps: Список шагов пайплайна. ``None`` → ``default_pipeline()``.
        """
        self._config = config
        self._data_dir = data_dir
        self._tmp_dir = data_dir / 'tmp'
        self._intermediate_dir = data_dir / 'intermediate'
        self._steps: list[BaseParseStep] = (
            steps if steps is not None else default_pipeline()
        )

    @classmethod
    def with_steps_excluded(
        cls,
        config: ParserConfigSchema,
        data_dir: Path,
        exclude: list[type],
    ) -> 'ComponentParser':
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

        Args:
            save_intermediate: Сохранять ли JSON-снимок после каждого шага.

        Returns:
            ``ParsedResult`` с данными всех компонентов.

        Raises:
            ParsingError: Если критический шаг завершился с ошибкой.
        """
        ctx = PipelineContext(
            config=self._config,
            tmp_dir=self._tmp_dir,
        )

        if save_intermediate:
            self._intermediate_dir.mkdir(parents=True, exist_ok=True)

        try:
            for step in self._steps:
                logger.info('ComponentParser → [%s]…', step.name)
                try:
                    step.execute(ctx)
                    logger.info('ComponentParser ✓ [%s]', step.name)
                except Exception as exc:
                    if step.is_critical:
                        logger.error(
                            'ComponentParser ✗ [%s] — критическая ошибка: %s',
                            step.name, exc,
                        )
                        raise ParsingError(
                            'Критический шаг "%s" завершился с ошибкой: %s'
                            % (step.name, exc)
                        ) from exc
                    logger.warning(
                        'ComponentParser ⚠ [%s] — некритическая ошибка (продолжаем): %s',
                        step.name, exc,
                    )

                if save_intermediate:
                    self._save_intermediate(ctx, step.name)

        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            logger.debug('временная директория очищена.')

        if ctx.result is None:
            raise ParsingError('ComponentParser: FinalizeStep не заполнил ctx.result.')

        return ctx.result

    def _save_intermediate(self, ctx: PipelineContext, step_name: str) -> None:
        """Сохраняет снимок промежуточного состояния контекста в JSON-файл."""
        step_idx = next(
            (i for i, s in enumerate(self._steps) if s.name == step_name), 0
        )
        safe_name = step_name.lower().replace(' ', '_').replace('/', '_')
        filepath = self._intermediate_dir / ('%02d_%s.json' % (step_idx + 1, safe_name))

        snapshot = {
            'step': step_name,
            'components_count': len(ctx.components),
            # 3.15 docker_links доступен через intermediate
            'docker_links_count': len(ctx.intermediate.get('docker_links', {})),
            'intermediate_keys': list(ctx.intermediate.keys()),
        }

        try:
            filepath.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False, default=str),
                encoding='utf-8',
            )
            logger.debug('сохранён снимок → %s', filepath.name)
        except OSError as e:
            logger.warning('не удалось сохранить снимок %s: %s', filepath, e)
