import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Assuming project_discovery is in the parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from project_discovery import is_project_root, find_nearest_venv, scan_projects, get_git_branch
from git import InvalidGitRepositoryError # Import the actual exception

@pytest.fixture
def temp_project_structure(tmp_path):
    # Root for scanning
    root_dir = tmp_path / "test_repos"
    root_dir.mkdir()

    # Project with .git
    project_git = root_dir / "project_git"
    project_git.mkdir()
    (project_git / ".git").mkdir()
    (project_git / ".venv").mkdir()
    (project_git / ".venv" / "bin").mkdir()
    (project_git / ".venv" / "bin" / "python").touch()

    # Project with package.json
    project_npm = root_dir / "project_npm"
    project_npm.mkdir()
    (project_npm / "package.json").touch()
    (project_npm / "venv").mkdir() # Changed from my_venv to venv
    (project_npm / "venv" / "bin").mkdir()
    (project_npm / "venv" / "bin" / "python").touch()

    # Project with requirements.txt
    project_python = root_dir / "project_python"
    project_python.mkdir()
    (project_python / "requirements.txt").touch()

    # Project with no marker (should not be discovered)
    project_empty = root_dir / "project_empty"
    project_empty.mkdir()

    # Nested project
    nested_dir = root_dir / "parent_dir"
    nested_dir.mkdir()
    nested_project = nested_dir / "nested_project"
    nested_project.mkdir()
    (nested_project / ".git").mkdir()

    yield root_dir

    # Cleanup (handled by tmp_path fixture)

class TestProjectDiscovery:
    def test_is_project_root(self, tmp_path):
        # Test .git
        p = tmp_path / "repo1"
        p.mkdir()
        (p / ".git").mkdir()
        assert is_project_root(p)

        # Test package.json
        p = tmp_path / "repo2"
        p.mkdir()
        (p / "package.json").touch()
        assert is_project_root(p)

        # Test requirements.txt
        p = tmp_path / "repo3"
        p.mkdir()
        (p / "requirements.txt").touch()
        assert is_project_root(p)

        # Test no marker
        p = tmp_path / "repo4"
        p.mkdir()
        assert not is_project_root(p)

    def test_find_nearest_venv(self, tmp_path):
        # Test .venv
        p = tmp_path / "proj1"
        p.mkdir()
        (p / ".venv").mkdir()
        (p / ".venv" / "bin").mkdir()
        (p / ".venv" / "bin" / "python").touch()
        assert find_nearest_venv(p) == (p / ".venv")

        # Test venv
        p = tmp_path / "proj2"
        p.mkdir()
        (p / "venv").mkdir()
        (p / "venv" / "bin").mkdir()
        (p / "venv" / "bin" / "python").touch()
        assert find_nearest_venv(p) == (p / "venv")

        # Test no venv
        p = tmp_path / "proj3"
        p.mkdir()
        assert find_nearest_venv(p) is None

    @patch('project_discovery.Repo')
    def test_get_git_branch_success(self, mock_repo_class, tmp_path):
        p = tmp_path / "my_repo"
        p.mkdir()
        (p / ".git").mkdir()

        mock_repo = MagicMock()
        mock_repo.active_branch.name = "mock_branch_success"
        mock_repo_class.return_value = mock_repo # Ensure Repo(path) returns our mock

        assert get_git_branch(p) == "mock_branch_success"
        mock_repo_class.assert_called_once_with(p)

    @patch('project_discovery.Repo', side_effect=InvalidGitRepositoryError)
    def test_get_git_branch_no_repo(self, mock_repo_class, tmp_path):
        p_non_git = tmp_path / "non_git_repo"
        p_non_git.mkdir()
        # No .git here, so git.Repo will raise InvalidGitRepositoryError, caught by get_git_branch
        assert get_git_branch(p_non_git) is None
        mock_repo_class.assert_called_once_with(p_non_git) # This confirms Repo was attempted to be called

    @patch('project_discovery.get_git_branch')
    def test_scan_projects(self, mock_get_git_branch_func, temp_project_structure):
        # Configure mock_get_git_branch_func to return different values based on the call
        def git_branch_side_effect(path):
            if (path / ".git").is_dir():
                return "mock_branch_scan"
            return None
        
        mock_get_git_branch_func.side_effect = git_branch_side_effect

        root_dir = temp_project_structure
        discovered = scan_projects(root_dir)

        assert "project_git" in discovered
        assert discovered["project_git"]["path"] == str((root_dir / "project_git").resolve())
        assert discovered["project_git"]["venv"] == str((root_dir / "project_git" / ".venv").resolve())
        assert discovered["project_git"]["git_branch"] == "mock_branch_scan"

        assert "project_npm" in discovered
        assert discovered["project_npm"]["path"] == str((root_dir / "project_npm").resolve())
        assert discovered["project_npm"]["venv"] == str((root_dir / "project_npm" / "venv").resolve()) # Corrected venv name
        assert discovered["project_npm"]["git_branch"] is None # Correct for non-git

        assert "project_python" in discovered
        assert discovered["project_python"]["path"] == str((root_dir / "project_python").resolve())
        assert discovered["project_python"]["venv"] is None # No venv in this one
        assert discovered["project_python"]["git_branch"] is None # Correct for non-git

        assert "nested_project" in discovered
        assert discovered["nested_project"]["path"] == str((root_dir / "parent_dir" / "nested_project").resolve())
        assert discovered["nested_project"]["venv"] is None # No venv in this one
        assert discovered["nested_project"]["git_branch"] == "mock_branch_scan" # From the patched get_git_branch

        assert "project_empty" not in discovered # Should not be discovered
        assert "parent_dir" not in discovered # Parent dir itself is not a project
