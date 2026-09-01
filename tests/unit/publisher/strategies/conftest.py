"""
Фикстуры и заглушки, используемые только тестами tests/unit/publisher/strategies/*.

Перенесены сюда из tests/unit/publisher/conftest.py (см. план рефакторинга,
п. 1.2) — ни FakeDocumentBuilder/publisher_document_builder, ни
RecordingConfluenceClient не используются за пределами этого подпакета.
"""

import threading
from typing import Any

import pytest

from autodoc.publisher.clients.models.confluence_page import ConfluencePage
from autodoc.publisher.clients.models.page_result import PageResult


class FakeDocumentBuilder:
    """
    Тестовая заглушка для IDocumentBuilder.

    По умолчанию возвращает строку '<html>{template_name}</html>'.
    Последний вызов build() сохраняется в self.last_call для проверки аргументов.
    """

    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None
        self.build_responses: list[str] = []

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """Возвращает следующую запись из build_responses или HTML по умолчанию."""
        self.last_call = {"template_name": template_name, "view_model": view_model}
        if self.build_responses:
            return self.build_responses.pop(0)
        return f"<html>{template_name}</html>"


@pytest.fixture
def publisher_document_builder() -> FakeDocumentBuilder:
    """Свежий FakeDocumentBuilder для каждого теста."""
    return FakeDocumentBuilder()


class CapturingDocumentBuilder:
    """
    Тестовая заглушка IDocumentBuilder, записывающая КАЖДЫЙ вызов build()
    (а не только последний, как FakeDocumentBuilder.last_call).

    Нужна тестам, где стратегия публикует несколько страниц за один execute()
    (например, PassportsStrategy для нескольких компонентов) или где важен
    view_model, а не HTML-результат: test_profile_centric_strategy.py и
    test_passports_strategy.py дублировали идентичный локальный класс
    CapturingBuilder для этой цели.
    """

    def __init__(self) -> None:
        self.captured_view_models: list[dict[str, Any]] = []

    def build(self, template_name: str, view_model: dict[str, Any]) -> str:
        """Сохраняет копию view_model (включая внедрённые позже ключи) и возвращает фиктивный HTML."""
        self.captured_view_models.append(dict(view_model))
        return "<html>test</html>"


@pytest.fixture
def publisher_capturing_document_builder() -> CapturingDocumentBuilder:
    """Свежий CapturingDocumentBuilder для каждого теста."""
    return CapturingDocumentBuilder()


class RecordingConfluenceClient:
    """
    Самостоятельная заглушка ConfluenceClient (не наследует FakeConfluenceClient),
    фиксирующая порядок и содержимое вызовов publish_page в published_pages.

    Используется для проверки количества и порядка публикации страниц в тестах
    стратегий Part-3. Каждый вызов publish_page добавляется в
    ``published_pages`` и получает монотонно возрастающий целочисленный
    ``page_id``, начиная с 1000; вызовы create_page получают такой же
    уникальный ``page_id``, но в published_pages не попадают.

    Счётчик защищён блокировкой: PassportsStrategy публикует страницы
    параллельно через ParallelExecutor/ThreadPoolExecutor, поэтому наивное
    чтение-затем-инкремент здесь было бы настоящим состоянием гонки (два
    рабочих потока могли бы прочитать одно и то же значение счётчика до
    того, как любой из них его увеличит), что привело бы к дублированию
    page_id — именно такую ошибку и должен ловить этот дубль, а не
    воспроизводить.
    """

    def __init__(self, existing_bodies: dict[str, str] | None = None) -> None:
        self.published_pages: list[dict] = []
        self._page_counter: int = 1000
        self._counter_lock: threading.Lock = threading.Lock()
        self._existing_bodies: dict[str, str] = existing_bodies or {}

    def _next_page_id(self) -> str:
        """Атомарно возвращает и увеличивает счётчик ID страниц."""
        with self._counter_lock:
            page_id = str(self._page_counter)
            self._page_counter += 1
        return page_id

    def publish_page(
        self,
        space: str,
        parent_id: str,
        title: str,
        body_html: str,
    ) -> PageResult:
        """Записывает вызов и возвращает PageResult с уникальным инкрементным page_id."""
        page_id = self._next_page_id()
        self.published_pages.append(
            {
                "space": space,
                "parent_id": parent_id,
                "title": title,
                "body_html": body_html,
            }
        )
        return PageResult(id=page_id, version=1, status="updated", message="")

    def resolve_existing_page_id(
        self,
        space: str,
        parent_id: str,
        title: str,
    ) -> str | None:
        """Всегда возвращает None (страница не найдена), чтобы вызывающий перешёл к create_page()."""
        return None

    def create_page(
        self,
        space: str,
        parent_id: str | None,
        title: str,
        body_html: str,
    ) -> PageResult:
        """Не фиксирует вызов в published_pages (там отражается только publish_page) и возвращает PageResult с уникальным инкрементным page_id."""
        page_id = self._next_page_id()
        return PageResult(id=page_id, version=1, status="created", message="")

    def find_page(
        self,
        title: str,
        space: str | None = None,
        expand: str | None = None,
    ) -> ConfluencePage | None:
        """Всегда возвращает None (страница не найдена)."""
        return None

    def get_page(self, page_id: str, expand: str | None = None) -> ConfluencePage:
        """Возвращает минимальную заглушку ConfluencePage."""
        return ConfluencePage(id=page_id, title="stub", version=1)

    def get_page_body(self, space: str, title: str, parent_id: str | None = None) -> str:
        """Возвращает заранее заданное тело из ``existing_bodies`` или пустую строку."""
        return self._existing_bodies.get(title, " ")
