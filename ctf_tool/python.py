import paramiko
import subprocess
import sys
import tempfile
import os
import time
import logging
from ctf_tool.base_tool import BaseTool
from config import Config
from typing import Tuple, Dict

logger = logging.getLogger(__name__)


class PythonTool(BaseTool):
    def __init__(self):
        # Ask whether the user wants to execute code remotely
        self.remote = self.ask_remote_execution()
        if self.remote:
            ssh_config: dict = Config.get_tool_config("ssh_shell")
            self.hostname = ssh_config.get("host")
            self.port = ssh_config.get("port", 22)
            self.username = ssh_config.get("username")
            self.password = ssh_config.get("password")
            self.ssh_client = None
            self._connect()

    def ask_remote_execution(self) -> bool:
        """Prompt the user to decide whether to run code remotely."""
        print("\n--- Python execution options ---")
        print("1. Run locally")
        print("2. Run on the remote host")
        choice = input("Choose how to execute the Python code (1/2): ").strip()

        return choice == "2"

    def execute(self, arguments: dict) -> Tuple[str, str]:
        """Execute Python code."""
        content = arguments.get("content", "")

        if self.remote:
            return self._execute_remotely(content)
        return self._execute_locally(content)

    def _execute_locally(self, content: str) -> Tuple[str, str]:
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
                tmp.write(content.encode("utf-8"))
                tmp_path = tmp.name

            result = subprocess.run(
                [sys.executable, tmp_path], capture_output=True, text=True, timeout=30
            )
            os.unlink(tmp_path)
            return result.stdout, result.stderr
        except Exception as e:
            return "", str(e)

    def _execute_remotely(self, content: str) -> Tuple[str, str]:
        temp_name = f"py_script_{int(time.time())}.py"

        # Upload the script and execute it remotely
        upload_cmd = f"cat > {temp_name} << 'EOF'\n{content}\nEOF"
        self._shell_execute({"content": upload_cmd})
        stdout, stderr = self._shell_execute({"content": f"python3 {temp_name}"})
        self._shell_execute({"content": f"rm -f {temp_name}"})

        return stdout, stderr

    def _is_connected(self):
        """Verify that the SSH connection is still alive."""
        if not self.ssh_client:
            return False
        try:
            transport = self.ssh_client.get_transport()
            return transport and transport.is_active()
        except Exception:
            return False

    def _connect(self):
        """Establish or refresh the SSH connection."""
        try:
            if self.ssh_client:
                self.ssh_client.close()
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
            )
            self.ssh_client = client
            logger.info(f"SSH connection established: {self.username}@{self.hostname}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect over SSH: {str(e)}")
            raise ConnectionError(f"Failed to connect over SSH: {str(e)}")

    def _shell_execute(self, arguments: dict):
        # Check the connection and reconnect if necessary
        if not self._is_connected():
            logger.warning("SSH session dropped, attempting to reconnect...")
            self._connect()

        # Extract the command from the arguments
        command = arguments.get("content", "")
        if not command:
            return "", "Error: no command content provided"

        try:
            _, stdout, stderr = self.ssh_client.exec_command(command)

            # Read output
            stdout_bytes = stdout.read()
            stderr_bytes = stderr.read()

            # Decode safely
            def safe_decode(data: bytes) -> str:
                try:
                    return data.decode("utf-8")
                except UnicodeDecodeError:
                    return data.decode("utf-8", errors="replace")

            return safe_decode(stdout_bytes), safe_decode(stderr_bytes)

        except Exception as e:
            logger.error(f"Command execution failed: {str(e)}")
            return "", f"Command execution error: {str(e)}"

    @property
    def function_config(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": "execute_python_code",
                "description": "Execute a Python code snippet.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "purpose": {
                            "type": "string",
                            "description": "Explain why this step is required.",
                        },
                        "content": {
                            "type": "string",
                            "description": "The Python code to execute.",
                        },
                    },
                    "required": ["purpose", "content"],
                },
            },
        }
