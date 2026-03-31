from textual.widgets import Static, Input, Button # Import Button
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual import events
from textual.app import ComposeResult
import re # Import regex module
from textual.message import Message
from pathlib import Path


class AutocompleteInput(Input):
    """Custom Input widget with autocomplete suggestions."""
    
    command_history = reactive([])
    suggestion = reactive("")  # Current suggestion
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history_index = -1  # For up/down arrow navigation
        self._original_value = ""  # Store original value when navigating history
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Update suggestion as user types."""
        current_text = self.value
        
        # Reset history navigation when user types
        self.history_index = -1
        
        if not current_text:
            self.suggestion = ""
            return
        
        # Find matching command from history (most recent match)
        for cmd in reversed(self.command_history):
            if cmd.startswith(current_text) and cmd != current_text:
                self.suggestion = cmd[len(current_text):]
                return
        
        self.suggestion = ""
    
    def watch_suggestion(self, suggestion: str) -> None:
        """Update placeholder to show suggestion."""
        if suggestion:
            # Show suggestion in a dimmed style via placeholder
            self.placeholder = suggestion
        else:
            self.placeholder = "Enter command..."
    
    def on_key(self, event: events.Key) -> None:
        """Handle special keys for autocomplete."""
        # Accept suggestion with right arrow or Tab
        if event.key in ("right", "tab") and self.suggestion and self.cursor_position == len(self.value):
            self.value = self.value + self.suggestion
            self.suggestion = ""
            self.cursor_position = len(self.value)
            event.prevent_default()
            event.stop()
            return
        
        # Navigate command history with up/down arrows
        if event.key == "up":
            if self.command_history:
                if self.history_index == -1:
                    self._original_value = self.value
                    self.history_index = len(self.command_history) - 1
                elif self.history_index > 0:
                    self.history_index -= 1
                
                self.value = self.command_history[self.history_index]
                self.cursor_position = len(self.value)
                self.suggestion = ""
            event.prevent_default()
            event.stop()
            return
        
        if event.key == "down":
            if self.command_history and self.history_index != -1:
                if self.history_index < len(self.command_history) - 1:
                    self.history_index += 1
                    self.value = self.command_history[self.history_index]
                else:
                    self.history_index = -1
                    self.value = self._original_value
                
                self.cursor_position = len(self.value)
                self.suggestion = ""
            event.prevent_default()
            event.stop()
            return


class ProjectSelected(Message):
    """Custom message to indicate a project has been selected."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class ProjectExecute(Message):
    """Custom message to indicate a project should be executed."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class ProjectOpenTerminal(Message):
    """Custom message to open project in external iTerm terminal."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class ProjectExecuteRaw(Message):
    """Custom message to execute project without venv (raw terminal in console)."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class ProjectOpenTerminalRaw(Message):
    """Custom message to open project in iTerm without venv."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class ProjectOpenGemini(Message):
    """Custom message to open Gemini CLI for a project."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class ProjectOpenOpenCode(Message):
    """Custom message to open OpenCode for a project."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class PortConflictAction(Message):
    """Custom message to request action on a port conflict."""

    def __init__(self, pid: int, port: int, action: str) -> None:
        super().__init__()
        self.pid = pid
        self.port = port
        self.action = action # e.g., "kill", "restart"

