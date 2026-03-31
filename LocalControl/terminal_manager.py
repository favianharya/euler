"""
Terminal Manager for LocalControl - handles embedded terminal subprocess.
"""
import subprocess
import os
import signal
from pathlib import Path
from typing import Optional, Callable
import threading
import psutil


class EmbeddedTerminal:
    """Manages a persistent shell subprocess."""
    
    def __init__(self, output_callback: Optional[Callable[[str], None]] = None):
        self.process: Optional[subprocess.Popen] = None
        self.output_callback = output_callback
        self.active_venv: Optional[dict] = None
        self.current_dir: Path = Path.home()
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        
    def start(self):
        """Start the persistent shell subprocess."""
        if self.process:
            return
            
        try:
            shell = '/bin/bash'
            
            self.process = subprocess.Popen(
                [shell, '--norc', '--noprofile'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(self.current_dir),
                env=os.environ.copy(),
                start_new_session=True
            )
            
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self._reader_thread.start()
            
            # Give it a moment to start
            import time
            time.sleep(0.2)
            
            # Send initial setup
            self.run_command("export PS1='$ '")
            self.run_command(f"cd '{self.current_dir}'")
            self.run_command("echo '🚀 Terminal ready'")
            time.sleep(0.1)
            
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"⚠️  Failed to start terminal: {e}")

        
    def _read_output(self):
        """Read output from stdout and stderr in a separate thread."""
        if not self.process:
            return
            
        while self._running:
            try:
                # Check if process is still alive
                if self.process.poll() is not None:
                    if self._running and self.output_callback:
                        self.output_callback("⚠️  Terminal process ended")
                    break
                
                # Read stdout
                if self.process.stdout:
                    line = self.process.stdout.readline()
                    if line:
                        if self.output_callback:
                            self.output_callback(line.rstrip())
                
                # Read stderr
                if self.process.stderr:
                    try:
                        import select
                        # Check if stderr has data without blocking
                        ready, _, _ = select.select([self.process.stderr], [], [], 0.01)
                        if ready:
                            err_line = self.process.stderr.readline()
                            if err_line:
                                if self.output_callback:
                                    self.output_callback(f"⚠️  {err_line.rstrip()}")
                    except Exception:
                        pass
                    
            except Exception as e:
                if self._running:
                    if self.output_callback:
                        self.output_callback(f"⚠️  Output read error: {e}")
                break
    
    def run_command(self, command: str):
        """Execute a command in the shell."""
        if not self.process or not self.process.stdin:
            if self.output_callback:
                self.output_callback("⚠️  Terminal not running")
            return
        
        # Check if process is still alive
        if self.process.poll() is not None:
            if self.output_callback:
                self.output_callback("⚠️  Terminal process has ended")
            return
            
        try:
            self.process.stdin.write(f"{command}\n")
            self.process.stdin.flush()
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"⚠️  Error executing command: {e}")
    
    def send_interrupt(self):
        """Send SIGINT (Ctrl+C) to the terminal."""
        if not self.process:
            if self.output_callback:
                self.output_callback("⚠️  Terminal not running")
            return
        
        try:
            # Get all child processes
            try:
                parent = psutil.Process(self.process.pid)
                children = parent.children(recursive=True)
                
                # Send SIGINT to all children
                for child in children:
                    try:
                        child.send_signal(signal.SIGINT)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                        
            except psutil.NoSuchProcess:
                pass
            
            # Send SIGINT to the main process
            self.process.send_signal(signal.SIGINT)
            
            if self.output_callback:
                self.output_callback("⚡ Interrupt signal sent")
                    
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"⚠️  Error sending interrupt: {e}")
    
    def activate_venv(self, project_name: str, venv_path: str, project_path: str):
        """Activate a virtual environment for a project."""
        # Deactivate current venv if any
        if self.active_venv:
            self.run_command("deactivate 2>/dev/null || true")
        
        activate_script = Path(venv_path) / "bin" / "activate"
        
        if not activate_script.exists():
            if self.output_callback:
                self.output_callback(f"❌ Activation script not found: {activate_script}")
            return
        
        # Change to project directory
        self.run_command(f"cd '{project_path}' 2>/dev/null || cd ~")
        
        # Source the activation script
        self.run_command(f"source '{activate_script}' 2>/dev/null")
        
        # Confirm activation
        self.run_command("echo '✅ Virtual environment activated'")
        self.run_command(f"echo 'Project: {project_name}'")
        self.run_command("echo 'Python: '$(which python 2>/dev/null || echo 'not found')")
        self.run_command("echo 'Directory: '$(pwd)")
        self.run_command("echo ''")
        self.run_command("echo 'Type commands below (Ctrl+C=interrupt | Ctrl+L=clear)'")
        
        self.active_venv = {
            "name": project_name,
            "path": venv_path,
            "project_path": project_path
        }
        self.current_dir = Path(project_path)
    
    def deactivate_venv(self):
        """Deactivate the current virtual environment."""
        if not self.active_venv:
            if self.output_callback:
                self.output_callback("⚠️  No virtual environment is currently active")
            return
        
        project_name = self.active_venv.get('name', 'unknown')
        self.run_command("deactivate 2>/dev/null || true")
        self.run_command("echo '🔴 Virtual environment deactivated'")
        self.run_command(f"echo 'Project: {project_name}'")
        self.active_venv = None
    
    def change_directory(self, path: str):
        """Change the working directory."""
        self.run_command(f"cd '{path}'")
        self.current_dir = Path(path)
    
    def stop(self):
        """Stop the shell subprocess and all its child processes."""
        self._running = False
        
        if not self.process:
            self._cleanup_fds()
            return
        
        try:
            # Get the process and all its children using psutil
            try:
                parent = psutil.Process(self.process.pid)
                
                # Get all descendants (children, grandchildren, etc.) recursively
                children = parent.children(recursive=True)
                
                if self.output_callback:
                    if children:
                        self.output_callback(f"🔴 Stopping {len(children)} child process(es)...")
                
                # Terminate children first (in reverse order - deepest first)
                for child in reversed(children):
                    try:
                        cmd = ' '.join(child.cmdline()[:3]) if child.cmdline() else child.name()
                        if self.output_callback:
                            self.output_callback(f"  🛑 Terminating: {cmd} (PID: {child.pid})")
                        child.terminate()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                # Wait briefly for graceful termination
                gone, alive = psutil.wait_procs(children, timeout=2)
                
                # Force kill any that are still alive
                if alive:
                    if self.output_callback:
                        self.output_callback(f"  ⚠️  Force killing {len(alive)} remaining process(es)...")
                    for p in alive:
                        try:
                            cmd = ' '.join(p.cmdline()[:3]) if p.cmdline() else p.name()
                            if self.output_callback:
                                self.output_callback(f"  💀 Force kill: {cmd} (PID: {p.pid})")
                            p.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                
                # Now terminate the parent shell
                parent.terminate()
                parent.wait(timeout=1)
                        
            except psutil.NoSuchProcess:
                # Process already gone
                pass
            
            # Force kill the main process if still alive
            try:
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
            except Exception:
                pass
                
        except Exception as e:
            if self.output_callback:
                self.output_callback(f"⚠️  Cleanup error: {e}")
            try:
                if self.process and self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass
        finally:
            self.process = None
        
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1)
        
        if self.output_callback:
            self.output_callback("✅ All processes stopped")
