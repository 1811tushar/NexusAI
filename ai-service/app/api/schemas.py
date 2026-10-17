"""ALL contract (v2.1) Pydantic models for the Python side (AI-FD-01..). Mirrors file 06 sections 1-6.
JSON is camelCase on the wire; Python attributes are snake_case. If a field changes, change contract 06 FIRST."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, use_enum_values=False, extra="forbid")

    def wire(self) -> dict[str, Any]:
        """JSON-ready camelCase dict (what goes on the wire)."""
        return self.model_dump(mode="json", by_alias=True)


# ----------------------------------------------------------------------------- enums
class StrEnum_(str, Enum):  # noqa: N801  (JSON-friendly str enum)
    def __str__(self) -> str:
        return self.value


class Role(StrEnum_):
    ADMIN = "ADMIN"; ANALYST = "ANALYST"; APPROVER = "APPROVER"  # noqa: E702


class SourceType(StrEnum_):
    PDF = "PDF"; DOCX = "DOCX"; TXT = "TXT"; MD = "MD"  # noqa: E702


class DocumentStatus(StrEnum_):
    UPLOADED = "UPLOADED"; INGESTING = "INGESTING"; READY = "READY"; FAILED = "FAILED"; DELETING = "DELETING"  # noqa: E702


class InvestigationStatus(StrEnum_):
    RUNNING = "RUNNING"; AWAITING_APPROVAL = "AWAITING_APPROVAL"; COMPLETED = "COMPLETED"  # noqa: E702
    FAILED = "FAILED"; CANCELLED = "CANCELLED"; REFUSED = "REFUSED"  # noqa: E702


class ClaimStatus(StrEnum_):
    VERIFIED = "VERIFIED"; UNSUPPORTED = "UNSUPPORTED"; CONTRADICTED = "CONTRADICTED"  # noqa: E702


class EvidenceKind(StrEnum_):
    DOCUMENT = "DOCUMENT"; SQL = "SQL"; STATS = "STATS"; WEB = "WEB"; MEMORY = "MEMORY"  # noqa: E702


class Risk(StrEnum_):
    LOW = "LOW"; HIGH = "HIGH"  # noqa: E702


class ApprovalStatus(StrEnum_):
    PENDING = "PENDING"; APPROVED = "APPROVED"; REJECTED = "REJECTED"; EXPIRED = "EXPIRED"  # noqa: E702


class ActionType(StrEnum_):
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"; CREATE_FOLLOWUP_TASK = "CREATE_FOLLOWUP_TASK"; SAVE_INSIGHT = "SAVE_INSIGHT"  # noqa: E702
    ADJUST_PRICE = "ADJUST_PRICE"; PAUSE_CAMPAIGN = "PAUSE_CAMPAIGN"; REALLOCATE_BUDGET = "REALLOCATE_BUDGET"  # noqa: E702


class ActionStatus(StrEnum_):
    EXECUTED = "EXECUTED"; REJECTED = "REJECTED"; EXPIRED = "EXPIRED"; FAILED = "FAILED"  # noqa: E702


class AgentName(StrEnum_):
    SUPERVISOR = "SUPERVISOR"; PLANNER = "PLANNER"; RESEARCHER = "RESEARCHER"; DATA_ANALYST = "DATA_ANALYST"  # noqa: E702
    ANALYST = "ANALYST"; VERIFIER = "VERIFIER"; REPORTER = "REPORTER"  # noqa: E702


class ToolName(StrEnum_):
    rag_search = "rag_search"; sql_query = "sql_query"; web_search = "web_search"  # noqa: E702
    stats_compare = "stats_compare"; stats_contribution = "stats_contribution"; stats_anomaly = "stats_anomaly"  # noqa: E702
    recall_memory = "recall_memory"  # noqa: E702


class SearchMode(StrEnum_):
    HYBRID = "HYBRID"; VECTOR = "VECTOR"; KEYWORD = "KEYWORD"  # noqa: E702


class ErrorCode(StrEnum_):
    VALIDATION_FAILED = "VALIDATION_FAILED"; INVALID_CREDENTIALS = "INVALID_CREDENTIALS"; TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: E702
    UNAUTHENTICATED = "UNAUTHENTICATED"; FORBIDDEN = "FORBIDDEN"; SELF_APPROVAL_NOT_ALLOWED = "SELF_APPROVAL_NOT_ALLOWED"  # noqa: E702
    NOT_FOUND = "NOT_FOUND"; DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"; INVALID_STATE = "INVALID_STATE"  # noqa: E702
    FILE_TOO_LARGE = "FILE_TOO_LARGE"; UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"; QUOTA_EXCEEDED = "QUOTA_EXCEEDED"  # noqa: E702
    INGESTION_FAILED = "INGESTION_FAILED"; RATE_LIMITED = "RATE_LIMITED"; AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"  # noqa: E702
    LLM_RATE_LIMITED = "LLM_RATE_LIMITED"; INTERNAL_ERROR = "INTERNAL_ERROR"  # noqa: E702


class GuardrailStage(StrEnum_):
    INPUT = "INPUT"; TOOL = "TOOL"; OUTPUT = "OUTPUT"  # noqa: E702


class GuardrailAction(StrEnum_):
    BLOCKED = "BLOCKED"; REDACTED = "REDACTED"; FLAGGED = "FLAGGED"  # noqa: E702


class GuardrailCategory(StrEnum_):
    PROMPT_INJECTION = "PROMPT_INJECTION"; OFF_TOPIC = "OFF_TOPIC"; UNSAFE_REQUEST = "UNSAFE_REQUEST"  # noqa: E702
    PII = "PII"; INVALID_CITATION = "INVALID_CITATION"; INVALID_OUTPUT = "INVALID_OUTPUT"  # noqa: E702


class PlanStepStatus(StrEnum_):
    PENDING = "PENDING"; RUNNING = "RUNNING"; DONE = "DONE"; FAILED = "FAILED"  # noqa: E702


class Decision(StrEnum_):
    APPROVE = "APPROVE"; REJECT = "REJECT"  # noqa: E702


class ConfidenceDecision(StrEnum_):
    ACCEPT = "ACCEPT"; LOOP = "LOOP"; ACCEPT_LOW_CONFIDENCE = "ACCEPT_LOW_CONFIDENCE"  # noqa: E702


class EvalSystem(StrEnum_):
    BASELINE = "BASELINE"; SINGLE_AGENT = "SINGLE_AGENT"; AGENT_NO_VERIFIER = "AGENT_NO_VERIFIER"; AGENT = "AGENT"  # noqa: E702


class EvalCategory(StrEnum_):
    NORMAL = "NORMAL"; EDGE = "EDGE"; ADVERSARIAL = "ADVERSARIAL"; MISSING_DATA = "MISSING_DATA"; TOOL_FAILURE = "TOOL_FAILURE"  # noqa: E702


AgentEventType = Literal[
    "run_started", "memory_recalled", "supervisor_routed", "plan", "step_status", "agent_started", "tool_call",
    "tool_result", "evidence_added", "claims_drafted", "claim_verified", "confidence", "loop", "action_proposed",
    "approval_required", "approval_decided", "action_executed", "guardrail_triggered", "report_delta", "report_ready",
    "memory_saved", "error", "done",
]


# ----------------------------------------------------------------------------- envelopes (public API; kept for parity)
class ApiError(CamelModel):
    code: ErrorCode
    message: str
    details: dict[str, str] | None = None
    request_id: str | None = None


class ApiResponse(CamelModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None


class PagedResponse(CamelModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total_items: int
    total_pages: int


class InternalError(CamelModel):
    """Body of every non-2xx response from the INTERNAL API (Spring maps it, see contract 6)."""
    code: ErrorCode
    message: str
    retryable: bool = False
    request_id: str | None = None
    details: dict[str, str] | None = None


# ----------------------------------------------------------------------------- ingestion / search (contract 6)
class HealthResponse(CamelModel):
    status: Literal["ok", "degraded"]
    embedding_model: str
    llm_provider: str


class IngestRequest(CamelModel):
    document_id: int
    uploaded_by_user_id: int
    source_type: SourceType
    title: str = Field(min_length=1, max_length=255)
    filename: str = Field(min_length=1, max_length=255)


class IngestResponse(CamelModel):
    document_id: int
    page_count: int | None
    chunk_count: int
    warnings: list[str] = []


class ChunkDTO(CamelModel):
    id: int
    chunk_index: int
    page: int | None
    section: str | None
    content: str


class SearchRequest(CamelModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: SearchMode = SearchMode.HYBRID
    k: int = Field(8, ge=1, le=50)
    document_ids: list[int] | None = Field(default=None, max_length=500)


class SearchResultDTO(CamelModel):
    chunk_id: int
    document_id: int
    document_title: str
    page: int | None
    section: str | None
    snippet: str
    score: float


class DeleteDocumentResponse(CamelModel):
    deleted: int


# ----------------------------------------------------------------------------- investigation (contract 4.3 / 6)
class InvestigateOptions(CamelModel):
    web_search: bool = True
    document_ids: list[int] | None = None
    use_memory: bool = True
    max_loops: int = Field(3, ge=1, le=5)


class InvestigateRequest(CamelModel):
    investigation_id: int
    thread_id: str
    user_id: int
    question: str = Field(min_length=10, max_length=2000)
    options: InvestigateOptions
    now: str


class ResumeDecision(CamelModel):
    action_key: str
    approval_id: int
    decision: Decision
    decided_by: str
    comment: str | None = None


class ResumeRequest(CamelModel):
    investigation_id: int
    decisions: list[ResumeDecision]


class PlanStep(CamelModel):
    id: str
    description: str
    agent: AgentName
    status: PlanStepStatus = PlanStepStatus.PENDING


class EvidenceSource(CamelModel):
    document_id: int | None = None
    page: int | None = None
    url: str | None = None
    sql: str | None = None
    table: str | None = None
    investigation_id: int | None = None


class EvidenceData(CamelModel):
    columns: list[str]
    rows: list[list[str | int | float | None]] = Field(max_length=50)
    truncated: bool = False


class ChartSeries(CamelModel):
    name: str
    values: list[float]


class EvidenceChart(CamelModel):
    type: Literal["line", "bar"]
    x: list[str]
    series: list[ChartSeries]


class EvidenceDTO(CamelModel):
    evidence_key: str
    kind: EvidenceKind
    title: str
    snippet: str
    source: EvidenceSource
    data: EvidenceData | None = None
    chart: EvidenceChart | None = None
    score: float | None = None
    created_at: str


class RecommendationDTO(CamelModel):
    id: str
    text: str
    risk: Risk
    action_key: str | None = None


class UsageTokens(CamelModel):
    input_tokens: int
    output_tokens: int


# ----------------------------------------------------------------------------- event payloads (contract 5)
class RunStarted(CamelModel):
    investigation_id: int; thread_id: str; started_at: str  # noqa: E702


class MemoryItem(CamelModel):
    id: int; summary: str; score: float  # noqa: E702


class MemoryRecalled(CamelModel):
    items: list[MemoryItem]


class SupervisorRouted(CamelModel):
    agents: list[AgentName]; reason: str  # noqa: E702


class PlanEvent(CamelModel):
    steps: list[PlanStep]


class StepStatusEvent(CamelModel):
    step_id: str; status: Literal["RUNNING", "DONE", "FAILED"]  # noqa: E702


class AgentStarted(CamelModel):
    agent: AgentName; step_id: str | None = None  # noqa: E702


class ToolCall(CamelModel):
    call_id: str; agent: AgentName; tool: ToolName; args: dict[str, Any]  # noqa: E702


class ToolResult(CamelModel):
    call_id: str; tool: ToolName; ok: bool; summary: str; duration_ms: int  # noqa: E702


class EvidenceAdded(CamelModel):
    evidence: EvidenceDTO


class DraftClaim(CamelModel):
    claim_key: str; text: str; is_key: bool; evidence_keys: list[str]  # noqa: E702


class ClaimsDrafted(CamelModel):
    claims: list[DraftClaim]


class ClaimVerified(CamelModel):
    claim_key: str; text: str; status: ClaimStatus; confidence: float  # noqa: E702
    evidence_keys: list[str]; reason: str  # noqa: E702


class ConfidenceEvent(CamelModel):
    overall: float; threshold: float; decision: ConfidenceDecision; loop: int  # noqa: E702


class LoopEvent(CamelModel):
    loop: int; max_loops: int; reason: str; focus: list[str]  # noqa: E702


class ActionProposed(CamelModel):
    action_key: str; action_type: ActionType; risk: Risk; title: str; description: str  # noqa: E702
    params: dict[str, Any]; rationale: str; evidence_keys: list[str]  # noqa: E702


class ApprovalRequired(CamelModel):
    actions: list[ActionProposed]


class ApprovalDecided(CamelModel):
    approval_id: int; action_key: str; decision: Decision; decided_by: str; comment: str | None = None  # noqa: E702


class ActionExecuted(CamelModel):
    action_log_id: int; action_key: str; action_type: ActionType; status: ActionStatus  # noqa: E702
    automatic: bool; note: str  # noqa: E702


class GuardrailTriggered(CamelModel):
    stage: GuardrailStage; action: GuardrailAction; category: GuardrailCategory; detail: str  # noqa: E702


class ReportDelta(CamelModel):
    text: str


class ReportReady(CamelModel):
    report_markdown: str; summary: str; recommendations: list[RecommendationDTO]; confidence: float  # noqa: E702


class MemorySaved(CamelModel):
    id: int; summary: str  # noqa: E702


class ErrorEvent(CamelModel):
    code: ErrorCode; message: str; retryable: bool  # noqa: E702


class Done(CamelModel):
    status: Literal["COMPLETED", "CANCELLED", "REFUSED"]; confidence: float | None; loops_used: int  # noqa: E702
    usage: UsageTokens; latency_ms: int  # noqa: E702


EVENT_PAYLOADS: dict[str, type[CamelModel]] = {
    "run_started": RunStarted, "memory_recalled": MemoryRecalled, "supervisor_routed": SupervisorRouted,
    "plan": PlanEvent, "step_status": StepStatusEvent, "agent_started": AgentStarted, "tool_call": ToolCall,
    "tool_result": ToolResult, "evidence_added": EvidenceAdded, "claims_drafted": ClaimsDrafted,
    "claim_verified": ClaimVerified, "confidence": ConfidenceEvent, "loop": LoopEvent,
    "action_proposed": ActionProposed, "approval_required": ApprovalRequired, "approval_decided": ApprovalDecided,
    "action_executed": ActionExecuted, "guardrail_triggered": GuardrailTriggered, "report_delta": ReportDelta,
    "report_ready": ReportReady, "memory_saved": MemorySaved, "error": ErrorEvent, "done": Done,
}


class AgentEvent(CamelModel):
    """Envelope for one SSE frame. `seq` is assigned by Spring, never by Python."""
    type: AgentEventType
    data: dict[str, Any]

    @classmethod
    def of(cls, payload: CamelModel) -> AgentEvent:
        for name, model in EVENT_PAYLOADS.items():
            if type(payload) is model:
                return cls(type=name, data=payload.wire())  # type: ignore[arg-type]
        raise TypeError(f"{type(payload).__name__} is not a contract event payload")

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


# ----------------------------------------------------------------------------- memory + eval (contract 4.5)
class MemoryDTO(CamelModel):
    id: int; summary: str; source_investigation_id: int | None; importance: float  # noqa: E702
    created_at: str; last_accessed_at: str | None  # noqa: E702


class EvalMetrics(CamelModel):
    answer_correctness: float; grounded_claims_share: float; hallucination_rate: float  # noqa: E702
    avg_latency_ms: float; avg_tokens: float  # noqa: E702
    approval_gate_compliance: float | None = None; retrieval_hit_rate: float | None = None  # noqa: E702
    citation_validity: float | None = None; guardrail_block_rate: float | None = None  # noqa: E702
    failure_recovery_rate: float | None = None  # noqa: E702


class EvalRunDTO(CamelModel):
    id: int; created_at: str; variant: str | None; system: EvalSystem; question_count: int; metrics: EvalMetrics  # noqa: E702


class EvalResultItem(CamelModel):
    question_id: str; category: EvalCategory; question: str; expected_facts: list[str]; answer: str  # noqa: E702
    correct: bool; grounded_share: float; hallucinated: bool; latency_ms: int  # noqa: E702


class EvalRunDetailDTO(EvalRunDTO):
    results: list[EvalResultItem]