class TerminalCloseRequest(Message):
    """Custom message to request closing a terminal."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name

class RunCommand(Message):
    """Custom message to run a command in the embedded terminal."""

    def __init__(self, command: str) -> None:
        super().__init__()
        self.command = command

class TerminalOutput(Message):
    """Custom message for terminal output from background thread."""

    def __init__(self, project_name: str, line: str) -> None:
        super().__init__()
        self.project_name = project_name
        self.line = line

class TerminalInterrupt(Message):
    """Custom message to send Ctrl+C interrupt to terminal."""
    
    def __init__(self, tab_id: str = None) -> None:
        super().__init__()
        self.tab_id = tab_id  # Which tab to interrupt (None = current)

class KillPort(Message):
    """Custom message to kill a process."""

    def __init__(self, pid: int, process_name: str, port: int = None) -> None:
        super().__init__()
        self.pid = pid
        self.port = port  # Optional, kept for backward compatibility
        self.process_name = process_name

class FocusApp(Message):
    """Custom message to focus/bring forward an application."""

    def __init__(self, process_name: str, pid: int) -> None:
        super().__init__()
        self.process_name = process_name
        self.pid = pid

class AddFolder(Message):
    """Custom message to request adding a folder manually."""
    pass

class RemoveProject(Message):
    """Custom message to remove a manually added project."""

    def __init__(self, project_name: str) -> None:
        super().__init__()
        self.project_name = project_name


class ProjectNavigator(Vertical):
    """A widget to display a list of projects."""

    projects = reactive(dict)
    selected_project_name = reactive(None)
    selected_widget = None  # Track the selected widget directly
    active_terminals = set()  # Track which projects have active terminals
    manual_projects = set()  # Track manually added projects
    _last_click_time = 0  # Track last click time for double-click detection
    _last_clicked_widget = None  # Track last clicked widget
    
    can_focus = True  # Allow this widget to receive keyboard focus
    
    BINDINGS = [
        ("a", "add_folder", "Add Folder"),
        ("d", "remove_project", "Remove"),
        ("ctrl+r", "refresh_projects", "Refresh"),
        ("enter", "execute_project", "Console w/ venv"),
        ("r", "execute_raw", "Console w/o venv"),
        ("t", "open_terminal", "iTerm w/ venv"),
        ("T", "open_terminal_raw", "iTerm w/o venv"),
        ("g", "open_gemini", "Gemini CLI"),
        ("o", "open_opencode", "OpenCode"),
    ]
    
    def on_focus(self) -> None:
        """Log when navigator receives focus."""
        self.app.log("✅ Navigator received focus")
    
    def on_blur(self) -> None:
        """Log when navigator loses focus."""
        self.app.log("⚠️ Navigator lost focus")
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the navigator."""
        with Horizontal(id="navigator-buttons"):
            yield Button("+ Add", id="add-folder-btn", classes="nav-button")
            yield Button("↻ Refresh", id="refresh-btn", classes="nav-button")
            yield Button("x Del", id="remove-folder-btn", classes="nav-button remove-button")
        yield ScrollableContainer(id="project-list")

    def watch_projects(self, projects: dict) -> None:
        """Called when the projects reactive changes."""
        self.app.log(f"watch_projects called with {len(projects) if projects else 0} projects")
        if projects:
            self.app.log(f"Project keys: {list(projects.keys())}")
        else:
            self.app.log("WARNING: watch_projects called with empty/None projects dict!")
        self.refresh_projects()
    
    def watch_selected_project_name(self, project_name: str) -> None:
        """Update remove button state when selection changes."""
        self._update_remove_button()
    
    def _update_remove_button(self) -> None:
        """Enable/disable remove button based on whether selected project is manual."""
        try:
            remove_btn = self.query_one("#remove-folder-btn", Button)
            if self.selected_project_name and self.selected_project_name in self.manual_projects:
                remove_btn.disabled = False
                remove_btn.variant = "error"
            else:
                remove_btn.disabled = True
                remove_btn.variant = "default"
        except Exception:
            pass
    
    def refresh_projects(self) -> None:
        """Refresh the project list display."""
        self.app.log(f"=== refresh_projects called, have {len(self.projects)} projects ===")
        
        try:
            # Remember which project was selected
            currently_selected = self.selected_project_name
            self.app.log(f"Currently selected before refresh: {currently_selected}")
            
            # Get the project list container
            try:
                project_container = self.query_one("#project-list", ScrollableContainer)
            except Exception as e:
                self.app.log(f"ERROR: Cannot find project container: {e}")
                return
            
            # Always recreate to ensure consistency
            self.app.log(f"Clearing container and recreating {len(self.projects)} projects")
            
            # Remove all children - do it explicitly
            children = list(project_container.children)
            for child in children:
                child.remove()
            
            if not self.projects:
                self.app.log("No projects to display")
                project_container.mount(Static("No projects discovered."))
                self._update_remove_button()
                return
            
            self.selected_widget = None  # Reset since we're recreating widgets
            
            # Mount all projects
            for name, details in self.projects.items():
                self.app.log(f"Mounting project widget for: {name}")
                venv_status = ""
                project_classes = "project-item"
                
                # Add active terminal indicator
                terminal_indicator = ""
                manual_indicator = ""
                if name in self.active_terminals:
                    terminal_indicator = " 🔵"
                    project_classes += " terminal-active"
                
                # Add manual project indicator
                if name in self.manual_projects:
                    manual_indicator = " 📌"  # Pin icon for manual projects
                
                if not details.get('venv'):
                    venv_status = " ⚠️" # Warning icon for missing venv
                    project_classes += " no-venv" # Add a class for styling
                
                # Check if this was the previously selected project
                if name == currently_selected:
                    project_classes += " selected"
                    self.app.log(f"Restoring selection to: {name}")
                
                # Sanitize name to create a valid Textual ID
                sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name).lower()
                project_display = Static(f"{name}{venv_status}{terminal_indicator}{manual_indicator}", classes=project_classes, id=f"project-{sanitized_name}")
                project_display.data = {"project_name": name}
                project_container.mount(project_display)
                
                # Restore selected_widget reference if this was selected
                if name == currently_selected:
                    self.selected_widget = project_display
                    self.selected_project_name = name  # Ensure selected_project_name is preserved
                    self.app.log(f"Selected widget and name restored: {name}")
            
            # Verify what we mounted
            mounted_count = len(list(project_container.query(".project-item")))
            self.app.log(f"=== Finished mounting. Container now has {mounted_count} project widgets ===")
            self.app.log(f"Selected project after refresh: {self.selected_project_name}")
            self._update_remove_button()
        except Exception as e:
            self.app.log(f"Error refreshing projects: {e}")
            # Try to remount at least something
            project_container = self.query_one("#project-list", ScrollableContainer)
            if not project_container.query(".project-item"):
                project_container.mount(Static(f"Error: {e}", classes="error-message"))
    
    def _update_existing_widgets(self) -> None:
        """Update existing widgets without recreating them."""
        try:
            project_container = self.query_one("#project-list", ScrollableContainer)
            for widget in project_container.query(".project-item"):
                name = widget.data.get("project_name")
                if not name or name not in self.projects:
                    continue
                
                details = self.projects[name]
                venv_status = " ⚠️" if not details.get('venv') else ""
                terminal_indicator = " 🟢" if name in self.active_terminals else ""
                manual_indicator = " 📌" if name in self.manual_projects else ""
                
                # Update display text
                widget.update(f"{name}{venv_status}{terminal_indicator}{manual_indicator}")
                
                # Update classes
                widget.remove_class("terminal-active")
                if name in self.active_terminals:
                    widget.add_class("terminal-active")
        except Exception as e:
            self.app.log(f"Error updating widgets: {e}")
        
        self._update_remove_button()

    def on_mount(self) -> None:
        # Initial render of projects
        self.refresh_projects()
        
        # Auto-select first project if none selected
        if not self.selected_project_name and self.projects:
            first_project = next(iter(self.projects.keys()))
            project_container = self.query_one("#project-list", ScrollableContainer)
            for widget in project_container.query(".project-item"):
                if widget.data.get("project_name") == first_project:
                    self.selected_widget = widget
                    self.selected_project_name = first_project
                    widget.add_class("selected")
                    break
        
        # Give this widget focus so it can receive keyboard events
        self.focus()

    def on_click(self, event: events.Click) -> None:
        """Called when the user clicks on a project item."""
        if event.button == 1: # Left click
            # Check if clicked on a project item (could be in nested container)
            clicked_widget = event.widget
            
            # Walk up the widget tree to find a project item
            while clicked_widget and clicked_widget != self:
                if hasattr(clicked_widget, 'classes') and "project-item" in clicked_widget.classes:
                    # Check for double-click (within 0.5 seconds)
                    import time
                    current_time = time.time()
                    is_double_click = (
                        self._last_clicked_widget == clicked_widget and
                        (current_time - self._last_click_time) < 0.5
                    )
                    
                    self._last_click_time = current_time
                    self._last_clicked_widget = clicked_widget
                    
                    # Remove highlight from previously selected item
                    if self.selected_widget:
                        try:
                            self.selected_widget.remove_class("selected")
                        except Exception:
                            pass  # Widget might have been removed during refresh

                    # Add highlight to new selected item
                    self.selected_project_name = clicked_widget.data.get("project_name") # Retrieve original name from data
                    if self.selected_project_name: # Ensure a project name was retrieved
                        self.selected_widget = clicked_widget
                        clicked_widget.add_class("selected")
                        self.focus()  # Ensure navigator has focus for keyboard input
                        self.post_message(ProjectSelected(self.selected_project_name)) # Emit custom message
                        self.app.log(f"Selected project: {self.selected_project_name}")
                        
                        # On double-click, execute project (like pressing Enter)
                        if is_double_click:
                            self.app.log(f"Double-click detected on: {self.selected_project_name}")
                            self.action_execute_project()
                    break
                clicked_widget = clicked_widget.parent
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses for add/remove/refresh."""
        if event.button.id == "add-folder-btn":
            self.post_message(AddFolder())
        elif event.button.id == "refresh-btn":
            self.action_refresh_projects()
        elif event.button.id == "remove-folder-btn":
            if self.selected_project_name and self.selected_project_name in self.manual_projects:
                self.post_message(RemoveProject(project_name=self.selected_project_name))
    
    def action_execute_project(self) -> None:
        """Execute project in console with venv."""
        if self.selected_project_name:
            self.post_message(ProjectExecute(self.selected_project_name))
            self.app.log(f"Attempting to execute project: {self.selected_project_name}")
    
    def action_execute_raw(self) -> None:
        """Execute project in console without venv."""
        if self.selected_project_name:
            self.post_message(ProjectExecuteRaw(self.selected_project_name))
            self.app.log(f"Opening raw console terminal for: {self.selected_project_name}")
    
    def action_open_terminal(self) -> None:
        """Open iTerm terminal with venv."""
        if self.selected_project_name:
            self.post_message(ProjectOpenTerminal(self.selected_project_name))
            self.app.log(f"Opening iTerm terminal for: {self.selected_project_name}")
    
    def action_open_terminal_raw(self) -> None:
        """Open iTerm terminal without venv."""
        if self.selected_project_name:
            self.post_message(ProjectOpenTerminalRaw(self.selected_project_name))
            self.app.log(f"Opening raw iTerm terminal for: {self.selected_project_name}")
    
    def action_open_gemini(self) -> None:
        """Open Gemini CLI in iTerm."""
        if self.selected_project_name:
            self.post_message(ProjectOpenGemini(self.selected_project_name))
            self.app.log(f"Opening Gemini CLI for: {self.selected_project_name}")

    def action_open_opencode(self) -> None:
        """Open OpenCode in iTerm."""
        if self.selected_project_name:
            self.post_message(ProjectOpenOpenCode(self.selected_project_name))
            self.app.log(f"Opening OpenCode for: {self.selected_project_name}")
    
    def on_key(self, event: events.Key) -> None:
        """Handles key presses for navigation."""
        self.app.log(f"Navigator received key: {event.key}")
        if event.key in ("up", "down", "j", "k"):
            # Handle arrow key navigation
            self.app.log(f"Navigating with key: {event.key}")
            self.navigate_projects(event.key)
            event.prevent_default()
            event.stop()
    
    def navigate_projects(self, direction: str) -> None:
        """Navigate through projects with arrow keys."""
        if not self.projects:
            return
        
        project_names = list(self.projects.keys())
        if not project_names:
            return
        
        if self.selected_project_name in project_names:
            current_index = project_names.index(self.selected_project_name)
        else:
            current_index = -1
        
        # Calculate new index
        if direction in ("down", "j"):
            new_index = (current_index + 1) % len(project_names)
        else:  # up or k
            new_index = (current_index - 1) % len(project_names)
        
        # Select the new project
        new_project_name = project_names[new_index]
        
        # Remove old selection
        if self.selected_widget:
            try:
                self.selected_widget.remove_class("selected")
            except Exception:
                pass
        
        # Find and select new widget
        project_container = self.query_one("#project-list", ScrollableContainer)
        for widget in project_container.query(".project-item"):
            if widget.data.get("project_name") == new_project_name:
                self.selected_widget = widget
                self.selected_project_name = new_project_name
                widget.add_class("selected")
                widget.scroll_visible()
                self.post_message(ProjectSelected(new_project_name))
                break
    
    def action_add_folder(self) -> None:
        """Request to add a folder manually."""
        self.post_message(AddFolder())
    
    def action_remove_project(self) -> None:
        """Request to remove the selected project (if manually added)."""
        if self.selected_project_name and self.selected_project_name in self.manual_projects:
            self.post_message(RemoveProject(project_name=self.selected_project_name))
    
    def action_refresh_projects(self) -> None:
        """Manually refresh the project list from app state."""
        self.app.log("Manual refresh triggered")
        # Get fresh project data from main app
        if hasattr(self.app, 'discovered_projects'):
            self.projects = dict(self.app.discovered_projects)
            self.manual_projects = set(self.app.manual_projects)
            self.active_terminals = set(self.app.active_terminals.keys())
        # Force full refresh
        self.refresh_projects()
    
    def add_project_directly(self, name: str, details: dict, is_manual: bool = False) -> None:
        """Directly add a project without relying on reactive."""
        self.app.log(f"add_project_directly called for: {name}")
        
        # Add to internal projects dict
        self.projects[name] = details
        
        if is_manual:
            self.manual_projects.add(name)
        
        # Get container and add the widget
        try:
            project_container = self.query_one("#project-list", ScrollableContainer)
            
            # Remove "No projects" message if present
            for widget in project_container.query():
                if not widget.has_class("project-item"):
                    widget.remove()
            
            # Create and mount the new project widget
            venv_status = " ⚠️" if not details.get('venv') else ""
            manual_indicator = " 📌" if is_manual else ""
            
            sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name).lower()
            project_display = Static(
                f"{name}{venv_status}{manual_indicator}",
                classes="project-item",
                id=f"project-{sanitized_name}"
            )
            project_display.data = {"project_name": name}
            project_container.mount(project_display)
            
            # Force refresh the container to ensure visibility
            project_container.refresh()
            self.refresh()
            
            self.app.log(f"Successfully added {name} to navigator")
            self._update_remove_button()
            
        except Exception as e:
            self.app.log(f"ERROR adding project widget: {e}")
    
    def remove_project_directly(self, name: str) -> None:
        """Directly remove a project widget without affecting others."""
        self.app.log(f"remove_project_directly called for: {name}")
        
        try:
            # Remove from internal dicts
            if name in self.projects:
                del self.projects[name]
            self.manual_projects.discard(name)
            
            # Find and remove the specific widget
            project_container = self.query_one("#project-list", ScrollableContainer)
            sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name).lower()
            widget_id = f"project-{sanitized_name}"
            
            # Try to find by ID first
            try:
                widget = self.query_one(f"#{widget_id}")
                widget.remove()
                self.app.log(f"Removed widget by ID: {widget_id}")
            except Exception:
                # Fall back to searching by data
                for widget in project_container.query(".project-item"):
                    if widget.data.get("project_name") == name:
                        widget.remove()
                        self.app.log(f"Removed widget by data match: {name}")
                        break
            
            # Clear selection if this was selected
            if self.selected_project_name == name:
                self.selected_project_name = None
                self.selected_widget = None
            
            # Check if we need to show "No projects" message
            if not self.projects:
                project_container.mount(Static("No projects discovered."))
            
            self._update_remove_button()
            self.app.log(f"Successfully removed {name} from navigator")
            
        except Exception as e:
            self.app.log(f"ERROR removing project widget: {e}")


class ServiceMonitor(Vertical):
    """A widget to display active services and port conflicts."""

    conflicts = reactive(list)
    active_terminals = reactive(dict)

    def watch_conflicts(self, conflicts: list) -> None:
        self._update_display()

    def watch_active_terminals(self, terminals: dict) -> None:
        self._update_display()

    def _update_display(self) -> None:
        """Update the display to show both active terminals and port conflicts."""
        self.remove_children()
        
        # Show active terminals first
        if self.active_terminals:
            self.mount(Static("🖥️  Active Terminals", classes="service-section-header"))
            for project_name, terminal_info in self.active_terminals.items():
                venv_path = terminal_info.get('venv', 'N/A')
                venv_name = Path(venv_path).parent.name if venv_path and venv_path != 'N/A' else 'N/A'
                terminal_line = Static(f"🟢 {project_name} [{venv_name}]", classes="active-terminal-line")
                self.mount(terminal_line)
                
                close_button = Button("Close Terminal", classes="close-terminal-button")
                close_button.data = {"project_name": project_name}
                self.mount(close_button)
        
        # Show port conflicts
        if self.conflicts:
            if self.active_terminals:  # Add spacing if we had terminals above
                self.mount(Static(""))
            self.mount(Static("🚨 Port Conflicts", classes="service-section-header"))
            
            for conflict in self.conflicts:
                message = conflict["message"]
                process_details = conflict["process"]
                port = conflict["port"]
                pid = process_details.get('pid', None)

                conflict_line = Static(f"Port {port}: {message} (PID: {pid if pid else 'N/A'})", classes="service-conflict-message")
                self.mount(conflict_line)

                if pid:
                    kill_button = Button("Auto-Kill", classes="kill-button")
                    kill_button.data = {"pid": pid, "port": port}
                    self.mount(kill_button)
        
        # Show message if nothing to display
        if not self.active_terminals and not self.conflicts:
            self.mount(Static("No active terminals or port conflicts detected."))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses for terminal and port conflict actions."""
        if "close-terminal-button" in event.button.classes:
            project_name = event.button.data.get("project_name")
            if project_name:
                self.post_message(TerminalCloseRequest(project_name=project_name))
                self.app.log(f"Requested to close terminal for {project_name}")
        elif "kill-button" in event.button.classes:
            pid = event.button.data.get("pid")
            port = event.button.data.get("port")
            if pid and port:
                self.post_message(PortConflictAction(pid=pid, port=port, action="kill"))
                self.app.log(f"Requested to kill PID {pid} on port {port}")

    def on_mount(self) -> None:
        """Initial setup - defer update to ensure children are mounted."""
        self.call_after_refresh(self._update_display)


