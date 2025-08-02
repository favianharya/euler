import random
import string
import argparse
import sys
import yaml
import os
from cryptography.fernet import Fernet

from utils.view import ScreenUtils
from utils.file import Storage

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings

from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app_or_none

import questionary
from zxcvbn import zxcvbn

console = Console()

class PasswordEnhancer:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Enhance your password with random characters.")
        parser.add_argument("-l", "--length", type=int, default=6, help="Number of random characters to add")
        parser.add_argument("-ns", "--no-shuffle", action="store_true", help="Disable shuffling of the final password")
        args = parser.parse_args()

        self.add_length = args.length
        self.shuffle = not args.no_shuffle
        self.storage = Storage()

    def get_base_password(self):
        bindings = KeyBindings()
        session = PromptSession()

        @bindings.add("escape")
        def _(event):
            event.app.exit(result=None)

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
        encrypted_password = self.storage.encrypt(password)
        data = self.storage.load_passwords()
        data[name] = encrypted_password
        self.storage.save_passwords(data)

        print(f"\n🔐 Encrypted password saved under name: {name} in `{self.storage.yaml_file}`")

    def run(self):
        while True:
            ScreenUtils.clear()

            base_password = self.get_base_password()
            if base_password is None:
                return

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
    def __init__(self):
        self.storage = Storage()

    def _get_name_input(self):
        bindings = KeyBindings()
        cancel_flag = {"cancelled": False}

        @bindings.add("escape")
        def _(event):
            cancel_flag["cancelled"] = True
            event.app.exit("")

        while True:
            result = prompt(
                "Enter a name for this password (press [Esc] to cancel): ",
                key_bindings=bindings,
            )

            if cancel_flag["cancelled"]:
                return None

            if not result.strip():
                print("❌ Name input cancelled or empty.")
                continue

            return result.strip()

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

        encrypted_data = self.storage.load_passwords()

        if name in encrypted_data:
            overwrite = questionary.confirm(f"'{name}' already exists. Overwrite?").ask()
            if not overwrite:
                return

        encrypted_password = self.storage.encrypt(password)
        encrypted_data[name] = encrypted_password

        self.storage.save_passwords(encrypted_data)
        ScreenUtils.clear()
        PasswordAdder.show_added_message(name, password)
        input("\nPress [Enter] to return to the menu...")

    @staticmethod
    def show_added_message(name, password):
        text = f"""✅ Password for '[bold cyan]{name}[/bold cyan]' added successfully.

[bold green]🔐 Stored Password:[/bold green] [bold yellow]{password}[/bold yellow]
"""
        panel = Panel(text, border_style="green", title="Saved", title_align="left", expand=False)
        console.print(panel)

class PasswordViewer:
    def __init__(self):
        self.storage = Storage()

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

    def view(self):
        while True:
            ScreenUtils.clear()
            encrypted_data = self.storage.load_passwords()

            if not encrypted_data:
                print("🔎 No saved passwords found.")
                input("\nPress [Enter] to return to the menu...")
                break

            all_passwords = sorted(encrypted_data.keys())

            while True:
                ScreenUtils.clear()
                search = self._get_search_input()
                if search is None:
                    return
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
                    continue

                ScreenUtils.clear()
                try:
                    decrypted = self.storage.decrypt(encrypted_data[selected])
                    PasswordViewer.show_password(selected, decrypted)
                except Exception:
                    print(f"\n❌ Failed to decrypt password for '{selected}'")
                    input("\nPress [Enter] to return to the password list...")
                    continue

                action = questionary.select(
                    "What would you like to do?",
                    choices=["🔙 Return to list", "🗑️ Delete this password"]
                ).ask()

                if action == "🗑️ Delete this password":
                    ScreenUtils.clear()
                    confirm = questionary.confirm(f"Are you sure you want to delete '{selected}'?").ask()
                    if confirm:
                        del encrypted_data[selected]
                        self.storage.save_passwords(encrypted_data)
                        PasswordViewer.show_deletion_message(selected)
                        input("Press [Enter] to continue...")
                        break
    
    @staticmethod
    def show_password(selected, decrypted):
        analysis = zxcvbn(decrypted)

        score_labels = {
            0: "🟥 Very Weak",
            1: "🟧 Weak",
            2: "🟨 Fair",
            3: "🟩 Strong",
            4: "🟦 Very Strong"
        }

        score = analysis["score"]
        crack_time = analysis["crack_times_display"]["offline_fast_hashing_1e10_per_second"]
        feedback = analysis["feedback"]

        text = Text()
        text += Text.from_markup(f"🔐 Password for '[bold cyan]{selected}[/bold cyan]':\n")
        text += Text.from_markup(f"[bold yellow]{decrypted}[/bold yellow]\n\n")
        text += Text.from_markup(f"🔎 Strength: {score_labels[score]}\n")
        text += Text.from_markup(f"⏳ Estimated crack time: [bold]{crack_time}[/bold]\n")

        if feedback["warning"]:
            text += Text.from_markup(f"⚠️  Warning: [red]{feedback['warning']}[/red]\n")

        if feedback["suggestions"]:
            text += Text.from_markup("💡 Suggestions:\n", style="blue")
            for s in feedback["suggestions"]:
                text += Text(f"   - {s}\n")

        console.print(Panel(text, border_style="green", title="Password Details", expand=False))

    @staticmethod
    def show_deletion_message(name):
        text = f"✅ Password '[bold cyan]{name}[/bold cyan]' deleted."
        panel = Panel(text, border_style="red", title="Deleted", title_align="left", expand=False)
        console.print(panel)

class PasswordPowerChecker:
    def __init__(self):
        self.console = Console()
        self.strength_levels = {
            0: ("💀 Very Weak", "bold red"),
            1: ("⚠️ Weak", "red"),
            2: ("🟡 Fair", "yellow"),
            3: ("🟢 Strong", "green"),
            4: ("✅ Very Strong", "bold green")
        }
        self.escape_pressed = False

    def check(self, password: str):
        result = zxcvbn(password)
        score = result['score']
        feedback = result['feedback']
        level_text, color = self.strength_levels.get(score, ("Unknown", "white"))

        # Prepare output
        password_info = Text()
        password_info.append(f"Password: ", style="bold cyan")
        password_info.append(f"{password}\n")
        password_info.append(f"Strength: ", style="bold cyan")
        password_info.append(f"{level_text}\n", style=color)

        if feedback['warning']:
            password_info.append("\n⚠️ Warning:\n", style="bold red")
            password_info.append(f"  {feedback['warning']}\n")

        if feedback['suggestions']:
            password_info.append("\n💡 Suggestions:\n", style="bold yellow")
            for suggestion in feedback['suggestions']:
                password_info.append(f"  - {suggestion}\n")

        self.console.print(Panel(password_info, title="🔐 Password Power Checker", border_style=color))

    def get_password_input(self):
        bindings = KeyBindings()

        @bindings.add('escape')
        def _(event):
            self.escape_pressed = True
            event.app.exit()

        while True:
            self.escape_pressed = False
            password = prompt("Enter your password: ", key_bindings=bindings)

            if self.escape_pressed:
                return None

            if password is None or password.strip() == "":
                print("❌ Password input cancelled or empty.")
                continue  # retry

            return password 


    def run(self):
        while True:
            ScreenUtils.clear()
            self.console.print("[cyan]🔍 Analyze your password strength with instant feedback[/cyan]\n")
            password = self.get_password_input()
            if password is None:
                return  # User pressed Esc

            self.check(password)

            # Ask to check another password
            again = questionary.confirm("🔁 Do you want to check another password?").ask()
            if not again:
                break