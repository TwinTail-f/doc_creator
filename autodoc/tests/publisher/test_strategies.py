"""Тесты Registry стратегий публикации."""
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport

import autodoc.publisher.strategies.release_strategy   # noqa: F401
import autodoc.publisher.strategies.passports_strategy  # noqa: F401

from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy


class TestRegistry:
    def test_full_release_creates_release_page_strategy(self) -> None:
        strategy = BasePublishStrategy.create(
            'full_release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Релиз 2.0', template_name='release_doc_full.jinja2',
        )
        assert isinstance(strategy, ReleasePageStrategy)

    def test_passports_creates_passports_strategy(self) -> None:
        strategy = BasePublishStrategy.create(
            'passports',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', root_page_id='12345',
        )
        assert isinstance(strategy, PassportsStrategy)

    def test_unknown_strategy_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match='Неизвестная стратегия'):
            BasePublishStrategy.create('nonexistent', confluence_client=MagicMock(),
                                       document_builder=MagicMock(), parsed_data=MagicMock(), space='DOC')

    def test_available_strategies_includes_expected_types(self) -> None:
        available = BasePublishStrategy.available_strategies()
        for expected in ('full_release', 'minimal_release', 'profile_centric', 'full_combined', 'passports'):
            assert expected in available

    def test_custom_strategy_auto_registered(self) -> None:
        class _TestStrategy(BasePublishStrategy, strategy_type='_test_only'):
            def execute(self) -> PublishReport:
                return PublishReport(success=True, pages_published=0)

        assert '_test_only' in BasePublishStrategy._registry
        del BasePublishStrategy._registry['_test_only']


class TestPublishReport:
    """3.1 Тест типизированного PublishReport."""

    def test_execute_returns_publish_report(self) -> None:
        """execute() возвращает PublishReport, а не Dict."""
        strategy = BasePublishStrategy.create(
            'full_release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
        )
        # Мокаем transformer и client чтобы не делать реальных вызовов
        strategy._transformer = MagicMock()
        strategy._transformer.transform.return_value = {'components': []}
        strategy._builder = MagicMock()
        strategy._builder.build.return_value = '<p>html</p>'
        strategy._client = MagicMock()
        strategy._client.publish_page.return_value = {'id': '1', 'version': 1, 'status': 'created'}

        result = strategy.execute()

        assert isinstance(result, PublishReport)  # не Dict
        assert result.success is True
        assert result.pages_published == 1
        assert isinstance(result.errors, list)
        assert isinstance(result.details, list)

    def test_publish_report_failure_on_exception(self) -> None:
        strategy = BasePublishStrategy.create(
            'full_release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
        )
        strategy._transformer = MagicMock()
        strategy._transformer.transform.side_effect = RuntimeError('boom')

        result = strategy.execute()
        assert isinstance(result, PublishReport)
        assert result.success is False
        assert len(result.errors) == 1


class TestCommonInit:
    """3.3 Тест что общие атрибуты инициализируются в базовом классе."""

    def test_base_attrs_set_by_super_init(self) -> None:
        client = MagicMock()
        builder = MagicMock()
        data = MagicMock()
        strategy = ReleasePageStrategy(
            confluence_client=client, document_builder=builder, parsed_data=data,
            space='DOC', page_title='T', template_name='t.jinja2', transformer=MagicMock(),
        )
        assert strategy._client is client
        assert strategy._builder is builder
        assert strategy._data is data
        assert strategy._space == 'DOC'


class TestPassportsStrategyInit:
    def test_missing_root_page_id_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            PassportsStrategy(
                confluence_client=MagicMock(), document_builder=MagicMock(),
                parsed_data=MagicMock(), space='DOC', root_page_id='',
            )

    def test_default_template_name_applied(self) -> None:
        strategy = PassportsStrategy(
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', root_page_id='99999',
        )
        assert strategy._template_name == 'component_passport.jinja2'
