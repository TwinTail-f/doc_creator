"""
Модель задачи для одного вызова ``conan graph info``.
"""

from dataclasses import dataclass

from autodoc.models.conan_variant import ProfileBuild
from autodoc.models.release import Release


@dataclass(frozen=True)
class ConanTask:
    """
    Единица задачи для одного вызова ``conan graph info``.

    Хранит готовую CLI-команду и ссылки на модели данных,
    которые будут обогащены после успешного выполнения.

    Attributes:
        cmd: Готовая CLI-команда для передачи в ``subprocess.run``.
        comp_name: Имя компонента.
        version: Версия компонента.
        channel: Канал (например ``'stable'``).
        profile_name: Имя профиля сборки Conan.
        option_id: Идентификатор набора опций.
        option_str: Строка опций через запятую.
        target_platform: Целевая платформа.
        artifactory_base_url: Базовый URL Artifactory для построения ссылок.
        release: Ссылка на объект ``Release`` для последующего обогащения.
        pb: Ссылка на объект ``ProfileBuild`` для последующего обогащения.
    """

    cmd: list[str]
    comp_name: str
    version: str
    channel: str
    profile_name: str
    option_id: str
    option_str: str
    target_platform: str
    artifactory_base_url: str
    release: Release
    pb: ProfileBuild
