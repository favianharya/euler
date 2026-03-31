"""Configuration persistence for LocalControl."""
import json
from pathlib import Path
from typing import Dict, Set
import os

CONFIG_DIR = Path.home() / ".localcontrol"
CONFIG_FILE = CONFIG_DIR / "config.json"

def ensure_config_dir():
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def save_manual_projects(manual_projects: Set[str], discovered_projects: Dict[str, Dict]) -> None:
    """
    Save manually added projects to persistent config file.
    
    Args:
        manual_projects: Set of project names that were manually added
        discovered_projects: Dict of all projects with their details
    """
    ensure_config_dir()
    
    # Extract only the manual project details from discovered_projects
    manual_project_data = {}
    for project_name in manual_projects:
        if project_name in discovered_projects:
            manual_project_data[project_name] = discovered_projects[project_name]
    
    config = {
        "manual_projects": manual_project_data
    }
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        # Silently fail - don't crash the app over config issues
        print(f"Warning: Could not save config: {e}")

def load_manual_projects() -> Dict[str, Dict]:
    """
    Load manually added projects from persistent config file.
    
    Returns:
        Dict of manual projects with their details
    """
    if not CONFIG_FILE.exists():
        return {}
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get("manual_projects", {})
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        return {}
