import os
import platform

@staticmethod
def read_text(file_path: str) -> str:
    """Reads and returns plain text content from a file."""
    with open(file_path, "r") as file:
        return file.read()

@staticmethod
def clear():
    os.system("cls" if platform.system() == "Windows" else "clear")