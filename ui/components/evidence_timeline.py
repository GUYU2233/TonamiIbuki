"""Evidence timeline component for diagnosis sessions."""

import streamlit as st
from datetime import datetime, timezone


def _severity_icon(level: str) -> str:
    icons = {
        "critical": "🔴",
        "error": "🟠",
        "warning": "🟡",
        "info": "🔵",
        "debug": "⚪",
    }
    return icons.get(level.lower(), "⚪")


def render_evidence_timeline(
    evidence: list[dict],
    title: str = "📋 诊断证据时间线",
    max_items: int = 20,
) -> None:
    """Render a vertical timeline of diagnosis evidence.

    Each evidence dict should have:
        - timestamp (str or datetime)
        - message (str)
        - source (str): e.g. "monitor", "rag", "llm", "tool", "report"
        - severity (str, optional): critical/error/warning/info/debug
        - detail (str, optional): expandable detail text

    Args:
        evidence: List of evidence dicts.
        title: Timeline title.
        max_items: Maximum number of items to display.
    """
    if not evidence:
        st.info("暂无证据记录")
        return

    st.subheader(title)

    display_items = evidence[-max_items:]  # show most recent

    for i, item in enumerate(reversed(display_items)):
        ts = item.get("timestamp", "")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        ts_str = ts.strftime("%H:%M:%S") if isinstance(ts, datetime) else str(ts)
        sev = item.get("severity", "info")
        icon = _severity_icon(sev)
        source = item.get("source", "unknown")
        message = item.get("message", "")

        cols = st.columns([0.06, 0.12, 0.12, 0.70])
        with cols[0]:
            st.markdown(f"**{icon}**")
        with cols[1]:
            st.caption(ts_str)
        with cols[2]:
            st.caption(f"`{source}`")
        with cols[3]:
            st.markdown(message)

        detail = item.get("detail", "")
        if detail:
            with st.expander(f"详情 #{len(display_items) - i}"):
                st.text(detail)

        if i < len(display_items) - 1:
            st.markdown(
                '<div style="margin-left:18px;border-left:2px solid #e0e0e0;height:12px"></div>',
                unsafe_allow_html=True,
            )


def render_evidence_summary(evidence: list[dict]) -> None:
    """Render a compact summary bar of evidence counts by source."""
    if not evidence:
        return

    from collections import Counter
    sources = Counter(item.get("source", "unknown") for item in evidence)
    severities = Counter(item.get("severity", "info") for item in evidence)

    cols = st.columns(len(sources) + len(severities) + 1)
    idx = 0
    cols[idx].metric("总计", len(evidence))
    idx += 1
    for src, cnt in sources.most_common():
        cols[idx].metric(f"📎 {src}", cnt)
        idx += 1
    for sev, cnt in severities.most_common():
        cols[idx].metric(f"{_severity_icon(sev)} {sev}", cnt)
        idx += 1
