import random
import string
import argparse
import getpass
import sys
import yaml
import os
from cryptography.fernet import Fernet

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
        try:
            return getpass.getpass("Enter your base password: ")
        except KeyboardInterrupt:
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
            base_password = self.get_base_password()
            enhanced = self.generate(base_password)
            print("\nEnhanced password:", enhanced)

            choice = input("\nAre you satisfied with this password? (y/n): ").strip().lower()
            if choice == "y":
                label = input("Enter a name for this password (e.g., 'email', 'github'): ").strip()
                self.save_to_yaml(label, enhanced)
                break
            print("\nLet's try again...\n")