class ProjectConsole(Vertical):
    """A widget to display console output for running terminal commands."""

    console_lines = reactive([])
    active_venv = reactive(None)  # Track which venv is currently active
    git_branch = reactive(None)  # Track current git branch
    project_name = reactive(None)  # Track current project name
    command_history = reactive([])  # Track command history for autocomplete
    
    BINDINGS = [
        ("ctrl+c", "interrupt", "Interrupt"),
        ("ctrl+l", "clear_console", "Clear"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create child widgets with simple console interface."""
        yield ScrollableContainer(id="console-output")
        with Horizontal(id="console-input-bar"):
            yield Static("$", id="console-prompt")
            yield AutocompleteInput(placeholder="Select a project and press Enter to start terminal...", id="console-input")

    def watch_console_lines(self, lines: list) -> None:
        """Update console output when lines change."""
        try:
            output = self.query_one("#console-output", ScrollableContainer)
            output.remove_children()
            for line in lines:
                output.mount(Static(line, classes="console-log-line"))
            output.scroll_end()
        except Exception as e:
            self.app.log(f"Error updating console: {e}")
    
    def watch_command_history(self, history: list) -> None:
        """Update autocomplete input with new command history."""
        try:
            console_input = self.query_one("#console-input", AutocompleteInput)
            console_input.command_history = history
        except Exception:
            pass

    def watch_active_venv(self, venv_info) -> None:
        """Update prompt when venv changes."""
        self._update_prompt()
    
    def watch_git_branch(self, branch: str) -> None:
        """Update prompt when branch changes."""
        self._update_prompt()
    
    def watch_project_name(self, project: str) -> None:
        """Update prompt when project changes."""
        self._update_prompt()
    
    def _update_prompt(self) -> None:
        """Update the console prompt with project/venv and/or branch info."""
        try:
            prompt = self.query_one("#console-prompt", Static)
            parts = []
            
            # Show venv name if available, otherwise show project name
            if self.active_venv:
                parts.append(self.active_venv['name'])
            elif self.project_name:
                parts.append(self.project_name)
            
            if self.git_branch:
                parts.append(self.git_branch)
            
            if parts:
                prompt.update(f"({' | '.join(parts)}) $")
            else:
                prompt.update("$")
        except Exception as e:
            self.app.log(f"Error updating prompt: {e}")

    def write_line(self, line: str) -> None:
        """Write a line to the console output."""
        try:
            output = self.query_one("#console-output", ScrollableContainer)
            output.mount(Static(line, classes="console-log-line"))
            output.scroll_end()
        except Exception as e:
            self.app.log(f"Error writing line: {e}")

    def clear(self) -> None:
        """Clear all console output."""
        try:
            output = self.query_one("#console-output", ScrollableContainer)
            output.remove_children()
        except Exception as e:
            self.app.log(f"Error clearing console: {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command submission."""
        command = event.value.strip()
        if command:
            self.post_message(RunCommand(command=command))
            event.input.value = ""
    
    def action_interrupt(self) -> None:
        """Handle Ctrl+C to interrupt running process."""
        self.post_message(TerminalInterrupt())
        self.write_line("^C")
    
    def action_clear_console(self) -> None:
        """Handle Ctrl+L to clear console output."""
        self.clear()

    def on_mount(self) -> None:
        """Initial setup - defer writing to ensure children are mounted."""
        def write_initial_text():
            self.write_line("✨ LocalControl Terminal ready!")
            self.write_line("📌 Enter=console with venv | r=console without venv")
            self.write_line("🖥️  t=iTerm with venv | T=iTerm without venv | g=Gemini CLI | o=OpenCode")
            self.write_line("💻 Ctrl+C=interrupt | Ctrl+L=clear")
        self.call_after_refresh(write_initial_text)




class PortMonitor(Vertical):
    """A widget to display all running applications and allow instant killing."""

    can_focus = True  # Allow focusing this widget
    ports = reactive(list)
    selected_index = reactive(0)
    search_term = reactive("")  # Track search filter
    _last_click_time = 0  # Track last click time for double-click detection
    _last_clicked_index = None  # Track last clicked index
    
    BINDINGS = [
        ("enter", "focus_selected", "Focus App"),
        ("x", "kill_selected", "Kill Selected"),
        ("delete", "kill_selected", "Kill Selected"),
        ("up", "move_up", "Move Up"),
        ("down", "move_down", "Move Down"),
        ("j", "move_down", "Move Down"),
        ("k", "move_up", "Move Up"),
        ("/", "focus_search", "Search Apps"),
        ("ctrl+f", "focus_search", "Search Apps"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the port monitor."""
        yield ScrollableContainer(id="port-list-container")
        yield Input(placeholder="Type to search apps...", id="port-search-input")

    def watch_ports(self, ports: list) -> None:
        # Reset selection when ports change
        if self.selected_index >= len(ports):
            self.selected_index = 0
        self._update_display()
    
    def watch_search_term(self, search_term: str) -> None:
        # Reset selection when search changes
        self.selected_index = 0
        self._update_display()

    def _update_display(self) -> None:
        """Update the display to show all running applications."""
        try:
            container = self.query_one("#port-list-container", ScrollableContainer)
        except Exception:
            # Container not mounted yet
            return
        
        container.remove_children()
        
        if not self.ports:
            container.mount(Static("No running applications detected.", classes="port-empty-message"))
            return
        
        container.mount(Static("🔫 Quick Kill (x=kill, Enter=focus, j/k=select, /=search)", classes="port-section-header"))
        
        # Sort by process name alphabetically
        sorted_apps = sorted(self.ports, key=lambda x: x['process_info']['name'].lower())
        
        # Filter by search term if present
        if self.search_term:
            search_lower = self.search_term.lower()
            sorted_apps = [app for app in sorted_apps if search_lower in app['process_info']['name'].lower()]
        
        # Show message if no results after filtering
        if not sorted_apps:
            container.mount(Static(f"No apps matching '{self.search_term}'", classes="port-empty-message"))
            return
        
        # Count duplicates to add numbers
        name_counts = {}
        name_instances = {}
        for app_info in sorted_apps:
            name = app_info['process_info']['name']
            name_counts[name] = name_counts.get(name, 0) + 1
            if name not in name_instances:
                name_instances[name] = 0
        
        for idx, app_info in enumerate(sorted_apps):
            pid = app_info['pid']
            process_name = app_info['process_info']['name']
            
            # Add numbering for duplicates
            display_name = process_name
            if name_counts[process_name] > 1:
                name_instances[process_name] += 1
                display_name = f"{process_name} ({name_instances[process_name]})"
            
            # Create app display line with selection indicator
            selection_marker = "▶ " if idx == self.selected_index else "  "
            app_text = f"{selection_marker}{display_name}"
            
            app_class = "port-line-selected" if idx == self.selected_index else "port-line"
            app_line = Static(app_text, classes=app_class)
            app_line.data = {"pid": pid, "process_name": process_name, "index": idx}
            container.mount(app_line)
    
    def _get_filtered_apps(self) -> list:
        """Get the filtered and sorted list of applications."""
        sorted_apps = sorted(self.ports, key=lambda x: x['process_info']['name'].lower())
        if self.search_term:
            search_lower = self.search_term.lower()
            sorted_apps = [app for app in sorted_apps if search_lower in app['process_info']['name'].lower()]
        return sorted_apps
    
    def action_kill_selected(self) -> None:
        """Kill the currently selected process."""
        if not self.ports:
            return
        
        filtered_apps = self._get_filtered_apps()
        if not filtered_apps:
            return
        
        if 0 <= self.selected_index < len(filtered_apps):
            app_info = filtered_apps[self.selected_index]
            pid = app_info['pid']
            process_name = app_info['process_info']['name']
            self.post_message(KillPort(pid=pid, process_name=process_name))
            self.app.log(f"Instant kill requested for {process_name} (PID {pid})")
    
    def action_focus_selected(self) -> None:
        """Focus/bring forward the currently selected application."""
        if not self.ports:
            return
        
        filtered_apps = self._get_filtered_apps()
        if not filtered_apps:
            return
        
        if 0 <= self.selected_index < len(filtered_apps):
            app_info = filtered_apps[self.selected_index]
            process_name = app_info['process_info']['name']
            pid = app_info['pid']
            self.post_message(FocusApp(process_name=process_name, pid=pid))
            self.app.log(f"Focus requested for {process_name} (PID {pid})")
    
    def action_move_up(self) -> None:
        """Move selection up."""
        if self.ports and self.selected_index > 0:
            self.selected_index -= 1
            self._update_display()
    
    def action_move_down(self) -> None:
        """Move selection down."""
        filtered_apps = self._get_filtered_apps()
        if self.ports and self.selected_index < len(filtered_apps) - 1:
            self.selected_index += 1
            self._update_display()
    
    def action_focus_search(self) -> None:
        """Focus the search input."""
        try:
            search_input = self.query_one("#port-search-input", Input)
            search_input.focus()
        except Exception:
            pass
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "port-search-input":
            self.search_term = event.value
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input - focus the selected app."""
        if event.input.id == "port-search-input":
            # Trigger the focus action on the selected app
            self.action_focus_selected()
            # Clear the search to show full list again
            event.input.value = ""
            # Blur the search input and focus the container
            self.focus()
            event.prevent_default()
            event.stop()
    
    def on_key(self, event: events.Key) -> None:
        """Handle key presses when focused."""
        # Allow arrow keys and vim keys to work even when search input is focused
        try:
            search_input = self.query_one("#port-search-input", Input)
            if search_input.has_focus:
                # Allow navigation keys to work from search input
                if event.key in ("up", "down", "j", "k"):
                    # Handle navigation, let other keys go to the input
                    if event.key in ("up", "k"):
                        self.action_move_up()
                    elif event.key in ("down", "j"):
                        self.action_move_down()
                    event.prevent_default()
                    event.stop()
                # Let other keys (typing) pass through to the input
                return
        except Exception:
            pass
        
        # Otherwise handle navigation keys normally
        if event.key in ("j", "k", "up", "down", "x", "delete", "enter"):
            # These are handled by actions, so we're good
            pass
    
    def on_click(self, event: events.Click) -> None:
        """Called when the user clicks on an application item."""
        if event.button == 1:  # Left click
            clicked_widget = event.widget
            
            # Walk up the widget tree to find an app item
            while clicked_widget and clicked_widget != self:
                if hasattr(clicked_widget, 'classes') and ("port-line" in clicked_widget.classes or "port-line-selected" in clicked_widget.classes):
                    # Get the index from the widget data
                    idx = clicked_widget.data.get("index")
                    if idx is not None:
                        # Check for double-click (within 0.5 seconds)
                        import time
                        current_time = time.time()
                        is_double_click = (
                            self._last_clicked_index == idx and
                            (current_time - self._last_click_time) < 0.5
                        )
                        
                        self._last_click_time = current_time
                        self._last_clicked_index = idx
                        
                        self.selected_index = idx
                        self._update_display()
                        self.focus()  # Ensure widget has focus for keyboard input
                        self.app.log(f"Selected app at index: {idx}")
                        
                        # On double-click, focus the app (like pressing Enter)
                        if is_double_click:
                            self.app.log(f"Double-click detected on app at index: {idx}")
                            self.action_focus_selected()
                    break
                clicked_widget = clicked_widget.parent
    
    def on_mount(self) -> None:
        """Initial setup for port monitor - defer update to ensure children are mounted."""
        self.call_after_refresh(self._update_display)


class ResourceMonitor(Vertical):
    """A widget to display system resource usage (RAM, CPU, Disk)."""

    resources = reactive(dict)

    def watch_resources(self, resources: dict) -> None:
        self._update_display()
    
    def _generate_sparkline(self, history: list, width: int = 20) -> str:
        """Generate a sparkline from history data using Unicode block characters."""
        if not history or len(history) < 2:
            return "▁" * width
        
        # Use only the last 'width' readings
        data = history[-width:]
        
        # Find min/max for scaling
        min_val = min(data)
        max_val = max(data)
        
        # Avoid division by zero
        if max_val - min_val < 0.001:  # Almost no variation
            return "▄" * len(data)
        
        # Map to sparkline characters (8 levels)
        sparkline_chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        sparkline = ""
        
        for value in data:
            # Normalize to 0-1 range
            normalized = (value - min_val) / (max_val - min_val)
            # Map to character index (0-7)
            index = min(int(normalized * 7.99), 7)
            sparkline += sparkline_chars[index]
        
        return sparkline

    def _update_display(self) -> None:
        """Update the display to show system resources."""
        self.remove_children()
        
        if not self.resources:
            self.mount(Static("Loading resources...", classes="resource-loading"))
            return
        
        # RAM Usage
        ram = self.resources.get('ram', {})
        if ram:
            ram_percent = ram.get('percent', 0)
            ram_used = ram.get('used_gb', 0)
            ram_total = ram.get('total_gb', 0)
            
            # Color code based on usage
            ram_color = "success" if ram_percent < 60 else "warning" if ram_percent < 85 else "error"
            
            ram_text = f"💾 RAM: {ram_used:.1f}GB / {ram_total:.1f}GB ({ram_percent:.1f}%)"
            self.mount(Static(ram_text, classes=f"resource-line resource-{ram_color}"))
            
            # Progress bar visualization
            bar_width = 30
            filled = int((ram_percent / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            self.mount(Static(f"[{bar}]", classes=f"resource-bar resource-{ram_color}"))
        
        self.mount(Static("", classes="resource-spacer"))  # Spacing
        
        # CPU Usage
        cpu = self.resources.get('cpu', {})
        if cpu:
            cpu_percent = cpu.get('percent', 0)
            cpu_count = cpu.get('count', 0)
            
            cpu_color = "success" if cpu_percent < 60 else "warning" if cpu_percent < 85 else "error"
            
            cpu_text = f"⚡ CPU: {cpu_percent:.1f}% ({cpu_count} cores)"
            self.mount(Static(cpu_text, classes=f"resource-line resource-{cpu_color}"))
            
            # Progress bar
            bar_width = 30
            filled = int((cpu_percent / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            self.mount(Static(f"[{bar}]", classes=f"resource-bar resource-{cpu_color}"))
        
        self.mount(Static("", classes="resource-spacer"))  # Spacing
        
        # Disk Usage
        disk = self.resources.get('disk', {})
        if disk:
            disk_percent = disk.get('percent', 0)
            disk_used = disk.get('used_gb', 0)
            disk_total = disk.get('total_gb', 0)
            disk_free = disk.get('free_gb', 0)
            
            disk_color = "success" if disk_percent < 70 else "warning" if disk_percent < 90 else "error"
            
            disk_text = f"💿 Disk: {disk_percent:.1f}%  {disk_used:.0f} / {disk_total:.0f} GB (Free: {disk_free:.0f}GB)"
            self.mount(Static(disk_text, classes=f"resource-line resource-{disk_color}"))
            
            # Progress bar
            bar_width = 30
            filled = int((disk_percent / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            self.mount(Static(f"[{bar}]", classes=f"resource-bar resource-{disk_color}"))
        
        # Battery Status
        battery = self.resources.get('battery')
        if battery:
            self.mount(Static("", classes="resource-spacer"))  # Spacing
            
            battery_percent = battery.get('percent', 0)
            is_plugged = battery.get('plugged', False)
            time_left = battery.get('time_left')
            
            # Color code based on battery level
            if is_plugged:
                battery_color = "success"
                status_icon = "🔌"
            else:
                battery_color = "success" if battery_percent > 40 else "warning" if battery_percent > 20 else "error"
                status_icon = "🔋"
            
            # Format time remaining
            time_str = ""
            if time_left and not is_plugged:
                hours = int(time_left // 3600)
                minutes = int((time_left % 3600) // 60)
                time_str = f" ({hours}h {minutes}m left)"
            elif is_plugged:
                time_str = " (Charging)"
            
            battery_text = f"{status_icon} Battery: {battery_percent:.0f}%{time_str}"
            self.mount(Static(battery_text, classes=f"resource-line resource-{battery_color}"))
            
            # Progress bar
            bar_width = 30
            filled = int((battery_percent / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            self.mount(Static(f"[{bar}]", classes=f"resource-bar resource-{battery_color}"))
        
        # Network I/O with Sparkline
        network = self.resources.get('network')
        if network:
            self.mount(Static("", classes="resource-spacer"))  # Spacing
            
            upload_mbps = network.get('upload_mbps', 0)
            download_mbps = network.get('download_mbps', 0)
            upload_history = network.get('upload_history', [])
            download_history = network.get('download_history', [])
            
            # Format speeds nicely (show KB/s if less than 1 MB/s)
            if upload_mbps < 1:
                upload_str = f"{upload_mbps * 1024:.1f} KB/s"
            else:
                upload_str = f"{upload_mbps:.2f} MB/s"
            
            if download_mbps < 1:
                download_str = f"{download_mbps * 1024:.1f} KB/s"
            else:
                download_str = f"{download_mbps:.2f} MB/s"
            
            # Generate sparklines
            upload_sparkline = self._generate_sparkline(upload_history, width=25)
            download_sparkline = self._generate_sparkline(download_history, width=25)
            
            self.mount(Static("🌐 Network", classes="resource-line resource-success"))
            self.mount(Static(f"   ↑ {upload_str:>12}  {upload_sparkline}", classes="resource-detail"))
            self.mount(Static(f"   ↓ {download_str:>12}  {download_sparkline}", classes="resource-detail"))


class CommandBar(Input):
    """A global command bar for searching and executing actions."""
    def on_mount(self) -> None:
        self.placeholder = "Type project name to search and execute..."

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle live filtering as user types."""
        search_term = event.value.strip().lower()
        navigator = self.app.query_one("#navigator-panel", ProjectNavigator)
        project_container = navigator.query_one("#project-list", ScrollableContainer)
        
        if not search_term:
            # Show all projects
            for widget in project_container.query(".project-item"):
                widget.remove_class("hidden")
                widget.styles.display = "block"
            return
        
        # Filter projects by search term
        for widget in project_container.query(".project-item"):
            project_name = widget.data.get("project_name", "").lower()
            if search_term in project_name:
                widget.styles.display = "block"
            else:
                widget.styles.display = "none"

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user presses Enter in the command bar."""
        search_term = event.value.strip().lower()
        if not search_term:
            return
        
        # Get the navigator to access projects
        navigator = self.app.query_one("#navigator-panel", ProjectNavigator)
        project_container = navigator.query_one("#project-list", ScrollableContainer)
        
        # Find matching project (first visible match)
        matching_project = None
        for widget in project_container.query(".project-item"):
            if widget.styles.display != "none":
                project_name = widget.data.get("project_name")
                if search_term in project_name.lower():
                    matching_project = project_name
                    break
        
        if matching_project:
            # Select the project
            navigator.selected_project_name = matching_project
            
            # Find the widget and highlight it
            for widget in project_container.query(".project-item"):
                if widget.data.get("project_name") == matching_project:
                    # Remove previous selection
                    if navigator.selected_widget:
                        try:
                            navigator.selected_widget.remove_class("selected")
                        except Exception:
                            pass  # Widget might have been removed
                    # Select new widget
                    navigator.selected_widget = widget
                    widget.add_class("selected")
                    widget.scroll_visible()
                    break
            
            # Post messages to select and execute
            self.post_message(ProjectSelected(matching_project))
            self.post_message(ProjectExecute(matching_project))
            
            # Clear the input and show all projects
            self.value = ""
            for widget in project_container.query(".project-item"):
                widget.styles.display = "block"
            
            self.app.log(f"Command bar executed project: {matching_project}")
        else:
            # If no match, just clear and show message
            current_value = self.value
            self.value = ""
            self.placeholder = f"No match found for: {current_value}"
            self.app.set_timer(2, lambda: setattr(self, "placeholder", "Type project name to search and execute..."))
            self.app.log(f"No project found matching: {search_term}")
