"""
Парсер Docker-образов: извлекает ссылки из YAML-структур профилей сборки.
Не имеет доступа к TFS и не выполняет сетевых вызовов.
"""
from pathlib import Path

# Тип: имя_профиля → docker_image_url
DockerLinksMap = dict[str, str]


class DockerParser:
    """Статические методы для разбора YAML-профилей и извлечения Docker-ссылок."""

    @staticmethod
    def extract_from_yaml(content: dict, docker_links: DockerLinksMap) -> None:
        """Обходит раздел archs: YAML-профиля и заполняет маппинг docker_links."""
        archs = content.get("archs", {})
        for key, val in archs.items():
            if key == "common" or not isinstance(val, dict):
                continue

            docker_img = DockerParser.extract_docker_image(val)
            if not docker_img:
                continue

            DockerParser.add_aliases(key, docker_img, docker_links)

            prof_host = val.get("profile_host")
            if isinstance(prof_host, str):
                DockerParser.add_aliases(prof_host, docker_img, docker_links)
            elif isinstance(prof_host, list):
                for ph in prof_host:
                    DockerParser.add_aliases(ph, docker_img, docker_links)

    @staticmethod
    def extract_docker_image(arch_val: dict) -> str:
        """Извлекает URL Docker-образа из словаря значений одной архитектуры."""
        docker_val = arch_val.get("docker")
        if isinstance(docker_val, str):
            return docker_val
        if isinstance(docker_val, dict):
            return docker_val.get("image", "")
        return ""

    @staticmethod
    def add_aliases(name: str, docker_img: str, docker_links: DockerLinksMap) -> None:
        """Добавляет имя профиля и все его псевдонимы в маппинг Docker-образов."""
        if not name:
            return
        path_obj = Path(name)
        docker_links[name] = docker_img
        docker_links[path_obj.name] = docker_img
        docker_links[path_obj.stem] = docker_img
        if path_obj.parent != Path("."):
            docker_links[f"{path_obj.parent}/{path_obj.stem}"] = docker_img
