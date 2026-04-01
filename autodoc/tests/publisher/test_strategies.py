"""Тесты Registry стратегий публикации."""
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from autodoc.publisher.strategies.base import BasePublishStrategy, PublishReport

from autodoc.publisher.strategies.passports_strategy import PassportsStrategy
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy
from autodoc.publisher.strategies.profile_strategy import ProfileCentricStrategy
from autodoc.publisher.transformers.profile_transformer import ProfileCentricTransformer


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

    def test_profile_centric_creates_profile_strategy(self) -> None:
        strategy = BasePublishStrategy.create(
            'profile_centric',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', page_title='Profile',
        )
        assert isinstance(strategy, ProfileCentricStrategy)

    def test_unknown_strategy_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match='Неизвестная стратегия'):
            BasePublishStrategy.create(
                'nonexistent',
                confluence_client=MagicMock(), document_builder=MagicMock(),
                parsed_data=MagicMock(), space='DOC',
            )

    def test_available_strategies_includes_expected_types(self) -> None:
        available = BasePublishStrategy.available_strategies()
        for expected in ('release', 'passports', 'profile_centric'):
            assert expected in available, 'Стратегия %r не найдена в реестре' % expected
        for removed in ('full_release', 'minimal_release', 'full_combined'):
            assert removed not in available, 'Удалённая стратегия %r всё ещё в реестре' % removed

    def test_custom_strategy_auto_registered(self) -> None:
        class _TestStrategy(BasePublishStrategy, strategy_type='_test_only'):
            def execute(self) -> PublishReport:
                return PublishReport(success=True, pages_published=0)

        assert '_test_only' in BasePublishStrategy._registry
        del BasePublishStrategy._registry['_test_only']

    def test_no_transformer_cls_on_base(self) -> None:
        """После рефакторинга __init_subclass__ не принимает transformer_cls."""
        import inspect
        sig = inspect.signature(BasePublishStrategy.__init_subclass__)
        assert 'transformer_cls' not in sig.parameters


class TestBugFixes:
    """Регрессионные тесты для Bug A и Bug B."""

    def test_bug_a_include_passport_links_false_reaches_strategy(self) -> None:
        """
        Bug A: create('release', include_passport_links=False) должен
        устанавливать strategy._include_passport_links = False.
        До исправления create() удалял ключ из kwargs и стратегия
        всегда получала дефолт True.
        """
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
            include_passport_links=False,
        )
        assert strategy._include_passport_links is False

    def test_bug_a_include_passport_links_true_preserved(self) -> None:
        """Значение True тоже сохраняется корректно."""
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
            include_passport_links=True,
        )
        assert strategy._include_passport_links is True

    def test_bug_a_transformer_and_strategy_share_flag(self) -> None:
        """Трансформер и стратегия должны использовать одно значение флага."""
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
            include_passport_links=False,
        )
        assert strategy._transformer._include_passport_links is False
        assert strategy._include_passport_links is False

    def test_bug_b_include_passport_links_reaches_profile_strategy(self) -> None:
        """
        Bug B: create('profile_centric', include_passport_links=False) должен
        дойти до трансформера. До исправления else-ветка в create() удаляла
        kwargs и стратегия всегда получала дефолт True.
        """
        strategy = BasePublishStrategy.create(
            'profile_centric',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', page_title='Profile',
            include_passport_links=False,
        )
        assert strategy._transformer._include_passport_links is False

    def test_bug_b_passport_page_pattern_reaches_profile_transformer(self) -> None:
        """passport_page_pattern не должен теряться при создании ProfileCentricStrategy."""
        custom_pattern = 'https://wiki.example.com/{component_name}'
        strategy = BasePublishStrategy.create(
            'profile_centric',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', page_title='Profile',
            passport_page_pattern=custom_pattern,
        )
        assert strategy._transformer._pattern == custom_pattern

    def test_passport_page_pattern_popped_for_release_strategy(self) -> None:
        """
        passport_page_pattern должен быть извлечён (pop) из kwargs для release,
        так как ReleasePageStrategy.__init__ его не принимает.
        """
        # Не должен падать с TypeError о неожиданном аргументе
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
            passport_page_pattern='https://wiki.example.com/{component_name}',
        )
        assert isinstance(strategy, ReleasePageStrategy)


