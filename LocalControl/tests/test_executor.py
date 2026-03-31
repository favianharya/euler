import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import asyncio
from rich.text import Text # Needed for project_tag
import subprocess # Needed for subprocess.PIPE and STDOUT
import os # Import os

# Assuming executor is in the parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from executor import ManagedProcess

@pytest.fixture
def dummy_project_env(tmp_path):
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    venv_path = project_path / ".venv"
    venv_path.mkdir()
    (venv_path / "bin").mkdir()
    (venv_path / "bin" / "python").touch()
    script_path = project_path / "test_script.py"
    script_path.write_text("import sys; print('hello'); print('world', file=sys.stderr)")
    return project_path, venv_path, script_path

@pytest.mark.asyncio
async def test_managed_process_run_success(dummy_project_env):
    project_path, venv_path, script_path = dummy_project_env
    
    mock_output_callback = MagicMock()
    
    # Mock the asyncio.create_subprocess_exec call
    mock_process = AsyncMock()
    mock_process.stdout.readline.side_effect = [
        b"line 1\n",
        b"line 2\n",
        b"" # End of stream
    ]
    mock_process.returncode = 0
    
    with patch('executor.asyncio.create_subprocess_exec', new=AsyncMock(return_value=mock_process)) as mock_subproc_exec:
        managed_process = ManagedProcess(project_path, script_path.name, venv_path)
        await managed_process.run(output_callback=mock_output_callback)

        # Assert create_subprocess_exec was called correctly
        mock_subproc_exec.assert_called_once_with(
            str(venv_path / "bin" / "python"),
            script_path.name,
            cwd=str(project_path),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        
        # Assert output callback was called
        mock_output_callback.assert_any_call("line 1")
        mock_output_callback.assert_any_call("line 2")
        assert mock_output_callback.call_count == 2

@pytest.mark.asyncio
async def test_managed_process_run_no_venv(dummy_project_env):
    project_path, _, script_path = dummy_project_env
    
    mock_output_callback = MagicMock()
    
    mock_process = AsyncMock()
    mock_process.stdout.readline.side_effect = [b"no venv output\n", b""]
    mock_process.returncode = 0
    
    with patch('executor.asyncio.create_subprocess_exec', new=AsyncMock(return_value=mock_process)) as mock_subproc_exec:
        managed_process = ManagedProcess(project_path, script_path.name, venv_path=None)
        await managed_process.run(output_callback=mock_output_callback)

        mock_subproc_exec.assert_called_once_with(
            "python", # Should use system python
            script_path.name,
            cwd=str(project_path),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        mock_output_callback.assert_called_once_with("no venv output")

@pytest.mark.asyncio
async def test_managed_process_terminate(dummy_project_env):
    project_path, venv_path, script_path = dummy_project_env
    
    mock_output_callback = MagicMock()
    
    mock_process = AsyncMock()
    # Simulate a running process that keeps producing output
    mock_process.returncode = None
    mock_process.stdout.readline.side_effect = [
        b"line 1\n",
        b"line 2\n",
        asyncio.CancelledError # Simulate cancellation causing run to exit
    ]
    
    with patch('executor.asyncio.create_subprocess_exec', new=AsyncMock(return_value=mock_process)):
        managed_process = ManagedProcess(project_path, script_path.name, venv_path)
        # Start the process in a background task (similar to how LocalControlApp does)
        task = asyncio.create_task(managed_process.run(output_callback=mock_output_callback))
        
        # Give it a moment to "start"
        await asyncio.sleep(0.01)

        assert managed_process.is_running is True
        
        await managed_process.terminate()
        
        mock_process.terminate.assert_called_once()
        assert mock_process.wait.await_count == 2 
        # Check the last call to output_callback is the termination message
        mock_output_callback.assert_called() # Ensure it was called at least once
        last_call_args, _ = mock_output_callback.call_args
        assert last_call_args[0] == f"--- Process for {script_path.name} terminated ---"
        
        mock_process.returncode = 0 # Manually set returncode to simulate termination
        assert managed_process.is_running is False
        
        task.cancel() # Clean up the running task

@pytest.mark.asyncio
async def test_managed_process_is_running(dummy_project_env):
    project_path, venv_path, script_path = dummy_project_env
    
    mock_process = AsyncMock()
    mock_process.returncode = None # Process is running
    
    with patch('executor.asyncio.create_subprocess_exec', new=AsyncMock(return_value=mock_process)):
        managed_process = ManagedProcess(project_path, script_path.name, venv_path)
        # Start without waiting for completion
        task = asyncio.create_task(managed_process.run())
        await asyncio.sleep(0.01) # Give it a moment to start
        assert managed_process.is_running is True
        
        mock_process.returncode = 0 # Process has finished
        assert managed_process.is_running is False
        task.cancel() # Clean up

@pytest.mark.asyncio
async def test_managed_process_run_with_tag(dummy_project_env):
    project_path, venv_path, script_path = dummy_project_env
    
    mock_output_callback = MagicMock()
    project_tag = Text("[TEST]", style="red")
    
    mock_process = AsyncMock()
    mock_process.stdout.readline.side_effect = [
        b"output line\n",
        b""
    ]
    mock_process.returncode = 0
    
    with patch('executor.asyncio.create_subprocess_exec', new=AsyncMock(return_value=mock_process)):
        managed_process = ManagedProcess(project_path, script_path.name, venv_path, project_tag=project_tag)
        await managed_process.run(output_callback=mock_output_callback)

        expected_output = Text.assemble(project_tag, " ", "output line")
        mock_output_callback.assert_called_once_with(expected_output)
