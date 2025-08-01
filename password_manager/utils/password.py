import random
import string
import argparse
import sys
import yaml
import os
from cryptography.fernet import Fernet

from utils.view import ScreenUtils

from rich.console import Console
from rich.panel import Panel

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app_or_none

import questionary

console = Console()

class PasswordEnhancer:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Enhance your password with random characters.")
        parser.add_argument("-l", "--length", type=int, default=6, help="Number of random characters to add")
        parser.add_argument("-ns", "--no-shuffle", action="store_true", help="Disable shuffling of the final password")
        args = parser.parse_args()

        self.add_length = args.length
        self.shuffle = not args.no_shuffle
        self.output_file = "passwords.yaml"
        self.key_file = "secret.key"
        self.fernet = self._load_or_create_key()

    def _load_or_create_key(self):
        if not os.path.exists(self.key_file):
            key = Fernet.generate_key()
            with open(self.key_file, "wb") as f:
                f.write(key)
        else:
            with open(self.key_file, "rb") as f:
                key = f.read()
        return Fernet(key)

    def get_base_password(self):
        bindings = KeyBindings()
        session = PromptSession()

        @bindings.add("escape")
        def _(event):
            event.app.exit(result=None)  # Exit prompt with result = None

        try:
            password = session.prompt(
                "Enter your base password: ",
                is_password=True,
                key_bindings=bindings,
            )
            if password is None:
                return None
            return password
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            sys.exit(1)

    def generate(self, base_password):
        chars = string.ascii_letters + string.digits + string.punctuation
        added = ''.join(random.choice(chars) for _ in range(self.add_length))
        random_integer = str(random.randint(10, 99))
        combined = base_password + added + random_integer

        if self.shuffle:
            combined = list(combined)
            random.shuffle(combined)
            combined = ''.join(combined)

        return combined

    @staticmethod
    def show_enhanced_password(enhanced):
        content = f"🔧 [bold green]Enhanced password:[/bold green] [bold yellow]{enhanced}[/bold yellow]"
        panel = Panel(content, border_style="blue", expand=False)
        console.print(panel)

    def save_to_yaml(self, name, password):
        encrypted_password = self.fernet.encrypt(password.encode()).decode()
        data = {}

        if os.path.exists(self.output_file):
            with open(self.output_file, 'r') as f:
                try:
                    data = yaml.safe_load(f) or {}
                except yaml.YAMLError:
                    print("Error reading YAML file. Overwriting.")

        data[name] = encrypted_password

        with open(self.output_file, 'w') as f:
            yaml.safe_dump(data, f)

        print(f"\n🔐 Encrypted password saved under name: {name} in `{self.output_file}`")

    def run(self):
        while True:
            ScreenUtils.clear()

            base_password = self.get_base_password()
            if base_password is None:
                return  # ← exit run() completely

            ScreenUtils.clear()

            enhanced = self.generate(base_password)
            PasswordEnhancer.show_enhanced_password(enhanced)

            choice = input("\nAre you satisfied with this password? (y/n): ").strip().lower()
            if choice == "y":
                label = input("Enter a name for this password (e.g., 'email', 'github'): ").strip()
                self.save_to_yaml(label, enhanced)
                break
            print("\nLet's try again...\n")

class PasswordAdder:
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
        if os.path.exists(self.yaml_file):
            with open(self.yaml_file, "r") as f:
                try:
                    return yaml.safe_load(f) or {}
                except yaml.YAMLError:
                    print("❌ Error reading password file.")
                    sys.exit(1)
        return {}

    def _save_passwords(self, data):
        with open(self.yaml_file, "w") as f:
            yaml.safe_dump(data, f)

    @staticmethod
    def show_added_message(name, password):
        text = f"""✅ Password for '[bold cyan]{name}[/bold cyan]' added successfully.

[bold green]🔐 Stored Password:[/bold green] [bold yellow]{password}[/bold yellow]
"""
        panel = Panel(text, border_style="green", title="Saved", title_align="left", expand=False)
        console.print(panel)

    def _get_name_input(self):
        bindings = KeyBindings()
        cancel_flag = {"cancelled": False}

        @bindings.add("escape")
        def _(event):
            cancel_flag["cancelled"] = True
            event.app.exit("")

        result = prompt(
            "Enter a name for this password (press [Esc] to cancel): ",
            key_bindings=bindings,
        )

        return None if cancel_flag["cancelled"] else result

    def add(self):
        ScreenUtils.clear()

        name = self._get_name_input()
        if name is None or not name.strip():
            print("❌ Name input cancelled or empty.")
            return

        password = questionary.password("Enter the password to store:").ask()
        if not password:
            print("❌ Password cannot be empty.")
            return

        encrypted_data = self._load_encrypted_passwords()

        if name in encrypted_data:
            overwrite = questionary.confirm(f"'{name}' already exists. Overwrite?").ask()
            if not overwrite:
                return

        encrypted_password = self.fernet.encrypt(password.encode()).decode()
        encrypted_data[name] = encrypted_password

        self._save_passwords(encrypted_data)
        ScreenUtils.clear()
        PasswordAdder.show_added_message(name, password)
        input("\nPress [Enter] to return to the menu...")

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
    
    @staticmethod
    def show_deletion_message(name):
        text = f"✅ Password '[bold cyan]{name}[/bold cyan]' deleted."
        panel = Panel(text, border_style="red", title="Deleted", title_align="left", expand=False)
        console.print(panel)


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
                    continue

                # Ask whether to delete the password
                action = questionary.select(
                    "What would you like to do?",
                    choices=["🔙 Return to list", "🗑️ Delete this password"]
                ).ask()

                if action == "🗑️ Delete this password":
                    ScreenUtils.clear()
                    confirm = questionary.confirm(f"Are you sure you want to delete '{selected}'?").ask()
                    if confirm:
                        del encrypted_data[selected]
                        with open(self.yaml_file, "w") as f:
                            yaml.safe_dump(encrypted_data, f)
                        PasswordViewer.show_deletion_message(selected)
                        input("Press [Enter] to continue...")
                        break  # Go back to search view with updated list