class TestPublishReport:
    """Тест типизированного PublishReport."""

    def test_execute_returns_publish_report(self) -> None:
        """execute() возвращает PublishReport, а не dict."""
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
        )
        strategy._transformer = MagicMock()
        strategy._transformer.transform.return_value = {'components': []}
        strategy._builder = MagicMock()
        strategy._builder.build.return_value = '<p>html</p>'
        strategy._client = MagicMock()
        strategy._client.publish_page.return_value = {
            'id': '1', 'version': 1, 'status': 'created'
        }

        result = strategy.execute()

        assert isinstance(result, PublishReport)
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

    def test_publish_report_empty_transformer_result(self) -> None:
        """Пустой результат трансформера записывается в errors."""
        strategy = BasePublishStrategy.create(
            'release',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC',
            page_title='Test', template_name='tpl.jinja2',
        )
        strategy._transformer = MagicMock()
        strategy._transformer.transform.return_value = {}

        result = strategy.execute()
        assert result.success is False
        assert result.pages_published == 0


class TestCommonInit:
    """Тест что общие атрибуты инициализируются в базовом классе."""

    def test_base_attrs_set_by_super_init(self) -> None:
        client = MagicMock()
        builder = MagicMock()
        data = MagicMock()
        strategy = ReleasePageStrategy(
            confluence_client=client, document_builder=builder, parsed_data=data,
            space='DOC', page_title='T', template_name='t.jinja2',
            transformer=MagicMock(),
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

    def test_missing_space_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            PassportsStrategy(
                confluence_client=MagicMock(), document_builder=MagicMock(),
                parsed_data=MagicMock(), space='', root_page_id='123',
            )

    def test_default_template_name_applied(self) -> None:
        strategy = PassportsStrategy(
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', root_page_id='99999',
        )
        assert strategy._template_name == 'component_passport.jinja2'

    def test_make_page_title_format(self) -> None:
        title = PassportsStrategy._make_page_title('MyComp', '1.2.3')
        assert title == 'Документация MyComp 1.2.3'

    def test_build_pages_map_structure(self) -> None:
        details: list[dict[str, Any]] = [
            {
                'component_name': 'CompA',
                'release_version': '1.0',
                'page_title': 'Документация CompA 1.0',
                'page_id': '42',
                'version': 3,
                'status': 'updated',
            }
        ]
        result = PassportsStrategy._build_pages_map(details)
        assert result == {
            'CompA': {
                '1.0': {
                    'page_id': '42',
                    'page_title': 'Документация CompA 1.0',
                    'version': 3,
                }
            }
        }

    def test_fetch_existing_body_returns_empty_on_error(self) -> None:
        """_fetch_existing_body возвращает пустую строку при любом исключении."""
        client = MagicMock()
        client.get_page_body.side_effect = RuntimeError('connection error')
        strategy = PassportsStrategy(
            confluence_client=client, document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', root_page_id='99',
        )
        result = strategy._fetch_existing_body('Some Page')
        assert result == ''

    def test_fetch_existing_body_returns_html_on_success(self) -> None:
        client = MagicMock()
        client.get_page_body.return_value = '<p>old</p>'
        strategy = PassportsStrategy(
            confluence_client=client, document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', root_page_id='99',
        )
        result = strategy._fetch_existing_body('Some Page')
        assert result == '<p>old</p>'

    def test_passports_create_unaffected_by_factory(self) -> None:
        """Task 4.4: PassportsStrategy не имеет _make_transformer, kwargs проходит без изменений."""
        strategy = BasePublishStrategy.create(
            'passports',
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', root_page_id='123',
        )
        assert isinstance(strategy, PassportsStrategy)
        assert not hasattr(PassportsStrategy, '_make_transformer') or \
            PassportsStrategy._make_transformer is None or \
            getattr(PassportsStrategy, '_make_transformer', None) is None


class TestProfileCentricStrategyInit:
    """Тесты ProfileCentricStrategy — инжекция трансформера и kwargs."""

    def test_injectable_transformer_used_when_provided(self) -> None:
        """transformer=... должен использоваться напрямую без создания нового."""
        custom_transformer = ProfileCentricTransformer(include_passport_links=False)
        strategy = ProfileCentricStrategy(
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', page_title='P',
            transformer=custom_transformer,
        )
        assert strategy._transformer is custom_transformer

    def test_transformer_built_from_kwargs_when_not_provided(self) -> None:
        """Если transformer не передан — создаётся из include_passport_links."""
        strategy = ProfileCentricStrategy(
            confluence_client=MagicMock(), document_builder=MagicMock(),
            parsed_data=MagicMock(), space='DOC', page_title='P',
            include_passport_links=False,
        )
        assert strategy._transformer._include_passport_links is False

    def test_make_transformer_uses_get_not_pop(self) -> None:
        """_make_transformer читает оба ключа через .get() — они остаются в kwargs."""
        kwargs: dict = {
            'include_passport_links': False,
            'passport_page_pattern': 'https://example.com/{component_name}',
        }
        transformer = ProfileCentricStrategy._make_transformer(kwargs)
        # Ключи остаются в kwargs после вызова
        assert 'include_passport_links' in kwargs
        assert 'passport_page_pattern' in kwargs
        assert transformer._include_passport_links is False
        assert transformer._pattern == 'https://example.com/{component_name}'


class TestMakeTransformerContract:
    """Проверка контракта _make_transformer для release и profile_centric."""

    def test_release_make_transformer_pops_pattern_keeps_links(self) -> None:
        """_make_transformer для release: pop passport_page_pattern, get include_passport_links."""
        kwargs: dict = {
            'include_passport_links': False,
            'passport_page_pattern': 'https://example.com/{component_name}',
        }
        transformer = ReleasePageStrategy._make_transformer(kwargs)
        # passport_page_pattern должен быть извлечён (ReleasePageStrategy его не принимает)
        assert 'passport_page_pattern' not in kwargs
        # include_passport_links должен остаться (стратегия его принимает)
        assert 'include_passport_links' in kwargs
        assert transformer._include_passport_links is False
        assert transformer._pattern == 'https://example.com/{component_name}'

    def test_release_make_transformer_default_values(self) -> None:
        """Без явных значений используются дефолты."""
        kwargs: dict = {}
        transformer = ReleasePageStrategy._make_transformer(kwargs)
        assert transformer._include_passport_links is True

    def test_profile_make_transformer_keeps_both_keys(self) -> None:
        """_make_transformer для profile: оба ключа остаются в kwargs через .get()."""
        kwargs: dict = {
            'include_passport_links': False,
            'passport_page_pattern': 'https://example.com/{component_name}',
        }
        transformer = ProfileCentricStrategy._make_transformer(kwargs)
        assert 'include_passport_links' in kwargs
        assert 'passport_page_pattern' in kwargs
        assert transformer._include_passport_links is False


class TestPassportLinkMixin:
    """Тесты миксина — устранение дублирования."""

    def test_mixin_in_base_release_transformer_mro(self) -> None:
        from autodoc.publisher.transformers.release_transformer import BaseReleaseTransformer
        from autodoc.publisher.transformers.base_transformer import PassportLinkMixin
        assert PassportLinkMixin in BaseReleaseTransformer.__mro__

    def test_mixin_in_profile_centric_transformer_mro(self) -> None:
        from autodoc.publisher.transformers.base_transformer import PassportLinkMixin
        assert PassportLinkMixin in ProfileCentricTransformer.__mro__

    def test_default_pattern_defined_once(self) -> None:
        """_DEFAULT_PASSPORT_PATTERN должен быть только в base_transformer, не в дочерних."""
        import autodoc.publisher.transformers.release_transformer as rt
        import autodoc.publisher.transformers.profile_transformer as pt
        from autodoc.publisher.transformers.base_transformer import _DEFAULT_PASSPORT_PATTERN

        # В дочерних модулях не должно быть своих копий константы
        assert not hasattr(rt, '_DEFAULT_PASSPORT_PATTERN') or \
            getattr(rt, '_DEFAULT_PASSPORT_PATTERN') is _DEFAULT_PASSPORT_PATTERN
        assert not hasattr(pt, '_DEFAULT_PASSPORT_PATTERN') or \
            getattr(pt, '_DEFAULT_PASSPORT_PATTERN') is _DEFAULT_PASSPORT_PATTERN

    def test_passport_link_returns_none_when_disabled(self) -> None:
        from autodoc.publisher.transformers.base_transformer import PassportLinkMixin

        class _ConcreteTransformer(PassportLinkMixin):
            _include_passport_links = False
            _pattern = 'https://example.com/{component_name}+{release_version}'

        t = _ConcreteTransformer()
        assert t._passport_link('CompA', '1.0') is None

    def test_passport_link_formats_correctly_when_enabled(self) -> None:
        from autodoc.publisher.transformers.base_transformer import PassportLinkMixin

        class _ConcreteTransformer(PassportLinkMixin):
            _include_passport_links = True
            _pattern = 'https://wiki/{component_name}+{release_version}'

        t = _ConcreteTransformer()
        assert t._passport_link('My Comp', '1.2') == 'https://wiki/My+Comp+1.2'


class TestPassportTransformerSerialization:
    """Проверяем что PassportTransformer сериализует build_option_sets в dict."""

    def test_build_option_sets_are_plain_dicts(self) -> None:
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
            assert isinstance(bos, dict)
            assert 'id' in bos
            assert 'options' in bos

    def test_default_options_are_plain_dicts(self) -> None:
        from autodoc.publisher.transformers.passport_transformer import PassportTransformer
        from autodoc.models.parsed_result import ParsedResult

        data_file = Path('data/parsed_data.json')
        if not data_file.exists():
            pytest.skip('parsed_data.json не найден')

        data = ParsedResult.model_validate_json(data_file.read_text())
        for comp in data.components:
            for rel in comp.releases:
                if rel.default_options:
                    tr = PassportTransformer(comp.name, rel.version)
                    vm = tr.transform(data)
                    for opt in vm['release']['default_options']:
                        assert isinstance(opt, dict)
                    return
        pytest.skip('Нет компонентов с default_options в тестовых данных')


class TestTemplateRendering:
    """Smoke-тесты: проверяем что шаблоны рендерятся без ошибок."""

    def _get_builder(self):
        from autodoc.publisher.rendering.document_builder import DocumentBuilder
        tpl_dir = Path('autodoc/publisher/rendering/templates')
        if not tpl_dir.exists():
            pytest.skip('Директория шаблонов не найдена: %s' % tpl_dir)
        return DocumentBuilder(tpl_dir)

    def _get_data(self):
        from autodoc.models.parsed_result import ParsedResult
        data_file = Path('data/parsed_data.json')
        if not data_file.exists():
            pytest.skip('parsed_data.json не найден')
        return ParsedResult.model_validate_json(data_file.read_text())

    def test_passport_template_renders_without_error(self) -> None:
        from autodoc.publisher.transformers.passport_transformer import PassportTransformer

        builder = self._get_builder()
        data = self._get_data()
        comp = data.components[0]

        tr = PassportTransformer(comp.name, comp.releases[0].version)
        vm = tr.transform(data)
        vm['target_platform'] = 'Платформа %s' % data.platform_version
        vm['legacy_contents'] = {}

        html = builder.build('component_passport.jinja2', vm)

        assert len(html) > 100
        assert 'profile_docker_url' not in html
        assert 'option_set_str' not in html
        assert 'option_set_id' not in html

    def test_release_template_renders_without_error(self) -> None:
        from autodoc.publisher.transformers.release_transformer import FullReleaseTransformer

        builder = self._get_builder()
        data = self._get_data()

        vm = FullReleaseTransformer().transform(data)
        vm['space'] = 'DOC'

        html = builder.build('release_doc.jinja2', vm)

        assert len(html) > 100
        assert 'profile_docker_url' not in html

    def test_profile_template_renders_without_error(self) -> None:
        builder = self._get_builder()
        data = self._get_data()

        vm = ProfileCentricTransformer().transform(data)
        html = builder.build('profile_centric.jinja2', vm)

        assert len(html) > 100

    def test_all_three_templates_exist(self) -> None:
        tpl_dir = Path('autodoc/publisher/rendering/templates')
        if not tpl_dir.exists():
            pytest.skip('Директория шаблонов не найдена: %s' % tpl_dir)

        for expected in (
            'component_passport.jinja2',
            'release_doc.jinja2',
            'profile_centric.jinja2',
        ):
            assert (tpl_dir / expected).exists(), 'Шаблон %s не найден' % expected

        for removed in (
            'release_doc_full.jinja2',
            'release_doc_minimal.jinja2',
            'release_doc_combined.jinja2',
        ):
            path = tpl_dir / removed
            if path.exists():
                content = path.read_text(encoding='utf-8').strip()
                assert len(content) < 50, 'Устаревший шаблон %s существует' % removed
