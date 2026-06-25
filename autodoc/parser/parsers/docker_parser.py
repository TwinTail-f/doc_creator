"""
Парсер Docker-образов: извлекает ссылки из YAML-структур профилей сборки.
Не имеет доступа к TFS и не выполняет сетевых вызовов.
"""

from pathlib import Path
from typing import Any

# Тип: имя_профиля → docker_image_url
DockerLinksMap = dict[str, str]


class DockerParser:
    """Статические методы для разбора YAML-профилей и извлечения Docker-ссылок."""

    @classmethod
    def extract_from_yaml(cls, content: dict[str, Any], docker_links: DockerLinksMap) -> None:
        """
        Обходит раздел ``archs`` YAML-профиля и заполняет маппинг Docker-образов.

        Args:
            content: Разобранное содержимое YAML-файла профиля.
            docker_links: Изменяемый маппинг ``имя_профиля → docker_image_url``,
                          заполняемый в процессе обхода.
        """
        archs = content.get("archs", {})
        for key, val in archs.items():
            if key == "common" or not isinstance(val, dict):
                continue

            docker_img = cls.extract_docker_image(val)
            if not docker_img:
                continue

            cls.add_aliases(key, docker_img, docker_links)

            prof_host = val.get("profile_host")
            if isinstance(prof_host, str):
                cls.add_aliases(prof_host, docker_img, docker_links)
            elif isinstance(prof_host, list):
                for ph in prof_host:
                    cls.add_aliases(ph, docker_img, docker_links)

    @classmethod
    def extract_docker_image(cls, arch_val: dict[str, Any]) -> str:
        """
        Извлекает URL Docker-образа из словаря значений одной архитектуры.

        Args:
            arch_val: Словарь значений архитектуры из раздела ``archs`` YAML-профиля.

        Returns:
            URL Docker-образа или пустая строка, если образ не задан.
        """
        docker_val = arch_val.get("docker")
        if isinstance(docker_val, str):
            return docker_val
        if isinstance(docker_val, dict):
            return docker_val.get("image", "")
        return ""

    @classmethod
    def add_aliases(cls, name: str, docker_img: str, docker_links: DockerLinksMap) -> None:
        """
        Добавляет имя профиля и все его псевдонимы в маппинг Docker-образов.

        Args:
            name: Имя профиля (может быть полным путём, например ``linux/gcc9``).
            docker_img: URL Docker-образа для данного профиля.
            docker_links: Изменяемый маппинг ``имя_профиля → docker_image_url``.
        """
        if not name:
            return
        path_obj = Path(name)
        docker_links[name] = docker_img
        docker_links[path_obj.name] = docker_img
        docker_links[path_obj.stem] = docker_img
        if path_obj.parent != Path("."):
            docker_links[f"{path_obj.parent.as_posix()}/{path_obj.stem}"] = docker_img
