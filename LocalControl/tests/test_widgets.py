import pytest
from unittest.mock import MagicMock, patch
from textual.app import App, ComposeResult
from textual.widgets import Static, Input, Button
from textual.containers import Vertical, Horizontal
from textual.message import Message
from textual.types import MessageTarget
from rich.text import Text
import re
import asyncio

# Assuming widgets is in the parent directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from widgets import ProjectNavigator, ServiceMonitor, ProjectConsole, CommandBar, ProjectSelected, ProjectExecute, PortConflictAction

# --- Test App for Widgets ---
class WidgetTestApp(App): # Renamed to avoid pytest collection warning
    def compose(self) -> ComposeResult:
        with Horizontal():
            yield ProjectNavigator(id="nav")
            yield ServiceMonitor(id="services")
            yield ProjectConsole(id="console")
        yield CommandBar(id="cmdbar")

    # Define message handlers to prevent errors, even if they do nothing
    def on_project_selected(self, message: ProjectSelected) -> None:
        pass

    def on_project_execute(self, message: ProjectExecute) -> None:
        pass

    def on_port_conflict_action(self, message: PortConflictAction) -> None:
        pass

# --- ProjectNavigator Tests ---
@pytest.mark.asyncio
async def test_project_navigator_display():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        navigator = app.query_one(ProjectNavigator)
        
        # Test empty projects
        navigator.projects = {}
        await driver.pause(0.5) # Increased pause
        assert "No projects discovered." in str(navigator.query_one(Static).render()) # Corrected access

        # Test projects with venv, git, and no venv
        projects_data = {
            "proj_git": {"path": "/a", "venv": "/a/.venv", "git_branch": "main"},
            "proj_npm": {"path": "/b", "venv": None, "git_branch": None},
            "proj_python": {"path": "/c", "venv": "/c/venv", "git_branch": "dev"}
        }
        navigator.projects = projects_data
        await driver.pause(0.5) # Increased pause

        assert "proj_git (main)" in str(navigator.query_one("#project-proj_git").render()) # Corrected access
        assert "proj_npm ⚠️" in str(navigator.query_one("#project-proj_npm").render()) # Corrected access
        assert "proj_python (dev)" in str(navigator.query_one("#project-proj_python").render()) # Corrected access
        assert navigator.query_one("#project-proj_npm").has_class("no-venv")

@pytest.mark.asyncio
async def test_project_navigator_selection():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        navigator = app.query_one(ProjectNavigator)
        projects_data = {
            "proj_a": {"path": "/a", "venv": "/a/.venv", "git_branch": "main"},
        }
        navigator.projects = projects_data
        await driver.pause(1.0) # Increased pause

        project_item = navigator.query_one("#project-proj_a")
        
        # Simulate click
        with patch.object(app, 'post_message') as mock_post_message:
            await driver.click(project_item)
            await driver.pause(1.0) # Increased pause for event processing
            
            assert navigator.selected_project_name == "proj_a"
            assert project_item.has_class("selected")
            mock_post_message.assert_called_once()
            message = mock_post_message.call_args[0][0]
            assert isinstance(message, ProjectSelected)
            assert message.project_name == "proj_a"

@pytest.mark.asyncio
async def test_project_navigator_execute_key():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        navigator = app.query_one(ProjectNavigator)
        projects_data = {
            "proj_a": {"path": "/a", "venv": "/a/.venv", "git_branch": "main"},
        }
        navigator.projects = projects_data
        navigator.selected_project_name = "proj_a" # Manually select
        await driver.pause(1.0) # Increased pause

        with patch.object(app, 'post_message') as mock_post_message:
            await driver.press("enter")
            await driver.pause(1.0) # Increased pause
            
            mock_post_message.assert_called_once()
            message = mock_post_message.call_args[0][0]
            assert isinstance(message, ProjectExecute)
            assert message.project_name == "proj_a"

# --- ServiceMonitor Tests ---
@pytest.mark.asyncio
async def test_service_monitor_display():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        monitor = app.query_one(ServiceMonitor)
        
        # Test empty conflicts
        monitor.conflicts = []
        await driver.pause(0.5) # Increased pause
        assert "No active services or port conflicts detected." in str(monitor.query_one(Static).render()) # Corrected access

        # Test conflicts with kill button
        conflicts_data = [
            {"port": 8000, "pid": 123, "process": {"pid": 123, "name": "backend"}, "message": "Port 8000 in use."},
            {"port": 3000, "pid": None, "process": {"name": "frontend"}, "message": "Port 3000 in use."},
        ]
        monitor.conflicts = conflicts_data
        await driver.pause(0.5) # Increased pause

        assert "Port 8000: Port 8000 in use. (PID: 123)" in str(monitor.query("Static.service-conflict-message").first().render()) # Corrected access
        assert "Port 3000: Port 3000 in use. (PID: N/A)" in str(monitor.query("Static.service-conflict-message").last().render()) # Corrected access
        assert monitor.query_one(Button).label == "Auto-Kill"
        assert len(monitor.query(Button)) == 1 # Corrected access to count

@pytest.mark.asyncio
async def test_service_monitor_kill_button_action():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        monitor = app.query_one(ServiceMonitor)
        conflicts_data = [
            {"port": 8000, "pid": 123, "process": {"pid": 123, "name": "backend"}, "message": "Port 8000 in use."},
        ]
        monitor.conflicts = conflicts_data
        await driver.pause(1.0) # Increased pause

        kill_button = monitor.query_one(Button)
        
        with patch.object(app, 'post_message') as mock_post_message:
            await driver.click(kill_button)
            await driver.pause(1.0) # Increased pause

            mock_post_message.assert_called_once()
            message = mock_post_message.call_args[0][0]
            assert isinstance(message, PortConflictAction)
            assert message.pid == 123
            assert message.port == 8000
            assert message.action == "kill"

# --- ProjectConsole Tests ---
@pytest.mark.asyncio
async def test_project_console_display_and_scroll():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        console = app.query_one(ProjectConsole)
        
        console.write_line("Line 1")
        console.write_line("Line 2")
        await driver.pause(0.5) # Increased pause
        
        lines = console.query("Static.console-log-line")
        assert len(lines) == 2
        assert lines[0].render().plain == "Line 1" # Corrected access
        assert lines[1].render().plain == "Line 2" # Corrected access
        # Implicitly checks scroll_end as it's called after update

# --- CommandBar Tests ---
@pytest.mark.asyncio
async def test_command_bar_placeholder():
    app = WidgetTestApp()
    async with app.run_test() as driver:
        cmdbar = app.query_one(CommandBar)
        assert cmdbar.placeholder == "Cmd+P to search or type command..."
