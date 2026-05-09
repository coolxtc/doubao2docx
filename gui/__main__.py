"""GUI 入口，支持 python -m gui"""
import flet as ft
from gui.app import main_app


def main():
    """GUI 入口函数，供 pyproject.toml scripts 调用"""
    ft.run(main_app)   # 直接传入 main_app


if __name__ == "__main__":
    main()
