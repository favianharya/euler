import psutil
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import sys

def get_process_info(pid: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves information about a process given its PID.
    """
    try:
        process = psutil.Process(pid)
        return {
            "pid": pid,
            "name": process.name(),
            "cmdline": " ".join(process.cmdline()),
            "cwd": process.cwd(),
            "status": process.status(),
            "username": process.username()
        }
    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied:
        # This can happen for system processes without elevated privileges
        return {
            "pid": pid,
            "name": "[Access Denied]",
            "cmdline": "[Access Denied]",
            "cwd": "[Access Denied]",
            "status": "[Access Denied]",
            "username": "[Access Denied]"
        }

def get_running_applications() -> List[Dict[str, Any]]:
    """
    Get all running GUI applications on the Mac.
    Filters to show only actual user applications like Chrome, Spotify, etc.
    """
    applications = []
    current_user = os.getenv('USER', '')
    
    # Common system process names to exclude
    system_processes = {
        'kernel_task', 'loginwindow', 'WindowServer', 'Finder', 'Dock', 
        'SystemUIServer', 'launchd', 'cfprefsd', 'distnoted', 'notifyd',
        'systemstats', 'mds', 'mds_stores', 'mdworker', 'UserEventAgent',
        'sysmond', 'bird', 'rapportd', 'trustd', 'hidd', 'coreauthd'
    }
    
    # Helper/agent process keywords to exclude (only when they appear with --type= flag)
    helper_keywords = [
        'crashpad', 'agent', 'xpc', 'widget'
    ]
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline', 'exe', 'status']):
            try:
                pinfo = proc.info
                name = pinfo.get('name', '')
                username = pinfo.get('username', '')
                cmdline = pinfo.get('cmdline', [])
                exe_path = pinfo.get('exe', '')
                
                # Filter: only show user's processes
                if username != current_user or name in system_processes:
                    continue
                
                # Only include if it's from an .app bundle (actual GUI applications)
                # or if the executable path contains /Applications/
                is_app = False
                if exe_path:
                    if '.app/Contents/' in exe_path or '/Applications/' in exe_path:
                        is_app = True
                elif cmdline and len(cmdline) > 0:
                    # Check first command line argument for .app path
                    if '.app/Contents/' in cmdline[0] or '/Applications/' in cmdline[0]:
                        is_app = True
                
                if not is_app:
                    continue
                
                # Skip helper/background processes only if they have --type= in cmdline
                # This catches Chrome Helper, VS Code Helper (Renderer), etc. but not main processes
                cmdline_str = ' '.join(cmdline) if cmdline else ''
                if '--type=' in cmdline_str:
                    # This is a subprocess (renderer, gpu-process, utility, etc.)
                    continue
                
                # Also skip processes with explicit helper keywords in the name
                name_lower = name.lower()
                if any(keyword in name_lower for keyword in helper_keywords):
                    continue
                
                # Get more detailed info
                process_info = get_process_info(proc.pid)
                if process_info and process_info['name'] != '[Access Denied]':
                    applications.append({
                        "pid": proc.pid,
                        "process_info": process_info
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        pass
    
    return applications

def map_ports_to_processes() -> List[Dict[str, Any]]:
    """
    Maps open network ports to their associated processes.
    Handles AccessDenied and ZombieProcess errors gracefully.
    Uses per-process scanning to work without root privileges.
    """
    port_process_map = []
    
    # First try the system-wide approach (requires root on macOS)
    try:
        connections = psutil.net_connections(kind='inet')
        for conn in connections:
            if conn.laddr and conn.status == psutil.CONN_LISTEN:
                if conn.pid:
                    process_info = get_process_info(conn.pid)
                    if process_info:
                        port_process_map.append({
                            "port": conn.laddr.port,
                            "pid": conn.pid,
                            "process_info": process_info
                        })
        return port_process_map
    except (psutil.AccessDenied, psutil.ZombieProcess):
        # Fall back to per-process scanning (works without root)
        pass
    
    # Per-process approach - slower but works without sudo
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Get connections for this specific process
            connections = proc.net_connections(kind='inet')
            for conn in connections:
                if conn.laddr and conn.status == psutil.CONN_LISTEN:
                    process_info = get_process_info(proc.pid)
                    if process_info:
                        port_process_map.append({
                            "port": conn.laddr.port,
                            "pid": proc.pid,
                            "process_info": process_info
                        })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # Skip processes we can't access
            continue
    
    return port_process_map

def identify_port_conflicts(
    current_projects: Dict[str, Any],
    port_process_map: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Identifies port conflicts by comparing active processes with known projects.
    A conflict occurs if a port is in use and either:
    1. The process using it is not associated with any of the `current_projects`.
    2. A `current_project` is expected to use a port that is held by another process.
    """
    conflicts = []
    project_paths = {Path(details["path"]).resolve() for details in current_projects.values()}

    for item in port_process_map:
        port = item["port"]
        process_info = item["process_info"]
        
        process_cwd = Path(process_info["cwd"]).resolve()
        
        # Check if the process's CWD is one of our known projects
        is_known_project_process = False
        for project_name, project_details in current_projects.items():
            if Path(project_details["path"]).resolve() == process_cwd:
                is_known_project_process = True
                break
        
        if not is_known_project_process:
            conflicts.append({
                "type": "external_process_using_port",
                "port": port,
                "process": process_info,
                "message": f"Port {port} is held by an external process (PID: {process_info['pid']}, Name: {process_info['name']}) not associated with a known project."
            })
    
    # TODO: Add logic for when a project is trying to start on an occupied port.
    # This would typically be handled during the "Direct-Execution Engine" phase
    # where we know which project wants which port.

    return conflicts

if __name__ == "__main__":
    # Example usage:
    # This part would typically be integrated into the main Textual app
    print("Mapping ports to processes...")
    ports_info = map_ports_to_processes()
    for p_info in ports_info:
        print(f"Port: {p_info['port']}, PID: {p_info['pid']}, Name: {p_info['process_info']['name']}, CWD: {p_info['process_info']['cwd']}")

    # Dummy projects for testing conflicts
    dummy_projects = {
        "my_backend": {"path": "/Users/t-favian.adrian/Documents/repository/LocalControl", "venv": None, "git_branch": "main"},
        "another_project": {"path": "/Users/t-favian.adrian/Documents/some_other_project", "venv": None, "git_branch": "dev"}
    }
    
    # Create a dummy directory to simulate another_project
    dummy_project_path = Path("/Users/t-favian.adrian/Documents/some_other_project")
    if not dummy_project_path.exists():
        dummy_project_path.mkdir()
    
    print("\nIdentifying port conflicts...")
    conflicts = identify_port_conflicts(dummy_projects, ports_info)
    for conflict in conflicts:
        print(f"Conflict: {conflict['message']}")
    
    # Clean up dummy directory
    if dummy_project_path.exists():
        dummy_project_path.rmdir()