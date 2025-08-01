import yaml
import os
import sys
import platform
from cryptography.fernet import Fernet
import questionary

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings

from rich.console import Console
from rich.panel import Panel

console = Console()

from utils.view import ScreenUtils

console = Console()

class PasswordViewer:
    def __init__(self, yaml_file="passwords.yaml", key_file="secret.key"):
        self.yaml_file = yaml_file
        self.key_file = key_file
        self.fernet = self._load_key()

    def _load_key(self):
        if not os.path.exists(self.key_file):
            print("❌ Error: Encryption key not found.")
            sys.exit(1)

        with open(self.key_file, "rb") as f:
            return Fernet(f.read())

    def _load_encrypted_passwords(self):
        if not os.path.exists(self.yaml_file):
            print("❌ Error: No password file found.")
            sys.exit(1)

        with open(self.yaml_file, "r") as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                print("❌ Error reading password file.")
                sys.exit(1)

        return data

    def _get_search_input(self):
        bindings = KeyBindings()
        cancel_flag = {"cancelled": False}

        @bindings.add("escape")
        def _(event):
            cancel_flag["cancelled"] = True
            event.app.exit("")

        result = prompt(
            "🔍 Search (press [Enter] to see all, [Esc] to return): ",
            key_bindings=bindings,
        )

        return None if cancel_flag["cancelled"] else result

    @staticmethod
    def show_password(selected, decrypted):
        text = f"🔐 Password for '[bold cyan]{selected}[/bold cyan]': [bold yellow]{decrypted}[/bold yellow]"
        console.print(Panel(text, border_style="green", expand=False))

    def view(self):
        while True:
            ScreenUtils.clear()
            encrypted_data = self._load_encrypted_passwords()

            if not encrypted_data:
                print("🔎 No saved passwords found.")
                input("\nPress [Enter] to return to the menu...")
                break

            all_passwords = sorted(encrypted_data.keys())

            while True:
                ScreenUtils.clear()
                search = self._get_search_input()
                if search is None:
                    return  # Esc pressed → exit to menu
                ScreenUtils.clear()

                filtered = [name for name in all_passwords if search.lower() in name.lower()] if search else all_passwords

                if not filtered:
                    print("❌ No matches found.")
                    input("Press [Enter] to search again...")
                    ScreenUtils.clear()
                    continue

                choices = filtered + ["🔙 Back to search"]

                selected = questionary.select("Select a password to view:", choices=choices).ask()

                if selected == "🔙 Back to search" or selected is None:
                    continue  # back to search prompt

                ScreenUtils.clear()
                try:
                    decrypted = self.fernet.decrypt(encrypted_data[selected].encode()).decode()
                    PasswordViewer.show_password(selected, decrypted)
                except Exception:
                    print(f"\n❌ Failed to decrypt password for '{selected}'")

                input("\nPress [Enter] to return to the password list...")