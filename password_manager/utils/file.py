import os
import sys
import yaml
from cryptography.fernet import Fernet

class Storage:
    def __init__(self, yaml_file="passwords.yaml", key_file="secret.key"):
        self.yaml_file = yaml_file
        self.key_file = key_file
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

    def load_passwords(self) -> dict:
        """Loads and returns passwords from the YAML file."""
        if not os.path.exists(self.yaml_file):
            return {}
        try:
            with open(self.yaml_file, "r") as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError:
            print("❌ Error reading password file.")
            sys.exit(1)

    def save_passwords(self, data: dict):
        """Saves the password dictionary to the YAML file."""
        with open(self.yaml_file, "w") as f:
            yaml.safe_dump(data, f)

    def encrypt(self, password: str) -> str:
        """Encrypts a password string."""
        return self.fernet.encrypt(password.encode()).decode()

    def decrypt(self, encrypted_password: str) -> str:
        """Decrypts an encrypted password string."""
        return self.fernet.decrypt(encrypted_password.encode()).decode()

    @staticmethod
    def read_text(file_path: str) -> str:
        """Reads and returns plain text content from a file."""
        with open(file_path, "r") as file:
            return file.read()

    @staticmethod
    def read_yaml(file_path: str) -> dict:
        """Reads and returns YAML data from a file."""
        with open(file_path, "r") as file:
            return yaml.safe_load(file) or {}
