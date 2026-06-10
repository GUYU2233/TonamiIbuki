"""Tool registry — simulated + real tool adapters."""

import time
import logging
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from src.tools.kubectl_adapter import KubectlAdapter
from src.tools.ansible_adapter import AnsibleAdapter
from src.tools.ssh_adapter import SSHAdapter

logger = logging.getLogger(__name__)


@dataclass
class ToolDef:
    name: str
    description: str
    category: str
    risk_level: str  # critical / high / medium / low / info
    enabled: bool = True


# ---------------------------------------------------------------------------
# Built-in simulated tools
# ---------------------------------------------------------------------------
SIMULATED_TOOLS: list[ToolDef] = [
    ToolDef("check_service_status", "检查指定服务运行状态", "system", "low"),
    ToolDef("check_system_resources", "检查 CPU / 内存 / 磁盘使用率", "system", "low"),
    ToolDef("check_network_connectivity", "测试网络连通性 (ping / telnet)", "network", "low"),
    ToolDef("check_process_list", "列出运行中的进程", "system", "low"),
    ToolDef("restart_service", "重启指定系统服务", "system", "high"),
    ToolDef("clear_disk_cache", "清理临时文件和缓存", "system", "medium"),
    ToolDef("fetch_remote_logs", "获取远端主机日志片段", "diagnostic", "low"),
]

# ---------------------------------------------------------------------------
# Real tool adapters
# ---------------------------------------------------------------------------
REAL_TOOL_DEFS: list[ToolDef] = [
    ToolDef("kubectl_get_pods", "获取 Kubernetes Pod 列表", "kubernetes", "low"),
    ToolDef("kubectl_get_nodes", "获取 Kubernetes Node 状态", "kubernetes", "low"),
    ToolDef("kubectl_get_events", "获取 Kubernetes 集群事件", "kubernetes", "low"),
    ToolDef("kubectl_describe_pod", "查看 Pod 详细信息", "kubernetes", "low"),
    ToolDef("kubectl_get_logs", "查看 Pod 日志", "kubernetes", "low"),
    ToolDef("ansible_ping", "Ansible 连通性测试", "automation", "low"),
    ToolDef("ansible_check_disk", "Ansible 批量磁盘检查", "automation", "low"),
    ToolDef("ansible_check_memory", "Ansible 批量内存检查", "automation", "low"),
    ToolDef("ansible_run_command", "Ansible 批量执行命令", "automation", "medium"),
    ToolDef("ssh_check_service", "SSH 检查远端服务状态", "remote", "low"),
    ToolDef("ssh_check_disk", "SSH 检查远端磁盘", "remote", "low"),
    ToolDef("ssh_check_memory", "SSH 检查远端内存", "remote", "low"),
    ToolDef("ssh_check_cpu", "SSH 检查远端 CPU", "remote", "low"),
    ToolDef("ssh_check_ports", "SSH 检查远端端口监听", "remote", "low"),
]


