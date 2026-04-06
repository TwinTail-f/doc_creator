"""
Корневой conftest.py — добавляет корень проекта в sys.path,
чтобы pytest находил пакет autodoc без установки через pip.

Альтернатива: установить пакет в режиме разработки:
    pip install -e .
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
