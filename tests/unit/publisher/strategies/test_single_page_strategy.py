"""
Тесты для общей валидации в autodoc.publisher.strategies.single_page_strategy.

SinglePagePublishStrategy — промежуточный абстрактный класс, поэтому конструктор
проверяется через конкретный наследник ReleasePageStrategy: __init__ базового
класса выполняется первым и поднимает ValueError до того, как код наследника
успевает что-либо сделать.
"""

from pathlib import Path

import pytest

from autodoc.models.parsed_result import ParsedResult
from autodoc.publisher.strategies.release_strategy import ReleasePageStrategy
from tests.unit.publisher.conftest import FakeConfluenceClient
from tests.unit.publisher.strategies.conftest import FakeDocumentBuilder

_SPACE: str = "TEST"
_TEMPLATE_NAME: str = "release_doc.jinja2"


@pytest.mark.business_logic
def test_empty_page_title_raises_value_error(
    publisher_confluence_client: FakeConfluenceClient,
    publisher_document_builder: FakeDocumentBuilder,
    publisher_parsed_result: ParsedResult,
    tmp_path: Path,
) -> None:
    """SinglePagePublishStrategy.__init__ поднимает ValueError на пустой page_title —
    пустой заголовок страницы Confluence публиковать бессмысленно и небезопасно."""
    with pytest.raises(ValueError, match="page_title"):
        ReleasePageStrategy(
            confluence_client=publisher_confluence_client,
            document_builder=publisher_document_builder,
            parsed_data=publisher_parsed_result,
            space=_SPACE,
            page_title="",
            template_name=_TEMPLATE_NAME,
            parent_id=None,
            include_passport_links=False,
            data_dir=tmp_path,
        )
