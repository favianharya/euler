import yaml

def read_text(file_path: str) -> str:
    """Reads the content of a text file. then returns it as a string."""

    with open(file_path, "r") as file:
        return file.read()


def read_yaml(file_path: str) -> dict:
    """Reads the content of a YAML file. then returns it as a dictionary."""

    with open(file_path, "r") as file:
        return yaml.safe_load(file)
