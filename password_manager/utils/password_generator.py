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

