import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from git import Repo, InvalidGitRepositoryError

def find_nearest_venv(project_path: Path) -> Optional[Path]:
    """
    Finds the nearest virtual environment associated with a project.
    Looks for .venv, venv, env, .env, or nested venv folders.
    """
    # Common venv names to check (in order of preference)
    venv_names = [".venv", "venv", "env", ".env", "virtualenv", ".virtualenv"]
    
    # First check at project root level
    for venv_name in venv_names:
        venv_path = project_path / venv_name
        if venv_path.is_dir() and (venv_path / "bin" / "python").is_file():
            return venv_path
    
    # Check for nested venvs (one level deep)
    # Some projects have structure like: project/venv/venv or project/subfolder/venv
    try:
        for item in project_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                for venv_name in venv_names:
                    nested_venv = item / venv_name
                    if nested_venv.is_dir() and (nested_venv / "bin" / "python").is_file():
                        return nested_venv
    except PermissionError:
        pass  # Skip directories we can't access
    
    # Check for poetry managed environments
    # This might require parsing poetry.toml or similar, for now assume .venv
    # TODO: Implement proper poetry venv detection

    return None


def find_subprojects_with_venvs(project_path: Path) -> list:
    """
    Checks if a project has subfolders that each contain their own venv.
    Returns a list of tuples: (subfolder_name, subfolder_path, venv_path)
    """
    subprojects = []
    venv_names = [".venv", "venv", "env", ".env", "virtualenv", ".virtualenv"]
    
    try:
        for item in project_path.iterdir():
            if not item.is_dir():
                continue
            
            # Skip common directories
            if item.name.startswith('.') or item.name in ['__pycache__', 'node_modules', 'dist', 'build']:
                continue
            
            # Check if this subfolder has a venv
            for venv_name in venv_names:
                venv_path = item / venv_name
                if venv_path.is_dir() and (venv_path / "bin" / "python").is_file():
                    subprojects.append((item.name, item, venv_path))
                    break
    except PermissionError:
        pass  # Skip directories we can't access
    
    return subprojects


def is_project_root(path: Path) -> bool:
    """
    Checks if a given path is a project root by looking for common markers.
    """
    if (path / ".git").is_dir():
        return True
    if (path / "package.json").is_file():
        return True
    if (path / "requirements.txt").is_file():
        return True
    if (path / "pyproject.toml").is_file():
        return True
    if (path / "uv.lock").is_file():
        return True
    return False

def get_git_branch(path: Path) -> Optional[str]:
    """
    Returns the current git branch name for a given repository path.
    """
    try:
        repo = Repo(path)
        return repo.active_branch.name
    except InvalidGitRepositoryError:
        return None
    except Exception as e: # Catch specific unexpected errors, or log them
        # self.app.log(f"Unexpected error in get_git_branch: {e}") # Would need app context
        return None

def get_git_remote_url(path: Path) -> Optional[str]:
    """
    Returns the git remote URL (origin) for a given repository path.
    Converts SSH URLs to HTTPS format for easier clicking.
    """
    try:
        repo = Repo(path)
        if 'origin' in repo.remotes:
            url = repo.remotes.origin.url
            # Convert SSH format to HTTPS
            if url.startswith('git@github.com:'):
                url = url.replace('git@github.com:', 'https://github.com/')
                url = url.replace('.git', '')
            elif url.endswith('.git'):
                url = url[:-4]
            return url
        return None
    except (InvalidGitRepositoryError, Exception):
        return None

def scan_projects(root_dir: Path) -> Dict[str, Any]:
    """
    Recursively scans the root_dir for ALL folders with venvs.
    Every folder containing a venv is treated as a project.
    """
    projects = {}
    
    def scan_for_venvs(current_dir: Path, parent_path: Path = None):
        """Helper to recursively find all venvs."""
        try:
            for path in current_dir.iterdir():
                if not path.is_dir():
                    continue
                
                # Skip venv folders themselves from being scanned deeper
                venv_names = {".venv", "venv", "env", ".env", "virtualenv", ".virtualenv"}
                if path.name in venv_names:
                    continue
                
                # Skip other common non-project directories
                skip_dirs = {"__pycache__", "node_modules", ".git", "dist", "build", 
                           ".idea", ".vscode", "target", "out"}
                if path.name in skip_dirs or path.name.startswith('.'):
                    continue
                
                # Check if this folder has a venv
                venv_path = None
                for venv_name in venv_names:
                    potential_venv = path / venv_name
                    if potential_venv.is_dir() and (potential_venv / "bin" / "python").is_file():
                        venv_path = potential_venv
                        break
                
                # If found a venv, register this as a project
                if venv_path:
                    # Create a display name showing the path from root
                    if parent_path:
                        relative_path = path.relative_to(parent_path)
                        project_name = str(relative_path)
                    else:
                        project_name = path.name
                    
                    git_branch = get_git_branch(path)
                    git_remote = get_git_remote_url(path)
                    
                    projects[project_name] = {
                        "path": str(path.resolve()),
                        "venv": str(venv_path.resolve()),
                        "git_branch": git_branch,
                        "git_remote": git_remote,
                        "status": "active"
                    }
                
                # Continue scanning deeper regardless of whether we found a venv
                scan_for_venvs(path, parent_path or root_dir)
                
        except PermissionError:
            pass  # Skip directories we can't access
    
    scan_for_venvs(root_dir)
    return projects
            
    return projects

if __name__ == "__main__":
    # For testing purposes, scan the parent directory of the current script
    current_script_dir = Path(__file__).parent
    # Assuming projects might be siblings or children of the current project
    projects_to_scan_dir = current_script_dir.parent 
    
    print(f"Scanning for projects in: {projects_to_scan_dir}")
    discovered_projects = scan_projects(projects_to_scan_dir)
    
    print("\nDiscovered Projects:")
    for name, details in discovered_projects.items():
        print(f"  Project: {name}")
        for key, value in details.items():
            print(f"    {key}: {value}")
