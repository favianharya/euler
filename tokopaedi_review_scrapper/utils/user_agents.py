from dataclasses import dataclass, field
from typing import List
import random
import yaml

@dataclass
class UserAgents:
    agents: List[str] = field(default_factory=list)
    yaml_file: str = "yaml/user_agents__yaml.yaml"  # default YAML path

    @classmethod
    def from_yaml(cls, file_path: str = None):
        # Use the default yaml_file if no path is provided
        path = file_path or cls().yaml_file
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(agents=data.get("agents", []))

    def get_random_user_agent(self) -> str:
        if not self.agents:
            raise ValueError("User agents list is empty!")
        return random.choice(self.agents)
