"""Тесты Registry стратегий публикации."""
from typing import Any
from unittest.mock import MagicMock

import pytest

from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport

import autodoc.publisher.strategies.release_strategy   # noqa: F401
import autodoc.publisher.strategies.passports_strategy  # noqa: F401
import autodoc.publisher.strategies.profile_strategy   # noqa: F401

from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy

class TestRegistry:
    def test_release_creates_release_page_strategy(self) -> None:
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Релиз 2.0', template_name='release_doc.jinja2',
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
        # Новые стратегии должны быть зарегистрированы
        for expected in ('release', 'passports', 'profile_centric'):
            assert expected in available, f'Стратегия {expected!r} не найдена в реестре'
        # Старых стратегий быть не должно
        for removed in ('full_release', 'minimal_release', 'full_combined'):
            assert removed not in available, f'Удалённая стратегия {removed!r} всё ещё в реестре'

    def test_custom_strategy_auto_registered(self) -> None:
        class _TestStrategy(BasePublishStrategy, strategy_type='_test_only'):
            def execute(self) -> PublishReport:
                return PublishReport(success=True, pages_published=0)

        assert '_test_only' in BasePublishStrategy._registry
        del BasePublishStrategy._registry['_test_only']

class TestPublishReport:
    """3.1 Тест типизированного PublishReport."""

    def test_execute_returns_publish_report(self) -> None:
        """execute() возвращает PublishReport, а не dict."""
        strategy = BasePublishStrategy.create(
            'release',
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

        assert isinstance(result, PublishReport)  # не dict
        assert result.success is True
        assert result.pages_published == 1
        assert isinstance(result.errors, list)
        assert isinstance(result.details, list)

    def test_publish_report_failure_on_exception(self) -> None:
        strategy = BasePublishStrategy.create(
            'release',
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


class TestPassportTransformerSerialization:
    """Проверяем что PassportTransformer сериализует build_option_sets в dict."""

    def test_build_option_sets_are_plain_dicts(self) -> None:
        """build_option_sets должны быть обычными dict, а не Pydantic-объектами."""
        from pathlib import Path
        from autodoc.publisher.transformers.passport_transformer import PassportTransformer
        from autodoc.models.parsed_result import ParsedResult

        data_file = Path('data/parsed_data.json')
        if not data_file.exists():
            pytest.skip('parsed_data.json не найден')

        data = ParsedResult.model_validate_json(data_file.read_text())
        comp = data.components[0]
        tr = PassportTransformer(comp.name, comp.releases[0].version)
        vm = tr.transform(data)

        for bos in vm['release']['build_option_sets']:
            assert isinstance(bos, dict), (
                f'build_option_sets должен содержать dict, получен {type(bos)}'
            )
            assert 'id' in bos, "В bos отсутствует ключ 'id'"
            assert 'options' in bos, "В bos отсутствует ключ 'options'"

    def test_default_options_are_plain_dicts(self) -> None:
        """default_options тоже должны быть dict (проверка единообразия)."""
        from pathlib import Path
        from autodoc.publisher.transformers.passport_transformer import PassportTransformer
        from autodoc.models.parsed_result import ParsedResult

        data_file = Path('data/parsed_data.json')
        if not data_file.exists():
            pytest.skip('parsed_data.json не найден')

        data = ParsedResult.model_validate_json(data_file.read_text())
        # Найдём компонент с default_options
        for comp in data.components:
            for rel in comp.releases:
                if rel.default_options:
                    tr = PassportTransformer(comp.name, rel.version)
                    vm = tr.transform(data)
                    for opt in vm['release']['default_options']:
                        assert isinstance(opt, dict), (
                            f'default_options должен содержать dict, получен {type(opt)}'
                        )
                    return
        pytest.skip('Нет компонентов с default_options в тестовых данных')


class TestTemplateRendering:
    """Smoke-тесты: проверяем что шаблоны рендерятся без ошибок."""

    def _get_builder(self):
        from pathlib import Path
        from autodoc.publisher.rendering.document_builder import DocumentBuilder
        tpl_dir = Path('autodoc/publisher/rendering/templates')
        if not tpl_dir.exists():
            pytest.skip(f'Директория шаблонов не найдена: {tpl_dir}')
        return DocumentBuilder(tpl_dir)

    def _get_data(self):
        from pathlib import Path
        from autodoc.models.parsed_result import ParsedResult
        data_file = Path('data/parsed_data.json')
        if not data_file.exists():
            pytest.skip('parsed_data.json не найден')
        return ParsedResult.model_validate_json(data_file.read_text())

    def test_passport_template_renders_without_error(self) -> None:
        """Паспорт рендерится и не содержит устаревших переменных."""
        from autodoc.publisher.transformers.passport_transformer import PassportTransformer

        builder = self._get_builder()
        data = self._get_data()
        comp = data.components[0]

        tr = PassportTransformer(comp.name, comp.releases[0].version)
        vm = tr.transform(data)
        vm['target_platform'] = f'Платформа {data.platform_version}'
        vm['legacy_contents'] = {}

        html = builder.build('component_passport.jinja2', vm)

        assert len(html) > 100, 'HTML слишком короткий — вероятно шаблон не отрендерился'
        assert 'profile_docker_url' not in html, 'Устаревший profile_docker_url в паспорте'
        assert 'option_set_str' not in html, 'Устаревший option_set_str в паспорте'
        assert 'option_set_id' not in html, 'Устаревший option_set_id в паспорте'

    def test_release_template_renders_without_error(self) -> None:
        """Релизная страница рендерится и не содержит устаревших переменных."""
        from autodoc.publisher.transformers.release_transformer import FullReleaseTransformer

        builder = self._get_builder()
        data = self._get_data()

        vm = FullReleaseTransformer().transform(data)
        vm['space'] = 'DOC'

        html = builder.build('release_doc.jinja2', vm)

        assert len(html) > 100, 'HTML слишком короткий — вероятно шаблон не отрендерился'
        assert 'profile_docker_url' not in html, 'Устаревший profile_docker_url в релизе'

    def test_profile_template_renders_without_error(self) -> None:
        """Профильная страница рендерится без ошибок."""
        from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer

        builder = self._get_builder()
        data = self._get_data()

        vm = ProfileCentricTransformer().transform(data)

        html = builder.build('profile_centric.jinja2', vm)

        assert len(html) > 100, 'HTML слишком короткий — вероятно шаблон не отрендерился'

    def test_all_three_templates_exist(self) -> None:
        """Три нужных шаблона существуют, три старых — удалены."""
        from pathlib import Path

        tpl_dir = Path('autodoc/publisher/rendering/templates')
        if not tpl_dir.exists():
            pytest.skip(f'Директория шаблонов не найдена: {tpl_dir}')

        # Должны существовать
        for expected in ('component_passport.jinja2', 'release_doc.jinja2', 'profile_centric.jinja2'):
            assert (tpl_dir / expected).exists(), f'Шаблон {expected} не найден!'

        # Не должны существовать (или должны быть пустыми заглушками)
        for removed in ('release_doc_full.jinja2', 'release_doc_minimal.jinja2', 'release_doc_combined.jinja2'):
            path = tpl_dir / removed
            if path.exists():
                content = path.read_text(encoding='utf-8').strip()
                assert len(content) < 50, (
                    f'Устаревший шаблон {removed} существует и не является заглушкой'
                )
