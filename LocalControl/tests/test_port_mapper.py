import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import psutil

# Assuming port_mapper is in the parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from port_mapper import get_process_info, map_ports_to_processes, identify_port_conflicts

class TestPortMapper:
    @patch('port_mapper.psutil.Process')
    def test_get_process_info_success(self, mock_process_class):
        mock_process = MagicMock()
        mock_process.name.return_value = "test_process"
        mock_process.cmdline.return_value = ["python", "script.py"]
        mock_process.cwd.return_value = "/tmp/test_dir"
        mock_process.status.return_value = "running"
        mock_process.username.return_value = "test_user"
        mock_process_class.return_value = mock_process

        info = get_process_info(1234)
        assert info["pid"] == 1234
        assert info["name"] == "test_process"
        assert info["cmdline"] == "python script.py"
        assert info["cwd"] == "/tmp/test_dir"
        assert info["status"] == "running"
        assert info["username"] == "test_user"

    @patch('port_mapper.psutil.Process')
    def test_get_process_info_no_such_process(self, mock_process_class):
        mock_process_instance = MagicMock()
        mock_process_instance.name.side_effect = psutil.NoSuchProcess(9999) # Raise on method call
        mock_process_class.return_value = mock_process_instance
        info = get_process_info(9999)
        assert info is None

    @patch('port_mapper.psutil.Process', side_effect=psutil.AccessDenied)
    def test_get_process_info_access_denied(self, mock_process_class):
        info = get_process_info(5678)
        assert info["pid"] == 5678
        assert info["name"] == "[Access Denied]"
        assert info["cmdline"] == "[Access Denied]"

    @patch('port_mapper.psutil.net_connections')
    @patch('port_mapper.get_process_info')
    def test_map_ports_to_processes(self, mock_get_process_info, mock_net_connections):
        # Mock connection objects
        mock_conn1 = MagicMock()
        mock_conn1.laddr.port = 8000
        mock_conn1.status = psutil.CONN_LISTEN
        mock_conn1.pid = 100

        mock_conn2 = MagicMock()
        mock_conn2.laddr.port = 3000
        mock_conn2.status = psutil.CONN_LISTEN
        mock_conn2.pid = 200

        # Non-listening connection
        mock_conn3 = MagicMock()
        mock_conn3.laddr.port = 5000
        mock_conn3.status = psutil.CONN_ESTABLISHED
        mock_conn3.pid = 300

        # Connection without PID
        mock_conn4 = MagicMock()
        mock_conn4.laddr.port = 9000
        mock_conn4.status = psutil.CONN_LISTEN
        mock_conn4.pid = None

        mock_net_connections.return_value = [mock_conn1, mock_conn2, mock_conn3, mock_conn4]

        mock_get_process_info.side_effect = [
            {"pid": 100, "name": "proc1", "cwd": "/project1"},
            {"pid": 200, "name": "proc2", "cwd": "/project2"}
        ]

        result = map_ports_to_processes()
        assert len(result) == 2
        assert result[0]["port"] == 8000
        assert result[0]["pid"] == 100
        assert result[1]["port"] == 3000
        assert result[1]["pid"] == 200

    @patch('port_mapper.psutil.net_connections', side_effect=psutil.AccessDenied)
    def test_map_ports_to_processes_access_denied(self, mock_net_connections):
        result = map_ports_to_processes()
        assert result == [] # Should return empty list on AccessDenied

    def test_identify_port_conflicts_no_conflicts(self):
        current_projects = {
            "proj1": {"path": "/project1", "venv": None, "git_branch": None},
            "proj2": {"path": "/project2", "venv": None, "git_branch": None},
        }
        port_process_map = [
            {"port": 8000, "pid": 100, "process_info": {"pid": 100, "name": "proc1", "cwd": "/project1"}},
            {"port": 3000, "pid": 200, "process_info": {"pid": 200, "name": "proc2", "cwd": "/project2"}},
        ]
        conflicts = identify_port_conflicts(current_projects, port_process_map)
        assert len(conflicts) == 0

    def test_identify_port_conflicts_external_process(self):
        current_projects = {
            "proj1": {"path": "/project1", "venv": None, "git_branch": None},
        }
        port_process_map = [
            {"port": 8000, "pid": 100, "process_info": {"pid": 100, "name": "proc1", "cwd": "/project1"}},
            {"port": 9000, "pid": 200, "process_info": {"pid": 200, "name": "external_proc", "cwd": "/external_path"}},
        ]
        conflicts = identify_port_conflicts(current_projects, port_process_map)
        assert len(conflicts) == 1
        assert conflicts[0]["port"] == 9000
        assert conflicts[0]["type"] == "external_process_using_port"
        assert "external_proc" in conflicts[0]["message"]

    def test_identify_port_conflicts_access_denied_cwd(self):
        current_projects = {
            "proj1": {"path": "/project1", "venv": None, "git_branch": None},
        }
        port_process_map = [
            {"port": 8000, "pid": 100, "process_info": {"pid": 100, "name": "proc1", "cwd": "[Access Denied]"}},
        ]
        conflicts = identify_port_conflicts(current_projects, port_process_map)
        assert len(conflicts) == 1
        assert conflicts[0]["port"] == 8000
        assert conflicts[0]["type"] == "external_process_using_port"
        assert conflicts[0]["process"]["cwd"] == "[Access Denied]" # Assert on cwd in process_info
