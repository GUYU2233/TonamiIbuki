"""Ansible adapter — real ansible execution with simulated fallback."""

import json
import subprocess
import shutil
from typing import Any


class AnsibleAdapter:
    """Execute Ansible playbooks and ad-hoc commands.

    Falls back to simulated output when ansible is not available.
    """

    SIMULATED_OUTPUTS: dict[str, dict] = {
        "ping": {
            "stats": {"ok": 3, "changed": 0, "unreachable": 0, "failures": 0},
            "hosts": {
                "web-01": {"ping": "pong"},
                "web-02": {"ping": "pong"},
                "db-01": {"ping": "pong"},
            },
        },
        "uptime": {
            "stats": {"ok": 3, "changed": 0, "unreachable": 0, "failures": 0},
            "hosts": {
                "web-01": {"stdout": "14:32:01 up 30 days,  2:15,  1 user,  load average: 0.08, 0.12, 0.09"},
                "web-02": {"stdout": "14:32:01 up 30 days,  3:42,  0 users, load average: 0.05, 0.10, 0.07"},
                "db-01": {"stdout": "14:32:01 up 45 days,  1:08,  2 users, load average: 0.45, 0.38, 0.41"},
            },
        },
        "disk": {
            "stats": {"ok": 3, "changed": 0, "unreachable": 0, "failures": 1},
            "hosts": {
                "web-01": {"stdout": "/dev/sda1       50G   30G   20G  60% /"},
                "web-02": {"stdout": "/dev/sda1       50G   12G   38G  24% /"},
                "db-01": {"stdout": "/dev/sda1      100G   95G    5G  95% /  ← WARNING"},
            },
        },
        "memory": {
            "stats": {"ok": 3, "changed": 0, "unreachable": 0, "failures": 0},
            "hosts": {
                "web-01": {"stdout": "total=16G used=8G free=8G"},
                "web-02": {"stdout": "total=16G used=4G free=12G"},
                "db-01": {"stdout": "total=32G used=28G free=4G"},
            },
        },
    }

    def __init__(self, simulate: bool = False, inventory: str | None = None):
        self.simulate = simulate
        self.inventory = inventory
        self._ansible_path = shutil.which("ansible")

    @property
    def available(self) -> bool:
        return self._ansible_path is not None and not self.simulate

    def _build_inventory_arg(self) -> list[str]:
        if self.inventory:
            return ["-i", self.inventory]
        return []

    def execute(self, module: str, args: str = "", hosts: str = "all") -> dict[str, Any]:
        """Execute an Ansible ad-hoc command.

        Args:
            module: Ansible module name (e.g. ping, shell, command).
            args: Module arguments.
            hosts: Target host pattern.

        Returns:
            Dict with success, output, error, simulated.
        """
        if self.simulate or not self.available:
            return self._simulate(module, args)

        try:
            cmd = [self._ansible_path or "ansible", hosts, "-m", module]
            if args:
                cmd.extend(["-a", args])
            cmd.extend(self._build_inventory_arg())

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "simulated": False,
            }
        except FileNotFoundError:
            return self._simulate(module, args)
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Ansible command timed out (60s)", "simulated": False}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "simulated": False}

    def _simulate(self, module: str, args: str = "") -> dict[str, Any]:
        # Match known modules
        if module == "ping":
            data = self.SIMULATED_OUTPUTS["ping"]
        elif module in ("shell", "command"):
            if "uptime" in args:
                data = self.SIMULATED_OUTPUTS["uptime"]
            elif "df" in args:
                data = self.SIMULATED_OUTPUTS["disk"]
            elif "free" in args:
                data = self.SIMULATED_OUTPUTS["memory"]
            else:
                data = {
                    "stats": {"ok": 3, "changed": 0, "unreachable": 0, "failures": 0},
                    "hosts": {"web-01": {"stdout": "simulated output"}, "web-02": {"stdout": "simulated output"}},
                }
        else:
            data = {
                "stats": {"ok": 2, "changed": 0, "unreachable": 0, "failures": 0},
                "hosts": {"target-01": {"result": f"simulated {module} {args}"}},
            }

        return {
            "success": True,
            "output": json.dumps(data, indent=2, ensure_ascii=False),
            "error": "",
            "simulated": True,
        }

    def ping_all(self) -> dict[str, Any]:
        return self.execute("ping")

    def run_shell(self, command: str, hosts: str = "all") -> dict[str, Any]:
        return self.execute("shell", command, hosts)

    def check_disk(self, hosts: str = "all") -> dict[str, Any]:
        return self.execute("shell", "df -h", hosts)

    def check_memory(self, hosts: str = "all") -> dict[str, Any]:
        return self.execute("shell", "free -h", hosts)
