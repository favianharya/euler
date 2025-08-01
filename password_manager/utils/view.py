import os
import platform

class ScreenUtils:
    @staticmethod
    def clear():
        os.system("cls" if platform.system() == "Windows" else "clear")
