"""Тесты пайплайна: ComponentParser, BaseParseStep, PipelineContext."""
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from autodoc.config.schemas import ParserConfigSchema
from autodoc.exceptions import ParsingError
from autodoc.infrastructure.singleton import Singleton
from autodoc.models.parsed_result import ParsedResult
from autodoc.parser.artifactory_client import ArtifactoryClient
from autodoc.parser.parser import ComponentParser
from autodoc.parser.steps.base import BaseParseStep, PipelineContext
from autodoc.parser.steps.manifest_step import ManifestStep
from autodoc.parser.tfs_client import TFSClient

MINIMAL_CONFIG = ParserConfigSchema(
    platform_version='2.0',
    platform_branch_name='develop',
    tfs_username='robot',
    tfs_token='secret',
    tfs_dep_components_url='https://tfs.example.com/DEP',
    manifests_remotes_path='/remotes/manifests',
)


@pytest.fixture(autouse=True)
def reset_singletons():
    """Сбрасывает реестр синглтонов до и после каждого теста."""
    TFSClient.reset()
    ArtifactoryClient.reset()
    yield
    TFSClient.reset()
    ArtifactoryClient.reset()


class _SuccessStep(BaseParseStep):
    name = 'SuccessStep'
    is_critical = False

    def __init__(self, mark='done', critical=False):
        self._mark = mark
        self.is_critical = critical

    @property
    def name(self):
        return 'SuccessStep[%s]' % self._mark

    def execute(self, ctx):
        ctx.intermediate[self._mark] = True


class _FailStep(BaseParseStep):
    name = 'FailStep'

    def __init__(self, critical=True):
        self.is_critical = critical

    def execute(self, ctx):
        raise RuntimeError('Намеренная ошибка шага')


class _FinalizeStub(BaseParseStep):
    name = 'FinalizeStep'

    def execute(self, ctx):
        ctx.result = ParsedResult(
            generated_at='2026-01-01T00:00:00',
            platform_version='2.0',
            components=[],
        )


class TestBaseParseStepContract:
    """Тест контракта BaseParseStep."""

    def test_step_without_name_raises_on_declaration(self) -> None:
        """Шаг без name вызывает TypeError при объявлении класса."""
        with pytest.raises(TypeError, match='должен определить атрибут name'):
            class BrokenStep(BaseParseStep):
                def execute(self, ctx):
                    pass


class TestPipelineStepOrder:
    def test_all_steps_executed_in_order(self, tmp_path: Path) -> None:
        order = []

        class OrderStep(BaseParseStep):
            name = 'placeholder'
            def __init__(self, n):
                self._n = n
                self.name = 'Step%d' % n
            def execute(self, ctx):
                order.append(self._n)
                if self._n == 3:
                    ctx.result = ParsedResult(
                        generated_at='2026-01-01', platform_version='2.0', components=[]
                    )

        parser = ComponentParser(
            MINIMAL_CONFIG, tmp_path, steps=[OrderStep(1), OrderStep(2), OrderStep(3)]
        )
        parser.parse()
        assert order == [1, 2, 3]

    def test_non_critical_step_failure_continues(self, tmp_path: Path) -> None:
        steps = [_FailStep(critical=False), _FinalizeStub()]
        parser = ComponentParser(MINIMAL_CONFIG, tmp_path, steps=steps)
        result = parser.parse()
        assert result is not None

    def test_critical_step_failure_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ParsingError, match='Намеренная ошибка'):
            ComponentParser(
                MINIMAL_CONFIG, tmp_path, steps=[_FailStep(critical=True), _FinalizeStub()]
            ).parse()

    def test_tmp_dir_cleaned_on_success(self, tmp_path: Path) -> None:
        ComponentParser(MINIMAL_CONFIG, tmp_path, steps=[_FinalizeStub()]).parse()
        assert not (tmp_path / 'tmp').exists()

    def test_tmp_dir_cleaned_on_failure(self, tmp_path: Path) -> None:
        (tmp_path / 'tmp').mkdir()
        with pytest.raises(ParsingError):
            ComponentParser(
                MINIMAL_CONFIG, tmp_path, steps=[_FailStep(critical=True)]
            ).parse()
        assert not (tmp_path / 'tmp').exists()

    def test_singletons_shut_down_after_parse(self, tmp_path: Path) -> None:
        """После завершения parse() синглтоны клиентов сброшены."""
        mock_session = MagicMock()
        with patch(
            'autodoc.parser.tfs_client.create_retryable_session', return_value=mock_session
        ), patch(
            'autodoc.parser.artifactory_client.create_retryable_session',
            return_value=MagicMock(),
        ):
            ComponentParser(MINIMAL_CONFIG, tmp_path, steps=[_FinalizeStub()]).parse()

        assert TFSClient not in Singleton._instances
        assert ArtifactoryClient not in Singleton._instances


class TestSaveIntermediate:
    def test_save_intermediate_creates_files(self, tmp_path: Path) -> None:
        steps = [_SuccessStep('a'), _FinalizeStub()]
        ComponentParser(MINIMAL_CONFIG, tmp_path, steps=steps).parse(save_intermediate=True)
        files = list((tmp_path / 'intermediate').glob('*.json'))
        assert len(files) == 2

    def test_save_intermediate_false_no_files(self, tmp_path: Path) -> None:
        ComponentParser(
            MINIMAL_CONFIG, tmp_path, steps=[_FinalizeStub()]
        ).parse(save_intermediate=False)
        assert not (tmp_path / 'intermediate').exists()


class TestManifestStepSingularity:
    def test_default_pipeline_has_exactly_one_manifest_step(self, tmp_path: Path) -> None:
        mock_session = MagicMock()
        with patch(
            'autodoc.parser.tfs_client.create_retryable_session', return_value=mock_session
        ), patch(
            'autodoc.parser.artifactory_client.create_retryable_session',
            return_value=MagicMock(),
        ):
            parser = ComponentParser(MINIMAL_CONFIG, tmp_path)
        manifest_steps = [s for s in parser._steps if isinstance(s, ManifestStep)]
        assert len(manifest_steps) == 1


class TestProfileBuildFieldNames:
    """Проверка переименованных полей ProfileBuild в пайплайне."""

    def test_finalize_uses_exists_not_pb_exist(self, tmp_path: Path) -> None:
        """FinalizeStep использует pb.exists, а не pb.pb_exist."""
        from autodoc.models.component import Component, ProfileBuild, Release
        from autodoc.parser.steps.finalize_step import FinalizeStep

        pb = ProfileBuild(profile_name='test', exists=False)
        release = Release(version='1.0', platform='2.0', channel='stable',
                          git_url='https://tfs.example.com')
        release.profile_builds = [pb]
        comp = Component(name='lib', releases=[release])

        ctx = PipelineContext(config=MINIMAL_CONFIG, tmp_dir=tmp_path)
        ctx.components = [comp]

        step = FinalizeStep()
        step._filter_empty_profiles([comp])
        assert len(release.profile_builds) == 0
