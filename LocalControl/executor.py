import subprocess
import os
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio
import sys # Import sys
from rich.text import Text # Import Text for rich text formatting

class ManagedProcess:
    """
    Manages the lifecycle of a subprocess, capturing its output.
    """
    def __init__(self, project_path: Path, script: str, venv_path: Optional[Path] = None, project_tag: Optional[Text] = None):
        self.project_path = project_path
        self.script = script
        self.venv_path = venv_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.output_callback = None # Callback function to receive output
        self.task: Optional[asyncio.Task] = None # Task for reading stdout/stderr
        self.project_tag = project_tag # Store the project tag

    async def _read_stream(self, stream, callback):
        """Helper to read output from a stream asynchronously."""
        while True:
            line = await stream.readline()
            if line:
                decoded_line = line.decode().strip()
                if self.project_tag:
                    # Prepend the rich text tag to the line
                    callback(Text.assemble(self.project_tag, " ", decoded_line))
                else:
                    callback(decoded_line)
            else:
                break

    async def run(self, output_callback=None):
        """
        Runs the script in the project's virtual environment.
        """
        self.output_callback = output_callback

        if self.venv_path:
            python_executable = self.venv_path / "bin" / "python"
        else:
            python_executable = "python" # Fallback to system python

        command = [str(python_executable), self.script]

        # Environment variables (can load from .env file if needed)
        env = os.environ.copy()
        # TODO: Implement load_dotenv from PRD

        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.project_path),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Merge stderr into stdout
            )
            
            if self.output_callback:
                # Create tasks to read stdout and stderr asynchronously
                self.task = asyncio.create_task(
                    self._read_stream(self.process.stdout, self.output_callback)
                )

            await self.process.wait() # Wait for the process to complete
            if self.task:
                await self.task # Ensure all output is read

        except Exception as e:
            if self.output_callback:
                self.output_callback(f"Error executing script: {str(e)}")
            else:
                print(f"Error running managed process for {self.script}: {str(e)}", file=sys.stderr)

    async def terminate(self):
        """Terminates the managed process."""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            await self.process.wait()
            if self.output_callback:
                self.output_callback(f"--- Process for {self.script} terminated ---")
            if self.task:
                self.task.cancel()
        elif self.output_callback:
            self.output_callback(f"--- Process for {self.script} was not running ---")
    
    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

# Example Usage (for testing executor.py directly)
async def main_test():
    # Create a dummy project path and a dummy script
    dummy_project_dir = Path("./dummy_project")
    dummy_project_dir.mkdir(exist_ok=True)
    (dummy_project_dir / "test_script.py").write_text(
        """import time
print('Hello from dummy project!')
time.sleep(2)
print('Goodbye from dummy project!')"""
    )

    def print_output(line):
        print(f"[SCRIPT OUTPUT] {line}")

    print("Starting managed process...")
    process_manager = ManagedProcess(dummy_project_dir, "test_script.py")
    await process_manager.run(output_callback=print_output)
    print("Managed process finished.")

    # Clean up
    (dummy_project_dir / "test_script.py").unlink()
    dummy_project_dir.rmdir()

if __name__ == "__main__":
    # To run this example: python -m asyncio executor.py
    # This will simulate running a script and printing its output
    # Will need to handle this differently in Textual app context
    # asyncio.run(main_test())
    pass # Placeholder, as this will be integrated into the Textual app
