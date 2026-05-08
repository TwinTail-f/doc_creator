"""
Unified exception module for the autodoc project.
"""


class DocGeneratorError(Exception):
    """Базовое исключение для всех ошибок проекта."""


class ConfigError(DocGeneratorError):
    """Ошибка конфигурации: отсутствует поле, неверный тип или файл не найден."""


class NetworkError(DocGeneratorError):
    """Ошибка сетевой операции (TFS, Artifactory, Confluence)."""


class RetryExhaustedError(NetworkError):
    """Retry-попытки исчерпаны после N попыток."""


class ParsingError(DocGeneratorError):
    """Ошибка парсинга данных (манифеста, JSON, YAML)."""


class ComponentParsingError(ParsingError):
    """
    Ошибка парсинга конкретного компонента.

    Не останавливает весь пайплайн — обрабатывается на уровне отдельного компонента.
    """

    def __init__(
        self,
        component_name: str,
        message: str,
        original_error: Exception | None = None,
    ) -> None:
        """
        Args:
            component_name: Имя компонента, при обработке которого возникла ошибка.
            message: Описание ошибки.
            original_error: Оригинальное исключение-причина (опционально).
        """
        self.component_name = component_name
        self.original_error = original_error
        super().__init__(f"Компонент \"{component_name}\": {message}")


class PublishError(DocGeneratorError):
    """Ошибка публикации страницы в Confluence."""


class ValidationError(DocGeneratorError):
    """Ошибка валидации данных (Pydantic или пользовательская)."""
