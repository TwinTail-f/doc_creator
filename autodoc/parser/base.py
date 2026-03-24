"""
Маркерный базовый класс для компонентов парсера, получающих данные из TFS.
"""
from abc import ABC
from typing import Generic, TypeVar

T = TypeVar('T')


class BaseDataFetcher(ABC, Generic[T]):
    """
    Маркерный базовый класс для компонентов парсера, получающих данные из TFS.

    3.5 Абстрактный метод ``fetch(*args, **kwargs)`` удалён — его сигнатуры
    у трёх наследников принципиально различаются, и они не вызываются
    взаимозаменяемо через общий интерфейс. Ложный полиморфизм хуже,
    чем его отсутствие.

    Класс выполняет роль маркера и документирует общий контракт наследников:

    - ``__init__`` принимает ``ParserConfigSchema``, создаёт ``TFSClient`` внутри.
    - Публичный метод ``fetch(...)`` возвращает данные типа ``T`` без мутации
      входных объектов.
    - Не знает о ``PipelineContext`` и шагах пайплайна.

    Наследники:
    - ``ManifestParser[List[Component]]`` — ``fetch(tmp_dir, excluded)``
    - ``OptionsResolver[OptionsMap]`` — ``fetch(components)``
    - ``DockerResolver[DockerLinksMap]`` — ``fetch(urls, target_platform)``
    """
