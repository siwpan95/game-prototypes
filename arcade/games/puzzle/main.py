"""
应用程序入口 —— 组装 MVVM 三层并启动
用法： python main.py
"""

from viewmodels import ImageViewModel
from views import ImageView


def main() -> None:
    view_model = ImageViewModel()
    view = ImageView(view_model)
    view.run()


if __name__ == "__main__":
    main()
