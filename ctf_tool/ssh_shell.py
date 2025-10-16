from typing import Dict
from config import Config
from ctf_tool.base_tool import BaseTool
import paramiko
import os
import logging

logger = logging.getLogger(__name__)


class SSHShell(BaseTool):
    def __init__(self):
        ssh_config: dict = Config.get_tool_config("ssh_shell")
        self.hostname = ssh_config.get("host")
        self.port = ssh_config.get("port", 22)
        self.username = ssh_config.get("username")
        self.password = ssh_config.get("password")
        self.ssh_client = None
        # Upload attachments if the directory is not empty
        if len(os.listdir("./attachments")) > 0:
            logger.info("Attachments detected, uploading to the remote host...")
            self.upload_folder("./attachments", ".")
            logger.info("Attachment upload complete.")
        self._connect()  # Connect immediately during initialization

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

    def _is_connected(self):
        """Verify that the SSH connection is still alive."""
        if not self.ssh_client:
            return False
        try:
            transport = self.ssh_client.get_transport()
            return transport and transport.is_active()
        except Exception:
            return False

    def execute(self, arguments: dict):
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

    def upload_folder(self, local_path, remote_path):
        if not self._is_connected():
            logger.warning("SSH session dropped, attempting to reconnect...")
            self._connect()

        try:
            sftp = self.ssh_client.open_sftp()

            # Ensure the remote path exists
            try:
                sftp.stat(remote_path)
            except IOError:
                sftp.mkdir(remote_path)

            # Recursively upload the folder
            for root, _, files in os.walk(local_path):
                # Compute the relative path and convert it to UNIX style
                relative_path = os.path.relpath(root, local_path).replace("\\", "/")
                remote_dir = (
                    remote_path + "/" + relative_path
                    if relative_path != "."
                    else remote_path
                )

                # Ensure the remote directory exists
                try:
                    sftp.stat(remote_dir)
                except IOError:
                    sftp.mkdir(remote_dir)

                # Upload files
                for file in files:
                    local_file = os.path.join(root, file)
                    remote_file = remote_dir + "/" + file  # Always use UNIX-style paths
                    sftp.put(local_file, remote_file)
                    logger.debug(f"Uploaded: {local_file} -> {remote_file}")

                sftp.close()
                return f"Successfully uploaded folder: {local_path} -> {remote_path}"

        except Exception as e:
            logger.error(f"Failed to upload folder: {str(e)}")
            raise IOError(f"Failed to upload folder: {str(e)}")

    @property
    def function_config(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": "execute_shell_command",
                "description": "Run a shell command on the remote server where curl, sqlmap, nmap, openssl, and other tools are available.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "purpose": {
                            "type": "string",
                            "description": "Explain why this step is required.",
                        },
                        "content": {
                            "type": "string",
                            "description": "The shell command to run.",
                        },
                    },
                    "required": ["content", "purpose"],
                },
            },
        }
