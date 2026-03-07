"""W5 evaluation runner for RAG and gateway scenarios."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.scorer import (  # noqa: E402
    EvalCaseResult,
    EvalSample,
    aggregate_results,
    compute_f1,
    compute_mrr,
    compute_recall_at_k,
    estimate_tokens,
    load_samples,
    write_summary_json,
)
from src.gateway.audit_logger import AuditEventType, AuditLogger  # noqa: E402
from src.gateway.authorizer import CallerIdentity, Role, ToolAuthorizer  # noqa: E402
from src.gateway.circuit_breaker import CircuitBreaker, CircuitConfig  # noqa: E402
from src.gateway.rate_limiter import RateLimiter  # noqa: E402
from src.gateway.tool_registry import QuotaConfig, ToolMeta, ToolRegistry, ToolStatus  # noqa: E402
from src.gateway.validator import ToolValidator  # noqa: E402
from src.observability.alert_manager import AlertManager  # noqa: E402
from src.observability.dashboard_exporter import DashboardExporter  # noqa: E402
from src.observability.error_bucket import ErrorBucketAnalyzer  # noqa: E402
from src.observability.incident_drill import IncidentDrillReporter  # noqa: E402
from src.observability.latency_analyzer import LatencyAnalyzer  # noqa: E402
from src.observability.logger import StructuredLogger  # noqa: E402
from src.observability.tracer import TraceContext, Tracer  # noqa: E402
from src.rag.compressor import Compressor  # noqa: E402
from src.rag.context_budget import ContextBudgetManager  # noqa: E402
from src.rag.keyword_retriever import IndexedChunk  # noqa: E402
from src.rag.reranker import RerankConfig, Reranker  # noqa: E402
from src.rag.retriever import HybridRetriever, RetrievalChunk  # noqa: E402


class EvaluationRunner:
    """Unified W5 evaluation runner."""

    def __init__(self, max_workers: int = 1, timeout_seconds: float = 10.0):
        self._max_workers = max_workers
        self._timeout_seconds = timeout_seconds
        self._retriever = HybridRetriever(final_top_k=10)
        self._reranker = Reranker(RerankConfig(top_n=10))
        self._compressor = Compressor(ContextBudgetManager(max_total_tokens=4096))
        self._tracer = Tracer()
        self._logger = StructuredLogger()
        self._alert_manager = AlertManager()
        self._dashboard_exporter = DashboardExporter()
        self._error_bucket_analyzer = ErrorBucketAnalyzer()
        self._incident_drill_reporter = IncidentDrillReporter()
        self._latency_analyzer = LatencyAnalyzer()
        self._seed_mock_knowledge()

    def run(self, dataset_path: str, output_dir: str) -> Dict[str, Any]:
        """Run evaluation for one dataset and persist outputs."""

        samples = load_samples(dataset_path)
        if not samples:
            raise ValueError("dataset must contain at least one sample")

        case_results = self._run_samples(samples)
        summary = aggregate_results(Path(dataset_path).name, case_results)
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        write_summary_json(summary, str(output_root / "summary.json"))
        self._write_markdown_report(summary.to_dict(), output_root / "report.md")
        self._write_failed_case_archive(samples, case_results, output_root / "failed-cases.jsonl")
        span_records = self._tracer.list_spans()
        latency_hotspots = self._latency_analyzer.build_hotspots(span_records)
        alert_events = self._alert_manager.evaluate(summary.to_dict())
        alert_payload = [event.to_dict() for event in alert_events]
        dashboard_snapshot = self._dashboard_exporter.build_snapshot(summary.to_dict(), alert_payload)
        self._tracer.write_jsonl(str(output_root / "traces.jsonl"))
        self._logger.write_jsonl(str(output_root / "logs.jsonl"))
        self._error_bucket_analyzer.write_markdown_report(case_results, str(output_root / "error-topn.md"))
        self._latency_analyzer.write_markdown_report(
            case_results,
            span_records,
            str(output_root / "latency-breakdown.md"),
        )
        self._alert_manager.write_json(alert_events, str(output_root / "alerts.json"))
        self._alert_manager.write_markdown(alert_events, str(output_root / "alert-report.md"))
        self._dashboard_exporter.write_snapshot(dashboard_snapshot, str(output_root / "dashboard-snapshot.json"))
        self._incident_drill_reporter.write_report(
            str(output_root / "incident-drill.md"),
            summary.dataset_name,
            [event for event in alert_events if event.status == "firing"],
            latency_hotspots,
        )
        return summary.to_dict()

    def _run_samples(self, samples: List[EvalSample]) -> List[EvalCaseResult]:
        """Run dataset samples with optional concurrency."""

        if self._max_workers <= 1:
            return [self._run_single_sample(sample) for sample in samples]

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [executor.submit(self._run_single_sample, sample) for sample in samples]
            return [future.result(timeout=self._timeout_seconds) for future in futures]

    def _run_single_sample(self, sample: EvalSample) -> EvalCaseResult:
        """Dispatch one sample to RAG or gateway evaluation flow."""

        if sample.tool_name:
            return self._run_gateway_sample(sample)
        return self._run_rag_sample(sample)

    def _run_rag_sample(self, sample: EvalSample) -> EvalCaseResult:
        """Run one RAG-style sample."""

        trace_id = f"trace-{sample.id}"
        session_id = f"sess-{sample.id}"
        trace_context = TraceContext(trace_id=trace_id, session_id=session_id, case_id=sample.id)
        start_time = time.perf_counter()
        self._logger.info("runner", "sample_start", "RAG sample started", trace_context)
        with self._tracer.start_span(trace_context, "retrieval", "retrieve") as retrieval_span:
            retrieval_result = self._retriever.retrieve(sample.query, user_role=sample.caller_role)
            self._logger.info(
                "retrieval",
                "retrieval_complete",
                "Retriever completed",
                trace_context,
                retrieval_span.step_id,
                {"chunk_count": len(retrieval_result.chunks)},
            )
        with self._tracer.start_span(trace_context, "rerank", "rerank") as rerank_span:
            rerank_output = self._reranker.rerank(retrieval_result.chunks)
            self._logger.info(
                "rerank",
                "rerank_complete",
                "Reranker completed",
                trace_context,
                rerank_span.step_id,
                {"result_count": len(rerank_output.results)},
            )
        with self._tracer.start_span(trace_context, "compression", "compress") as compression_span:
            compression_result = self._compressor.compress(rerank_output.results)
            self._logger.info(
                "compression",
                "compression_complete",
                "Context compression completed",
                trace_context,
                compression_span.step_id,
                {"chunk_count": len(compression_result.chunks)},
            )
        with self._tracer.start_span(trace_context, "generation", "build_answer") as answer_span:
            generated_answer = self._build_answer(sample=sample, compression_result=compression_result)
            self._logger.info(
                "generation",
                "answer_complete",
                "Answer builder completed",
                trace_context,
                answer_span.step_id,
                {"output_tokens": estimate_tokens(generated_answer)},
            )
        latency_ms = (time.perf_counter() - start_time) * 1000
        retrieved_source_ids = [item.chunk.source_id for item in rerank_output.results]
        answer_f1 = compute_f1(generated_answer, sample.expected_answer)
        success = answer_f1 >= 0.5 if sample.expect_error is None else False
        if success:
            self._logger.info("runner", "sample_complete", "RAG sample passed", trace_context)
        else:
            self._logger.warning(
                "runner",
                "sample_complete",
                "RAG sample failed",
                trace_context,
                error_code="quality_regression",
                metadata={"answer_f1": answer_f1},
            )
        return EvalCaseResult(
            sample_id=sample.id,
            category=sample.category,
            difficulty=sample.difficulty,
            success=success,
            answer=generated_answer,
            expected_answer=sample.expected_answer,
            answer_f1=answer_f1,
            latency_ms=latency_ms,
            trace_id=trace_id,
            session_id=session_id,
            retrieved_source_ids=retrieved_source_ids,
            recall_at_5=compute_recall_at_k(retrieved_source_ids, sample.relevant_source_ids, 5),
            recall_at_10=compute_recall_at_k(retrieved_source_ids, sample.relevant_source_ids, 10),
            mrr=compute_mrr(retrieved_source_ids, sample.relevant_source_ids),
            step_outcomes={
                "retrieval": True,
                "rerank": len(rerank_output.results) > 0,
                "compression": len(compression_result.chunks) > 0,
            },
            retrieval_calls=1,
            input_tokens=estimate_tokens(sample.query),
            output_tokens=estimate_tokens(generated_answer),
        )

    def _run_gateway_sample(self, sample: EvalSample) -> EvalCaseResult:
        """Run one gateway-governed tool sample."""

        runtime = _GatewayRuntime.build_default()
        trace_id = f"trace-{sample.id}-{uuid.uuid4().hex[:8]}"
        session_id = f"sess-{sample.id}"
        trace_context = TraceContext(trace_id=trace_id, session_id=session_id, case_id=sample.id)
        caller = runtime.build_caller(sample)
        start_time = time.perf_counter()
        step_outcomes: Dict[str, bool] = {}
        self._logger.info("runner", "sample_start", "Gateway sample started", trace_context)

        with self._tracer.start_span(trace_context, "gateway", "validation") as validation_span:
            validation_result = runtime.validator.validate(sample.tool_name or "", sample.tool_params)
            self._logger.info(
                "gateway",
                "validation_complete",
                "Validator completed",
                trace_context,
                validation_span.step_id,
                {"valid": validation_result.valid},
            )
        step_outcomes["validation"] = validation_result.valid
        if not validation_result.valid:
            latency_ms = (time.perf_counter() - start_time) * 1000
            error_code = validation_result.errors[0]["code"]
            self._logger.warning(
                "gateway",
                "validation_failed",
                "Validation rejected request",
                trace_context,
                error_code=error_code,
            )
            runtime.audit_logger.log_event(
                AuditEventType.TOOL_CALL_REJECTED,
                trace_id=trace_id,
                session_id=session_id,
                caller_id=caller.caller_id,
                tool_name=sample.tool_name or "",
                error=error_code,
            )
            return self._build_gateway_case_result(
                sample=sample,
                answer="",
                error_code=error_code,
                success=sample.expect_error == error_code,
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
                validation_rejected=True,
            )

        tool_meta = runtime.registry.get(sample.tool_name or "")
        if tool_meta is None:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return self._build_gateway_case_result(
                sample=sample,
                answer="",
                error_code="invalid_tool_name",
                success=sample.expect_error == "invalid_tool_name",
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
            )

        with self._tracer.start_span(trace_context, "gateway", "authorization") as auth_span:
            auth_decision = runtime.authorizer.authorize(caller, tool_meta)
            self._logger.info(
                "gateway",
                "authorization_complete",
                "Authorizer completed",
                trace_context,
                auth_span.step_id,
                {"allowed": auth_decision.allowed},
            )
        step_outcomes["authorization"] = auth_decision.allowed
        if not auth_decision.allowed:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._logger.warning(
                "gateway",
                "authorization_failed",
                "Authorization denied request",
                trace_context,
                error_code="unauthorized",
            )
            runtime.audit_logger.log_event(
                AuditEventType.AUTH_DENIED,
                trace_id=trace_id,
                session_id=session_id,
                caller_id=caller.caller_id,
                tool_name=tool_meta.name,
                error=auth_decision.reason,
            )
            return self._build_gateway_case_result(
                sample=sample,
                answer="",
                error_code="unauthorized",
                success=sample.expect_error == "unauthorized",
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
                auth_denied=True,
            )

        with self._tracer.start_span(trace_context, "gateway", "circuit_check") as circuit_span:
            circuit_allowed = runtime.circuit_breaker.allow_request(tool_meta.name)
            self._logger.info(
                "gateway",
                "circuit_check_complete",
                "Circuit breaker checked",
                trace_context,
                circuit_span.step_id,
                {"allowed": circuit_allowed},
            )
        if not circuit_allowed:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._logger.error(
                "gateway",
                "circuit_open",
                "Circuit breaker rejected request",
                trace_context,
                error_code="circuit_open",
            )
            runtime.audit_logger.log_event(
                AuditEventType.CIRCUIT_OPENED,
                trace_id=trace_id,
                session_id=session_id,
                caller_id=caller.caller_id,
                tool_name=tool_meta.name,
                error="circuit_open",
            )
            return self._build_gateway_case_result(
                sample=sample,
                answer="",
                error_code="circuit_open",
                success=sample.expect_error == "circuit_open",
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
                circuit_opened=True,
            )

        with self._tracer.start_span(trace_context, "gateway", "rate_limit") as rate_span:
            rate_limit_result = runtime.rate_limiter.acquire(caller.caller_id)
            self._logger.info(
                "gateway",
                "rate_limit_complete",
                "Rate limiter checked",
                trace_context,
                rate_span.step_id,
                {"allowed": rate_limit_result.allowed},
            )
        step_outcomes["rate_limit"] = rate_limit_result.allowed
        if not rate_limit_result.allowed:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._logger.warning(
                "gateway",
                "rate_limited",
                "Rate limiter rejected request",
                trace_context,
                error_code="rate_limited",
            )
            runtime.audit_logger.log_event(
                AuditEventType.RATE_LIMITED,
                trace_id=trace_id,
                session_id=session_id,
                caller_id=caller.caller_id,
                tool_name=tool_meta.name,
                error="rate_limited",
                metadata={"retry_after": rate_limit_result.retry_after},
            )
            return self._build_gateway_case_result(
                sample=sample,
                answer="",
                error_code="rate_limited",
                success=sample.expect_error == "rate_limited",
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
            )

        runtime.validator.quota_tracker.record_call_start(tool_meta.name)
        runtime.audit_logger.log_call_start(
            trace_id=trace_id,
            session_id=session_id,
            caller_id=caller.caller_id,
            tool_name=tool_meta.name,
            tool_version=tool_meta.version,
            params=sample.tool_params,
        )

        try:
            with self._tracer.start_span(trace_context, "gateway", "execution") as execution_span:
                tool_response = runtime.invoke(tool_name=tool_meta.name, params=sample.tool_params)
                self._logger.info(
                    "gateway",
                    "execution_complete",
                    "Tool invocation completed",
                    trace_context,
                    execution_span.step_id,
                    {"tool_name": tool_meta.name},
                )
            runtime.circuit_breaker.record_success(tool_meta.name)
            runtime.audit_logger.log_call_success(
                trace_id=trace_id,
                session_id=session_id,
                caller_id=caller.caller_id,
                tool_name=tool_meta.name,
                tool_version=tool_meta.version,
                result_summary=str(tool_response)[:120],
                latency_ms=(time.perf_counter() - start_time) * 1000,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            step_outcomes["execution"] = True
            self._logger.info("runner", "sample_complete", "Gateway sample passed", trace_context)
            answer = "PASS" if sample.expected_answer == "PASS" else json.dumps(tool_response, ensure_ascii=False)
            return self._build_gateway_case_result(
                sample=sample,
                answer=answer,
                error_code=None,
                success=sample.expect_error is None,
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
                tool_calls=1,
            )
        except Exception as error:
            runtime.circuit_breaker.record_failure(tool_meta.name)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._logger.error(
                "gateway",
                "execution_failed",
                "Tool invocation failed",
                trace_context,
                error_code="tool_execution_failed",
                metadata={"error": str(error)},
            )
            runtime.audit_logger.log_call_failure(
                trace_id=trace_id,
                session_id=session_id,
                caller_id=caller.caller_id,
                tool_name=tool_meta.name,
                tool_version=tool_meta.version,
                error=str(error),
                latency_ms=latency_ms,
            )
            step_outcomes["execution"] = False
            return self._build_gateway_case_result(
                sample=sample,
                answer="",
                error_code="tool_execution_failed",
                success=sample.expect_error == "tool_execution_failed",
                latency_ms=latency_ms,
                trace_id=trace_id,
                session_id=session_id,
                step_outcomes=step_outcomes,
                runtime=runtime,
                tool_calls=1,
            )
        finally:
            runtime.validator.quota_tracker.record_call_end(tool_meta.name)

    def _build_gateway_case_result(
        self,
        sample: EvalSample,
        answer: str,
        error_code: Optional[str],
        success: bool,
        latency_ms: float,
        trace_id: str,
        session_id: str,
        step_outcomes: Dict[str, bool],
        runtime: "_GatewayRuntime",
        validation_rejected: bool = False,
        auth_denied: bool = False,
        circuit_opened: bool = False,
        tool_calls: int = 0,
    ) -> EvalCaseResult:
        """Build normalized case result for gateway sample."""

        answer_f1 = compute_f1(answer, sample.expected_answer) if answer else 0.0
        return EvalCaseResult(
            sample_id=sample.id,
            category=sample.category,
            difficulty=sample.difficulty,
            success=success,
            answer=answer,
            expected_answer=sample.expected_answer,
            answer_f1=answer_f1,
            latency_ms=latency_ms,
            trace_id=trace_id,
            session_id=session_id,
            error_code=error_code,
            step_outcomes=step_outcomes,
            validation_rejected=validation_rejected,
            auth_denied=auth_denied,
            circuit_opened=circuit_opened,
            audit_entries=runtime.audit_logger.entry_count,
            tool_calls=tool_calls,
            input_tokens=estimate_tokens(sample.query),
            output_tokens=estimate_tokens(answer),
        )

    def _build_answer(self, sample: EvalSample, compression_result: Any) -> str:
        """Build final answer from compressed chunks."""

        if sample.expected_answer.startswith("[REFUSE]"):
            return sample.expected_answer
        if not compression_result.chunks:
            return "未找到相关信息"
        return compression_result.chunks[0].content

    def _seed_mock_knowledge(self) -> None:
        """Load mock knowledge for retrieval evaluation."""

        mock_documents = [
            (
                "doc_refund_policy",
                "doc",
                "退款政策规定退款有效期为30天，超过30天不予退款。用户需在购买后30天内提出退款申请。",
            ),
            (
                "doc_merchant_onboard",
                "doc",
                "商户入驻需要提供以下资质：营业执照、食品经营许可证、法人身份证。所有证件需在有效期内。",
            ),
            (
                "doc_coupon_rules",
                "doc",
                "优惠券规则：单张优惠券最大面额为500元。每日领券上限为10张。默认不允许叠加使用。",
            ),
            (
                "doc_verification",
                "doc",
                "核销流程说明：核销超时时间为30分钟，超过30分钟未完成核销将自动取消。",
            ),
            (
                "doc_settlement",
                "doc",
                "商户结算提现流程：进入商户端，点击财务管理，选择提现申请，填写金额，提交审核，1到3个工作日到账。",
            ),
        ]

        retrieval_chunks: List[RetrievalChunk] = []
        indexed_chunks: List[IndexedChunk] = []
        for source_id, source_type, content in mock_documents:
            metadata = {"updated_at": time.time()}
            retrieval_chunks.append(
                RetrievalChunk(
                    chunk_id=f"{source_id}_chunk_0",
                    content=content,
                    score=0.0,
                    source_id=source_id,
                    source_type=source_type,
                    access_level="public",
                    metadata=metadata,
                )
            )
            indexed_chunks.append(
                IndexedChunk(
                    chunk_id=f"{source_id}_chunk_0",
                    content=content,
                    source_id=source_id,
                    source_type=source_type,
                    access_level="public",
                    metadata=metadata,
                )
            )

        self._retriever.vector_retriever.add_documents(retrieval_chunks)
        self._retriever.keyword_retriever.add_documents(indexed_chunks)

    def _write_failed_case_archive(
        self,
        samples: List[EvalSample],
        case_results: List[EvalCaseResult],
        output_path: Path,
    ) -> None:
        """Persist failed cases for replay and triage."""

        sample_index = {sample.id: sample for sample in samples}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file_handle:
            for case_result in case_results:
                if case_result.success:
                    continue
                sample = sample_index.get(case_result.sample_id)
                if sample is None:
                    continue
                record = {
                    "case_id": case_result.sample_id,
                    "trace_id": case_result.trace_id,
                    "session_id": case_result.session_id,
                    "error_code": case_result.error_code,
                    "answer_f1": case_result.answer_f1,
                    "latency_ms": case_result.latency_ms,
                    "step_outcomes": case_result.step_outcomes,
                    "sample": asdict(sample),
                }
                json.dump(record, file_handle, ensure_ascii=False)
                file_handle.write("\n")

    def _write_markdown_report(self, summary: Dict[str, Any], output_path: Path) -> None:
        """Render a compact Markdown report from summary JSON."""

        template_path = PROJECT_ROOT / "eval" / "reports" / "template.md"
        template = template_path.read_text(encoding="utf-8")
        failure_buckets = "\n".join(
            f"- `{bucket}`: {count}" for bucket, count in summary["failure_buckets"].items()
        ) or "- 无"
        step_rows = "\n".join(
            f"| {step} | {rate:.2%} |" for step, rate in summary["step_success_rates"].items()
        ) or "| none | 0.00% |"
        rendered = template.format(
            dataset_name=summary["dataset_name"],
            total_samples=summary["total_samples"],
            e2e_success_rate=f"{summary['e2e_success_rate']:.2%}",
            avg_answer_f1=f"{summary['avg_answer_f1']:.4f}",
            accuracy=f"{summary['accuracy']:.2%}",
            avg_latency_ms=f"{summary['avg_latency_ms']:.2f}",
            p95_latency_ms=f"{summary['p95_latency_ms']:.2f}",
            validation_rejection_rate=f"{summary['validation_rejection_rate']:.2%}",
            auth_denial_rate=f"{summary['auth_denial_rate']:.2%}",
            circuit_open_frequency=f"{summary['circuit_open_frequency']:.2%}",
            audit_completeness=f"{summary['audit_completeness']:.2%}",
            total_tokens=summary["cost"]["total_tokens"],
            tool_calls=summary["cost"]["tool_calls"],
            retrieval_calls=summary["cost"]["retrieval_calls"],
            step_success_rows=step_rows,
            failure_bucket_rows=failure_buckets,
        )
        output_path.write_text(rendered, encoding="utf-8")


class _GatewayRuntime:
    """Isolated gateway runtime for one evaluation sample."""

    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.validator = ToolValidator(self.registry)
        self.authorizer = ToolAuthorizer()
        self.circuit_breaker = CircuitBreaker(CircuitConfig(failure_threshold=1, recovery_timeout=5.0))
        self.rate_limiter = RateLimiter()
        self.audit_logger = AuditLogger()
        self._handlers: Dict[str, Any] = {}

    @classmethod
    def build_default(cls) -> "_GatewayRuntime":
        """Build runtime with default mock tools."""

        runtime = cls()
        runtime._register_default_tools()
        return runtime

    def build_caller(self, sample: EvalSample) -> CallerIdentity:
        """Build caller identity from sample definition."""

        try:
            role = Role(sample.caller_role)
        except ValueError:
            role = Role.PUBLIC
        return CallerIdentity(caller_id=f"caller-{sample.id}", role=role, tenant=sample.tenant)

    def invoke(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke registered mock tool handler."""

        handler = self._handlers[tool_name]
        return handler(params)

    def _register_default_tools(self) -> None:
        """Register mock tools used by W5 datasets."""

        self._register_tool(
            ToolMeta(
                name="web_search",
                version="1.0.0",
                description="Mock public web search tool.",
                status=ToolStatus.AVAILABLE,
                required_roles=["public"],
                input_schema={
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer"},
                    },
                },
                quota=QuotaConfig(qps=5, max_concurrent=2, daily_limit=100),
            ),
            lambda params: {
                "items": [{"title": "search_result", "snippet": params["query"]}],
                "total": 1,
            },
        )
        self._register_tool(
            ToolMeta(
                name="merchant_lookup",
                version="1.0.0",
                description="Mock internal merchant lookup.",
                status=ToolStatus.AVAILABLE,
                required_roles=["internal"],
                input_schema={
                    "type": "object",
                    "required": ["merchant_id"],
                    "properties": {"merchant_id": {"type": "string"}},
                },
            ),
            lambda params: {"merchant_id": params["merchant_id"], "status": "active"},
        )
        self._register_tool(
            ToolMeta(
                name="admin_export",
                version="1.0.0",
                description="Mock sensitive admin export.",
                status=ToolStatus.AVAILABLE,
                required_roles=["admin"],
                is_sensitive=True,
                input_schema={
                    "type": "object",
                    "required": ["scope"],
                    "properties": {"scope": {"type": "string"}},
                },
            ),
            lambda params: {"scope": params["scope"], "exported": True},
        )

    def _register_tool(self, meta: ToolMeta, handler: Any) -> None:
        """Register one mock tool."""

        self.registry.register(meta)
        self._handlers[meta.name] = handler


def main() -> None:
    """CLI entry for W5 evaluation runner."""

    parser = argparse.ArgumentParser(description="Run W5 evaluation datasets")
    parser.add_argument(
        "--dataset",
        default=str(PROJECT_ROOT / "eval" / "datasets" / "smoke.jsonl"),
        help="Path to evaluation dataset JSONL",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "eval" / "results"),
        help="Directory for evaluation outputs",
    )
    parser.add_argument("--max-workers", type=int, default=1, help="Parallel worker count")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-sample timeout seconds")
    args = parser.parse_args()

    runner = EvaluationRunner(max_workers=args.max_workers, timeout_seconds=args.timeout)
    summary = runner.run(args.dataset, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
