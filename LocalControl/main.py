from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input
from textual.containers import Container, Vertical, Horizontal
from textual import events # Import events
from project_discovery import scan_projects, find_nearest_venv, get_git_branch, get_git_remote_url
from port_mapper import get_running_applications
from pathlib import Path
from typing import Dict, Optional
import os
import sys
import asyncio
import subprocess
import psutil # Import psutil for process management
import re # Import regex for temperature parsing
from executor import ManagedProcess # Import ManagedProcess
from widgets import ProjectNavigator, ServiceMonitor, PortMonitor, ResourceMonitor, ProjectConsole, CommandBar, ProjectSelected, ProjectExecute, ProjectExecuteRaw, ProjectOpenTerminal, ProjectOpenTerminalRaw, ProjectOpenGemini, ProjectOpenOpenCode, PortConflictAction, TerminalCloseRequest, RunCommand, TerminalOutput, TerminalInterrupt, KillPort, FocusApp, AddFolder, RemoveProject # Import custom messages
from terminal_manager import EmbeddedTerminal
from rich.color import Color # For color management
from rich.text import Text # For rich text formatting
from config import save_manual_projects, load_manual_projects

class LocalControlApp(App):
    CSS_PATH = str(Path(__file__).parent / "main.css")
    ENABLE_COMMAND_PALETTE = True
    BINDINGS = [
        ("ctrl+p", "focus_command_bar", "Search Projects"),
        ("/", "focus_command_bar", "Search Projects"),
        ("escape", "focus_navigator", "Focus Navigator"),
        ("ctrl+a", "add_folder", "Add Folder"),
        ("ctrl+k", "focus_ports", "Quick Kill Apps"),
        ("?", "show_keys", "Show All Keys"),
        ("h", "show_keys", "Show Help"),
    ]

    COLORS = [
        Color.from_rgb(255, 99, 71),  # Tomato
        Color.from_rgb(60, 179, 113), # MediumSeaGreen
        Color.from_rgb(65, 105, 225), # RoyalBlue
        Color.from_rgb(255, 165, 0),  # Orange
        Color.from_rgb(186, 85, 211), # MediumOrchid
        Color.from_rgb(0, 191, 255),  # DeepSkyBlue
        Color.from_rgb(255, 215, 0),  # Gold
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.discovered_projects = {}
        self.active_processes: Dict[str, ManagedProcess] = {}
        self.active_terminals: Dict[str, EmbeddedTerminal] = {}  # Map project_name to terminal instance
        self.selected_project: Optional[str] = None
        self._project_colors = {} # To store assigned colors for projects
        self.current_terminal: Optional[str] = None  # Currently displayed terminal in console
        self.app_process_map = []  # Store current running applications
        self.manual_projects = set()  # Track manually added projects
        self._awaiting_folder_input = False  # Flag for folder input mode
        self.command_history = []  # Store command history for autocomplete
        # Network I/O tracking for speed calculation
        self._last_net_io = None
        self._last_net_time = None
        # Network history for sparkline (store last 30 readings)
        self._upload_history = []
        self._download_history = []
        self._max_history_size = 30

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield ProjectNavigator(id="navigator-panel")
                yield ResourceMonitor(id="resources-panel")
            with Vertical(id="body"):
                yield ServiceMonitor(id="services-panel")
                yield PortMonitor(id="ports-panel")
                yield ProjectConsole(id="console-panel")
        yield CommandBar(id="command-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#navigator-panel", ProjectNavigator).border_title = "Scanning for projects..."
        self.query_one("#services-panel", ServiceMonitor).border_title = "Scanning for services..."
        self.query_one("#ports-panel", PortMonitor).border_title = "Scanning running applications..."
        self.query_one("#resources-panel", ResourceMonitor).border_title = "Loading resources..."
        self.query_one("#console-panel", ProjectConsole).border_title = "Console (Waiting for selection)"

        current_script_dir = Path(__file__).parent
        projects_to_scan_dir = current_script_dir.parent 
        
        self.discovered_projects = scan_projects(projects_to_scan_dir)
        
        # Load manually added projects from persistent config
        manual_project_data = load_manual_projects()
        for project_name, project_details in manual_project_data.items():
            # Ensure git_branch and git_remote are set for old configs
            if 'git_branch' not in project_details or 'git_remote' not in project_details:
                project_path = Path(project_details['path'])
                if 'git_branch' not in project_details:
                    project_details['git_branch'] = get_git_branch(project_path)
                if 'git_remote' not in project_details:
                    project_details['git_remote'] = get_git_remote_url(project_path)
            self.discovered_projects[project_name] = project_details
            self.manual_projects.add(project_name)
        
        # Also ensure all discovered projects have git info (in case scan_projects didn't set them)
        for project_name, project_details in self.discovered_projects.items():
            if 'git_branch' not in project_details or 'git_remote' not in project_details:
                project_path = Path(project_details['path'])
                if 'git_branch' not in project_details:
                    project_details['git_branch'] = get_git_branch(project_path)
                if 'git_remote' not in project_details:
                    project_details['git_remote'] = get_git_remote_url(project_path)
        
        self.log("Discovered Projects (from main.py on_mount):")
        
        # Assign colors to projects
        for i, (name, details) in enumerate(self.discovered_projects.items()):
            color = self.COLORS[i % len(self.COLORS)]
            self._project_colors[name] = color
            self.log(f"  Project: {name}, Color: {color}, Branch: {details.get('git_branch', 'None')}")
            for key, value in details.items():
                self.log(f"    {key}: {value}")
        
        self.query_one("#navigator-panel", ProjectNavigator).projects = self.discovered_projects
        self.query_one("#navigator-panel", ProjectNavigator).manual_projects = self.manual_projects
        self.query_one("#navigator-panel", ProjectNavigator).border_title = "Navigator (Projects)"

        # Scan and display running applications
        self.app_process_map = get_running_applications()
        self.update_app_display()
        
        # Services panel shows no conflicts anymore
        self.query_one("#services-panel", ServiceMonitor).border_title = "Services"
        
        # Initialize active terminals in service monitor
        self.query_one("#services-panel", ServiceMonitor).active_terminals = {}
        
        # Initialize resource monitor
        self.update_resources()
        
        # Set up periodic monitoring
        self.set_interval(3.0, self.refresh_ports)      # Port scanning every 3s
        self.set_interval(2.0, self.update_resources)   # Resource monitoring every 2s
        self.set_interval(2.0, self.update_git_branch)  # Git branch checking every 2s
        self.set_interval(2.0, self.update_app_display) # Update app display with top hog every 2s
        
        # Focus navigator so arrows work immediately
        self.set_timer(0.1, lambda: self.query_one("#navigator-panel", ProjectNavigator).focus())
    
    def update_app_display(self) -> None:
        """Update the app monitor display with running applications."""
        port_monitor = self.query_one("#ports-panel", PortMonitor)
        
        # Display all running applications
        port_monitor.ports = self.app_process_map
        
        app_count = len(self.app_process_map)
        
        # Get top resource hog from last resource update
        top_process = getattr(self, '_last_top_process', None)
        
        if app_count > 0:
            if top_process:
                process_name = top_process.get('name', 'Unknown')
                cpu_pct = top_process.get('cpu_percent', 0)
                mem_pct = top_process.get('memory_percent', 0)
                
                # Show whichever metric is higher
                if cpu_pct > mem_pct:
                    metric_str = f"{cpu_pct:.1f}% CPU"
                else:
                    metric_str = f"{mem_pct:.1f}% RAM"
                
                port_monitor.border_title = f"🖥️  Running Applications ({app_count}) | 🔥 Top: {process_name} - {metric_str}"
            else:
                port_monitor.border_title = f"🖥️  Running Applications ({app_count})"
        else:
            port_monitor.border_title = "🖥️  Running Applications (None)"
    
    def refresh_ports(self) -> None:
        """Periodically refresh running applications information."""
        try:
            self.app_process_map = get_running_applications()
            self.update_app_display()
        except Exception as e:
            self.log(f"Error refreshing applications: {e}")
    
    def update_resources(self) -> None:
        """Update system resource information."""
        try:
            import psutil
            import time
            
            # Get RAM info
            ram = psutil.virtual_memory()
            ram_info = {
                'percent': ram.percent,
                'used_gb': ram.used / (1024**3),
                'total_gb': ram.total / (1024**3),
                'available_gb': ram.available / (1024**3)
            }
            
            # Get CPU info
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_info = {
                'percent': cpu_percent,
                'count': psutil.cpu_count()
            }
            
            # Get Disk info (root filesystem)
            disk = psutil.disk_usage('/')
            disk_info = {
                'percent': disk.percent,
                'used_gb': disk.used / (1024**3),
                'total_gb': disk.total / (1024**3),
                'free_gb': disk.free / (1024**3)
            }
            
            # Get Network I/O (calculate speed)
            net_io = psutil.net_io_counters()
            current_time = time.time()
            net_info = {}
            
            if self._last_net_io and self._last_net_time:
                time_delta = current_time - self._last_net_time
                if time_delta > 0:
                    bytes_sent = net_io.bytes_sent - self._last_net_io.bytes_sent
                    bytes_recv = net_io.bytes_recv - self._last_net_io.bytes_recv
                    
                    # Convert to MB/s
                    upload_mbps = (bytes_sent / time_delta) / (1024**2)
                    download_mbps = (bytes_recv / time_delta) / (1024**2)
                    
                    # Store in history for sparkline
                    self._upload_history.append(upload_mbps)
                    self._download_history.append(download_mbps)
                    
                    # Keep only last N readings
                    if len(self._upload_history) > self._max_history_size:
                        self._upload_history.pop(0)
                    if len(self._download_history) > self._max_history_size:
                        self._download_history.pop(0)
                    
                    net_info = {
                        'upload_mbps': upload_mbps,
                        'download_mbps': download_mbps,
                        'upload_history': self._upload_history.copy(),
                        'download_history': self._download_history.copy(),
                        'total_sent_gb': net_io.bytes_sent / (1024**3),
                        'total_recv_gb': net_io.bytes_recv / (1024**3)
                    }
            
            self._last_net_io = net_io
            self._last_net_time = current_time
            
            # Get Battery info (if available)
            battery_info = None
            battery = psutil.sensors_battery()
            if battery:
                battery_info = {
                    'percent': battery.percent,
                    'plugged': battery.power_plugged,
                    'time_left': battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED and battery.secsleft != psutil.POWER_TIME_UNKNOWN else None
                }
            
            # Get Top Resource Hog
            top_process = None
            try:
                # Get all processes sorted by CPU usage
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        pinfo = proc.info
                        if pinfo['cpu_percent'] is not None:
                            processes.append(pinfo)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Sort by CPU usage and get top process
                if processes:
                    top_by_cpu = max(processes, key=lambda x: x.get('cpu_percent', 0))
                    top_by_mem = max(processes, key=lambda x: x.get('memory_percent', 0))
                    
                    # Choose the one with higher resource usage
                    if top_by_cpu.get('cpu_percent', 0) > 5 or top_by_mem.get('memory_percent', 0) > 5:
                        top_process = top_by_cpu if top_by_cpu.get('cpu_percent', 0) > top_by_mem.get('memory_percent', 0) else top_by_mem
            except Exception:
                pass
            
            resources = {
                'ram': ram_info,
                'cpu': cpu_info,
                'disk': disk_info,
                'network': net_info if net_info else None,
                'battery': battery_info
            }
            
            # Store top process for app display
            self._last_top_process = top_process
            
            resource_monitor = self.query_one("#resources-panel", ResourceMonitor)
            resource_monitor.resources = resources
            resource_monitor.border_title = "📊 System Resources"
            
        except Exception as e:
            self.log(f"Error updating resources: {e}")
    
    def update_git_branch(self) -> None:
        """Check and update git branch for the current terminal if it changed."""
        try:
            # Only check if there's an active terminal
            if not self.current_terminal:
                return
            
            # Get the project details
            project_details = self.discovered_projects.get(self.current_terminal)
            if not project_details:
                return
            
            # Check current branch
            project_path = Path(project_details["path"])
            current_branch = get_git_branch(project_path)
            
            # Get current console branch
            console = self.query_one("#console-panel", ProjectConsole)
            old_branch = project_details.get("git_branch")
            
            # Normalize None string to actual None
            if current_branch == "None":
                current_branch = None
            if old_branch == "None":
                old_branch = None
            
            # If branch changed, update display
            if current_branch != old_branch:
                self.log(f"🌿 Branch changed from '{old_branch}' to '{current_branch}'")
                console.git_branch = current_branch
                project_details["git_branch"] = current_branch  # Update in cache
                
                # Update console title
                branch_info = f" [{current_branch}]" if current_branch else ""
                if console.active_venv:
                    console.border_title = f"Console - {self.current_terminal}{branch_info}"
                else:
                    console.border_title = f"Console - {self.current_terminal}{branch_info} (no venv)"
                
                console.write_line(f"🌿 Branch changed to: {current_branch}")
        except Exception as e:
            self.log(f"Error updating git branch: {e}")
    
    async def on_project_selected(self, message: ProjectSelected) -> None:
        """Handle project selection - just update UI, tabs handle the rest."""
        self.selected_project = message.project_name
        project_details = self.discovered_projects.get(message.project_name, {})
        git_branch = project_details.get('git_branch')
        branch_info = f" [{git_branch}]" if git_branch else ""
        self.query_one("#console-panel", ProjectConsole).border_title = f"Console - {self.selected_project}{branch_info}"
        self.app.log(f"Project selected: {self.selected_project}")

    async def on_project_execute(self, message: ProjectExecute) -> None:
        """Execute a project - activate terminal and CREATE A TAB."""
        project_name = message.project_name
        project_details = self.discovered_projects.get(project_name)

        if not project_details:
            self.query_one("#console-panel", ProjectConsole).write_line(f"❌ Error: Project '{project_name}' not found.")
            return

        project_path = Path(project_details["path"])
        venv_path = project_details.get("venv")  # May be None for manual projects
        
        self.log(f"on_project_execute called for: {project_name}")
        self.log(f"Currently active terminals: {list(self.active_terminals.keys())}")
        
        console = self.query_one("#console-panel", ProjectConsole)
        
        # Show GitHub link if available
        git_remote = project_details.get('git_remote')
        if git_remote:
            console.write_line(f"🔗 GitHub: {git_remote}")
        
        # If this exact project is already active, deactivate it
        if project_name in self.active_terminals and self.current_terminal == project_name:
            terminal = self.active_terminals[project_name]
            terminal.stop()
            del self.active_terminals[project_name]
            self.current_terminal = None
            
            console.write_line(f"🔴 Deactivated {project_name}")
            console.clear()
            console.active_venv = None
            console.git_branch = None
            self.update_navigator_status()
            
            navigator = self.query_one("#navigator-panel", ProjectNavigator)
            navigator.focus()
            return
        
        # Stop any other active terminal first (only one terminal at a time)
        if self.active_terminals:
            for old_project in list(self.active_terminals.keys()):
                terminal = self.active_terminals[old_project]
                terminal.stop()
                del self.active_terminals[old_project]
                self.log(f"Stopped terminal for {old_project}")
            self.current_terminal = None
            console.clear()
        
        # Create a new terminal for this project
        self.log(f"Creating new terminal for {project_name}")
        
        # Create callback for terminal output
        def on_terminal_output(line: str):
            """Callback for terminal output - posts message to main thread."""
            self.post_message(TerminalOutput(project_name=project_name, line=line))
        
        # Create new terminal instance
        terminal = EmbeddedTerminal(output_callback=on_terminal_output)
        terminal.start()
        
        # Track the terminal
        self.active_terminals[project_name] = terminal
        self.current_terminal = project_name
        
        # Update console border title and prompt with branch info
        git_branch = project_details.get('git_branch')
        self.log(f"Git branch for {project_name}: '{git_branch}' (type: {type(git_branch)})")
        branch_info = f" [{git_branch}]" if git_branch and git_branch != "None" else ""
        console.border_title = f"Console - {project_name}{branch_info}"
        console.git_branch = git_branch if git_branch != "None" else None  # Set branch for prompt
        console.project_name = project_name  # Set project name for prompt
        
        # Write initial messages to console
        console.write_line(f"🚀 Activating terminal for {project_name}...")
        if git_branch:
            console.write_line(f"🌿 Branch: {git_branch}")
        console.write_line(f"📂 Path: {project_path}")
        
        # Activate venv if available, otherwise just cd to the directory
        if venv_path:
            console.write_line(f"🐍 Virtual env: {venv_path}")
            console.active_venv = {"name": project_name, "path": venv_path}  # Set venv for prompt
            terminal.activate_venv(project_name, venv_path, str(project_path))
        else:
            console.write_line(f"⚠️  No virtual environment")
            console.active_venv = None  # No venv
            terminal.change_directory(str(project_path))
            terminal.run_command("echo '✅ Terminal ready (no venv)'")
            terminal.run_command(f"echo 'Project: {project_name}'")
            terminal.run_command("echo ''")
        
        console.write_line(f"✅ Terminal activated! Ready for commands.")
        self.update_navigator_status()
        
        # Return focus to navigator after everything updates
        self.set_timer(0.1, lambda: self.query_one("#navigator-panel", ProjectNavigator).focus())
    
    async def on_project_execute_raw(self, message: ProjectExecuteRaw) -> None:
        """Execute project terminal WITHOUT venv activation (raw terminal)."""
        project_name = message.project_name
        project_details = self.discovered_projects.get(project_name)

        if not project_details:
            self.query_one("#console-panel", ProjectConsole).write_line(f"❌ Error: Project '{project_name}' not found.")
            return

        project_path = Path(project_details["path"])
        
        self.log(f"on_project_execute_raw called for: {project_name}")
        self.log(f"Currently active terminals: {list(self.active_terminals.keys())}")
        
        console = self.query_one("#console-panel", ProjectConsole)
        
        # If this exact project is already active, deactivate it
        if project_name in self.active_terminals and self.current_terminal == project_name:
            terminal = self.active_terminals[project_name]
            terminal.stop()
            del self.active_terminals[project_name]
            self.current_terminal = None
            
            console.write_line(f"🔴 Deactivated {project_name}")
            console.clear()
            console.active_venv = None
            console.git_branch = None
            console.project_name = None
            self.update_navigator_status()
            
            navigator = self.query_one("#navigator-panel", ProjectNavigator)
            navigator.focus()
            return
        
        # Stop any other active terminal first (only one terminal at a time)
        if self.active_terminals:
            for old_project in list(self.active_terminals.keys()):
                terminal = self.active_terminals[old_project]
                terminal.stop()
                del self.active_terminals[old_project]
                self.log(f"Stopped terminal for {old_project}")
            self.current_terminal = None
            console.clear()
        
        # Create a new terminal for this project WITHOUT venv
        self.log(f"Creating raw terminal (no venv) for {project_name}")
        
        # Create callback for terminal output
        def on_terminal_output(line: str):
            """Callback for terminal output - posts message to main thread."""
            self.post_message(TerminalOutput(project_name=project_name, line=line))
        
        # Create new terminal instance
        terminal = EmbeddedTerminal(output_callback=on_terminal_output)
        terminal.start()
        
        # Track the terminal
        self.active_terminals[project_name] = terminal
        self.current_terminal = project_name
        
        # Update console border title and prompt with branch info
        git_branch = project_details.get('git_branch')
        self.log(f"Git branch for {project_name} (raw mode): '{git_branch}' (type: {type(git_branch)})")
        branch_info = f" [{git_branch}]" if git_branch and git_branch != "None" else ""
        console.border_title = f"Console - {project_name}{branch_info} (no venv)"
        console.git_branch = git_branch if git_branch != "None" else None  # Set branch for prompt
        console.project_name = project_name  # Set project name for prompt
        console.active_venv = None  # No venv in raw mode
        
        # Write initial messages to console
        console.write_line(f"🚀 Activating raw terminal for {project_name}...")
        if git_branch:
            console.write_line(f"🌿 Branch: {git_branch}")
        console.write_line(f"📂 Path: {project_path}")
        console.write_line(f"⚡ No virtual environment (raw mode)")
        
        # Just cd to the directory, no venv activation
        terminal.change_directory(str(project_path))
        terminal.run_command("echo '✅ Raw terminal ready'")
        terminal.run_command(f"echo 'Project: {project_name}'")
        terminal.run_command("echo ''")
        
        console.write_line(f"✅ Raw terminal activated! Ready for commands.")
        self.update_navigator_status()
        
        # Return focus to navigator after everything updates
        self.set_timer(0.1, lambda: self.query_one("#navigator-panel", ProjectNavigator).focus())
    
    async def on_project_open_terminal(self, message: ProjectOpenTerminal) -> None:
        """Open an external iTerm terminal with venv activated."""
        project_name = message.project_name
        project_details = self.discovered_projects.get(project_name)
        
        if not project_details:
            self.query_one("#console-panel", ProjectConsole).write_line(f"❌ Error: Project '{project_name}' not found.")
            return
        
        project_path = Path(project_details["path"])
        venv_path = project_details.get("venv")  # May be None for manual projects
        
        self.log(f"Opening iTerm terminal for: {project_name}")
        console = self.query_one("#console-panel", ProjectConsole)
        console.write_line(f"🖥️  Opening iTerm terminal for '{project_name}'...")
        
        # Build the command to run in iTerm
        if venv_path:
            # Activate venv and cd to project
            activate_script = f"{venv_path}/bin/activate"
            command = f"cd '{project_path}' && source '{activate_script}' && clear && echo '✅ Virtual environment activated' && echo 'Project: {project_name}' && echo 'venv: {venv_path}' && echo '' && exec $SHELL"
        else:
            # Just cd to project
            command = f"cd '{project_path}' && clear && echo '📂 Project: {project_name}' && echo '⚠️  No virtual environment' && echo '' && exec $SHELL"
        
        # Use osascript to open iTerm with the command
        # If iTerm has windows, split vertically; otherwise create a new window
        applescript = f'''
tell application "iTerm"
    activate
    if (count of windows) > 0 then
        tell current window
            tell current session
                set newSession to (split vertically with default profile)
            end tell
            tell newSession
                write text "{command}"
            end tell
        end tell
    else
        create window with default profile
        tell current session of current window
            write text "{command}"
        end tell
    end if
end tell
'''
        
        try:
            import subprocess
            subprocess.run(['osascript', '-e', applescript], check=True)
            console.write_line(f"✅ iTerm pane opened for '{project_name}'")
            self.log(f"iTerm pane spawned for {project_name}")
        except subprocess.CalledProcessError as e:
            console.write_line(f"❌ Failed to open iTerm: {e}")
            self.log(f"Error spawning iTerm: {e}")
    
    async def on_project_open_terminal_raw(self, message: ProjectOpenTerminalRaw) -> None:
        """Open an external iTerm terminal WITHOUT venv activation (raw terminal)."""
        project_name = message.project_name
        project_details = self.discovered_projects.get(project_name)
        
        if not project_details:
            self.query_one("#console-panel", ProjectConsole).write_line(f"❌ Error: Project '{project_name}' not found.")
            return
        
        project_path = Path(project_details["path"])
        
        self.log(f"Opening raw iTerm terminal for: {project_name}")
        console = self.query_one("#console-panel", ProjectConsole)
        console.write_line(f"🖥️  Opening raw iTerm terminal for '{project_name}'...")
        
        # Just cd to project without venv activation
        command = f"cd '{project_path}' && clear && echo '📂 Project: {project_name}' && echo '⚡ Raw terminal (no venv)' && echo '' && exec $SHELL"
        
        # Use osascript to open iTerm with the command
        # If iTerm has windows, split vertically; otherwise create a new window
        applescript = f'''
tell application "iTerm"
    activate
    if (count of windows) > 0 then
        tell current window
            tell current session
                set newSession to (split vertically with default profile)
            end tell
            tell newSession
                write text "{command}"
            end tell
        end tell
    else
        create window with default profile
        tell current session of current window
            write text "{command}"
        end tell
    end if
end tell
'''
        
        try:
            import subprocess
            subprocess.run(['osascript', '-e', applescript], check=True)
            console.write_line(f"✅ Raw iTerm pane opened for '{project_name}'")
            self.log(f"Raw iTerm pane spawned for {project_name}")
        except subprocess.CalledProcessError as e:
            console.write_line(f"❌ Failed to open iTerm: {e}")
            self.log(f"Error spawning iTerm: {e}")
    
    async def close_terminal(self, project_name: str) -> None:
        """Legacy method - now handled by terminal_close_request."""
        pass
    
    async def on_project_open_gemini(self, message: ProjectOpenGemini) -> None:
        """Open Gemini CLI in iTerm pane for the selected project."""
        project_name = message.project_name
        project_details = self.discovered_projects.get(project_name)
        
        if not project_details:
            self.query_one("#console-panel", ProjectConsole).write_line(f"❌ Error: Project '{project_name}' not found.")
            return
        
        project_path = Path(project_details["path"])
        venv_path = project_details.get("venv")
        
        self.log(f"Opening Gemini CLI for: {project_name}")
        console = self.query_one("#console-panel", ProjectConsole)
        console.write_line(f"🤖 Opening Gemini CLI for '{project_name}'...")
        
        # Build command to cd and run gemini
        if venv_path:
            activate_script = f"{venv_path}/bin/activate"
            command = f"cd '{project_path}' && source '{activate_script}' && clear && echo '🤖 Gemini CLI' && echo 'Project: {project_name}' && echo 'venv: {venv_path}' && echo '' && gemini"
        else:
            command = f"cd '{project_path}' && clear && echo '🤖 Gemini CLI' && echo 'Project: {project_name}' && echo '' && gemini"
        
        # Use osascript to open iTerm with gemini
        applescript = f'''
tell application "iTerm"
    activate
    if (count of windows) > 0 then
        tell current window
            tell current session
                set newSession to (split vertically with default profile)
            end tell
            tell newSession
                write text "{command}"
            end tell
        end tell
    else
        create window with default profile
        tell current session of current window
            write text "{command}"
        end tell
    end if
end tell
'''
        
        try:
            import subprocess
            subprocess.run(['osascript', '-e', applescript], check=True)
            console.write_line(f"✅ Gemini CLI pane opened for '{project_name}'")
            self.log(f"Gemini CLI pane spawned for {project_name}")
        except subprocess.CalledProcessError as e:
            console.write_line(f"❌ Failed to open Gemini CLI: {e}")
            self.log(f"Error spawning Gemini CLI: {e}")

    async def on_project_open_open_code(self, message: ProjectOpenOpenCode) -> None:
        """Open OpenCode in iTerm pane for the selected project."""
        project_name = message.project_name
        project_details = self.discovered_projects.get(project_name)

        if not project_details:
            self.query_one("#console-panel", ProjectConsole).write_line(f"❌ Error: Project '{project_name}' not found.")
            return

        project_path = Path(project_details["path"])
        venv_path = project_details.get("venv")

        self.log(f"Opening OpenCode for: {project_name}")
        console = self.query_one("#console-panel", ProjectConsole)
        console.write_line(f"🧠 Opening OpenCode for '{project_name}'...")

        # Build command to cd and run opencode
        if venv_path:
            activate_script = f"{venv_path}/bin/activate"
            command = f"cd '{project_path}' && source '{activate_script}' && clear && echo '🧠 OpenCode' && echo 'Project: {project_name}' && echo 'venv: {venv_path}' && echo '' && opencode"
        else:
            command = f"cd '{project_path}' && clear && echo '🧠 OpenCode' && echo 'Project: {project_name}' && echo '' && opencode"

        # Use osascript to open iTerm with opencode
        applescript = f'''
tell application "iTerm"
    activate
    if (count of windows) > 0 then
        tell current window
            tell current session
                set newSession to (split vertically with default profile)
            end tell
            tell newSession
                write text "{command}"
            end tell
        end tell
    else
        create window with default profile
        tell current session of current window
            write text "{command}"
        end tell
    end if
end tell
'''

        try:
            import subprocess
            subprocess.run(['osascript', '-e', applescript], check=True)
            console.write_line(f"✅ OpenCode pane opened for '{project_name}'")
            self.log(f"OpenCode pane spawned for {project_name}")
        except subprocess.CalledProcessError as e:
            console.write_line(f"❌ Failed to open OpenCode: {e}")
            self.log(f"Error spawning OpenCode: {e}")

    def update_navigator_status(self) -> None:
        """Update the navigator to show which projects have active terminals."""
        navigator = self.query_one("#navigator-panel", ProjectNavigator)
        
        # Log before update
        self.log(f"update_navigator_status: discovered_projects count = {len(self.discovered_projects)}")
        self.log(f"update_navigator_status: active_terminals = {list(self.active_terminals.keys())}")
        
        navigator.active_terminals = set(self.active_terminals.keys())
        navigator.manual_projects = self.manual_projects
        
        # Create a NEW dict to ensure reactive detects the change
        navigator.projects = dict(self.discovered_projects)  # Copy the dict
        
        # Log after assignment - DON'T call refresh_projects() directly, let watch_projects handle it
        self.log(f"update_navigator_status: navigator.projects count = {len(navigator.projects)}")
        
        # Update services monitor with active terminals (create dict with project info)
        service_monitor = self.query_one("#services-panel", ServiceMonitor)
        active_info = {}
        for project_name, terminal in self.active_terminals.items():
            project_details = self.discovered_projects.get(project_name, {})
            active_info[project_name] = {
                "path": project_details.get("path", ""),
                "venv": project_details.get("venv", "")
            }
        service_monitor.active_terminals = active_info

    async def on_port_conflict_action(self, message: PortConflictAction) -> None:
        """Handle actions related to port conflicts (e.g., kill a process)."""
        if message.action == "kill":
            try:
                proc = psutil.Process(message.pid)
                proc_name = proc.name()
                proc.terminate() # or proc.kill()
                self.query_one("#console-panel", ProjectConsole).write_line(f"Killed process '{proc_name}' (PID: {message.pid}) on port {message.port}.")
                # Re-scan ports after killing a process
                self.on_mount() # Re-run mount to refresh service monitor
            except psutil.NoSuchProcess:
                self.query_one("#console-panel", ProjectConsole).write_line(f"Process with PID {message.pid} not found (already terminated?).")
            except psutil.AccessDenied:
                self.query_one("#console-panel", ProjectConsole).write_line(f"Permission denied to kill process with PID {message.pid}.")
            except Exception as e:
                self.query_one("#console-panel", ProjectConsole).write_line(f"Error killing process {message.pid}: {e}")
        # TODO: Implement "restart" logic if needed

    async def on_terminal_close_request(self, message: TerminalCloseRequest) -> None:
        """Handle terminal close requests from the service monitor."""
        project_name = message.project_name
        if project_name in self.active_terminals:
            self.query_one("#console-panel", ProjectConsole).write_line(f"🔴 Deactivating venv for '{project_name}'...")
            terminal = self.active_terminals[project_name]
            terminal.stop()
            del self.active_terminals[project_name]
            
            # If this was the current terminal, clear it
            if self.current_terminal == project_name:
                self.current_terminal = None
                console = self.query_one("#console-panel", ProjectConsole)
                console.active_venv = None
                console.git_branch = None
                console.project_name = None
                
            self.update_navigator_status()
    
    async def on_run_command(self, message: RunCommand) -> None:
        """Handle command execution in the active tab's terminal."""
        command = message.command.strip()
        if not command:
            return
        
        console = self.query_one("#console-panel", ProjectConsole)
        
        # Check if we're awaiting folder input for manual add
        if self._awaiting_folder_input:
            self._awaiting_folder_input = False
            console_input = self.query_one("#console-input", Input)
            console_input.placeholder = "Enter command..."
            
            if command.lower() == 'cancel':
                console.write_line("❌ Add folder cancelled")
                return
            
            # Validate and add the folder
            await self._add_manual_project(command)
            return
        
        # Handle 'clear' command specially
        if command.lower() in ['clear', 'cls']:
            console.clear()
            return
        
        # Check if there's an active terminal
        if not self.current_terminal or self.current_terminal not in self.active_terminals:
            console.write_line("⚠️  No active terminal - select a project and press Enter")
            return
        
        # Add to command history
        if command not in self.command_history:
            self.command_history.append(command)
        elif self.command_history[-1] != command:  # Move to end if it exists elsewhere
            self.command_history.remove(command)
            self.command_history.append(command)
        
        # Update console's command history
        console.command_history = self.command_history.copy()
        
        project_name = self.current_terminal
        terminal = self.active_terminals[project_name]
        
        # Display the command
        console.write_line(f"$ {command}")
        
        # Execute the command in the terminal
        terminal.run_command(command)
        self.log(f"Command '{command}' sent to {project_name}")
    
    async def on_terminal_output(self, message: TerminalOutput) -> None:
        """Handle terminal output from background thread."""
        if message.project_name == self.current_terminal:
            console = self.query_one("#console-panel", ProjectConsole)
            console.write_line(message.line)
    
    async def on_terminal_interrupt(self, message: TerminalInterrupt) -> None:
        """Handle Ctrl+C interrupt signal."""
        if not self.current_terminal or self.current_terminal not in self.active_terminals:
            console = self.query_one("#console-panel", ProjectConsole)
            console.write_line("⚠️  No active terminal to interrupt")
            return
        
        terminal = self.active_terminals[self.current_terminal]
        terminal.send_interrupt()
        self.log(f"Interrupt sent to {self.current_terminal}")
    
    async def on_kill_port(self, message: KillPort) -> None:
        """Handle killing a process."""
        try:
            proc = psutil.Process(message.pid)
            proc_name = proc.name()
            cmdline = ' '.join(proc.cmdline()[:3]) if proc.cmdline() else proc_name
            
            # Try graceful termination first
            proc.terminate()
            
            # Wait briefly for termination
            try:
                proc.wait(timeout=2)
                self.query_one("#console-panel", ProjectConsole).write_line(
                    f"✅ Terminated '{proc_name}' (PID: {message.pid})"
                )
            except psutil.TimeoutExpired:
                # Force kill if it didn't terminate
                proc.kill()
                self.query_one("#console-panel", ProjectConsole).write_line(
                    f"💥 Force killed '{proc_name}' (PID: {message.pid})"
                )
            
            # Refresh app list immediately
            self.refresh_ports()
            
        except psutil.NoSuchProcess:
            self.query_one("#console-panel", ProjectConsole).write_line(
                f"⚠️  Process (PID: {message.pid}) not found - may have already terminated"
            )
            self.refresh_ports()
        except psutil.AccessDenied:
            self.query_one("#console-panel", ProjectConsole).write_line(
                f"❌ Permission denied to kill PID {message.pid} - try running with sudo"
            )
        except Exception as e:
            self.query_one("#console-panel", ProjectConsole).write_line(
                f"❌ Error killing process {message.pid}: {e}"
            )
    
    async def on_focus_app(self, message: FocusApp) -> None:
        """Handle focusing/bringing forward a specific application instance."""
        try:
            import subprocess
            
            process_name = message.process_name
            pid = message.pid
            
            # Use AppleScript to bring the specific process to foreground using its PID
            script = f'''tell application "System Events"
    set frontmost of first process whose unix id is {pid} to true
end tell'''
            
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                self.query_one("#console-panel", ProjectConsole).write_line(
                    f"✨ Focused '{process_name}' (PID: {pid})"
                )
            else:
                # Fallback: try to open the app by name
                subprocess.run(['open', '-a', process_name], timeout=1)
                self.query_one("#console-panel", ProjectConsole).write_line(
                    f"✨ Activated '{process_name}' (may not be the specific instance)"
                )
            
        except subprocess.TimeoutExpired:
            self.query_one("#console-panel", ProjectConsole).write_line(
                f"⏱️  Timeout trying to focus '{message.process_name}'"
            )
        except Exception as e:
            self.query_one("#console-panel", ProjectConsole).write_line(
                f"❌ Error focusing app: {e}"
            )
    
    async def on_add_folder(self, message: AddFolder) -> None:
        """Handle adding a folder manually."""
        from textual.widgets import Input
        from textual.screen import ModalScreen
        
        # For now, use console input (could be replaced with a modal dialog)
        self.query_one("#console-panel", ProjectConsole).write_line("📌 Add Folder: Type the full path below and press Enter")
        self.query_one("#console-panel", ProjectConsole).write_line("Example: /Users/username/projects/mywebapp")
        self.query_one("#console-panel", ProjectConsole).write_line("(or type 'cancel' to abort)")
        
        # Focus the console input for folder path entry
        console_input = self.query_one("#console-input", Input)
        console_input.placeholder = "Enter folder path..."
        console_input.focus()
        
        # Store state that we're waiting for folder input
        self._awaiting_folder_input = True
    
    async def _add_manual_project(self, folder_path: str) -> None:
        """Validate and add a manual project."""
        console = self.query_one("#console-panel", ProjectConsole)
        
        # Expand user home directory
        folder_path = os.path.expanduser(folder_path)
        project_path = Path(folder_path)
        
        # Validate path exists and is a directory
        if not project_path.exists():
            console.write_line(f"❌ Path does not exist: {folder_path}")
            return
        
        if not project_path.is_dir():
            console.write_line(f"❌ Path is not a directory: {folder_path}")
            return
        
        # Use the folder name as the project name
        project_name = project_path.name
        
        # Check if already exists
        if project_name in self.discovered_projects:
            console.write_line(f"⚠️  Project '{project_name}' already exists")
            return
        
        # Find venv if it exists
        venv_path = find_nearest_venv(project_path)
        venv_str = str(venv_path.resolve()) if venv_path else None
        
        # Get git branch and remote if it's a git repo
        git_branch = get_git_branch(project_path)
        git_remote = get_git_remote_url(project_path)
        
        # Add to discovered projects
        self.discovered_projects[project_name] = {
            "path": str(project_path.resolve()),
            "venv": venv_str,
            "git_branch": git_branch,
            "git_remote": git_remote,
            "status": "active"
        }
        
        # Add to manual projects set
        self.manual_projects.add(project_name)
        
        # Assign a color
        color_index = len(self._project_colors) % len(self.COLORS)
        self._project_colors[project_name] = self.COLORS[color_index]
        
        # Save to persistent config first
        save_manual_projects(self.manual_projects, self.discovered_projects)
        
        # Write success messages to console
        venv_msg = f" (with venv)" if venv_str else " (no venv found)"
        git_msg = f" [{git_branch}]" if git_branch else ""
        console.write_line(f"✅ Added '{project_name}'{venv_msg}{git_msg}")
        console.write_line(f"📁 Path: {folder_path}")
        if git_remote:
            console.write_line(f"🔗 GitHub: {git_remote}")
        
        # Update navigator - use call_after_refresh for better timing
        def update_navigator():
            navigator = self.query_one("#navigator-panel", ProjectNavigator)
            # First update the internal state
            navigator.projects[project_name] = self.discovered_projects[project_name]
            navigator.manual_projects.add(project_name)
            # Then refresh the entire display
            navigator.refresh_projects()
            # Focus it so user sees the change
            navigator.focus()
        
        self.call_after_refresh(update_navigator)
    
    async def on_remove_project(self, message: RemoveProject) -> None:
        """Handle removing a manually added project."""
        project_name = message.project_name
        
        if project_name not in self.manual_projects:
            self.query_one("#console-panel", ProjectConsole).write_line(
                f"⚠️  Cannot remove '{project_name}' - not a manually added folder"
            )
            return
        
        # Close terminal if active
        if project_name in self.active_terminals:
            terminal = self.active_terminals[project_name]
            terminal.stop()
            del self.active_terminals[project_name]
            
            if self.current_terminal == project_name:
                self.current_terminal = None
                self.query_one("#console-panel", ProjectConsole).active_venv = None
        
        # Remove from projects and manual set
        if project_name in self.discovered_projects:
            del self.discovered_projects[project_name]
        self.manual_projects.discard(project_name)
        
        self.log(f"Removed {project_name} from discovered_projects. Total now: {len(self.discovered_projects)}")
        
        # Remove directly from navigator using new method
        navigator = self.query_one("#navigator-panel", ProjectNavigator)
        navigator.remove_project_directly(project_name)
        
        self.log(f"Navigator now has {len(navigator.projects)} projects")
        
        # Save to persistent config
        save_manual_projects(self.manual_projects, self.discovered_projects)
        
        self.query_one("#console-panel", ProjectConsole).write_line(
            f"✅ Removed '{project_name}' from projects"
        )

    async def on_shutdown(self, event) -> None:
        """Called when the app is shutting down."""
        self.log("Shutting down active processes...")
        for project_name, process_manager in self.active_processes.items():
            if process_manager.is_running:
                self.log(f"Terminating process for {project_name}...")
                await process_manager.terminate()
        
        # Stop all embedded terminals
        self.log(f"Stopping {len(self.active_terminals)} active terminal(s)...")
        for project_name, terminal in self.active_terminals.items():
            self.log(f"Stopping terminal for {project_name}...")
            terminal.stop()
            
        self.log("All active processes terminated.")
        await super().on_shutdown(event) # Call parent's shutdown

    def action_focus_command_bar(self) -> None:
        """Focus the command bar for search."""
        command_bar = self.query_one("#command-bar", CommandBar)
        command_bar.focus()
    
    def action_focus_navigator(self) -> None:
        """Focus the navigator panel for project selection."""
        navigator = self.query_one("#navigator-panel", ProjectNavigator)
        navigator.focus()
    
    def action_focus_ports(self) -> None:
        """Focus the ports panel for quick killing."""
        ports = self.query_one("#ports-panel", PortMonitor)
        ports.focus()
    
    def action_show_keys(self) -> None:
        """Show keyboard shortcuts help."""
        console = self.query_one("#console-panel", ProjectConsole)
        console.clear()
        console.write_line("=" * 70)
        console.write_line("⌨️  KEYBOARD SHORTCUTS REFERENCE")
        console.write_line("=" * 70)
        console.write_line("")
        console.write_line("🔍 GLOBAL COMMANDS:")
        console.write_line("  Ctrl+\\          → Command Palette (ALL commands)")
        console.write_line("  Ctrl+P or /     → Search projects")
        console.write_line("  Escape          → Focus Navigator (project list)")
        console.write_line("  Ctrl+K          → Focus Running Applications panel")
        console.write_line("  Ctrl+A          → Add folder manually")
        console.write_line("  ? or h          → Show this help screen")
        console.write_line("")
        console.write_line("📁 NAVIGATOR (Project List):")
        console.write_line("  Click           → Select project")
        console.write_line("  Enter           → Open console with venv activated")
        console.write_line("  r               → Open console WITHOUT venv (raw terminal)")
        console.write_line("  t               → Open iTerm tab WITH venv")
        console.write_line("  T               → Open iTerm tab WITHOUT venv (raw)")
        console.write_line("  g               → Open Gemini CLI in iTerm pane")
        console.write_line("  o               → Open OpenCode in iTerm pane")
        console.write_line("  a               → Add folder manually")
        console.write_line("  d               → Remove selected manual project")
        console.write_line("")
        console.write_line("💻 CONSOLE (Terminal):")
        console.write_line("  Ctrl+C          → Interrupt current running process")
        console.write_line("  Ctrl+L          → Clear console output")
        console.write_line("  Type commands   → Execute in active terminal")
        console.write_line("")
        console.write_line("🖥️  RUNNING APPLICATIONS:")
        console.write_line("  / or Ctrl+F     → Search/filter applications")
        console.write_line("  Click           → Select application")
        console.write_line("  Enter           → Bring app to foreground (focus)")
        console.write_line("  j or ↓          → Move selection down")
        console.write_line("  k or ↑          → Move selection up")
        console.write_line("  x or Delete     → Kill selected application")
        console.write_line("  Scroll          → View more applications")
        console.write_line("")
        console.write_line("=" * 70)
        console.write_line("💡 TIP: Press Ctrl+\\ for Command Palette with ALL shortcuts")
        console.write_line("=" * 70)
    
    def action_add_folder(self) -> None:
        """Trigger add folder action."""
        self.post_message(AddFolder())

    # def action_toggle_dark(self) -> None:
    #     """An action to toggle dark mode."""
    #     self.dark = not self.dark


def run_app():
    """Entry point for the CLI tool."""
    app = LocalControlApp()
    app.run()


if __name__ == "__main__":
    run_app()
