"""SSH adapter — remote command execution with simulated fallback."""

import json
import subprocess
import shutil
from typing import Any


class SSHAdapter:
    """Execute commands on remote hosts via SSH.

    Falls back to simulated output when ssh is not available.
    """

    SIMULATED_OUTPUTS: dict[str, str] = {
        "systemctl status nginx": "● nginx.service - A high performance web server\n   Loaded: loaded (/lib/systemd/system/nginx.service; enabled)\n   Active: active (running) since Mon 2024-06-10 08:30:00 UTC; 30 days ago",
        "systemctl status docker": "● docker.service - Docker Application Container Engine\n   Loaded: loaded (/lib/systemd/system/docker.service; enabled)\n   Active: active (running) since Mon 2024-06-10 08:00:00 UTC; 30 days ago",
        "df -h": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        50G   30G   20G  60% /\ntmpfs           7.8G     0  7.8G   0% /dev/shm",
        "free -h": "              total        used        free      shared  buff/cache   available\nMem:           15Gi       8.2Gi       2.1Gi       1.0Gi       5.1Gi       6.2Gi\nSwap:         2.0Gi       512Mi       1.5Gi",
        "top -bn1 | head -5": "top - 14:32:01 up 30 days,  2:15,  1 user,  load average: 0.08, 0.12, 0.09\nTasks: 156 total,   1 running, 155 sleeping\n%Cpu(s):  5.2 us,  2.1 sy,  0.0 ni, 92.5 id,  0.2 wa\nMiB Mem:  15996 total,  8400 used,  2100 free,  5100 buff/cache",
        "ps aux | head -10": "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 225672  9180 ?        Ss   Jun10   0:05 /sbin/init\nroot       512  0.0  0.3 380912 28140 ?        Ss   Jun10   0:12 /usr/sbin/nginx",
        "ss -tlnp": "State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process\nLISTEN 0      128    0.0.0.0:80         0.0.0.0:*        nginx\nLISTEN 0      128    0.0.0.0:443        0.0.0.0:*        nginx\nLISTEN 0      128    0.0.0.0:22         0.0.0.0:*        sshd\nLISTEN 0      128    0.0.0.0:8000       0.0.0.0:*        python",
    }

    def __init__(
        self,
        simulate: bool = False,
        host: str = "localhost",
        user: str = "root",
        port: int = 22,
        key_file: str | None = None,
    ):
        self.simulate = simulate
        self.host = host
        self.user = user
        self.port = port
        self.key_file = key_file
        self._ssh_path = shutil.which("ssh")

    @property
    def available(self) -> bool:
        if self.simulate:
            return False
        if self.host == "localhost":
            return True  # local execution always available
        return self._ssh_path is not None

    def _build_ssh_cmd(self, remote_cmd: str) -> list[str]:
        if self.host == "localhost":
            return ["bash", "-c", remote_cmd]

        cmd = [self._ssh_path or "ssh"]
        if self.key_file:
            cmd.extend(["-i", self.key_file])
        cmd.extend([
            "-p", str(self.port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            f"{self.user}@{self.host}",
            remote_cmd,
        ])
        return cmd

    def execute(self, command: str) -> dict[str, Any]:
        """Execute a command on the remote host.

        Args:
            command: Shell command to execute.

        Returns:
            Dict with success, output, error, simulated.
        """
        if self.simulate or (self.host != "localhost" and not self._ssh_path):
            return self._simulate(command)

        try:
            full_cmd = self._build_ssh_cmd(command)
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "simulated": False,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "SSH command timed out (30s)", "simulated": False}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "simulated": False}

    def _simulate(self, command: str) -> dict[str, Any]:
        for key, output in self.SIMULATED_OUTPUTS.items():
            if key in command:
                return {"success": True, "output": output, "error": "", "simulated": True}
        return {
            "success": True,
            "output": f"[simulated] {self.user}@{self.host}$ {command}\nCommand executed successfully (simulated).",
            "error": "",
            "simulated": True,
        }

    def check_service(self, service_name: str) -> dict[str, Any]:
        return self.execute(f"systemctl status {service_name}")

    def check_disk(self) -> dict[str, Any]:
        return self.execute("df -h")

    def check_memory(self) -> dict[str, Any]:
        return self.execute("free -h")

    def check_cpu(self) -> dict[str, Any]:
        return self.execute("top -bn1 | head -5")

    def check_processes(self) -> dict[str, Any]:
        return self.execute("ps aux | head -20")

    def check_ports(self) -> dict[str, Any]:
        return self.execute("ss -tlnp")
