"""Runnable W7 demo flows for single-agent vs multi-agent comparison."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from src.multi_agent.arbitrator import ArbitrationCandidate, Arbitrator
from src.multi_agent.callback_handler import CallbackHandler, CallbackRecord
from src.multi_agent.dispatcher import TaskAssignment, TaskDispatcher
from src.multi_agent.protocol_validator import ProtocolValidator
from src.multi_agent.shared_memory import SharedMemoryStore


def run_standard_flow() -> Dict[str, Any]:
    """Run a nominal planner->executor->auditor demo flow."""

    dispatcher = TaskDispatcher()
    callbacks = CallbackHandler()
    memory = SharedMemoryStore()
    validator = ProtocolValidator()
    request_message = {
        "version": "1.0.0",
        "header": {
            "message_id": "msg-standard-1",
            "message_type": "task_request",
            "sender_role": "planner",
            "receiver_role": "executor",
            "task_id": "task-standard-1",
        },
        "payload": {"instruction": "collect merchant refund evidence"},
        "meta": {
            "trace_id": "trace-standard-1",
            "session_id": "sess-standard-1",
            "status": "pending",
            "priority": 2,
            "conflict_fields": [],
        },
    }
    validation_result = validator.validate_message(request_message)
    if not validation_result.valid:
        return {"status": "invalid_protocol", "errors": validation_result.errors}

    dispatcher.enqueue(TaskAssignment(task_id="task-standard-1", role="executor", payload=request_message))
    assignment = dispatcher.dispatch_next("executor")
    callbacks.record(CallbackRecord(task_id=assignment.task_id, role="executor", succeeded=True, payload={"result": "evidence_found"}))
    dispatcher.complete(assignment.task_id, succeeded=True)
    memory.write("merchant:m-100", {"refund_status": "eligible"}, writer_role="executor")
    callbacks.record(CallbackRecord(task_id=assignment.task_id, role="auditor", succeeded=True, payload={"review": "approved"}))
    return {
        "status": "completed",
        "task": callbacks.aggregate_task("task-standard-1"),
        "memory": memory.read("merchant:m-100").value,
        "metrics": {
            "role_count": 3,
            "callback_count": 2,
            "memory_version": memory.read("merchant:m-100").version,
        },
    }


def run_conflict_flow() -> Dict[str, Any]:
    """Run a conflict flow that triggers arbitration."""

    arbitrator = Arbitrator()
    candidates: List[ArbitrationCandidate] = [
        ArbitrationCandidate(
            role="executor",
            result="approve_refund",
            confidence=0.82,
            priority=2,
            evidence=["refund within 30 days"],
        ),
        ArbitrationCandidate(
            role="auditor",
            result="reject_refund",
            confidence=0.78,
            priority=2,
            evidence=["missing receipt attachment"],
        ),
    ]
    decision = arbitrator.resolve(candidates)
    return {
        "status": decision.status,
        "selected_role": decision.selected_role,
        "result": decision.result,
        "evidence_chain": decision.evidence_chain,
        "metrics": {
            "candidate_count": len(candidates),
            "requires_human": decision.status == "needs_human",
        },
    }


def run_single_agent_flow() -> Dict[str, Any]:
    """Run a simplified single-agent baseline for W7 comparison."""

    start_time = time.perf_counter()
    result = {
        "status": "completed",
        "result": "approve_refund",
        "evidence": ["refund within 30 days", "receipt attached"],
    }
    latency_ms = (time.perf_counter() - start_time) * 1000
    return {
        "status": result["status"],
        "result": result["result"],
        "evidence": result["evidence"],
        "metrics": {
            "role_count": 1,
            "callback_count": 0,
            "latency_ms": latency_ms,
        },
    }
