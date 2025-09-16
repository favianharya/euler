import os
import platform
from importlib.resources import files

@staticmethod
def read_text(file_path: str) -> str:
        resource_path = files("tokoscrapedia").joinpath(file_path)
        with open(resource_path, "r", encoding="utf-8") as f:
            return f.read()

@staticmethod
def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")