"""
Единый модуль логирования с поддержкой контекстной информации.

Объединяет настройку логгера и контекстный менеджер LoggingContext.
"""
import logging
from contextlib import contextmanager
from typing import Generator, Optional


# Глобальное хранилище текущего контекста логирования
_logging_context: dict = {}


class ContextFilter(logging.Filter):
    """
    Фильтр логирования, добавляющий контекстную информацию в каждую запись.

    Подмешивает в запись поле ``context`` с именем компонента, версией
    и текущим шагом обработки.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Добавляет поле ``context`` к записи лога.

        Args:
            record: Запись лога для обогащения.

        Returns:
            True — запись всегда пропускается дальше.
        """
        global _logging_context

        context_parts = []
        if _logging_context:
            component = _logging_context.get('component_name', '')
            version = _logging_context.get('version', '')
            step = _logging_context.get('step', '')

            if component:
                context_parts.append(f'[{component}')
                if version:
                    context_parts.append(f' v{version}')
                context_parts.append(']')

            if step:
                context_parts.append(f'[{step}]')

        record.context = ' '.join(context_parts) if context_parts else ''
        return True


@contextmanager
def LoggingContext(
    component_name: Optional[str] = None,
    version: Optional[str] = None,
    step: Optional[str] = None,
) -> Generator[None, None, None]:
    """
    Контекстный менеджер для временной установки контекста логирования.

    Все сообщения, залогированные внутри блока ``with``, будут содержать
    заданные поля компонента, версии и шага. При вложенных вызовах
    старый контекст восстанавливается автоматически.

    Args:
        component_name: Имя компонента (например, ``'crypto_lib'``).
        version: Версия компонента (например, ``'1.2.3'``).
        step: Текущий шаг обработки (например, ``'Conan parsing'``).

    Example::

        with LoggingContext(component_name='my_lib', version='2.0', step='parse'):
            logger.info('Начало парсинга')
    """
    global _logging_context

    old_context = _logging_context.copy()

    if component_name is not None:
        _logging_context['component_name'] = component_name
    if version is not None:
        _logging_context['version'] = version
    if step is not None:
        _logging_context['step'] = step

    try:
        yield
    finally:
        _logging_context.clear()
        _logging_context.update(old_context)


def setup_logging(logger_name: str = 'doc_parser') -> logging.Logger:
    """
    Настраивает логгер с поддержкой контекстной информации.

    Формат сообщения: ``[HH:MM:SS] LEVEL [component v1.0][step]: message``.
    Повторная инициализация одного и того же логгера безопасна: обработчики
    добавляются только один раз.

    Args:
        logger_name: Имя логгера. По умолчанию ``'doc_parser'``.

    Returns:
        Настроенный экземпляр ``logging.Logger``.
    """
    log = logging.getLogger(logger_name)

    if not log.handlers:
        log.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt='[%(asctime)s] %(levelname)s %(context)s: %(message)s',
            datefmt='%H:%M:%S',
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        console_handler.addFilter(ContextFilter())

        log.addHandler(console_handler)

    return log


# Модульный логгер — используется по умолчанию во всех модулях проекта
logger = setup_logging()
