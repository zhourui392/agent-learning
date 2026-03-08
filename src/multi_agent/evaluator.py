"""W7 evaluator for single-agent vs multi-agent demo flows."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from src.multi_agent.demo_flow import run_conflict_flow, run_single_agent_flow, run_standard_flow
from src.observability.logger import StructuredLogger
from src.observability.tracer import TraceContext, Tracer


class MultiAgentEvaluator:
    """Evaluate W7 demo flows and persist comparison artifacts."""

    def __init__(self) -> None:
        self._tracer = Tracer()
        self._logger = StructuredLogger()

    def run(self, output_dir: str) -> Dict[str, Any]:
        """Run single-agent and multi-agent demos, then persist outputs."""

        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

        single_agent_result = self._run_with_trace("single-agent", run_single_agent_flow)
        multi_agent_result = self._run_with_trace("multi-agent-standard", run_standard_flow)
        conflict_result = self._run_with_trace("multi-agent-conflict", run_conflict_flow)

        summary = self._build_summary(single_agent_result, multi_agent_result, conflict_result)
        self._write_json(summary, output_root / "summary.json")
        self._write_markdown(summary, output_root / "report.md")
        self._tracer.write_jsonl(str(output_root / "traces.jsonl"))
        self._logger.write_jsonl(str(output_root / "logs.jsonl"))
        return summary

    def _run_with_trace(self, case_id: str, callback: Any) -> Dict[str, Any]:
        trace_context = TraceContext(
            trace_id=f"trace-{case_id}",
            session_id=f"sess-{case_id}",
            case_id=case_id,
        )
        start_time = time.perf_counter()
        self._logger.info("multi_agent", "flow_start", "Demo flow started", trace_context)
        with self._tracer.start_span(trace_context, "multi_agent", "demo_flow") as span_scope:
            result = callback()
            self._logger.info(
                "multi_agent",
                "flow_complete",
                "Demo flow completed",
                trace_context,
                span_scope.step_id,
                {"status": result.get("status")},
            )
        result["latency_ms"] = (time.perf_counter() - start_time) * 1000
        result["trace_id"] = trace_context.trace_id
        result["session_id"] = trace_context.session_id
        return result

    def _build_summary(
        self,
        single_agent_result: Dict[str, Any],
        multi_agent_result: Dict[str, Any],
        conflict_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "single_agent": single_agent_result,
            "multi_agent_standard": multi_agent_result,
            "multi_agent_conflict": conflict_result,
            "comparison": {
                "single_agent_role_count": single_agent_result["metrics"]["role_count"],
                "multi_agent_role_count": multi_agent_result["metrics"]["role_count"],
                "multi_agent_callback_count": multi_agent_result["metrics"]["callback_count"],
                "conflict_requires_human": conflict_result["metrics"]["requires_human"],
            },
        }

    def _write_json(self, summary: Dict[str, Any], output_path: Path) -> None:
        with output_path.open("w", encoding="utf-8") as file_handle:
            json.dump(summary, file_handle, ensure_ascii=False, indent=2)
            file_handle.write("\n")

    def _write_markdown(self, summary: Dict[str, Any], output_path: Path) -> None:
        lines = [
            "# W7 Single vs Multi Agent",
            "",
            f"- Single Agent Roles: {summary['comparison']['single_agent_role_count']}",
            f"- Multi Agent Roles: {summary['comparison']['multi_agent_role_count']}",
            f"- Multi Agent Callbacks: {summary['comparison']['multi_agent_callback_count']}",
            f"- Conflict Requires Human: {summary['comparison']['conflict_requires_human']}",
            "",
            "## Single Agent",
            "",
            f"- Status: `{summary['single_agent']['status']}`",
            f"- Result: `{summary['single_agent']['result']}`",
            "",
            "## Multi Agent Standard",
            "",
            f"- Status: `{summary['multi_agent_standard']['status']}`",
            f"- Memory Version: `{summary['multi_agent_standard']['metrics']['memory_version']}`",
            "",
            "## Multi Agent Conflict",
            "",
            f"- Status: `{summary['multi_agent_conflict']['status']}`",
            f"- Selected Role: `{summary['multi_agent_conflict']['selected_role']}`",
        ]
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
