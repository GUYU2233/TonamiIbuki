"""Phase Manager – tracks the diagnosis pipeline through its lifecycle phases.

Phases: ANALYSIS -> PLANNING -> EXECUTION -> VERIFICATION -> COMPLETION
"""

from enum import Enum
from typing import Optional


class Phase(str, Enum):
    ANALYSIS = "analysis"
    PLANNING = "planning"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    COMPLETION = "completion"


PHASE_TRANSITIONS = {
    Phase.ANALYSIS: Phase.PLANNING,
    Phase.PLANNING: Phase.EXECUTION,
    Phase.EXECUTION: Phase.VERIFICATION,
    Phase.VERIFICATION: Phase.COMPLETION,
    Phase.COMPLETION: None,
}

PHASE_OWNERS = {
    Phase.ANALYSIS: "Monitor Agent",
    Phase.PLANNING: "Diagnosis Agent",
    Phase.EXECUTION: "Execution Agent",
    Phase.VERIFICATION: "Supervisor Agent",
    Phase.COMPLETION: "Report Agent",
}

PHASE_DESCRIPTIONS = {
    Phase.ANALYSIS: "告警解析与初筛 – 判定严重级别、类别分类",
    Phase.PLANNING: "根因假设生成与方案规划 – RAG 上下文注入、CoT 推理",
    Phase.EXECUTION: "工具调用与修复执行 – 风险评估、HITL 审批拦截",
    Phase.VERIFICATION: "结果完整性审核 – 置信度评估、证据链汇总",
    Phase.COMPLETION: "诊断报告生成与案例归档",
}


class PhaseManager:
    """Tracks and transitions diagnosis phases.

    Usage:
        pm = PhaseManager()
        pm.transition()  # ANALYSIS -> PLANNING
        print(pm.current)  # Phase.PLANNING
        print(pm.progress_percent)  # 25
    """

    def __init__(self) -> None:
        self._current: Phase = Phase.ANALYSIS

    @property
    def current(self) -> Phase:
        return self._current

    @property
    def owner(self) -> str:
        return PHASE_OWNERS.get(self._current, "Unknown")

    @property
    def description(self) -> str:
        return PHASE_DESCRIPTIONS.get(self._current, "")

    @property
    def progress_percent(self) -> float:
        phases = list(Phase)
        idx = phases.index(self._current)
        return round(idx / (len(phases) - 1) * 100, 1)

    @property
    def is_complete(self) -> bool:
        return self._current == Phase.COMPLETION

    def transition(self) -> Optional[Phase]:
        """Move to next phase. Returns the new phase or None if already complete."""
        next_phase = PHASE_TRANSITIONS.get(self._current)
        if next_phase:
            self._current = next_phase
        return next_phase

    def jump_to(self, phase: Phase) -> None:
        """Force jump to a specific phase (e.g., for retry)."""
        self._current = phase

    def snapshot(self) -> dict:
        return {
            "phase": self._current.value,
            "owner": self.owner,
            "description": self.description,
            "progress_percent": self.progress_percent,
            "is_complete": self.is_complete,
        }

    def reset(self) -> None:
        self._current = Phase.ANALYSIS
