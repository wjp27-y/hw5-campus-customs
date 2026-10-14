from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentRole = Literal["inventory", "accounting", "facilities", "customer_service"]
ResolutionStatus = Literal["resolved", "blocked", "needs_human"]


class Ticket(BaseModel):
    id: int
    type: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


class AgentAssignment(BaseModel):
    agent: AgentRole
    reason: str = Field(description="Brief task-specific reason for assigning this role.")


class DispatchPlan(BaseModel):
    ticket_id: int
    assignments: list[AgentAssignment]
    rationale: str


class AgentWorkResult(BaseModel):
    agent: AgentRole
    summary: str
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    blocked: bool = False


class TicketResolution(BaseModel):
    ticket_id: int
    status: ResolutionStatus
    summary: str
    reasoning: str
    follow_up_required: bool = False


class CustomerReply(BaseModel):
    ticket_id: int
    message: str
    requires_human_review: bool = False


class TicketRunReport(BaseModel):
    ticket_id: int
    plan: DispatchPlan
    agent_results: list[AgentWorkResult]
    resolution: TicketResolution
    customer_reply: CustomerReply | None = None