class ToolRegistry:
    """Unified tool registry with simulated and real adapters."""

    def __init__(self, simulate: bool = True, sandbox_dir: str = "data/sandbox"):
        self.simulate = simulate
        self.sandbox_dir = Path(sandbox_dir)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Real adapters (always instantiated, simulate mode controlled by flag)
        self.kubectl = KubectlAdapter(simulate=simulate)
        self.ansible = AnsibleAdapter(simulate=simulate)
        self.ssh = SSHAdapter(simulate=simulate)

    # ------------------------------------------------------------------
    # Tool listing
    # ------------------------------------------------------------------
    def list_tools(self) -> list[dict]:
        tools = []
        for t in SIMULATED_TOOLS:
            tools.append({
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "risk_level": t.risk_level,
                "enabled": t.enabled,
                "type": "simulated",
            })
        for t in REAL_TOOL_DEFS:
            available = self._real_available(t.name)
            tools.append({
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "risk_level": t.risk_level,
                "enabled": t.enabled and available,
                "type": "real",
            })
        return tools

    def _real_available(self, name: str) -> bool:
        """Check if the real tool backend is available."""
        prefix = name.split("_")[0]
        if prefix == "kubectl":
            return self.kubectl.available or self.simulate
        if prefix == "ansible":
            return self.ansible.available or self.simulate
        if prefix == "ssh":
            return self.ssh.available or self.simulate
        return False

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def enrich(self, tool_name: str, params: dict | None = None) -> dict[str, Any]:
        """Alias for execute — used by diagnosis_graph for semantic naming."""
        return self.execute(tool_name, params)

    def execute(self, tool_name: str, params: dict | None = None) -> dict[str, Any]:
        """Execute a tool by name.

        Returns:
            Dict with tool_name, status, output, duration_ms, risk_level, simulated.
        """
        params = params or {}
        t0 = time.perf_counter()

        # Try real adapters first
        result = self._try_real(tool_name, params)
        if result is not None:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "tool_name": tool_name,
                "status": "success" if result.get("success") else "error",
                "output": result.get("output", ""),
                "error": result.get("error", ""),
                "duration_ms": round(elapsed, 1),
                "risk_level": self._risk_level(tool_name),
                "simulated": result.get("simulated", False),
                "params": params,
            }

        # Fall back to simulated tools
        result = self._execute_simulated(tool_name, params)
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            "tool_name": tool_name,
            "status": "success" if result.get("success") else "error",
            "output": result.get("output", ""),
            "error": result.get("error", ""),
            "duration_ms": round(elapsed, 1),
            "risk_level": self._risk_level(tool_name),
            "simulated": True,
            "params": params,
        }

    def _try_real(self, tool_name: str, params: dict) -> dict | None:
        if tool_name == "kubectl_get_pods":
            return self.kubectl.get_pods(params.get("namespace"))
        elif tool_name == "kubectl_get_nodes":
            return self.kubectl.get_nodes()
        elif tool_name == "kubectl_get_events":
            return self.kubectl.get_events(params.get("namespace"))
        elif tool_name == "kubectl_describe_pod":
            return self.kubectl.describe_pod(params.get("pod_name", ""), params.get("namespace"))
        elif tool_name == "kubectl_get_logs":
            return self.kubectl.get_logs(
                params.get("pod_name", ""), params.get("namespace"), params.get("tail", 100)
            )
        elif tool_name == "ansible_ping":
            return self.ansible.ping_all()
        elif tool_name == "ansible_check_disk":
            return self.ansible.check_disk(params.get("hosts", "all"))
        elif tool_name == "ansible_check_memory":
            return self.ansible.check_memory(params.get("hosts", "all"))
        elif tool_name == "ansible_run_command":
            return self.ansible.run_shell(params.get("command", "echo ok"), params.get("hosts", "all"))
        elif tool_name == "ssh_check_service":
            return self.ssh.check_service(params.get("service", "nginx"))
        elif tool_name == "ssh_check_disk":
            return self.ssh.check_disk()
        elif tool_name == "ssh_check_memory":
            return self.ssh.check_memory()
        elif tool_name == "ssh_check_cpu":
            return self.ssh.check_cpu()
        elif tool_name == "ssh_check_ports":
            return self.ssh.check_ports()
        return None

    def _execute_simulated(self, tool_name: str, params: dict) -> dict[str, Any]:
        sandbox_log = self.sandbox_dir / f"{tool_name}.log"
        result_output = ""

        if tool_name == "check_service_status":
            svc = params.get("service", "nginx")
            result_output = f"● {svc}.service - active (running)\n  Loaded: loaded\n  Active: active (running)"
        elif tool_name == "check_system_resources":
            result_output = (
                "CPU: 45% | Memory: 62% (9.8G/16G) | "
                "Disk: 60% (30G/50G) | Load: 0.85, 1.02, 0.95"
            )
        elif tool_name == "check_network_connectivity":
            target = params.get("host", "8.8.8.8")
            result_output = f"PING {target}: 56 data bytes\n64 bytes from {target}: icmp_seq=0 ttl=117 time=1.23 ms"
        elif tool_name == "check_process_list":
            result_output = (
                "USER       PID %CPU %MEM    VSZ   RSS COMMAND\n"
                "root         1  0.0  0.1 225672  9180 systemd\n"
                "root       512  0.0  0.3 380912 28140 nginx\n"
                "mysql     1024  2.1  8.5 1892344 1382400 mysqld"
            )
        elif tool_name == "restart_service":
            svc = params.get("service", "nginx")
            result_output = f"Restarting {svc}... OK\n● {svc}.service - active (running)"
        elif tool_name == "clear_disk_cache":
            result_output = "Cleared 1.2G from /tmp, 350M from /var/cache\nDisk usage: 60% → 57%"
        elif tool_name == "fetch_remote_logs":
            result_output = (
                "[2024-06-10 14:30:01] ERROR connection refused on 127.0.0.1:3000\n"
                "[2024-06-10 14:30:05] WARN retry attempt 1/3\n"
                "[2024-06-10 14:30:10] ERROR max retries exceeded"
            )
        else:
            result_output = f"Simulated execution of '{tool_name}' with params {params}"

        sandbox_log.write_text(result_output)
        return {"success": True, "output": result_output, "error": ""}

    def _risk_level(self, tool_name: str) -> str:
        for t in SIMULATED_TOOLS + REAL_TOOL_DEFS:
            if t.name == tool_name:
                return t.risk_level
        return "info"
