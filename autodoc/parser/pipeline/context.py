"""
Контекст выполнения пайплайна парсера.

Вынесен в отдельный модуль ``pipeline/context.py``, чтобы он не принадлежал
ни слою шагов (``steps/``), ни слою фетчеров (``fetchers/``).
Это делает граф зависимостей однонаправленным:

    pipeline/context.py  ←  config, models, clients   (ни от кого не зависит)
    fetchers/*.py        →  pipeline/context.py
    steps/base.py        →  pipeline/context.py  +  fetchers/base.py
    steps/*.py           →  pipeline/context.py  +  steps/base.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autodoc.config.schemas import ParserConfigSchema
from autodoc.models.component import Component, ProfileDefinition
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.clients.protocols import IArtifactoryClient, ITFSClient


@dataclass
class PipelineContext:
    """
    Контекст выполнения пайплайна парсера.

    Единственный канал передачи состояния между шагами.
    Каждый шаг читает нужные данные и записывает результат своей работы.

    Поле ``docker_links`` отсутствует намеренно — после переноса
    ``apply_docker_links`` в ``DockerResolveStep`` оно больше не используется
    следующими шагами. При необходимости диагностики данные доступны через
    ``ctx.intermediate['docker_links']``.

    Attributes:
        config: Валидированная конфигурация парсера.
        tmp_dir: Временная директория для промежуточных файлов.
        tfs_client: Реализация ``ITFSClient``, внедряется ``ComponentParser`` перед запуском пайплайна.
        artifactory_client: Реализация ``IArtifactoryClient``, внедряется ``ComponentParser``.
        components: Список компонентов, накапливаемый шагами пайплайна.
        result: Финальный результат, заполняется ``FinalizeStep``.
        intermediate: Произвольные данные для диагностики и передачи между шагами.
    """

    config: ParserConfigSchema
    tmp_dir: Path
    tfs_client: ITFSClient | None = None
    artifactory_client: IArtifactoryClient | None = None
    components: list[Component] = field(default_factory=list)
    result: ParsedResult | None = None
    intermediate: dict[str, Any] = field(default_factory=dict)
    profile_definitions: list[ProfileDefinition] = field(default_factory=list)
