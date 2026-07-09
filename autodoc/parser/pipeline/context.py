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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autodoc.config.schemas.parser_config import ParserConfigSchema
from autodoc.models.component import Component
from autodoc.models.profile_definition import ProfileDefinition
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.clients.artifactory_client import ArtifactoryClient
from autodoc.parser.clients.tfs_client import TFSClient


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
        tfs_client: Экземпляр ``TFSClient``, внедряется ``ComponentParser`` перед запуском пайплайна.
        artifactory_client: Экземпляр ``ArtifactoryClient``, внедряется ``ComponentParser``.
        components: Список компонентов, накапливаемый шагами пайплайна.
        result: Финальный результат, заполняется ``FinalizeStep``.
        intermediate: Произвольные данные для диагностики и передачи между шагами.
    """

    config: ParserConfigSchema
    tmp_dir: Path
    tfs_client: TFSClient | None = None
    artifactory_client: ArtifactoryClient | None = None
    components: list[Component] = field(default_factory=list)
    result: ParsedResult | None = None
    intermediate: dict[str, Any] = field(default_factory=dict)
    profile_definitions: list[ProfileDefinition] = field(default_factory=list)

    # Ключ, под которым DockerResolveStep хранит маппинг ссылок в intermediate.
    # Определён здесь, чтобы не дублировать магическую строку в parser.py
    # и исключить необходимость импортировать её из оркестратора.
    _DOCKER_LINKS_KEY: str = "docker_links"

    def to_snapshot_dict(self) -> dict[str, Any]:
        """
        Возвращает JSON-совместимый снимок текущего состояния контекста.

        Tuple-ключи в ``intermediate`` конвертируются в строковое представление
        списка. Ключ ``docker_links`` исключается из снимка — он большой
        и не несёт диагностической ценности; его размер фиксируется отдельно.

        Returns:
            Словарь, пригодный для сериализации через ``json.dumps``.
        """
        serialized_intermediate: dict = {}
        for k, v in self.intermediate.items():
            if k == self._DOCKER_LINKS_KEY:
                continue
            if isinstance(v, dict):
                serialized_intermediate[k] = {
                    str(list(ik)) if isinstance(ik, tuple) else ik: iv for ik, iv in v.items()
                }
            else:
                serialized_intermediate[k] = v

        return {
            "components_count": len(self.components),
            "intermediate_keys": list(self.intermediate.keys()),
            "components": [c.model_dump() for c in self.components],
            "intermediate": serialized_intermediate,
            "docker_links_count": len(self.intermediate.get(self._DOCKER_LINKS_KEY, {})),
        }
