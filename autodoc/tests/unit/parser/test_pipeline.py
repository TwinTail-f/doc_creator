"""Unit tests for autodoc/parser/pipeline/context.py and BaseParseStep."""

import pytest

from autodoc.parser.pipeline.context import PipelineContext
from autodoc.parser.steps.base import BaseParseStep

# ---------------------------------------------------------------------------
# Tests: PipelineContext
# ---------------------------------------------------------------------------


def test_pipeline_context_construction(
    parser_config,
    tmp_path,
) -> None:
    """PipelineContext initializes with empty components and result=None."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    assert ctx.components == []
    assert ctx.result is None


def test_pipeline_context_snapshot_excludes_docker_links(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict omits 'docker_links' from intermediate but reports its count."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.intermediate["docker_links"] = {"key1": "val1"}
    snapshot = ctx.to_snapshot_dict()
    assert "docker_links" not in snapshot["intermediate"]
    assert snapshot["docker_links_count"] == 1


def test_pipeline_context_snapshot_includes_components_count(
    parser_config,
    tmp_path,
    manifest_component,
) -> None:
    """to_snapshot_dict includes components_count matching len(ctx.components)."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.components = [manifest_component]
    snapshot = ctx.to_snapshot_dict()
    assert snapshot["components_count"] == 1


def test_pipeline_context_snapshot_converts_tuple_keys(
    parser_config,
    tmp_path,
) -> None:
    """to_snapshot_dict converts tuple keys in intermediate dicts to string representations."""
    ctx = PipelineContext(config=parser_config, tmp_dir=tmp_path)
    ctx.intermediate["test_data"] = {("a", "b"): "value"}
    snapshot = ctx.to_snapshot_dict()
    keys = list(snapshot["intermediate"]["test_data"].keys())
    assert all(isinstance(k, str) for k in keys)


# ---------------------------------------------------------------------------
# Tests: BaseParseStep
# ---------------------------------------------------------------------------


def test_base_parse_step_requires_name_attribute() -> None:
    """Defining a BaseParseStep subclass with an empty name raises TypeError at class definition."""
    with pytest.raises(TypeError):

        class BadStep(BaseParseStep):
            """Step with empty name — should raise at class definition."""

            name = ""  # falsy → __init_subclass__ raises

            def execute(self, ctx: PipelineContext) -> None:
                """No-op execute for the bad step."""
