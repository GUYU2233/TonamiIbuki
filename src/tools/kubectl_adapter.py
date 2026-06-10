"""Kubectl adapter — real kubectl execution with simulated fallback."""

import json
import subprocess
import shutil
from pathlib import Path
from typing import Any


class KubectlAdapter:
    """Execute kubectl commands against a Kubernetes cluster.

    Falls back to simulated output when kubectl is not available or
    SIMULATE_TOOLS is enabled.
    """

    SIMULATED_OUTPUTS = {
        "get pods": {
            "items": [
                {
                    "metadata": {"name": "nginx-deployment-7d8c6d8f9-abcde", "namespace": "default"},
                    "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
                },
                {
                    "metadata": {"name": "api-server-6b9c8d7f6-xyz12", "namespace": "default"},
                    "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
                },
                {
                    "metadata": {"name": "redis-cache-5f8d7c6b9-qwert", "namespace": "default"},
                    "status": {"phase": "CrashLoopBackOff", "conditions": [{"type": "Ready", "status": "False"}]},
                },
            ]
        },
        "get nodes": {
            "items": [
                {"metadata": {"name": "node-01"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}},
                {"metadata": {"name": "node-02"}, "status": {"conditions": [{"type": "Ready", "status": "True"}]}},
                {"metadata": {"name": "node-03"}, "status": {"conditions": [{"type": "Ready", "status": "False"}]}},
            ]
        },
        "get events": {
            "items": [
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container",
                    "involvedObject": {"name": "redis-cache-5f8d7c6b9-qwert"},
                },
                {
                    "type": "Normal",
                    "reason": "Pulled",
                    "message": "Successfully pulled image",
                    "involvedObject": {"name": "nginx-deployment-7d8c6d8f9-abcde"},
                },
            ]
        },
    }

    def __init__(self, simulate: bool = False, kubeconfig: str | None = None, namespace: str = "default"):
        self.simulate = simulate
        self.kubeconfig = kubeconfig
        self.namespace = namespace
        self._kubectl_path = shutil.which("kubectl")

    @property
    def available(self) -> bool:
        return self._kubectl_path is not None and not self.simulate

    def _build_cmd(self, args: list[str]) -> list[str]:
        cmd = [self._kubectl_path or "kubectl"]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        cmd.extend(args)
        return cmd

    def execute(self, command: str, params: dict | None = None) -> dict[str, Any]:
        """Execute a kubectl command.

        Args:
            command: Sub-command (e.g. "get pods", "describe pod <name>").
            params: Optional extra parameters.

        Returns:
            Dict with keys: success, output, error, simulated.
        """
        if self.simulate or not self.available:
            return self._simulate(command)

        try:
            args = command.split()
            full_cmd = self._build_cmd(args)
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "simulated": False,
            }
        except FileNotFoundError:
            return self._simulate(command)
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "kubectl command timed out (30s)", "simulated": False}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e), "simulated": False}

    def _simulate(self, command: str) -> dict[str, Any]:
        for key, output in self.SIMULATED_OUTPUTS.items():
            if key in command:
                return {
                    "success": True,
                    "output": json.dumps(output, indent=2, ensure_ascii=False),
                    "error": "",
                    "simulated": True,
                }
        return {
            "success": True,
            "output": json.dumps({"message": f"Simulated kubectl {command} — no output template"}, indent=2),
            "error": "",
            "simulated": True,
        }

    def get_pods(self, namespace: str | None = None) -> dict[str, Any]:
        ns = namespace or self.namespace
        return self.execute(f"get pods -n {ns} -o json")

    def get_nodes(self) -> dict[str, Any]:
        return self.execute("get nodes -o json")

    def get_events(self, namespace: str | None = None) -> dict[str, Any]:
        ns = namespace or self.namespace
        return self.execute(f"get events -n {ns} --sort-by=.lastTimestamp")

    def describe_pod(self, pod_name: str, namespace: str | None = None) -> dict[str, Any]:
        ns = namespace or self.namespace
        return self.execute(f"describe pod {pod_name} -n {ns}")

    def get_logs(self, pod_name: str, namespace: str | None = None, tail: int = 100) -> dict[str, Any]:
        ns = namespace or self.namespace
        return self.execute(f"logs {pod_name} -n {ns} --tail={tail}")
