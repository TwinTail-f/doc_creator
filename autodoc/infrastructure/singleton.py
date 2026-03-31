"""
Реализация паттерна Singleton через метакласс.

Используется клиентами инфраструктурного слоя (``TFSClient``, ``ArtifactoryClient``),
которым требуется единственный экземпляр на процесс.
"""


class Singleton(type):
    """
    Метакласс, реализующий паттерн Singleton.

    При повторных вызовах с любыми аргументами возвращает существующий экземпляр
    без повторного вызова ``__init__``. Для сброса экземпляра используйте
    ``Singleton._instances.pop(cls, None)`` или метод ``reset()`` конкретного класса.

    Example::

        class MyService(metaclass=Singleton):
            def __init__(self, config: Config) -> None:
                self._config = config

        svc = MyService(config)   # создаёт экземпляр
        svc2 = MyService(config)  # возвращает тот же экземпляр
        assert svc is svc2
    """

    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        """Возвращает существующий экземпляр или создаёт новый."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
