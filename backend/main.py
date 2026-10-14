from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from typing import Any, Awaitable, Callable

from pydantic_ai.mcp import MCPToolset

from backend import accounting_agent, boss_agent, customer_service_agent, facilities_agent, inventory_agent
from backend.audit import append_audit_event
from backend.mcp_tools import create_mcp_toolset, list_open_ticket_ids
from backend.models import AgentRole, AgentWorkResult, CustomerReply, DispatchPlan, TicketResolution, TicketRunReport

SPECIALISTS: dict[AgentRole, Any] = {
    "inventory": inventory_agent.create_agent,
    "accounting": accounting_agent.create_agent,
    "facilities": facilities_agent.create_agent,
}

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def _publish_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    agent: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return
    event: dict[str, Any] = {
        "stage": stage,
        "agent": agent,
        "status": status,
        "message": message,
    }
    if details:
        event["details"] = details
    await callback(event)


def _actual_tool_names(result: Any) -> list[str]:
    names: set[str] = set()
    for message in result.all_messages():
        for part in getattr(message, "parts", []):
            name = getattr(part, "tool_name", None)
            if isinstance(name, str):
                names.add(name)
    return sorted(names)


async def _run_ticket(
    ticket_id: int,
    run_id: str,
    model_name: str,
    mcp_server: MCPToolset,
    progress: ProgressCallback | None = None,
) -> TicketRunReport:
    append_audit_event(run_id, ticket_id, "ticket_started", "team", "started")
    await _publish_progress(
        progress,
        stage="team_started",
        agent="team",
        status="running",
        message=f"Kakashi Hatake opened the case for Ticket {ticket_id} and is assembling the team.",
    )

    append_audit_event(run_id, ticket_id, "dispatch_plan", "boss", "started")
    await _publish_progress(
        progress,
        stage="dispatch_plan",
        agent="boss",
        status="working",
        message="Kakashi is reading the ticket and deciding which specialists to assign.",
    )
    dispatch_agent = boss_agent.create_dispatch_agent(model_name, mcp_server)
    plan_result = await dispatch_agent.run(
        f"Read ticket {ticket_id} with the MCP server. Return its assignment plan; "
        "assign every specialist whose responsibilities are relevant."
    )
    plan: DispatchPlan = plan_result.output
    if plan.ticket_id != ticket_id:
        raise ValueError(f"Boss planned ticket {plan.ticket_id}, expected {ticket_id}.")
    append_audit_event(
        run_id,
        ticket_id,
        "dispatch_plan",
        "boss",
        "created",
        _actual_tool_names(plan_result),
    )
    await _publish_progress(
        progress,
        stage="dispatch_plan",
        agent="boss",
        status="completed",
        message=plan.rationale,
        details={
            "assignments": [assignment.model_dump(mode="json") for assignment in plan.assignments],
            "tools_used": _actual_tool_names(plan_result),
        },
    )

    work_results: list[AgentWorkResult] = []
    for assignment in plan.assignments:
        create_agent = SPECIALISTS.get(assignment.agent)
        if create_agent is None:
            continue
        append_audit_event(
            run_id,
            ticket_id,
            "specialist_work",
            assignment.agent,
            "started",
        )
        await _publish_progress(
            progress,
            stage="specialist_work",
            agent=assignment.agent,
            status="working",
            message=f"Kakashi assigned {assignment.agent.replace('_', ' ')}: {assignment.reason}",
            details={"assignment_reason": assignment.reason},
        )
        specialist = create_agent(model_name, mcp_server)
        prior_results = [result.model_dump(mode="json") for result in work_results]
        work_result = await specialist.run(
            f"Work on ticket {ticket_id}. Assignment reason: {assignment.reason}\n"
            f"Boss plan: {plan.model_dump_json()}\n"
            f"Prior specialist findings: {prior_results or 'None'}\n"
            f"Use get_ticket({ticket_id}) and the role-appropriate MCP tools for all shop data. "
            f"In the structured output, set agent to '{assignment.agent}'. "
            "Return evidence-based findings and recommendations."
        )
        specialist_output: AgentWorkResult = work_result.output
        if specialist_output.agent != assignment.agent:
            raise ValueError(
                f"{assignment.agent} agent returned result for {specialist_output.agent}."
            )
        work_results.append(specialist_output)
        append_audit_event(
            run_id,
            ticket_id,
            "specialist_work",
            assignment.agent,
            "blocked" if specialist_output.blocked else "completed",
            _actual_tool_names(work_result),
        )
        await _publish_progress(
            progress,
            stage="specialist_work",
            agent=assignment.agent,
            status="blocked" if specialist_output.blocked else "completed",
            message=specialist_output.summary,
            details={
                "findings": specialist_output.findings,
                "recommendations": specialist_output.recommendations,
                "tools_used": _actual_tool_names(work_result),
            },
        )

    append_audit_event(run_id, ticket_id, "final_judgment", "boss", "started")
    await _publish_progress(
        progress,
        stage="final_judgment",
        agent="boss",
        status="working",
        message="Kakashi is weighing the specialist reports before deciding the ticket status.",
    )
    resolution_agent = boss_agent.create_resolution_agent(model_name, mcp_server)
    resolution_result = await resolution_agent.run(
        f"Make the final judgment for ticket {ticket_id} using the MCP ticket data, dispatch plan, "
        "and all specialist findings. Choose resolved, blocked, or needs_human. Do not state an action "
        "was taken if it was only recommended.\n"
        f"Dispatch plan: {plan.model_dump_json()}\n"
        f"Specialist findings: {[result.model_dump(mode='json') for result in work_results]}"
    )
    resolution: TicketResolution = resolution_result.output
    if resolution.ticket_id != ticket_id:
        raise ValueError(f"Boss resolved ticket {resolution.ticket_id}, expected {ticket_id}.")
    append_audit_event(
        run_id,
        ticket_id,
        "final_judgment",
        "boss",
        resolution.status,
        _actual_tool_names(resolution_result),
    )
    await _publish_progress(
        progress,
        stage="final_judgment",
        agent="boss",
        status=resolution.status,
        message=resolution.summary,
        details={
            "reasoning": resolution.reasoning,
            "follow_up_required": resolution.follow_up_required,
            "tools_used": _actual_tool_names(resolution_result),
        },
    )

    customer_reply: CustomerReply | None = None
    if any(assignment.agent == "customer_service" for assignment in plan.assignments):
        append_audit_event(
            run_id,
            ticket_id,
            "customer_response",
            "customer_service",
            "started",
        )
        service_agent = customer_service_agent.create_agent(model_name, mcp_server)
        reply_result = await service_agent.run(
            f"Draft a response for ticket {ticket_id} based on the Boss's final resolution and specialist findings. "
            f"Retrieve the ticket with get_ticket({ticket_id}). In the structured output, set ticket_id to {ticket_id}. "
            "Use generic, non-identifying greeting language. Do not include sensitive financial, identifying, or account information.\n"
            f"Resolution: {resolution.model_dump_json()}\n"
            f"Specialist findings: {[result.model_dump(mode='json') for result in work_results]}"
        )
        customer_reply = reply_result.output
        if customer_reply.ticket_id != ticket_id:
            raise ValueError(
                f"Customer Service returned a reply for ticket {customer_reply.ticket_id}, expected {ticket_id}."
            )
        append_audit_event(
            run_id,
            ticket_id,
            "customer_response",
            "customer_service",
            "drafted",
            _actual_tool_names(reply_result),
        )
        await _publish_progress(
            progress,
            stage="customer_response",
            agent="customer_service",
            status="completed",
            message=customer_reply.message,
            details={
                "requires_human_review": customer_reply.requires_human_review,
                "tools_used": _actual_tool_names(reply_result),
            },
        )

    return TicketRunReport(
        ticket_id=ticket_id,
        plan=plan,
        agent_results=work_results,
        resolution=resolution,
        customer_reply=customer_reply,
    )


async def run_team(
    ticket_id: int | None = None,
    progress: ProgressCallback | None = None,
) -> list[TicketRunReport]:
    model_name = os.getenv("PYDANTIC_AI_MODEL")
    if not model_name:
        raise RuntimeError(
            "Set PYDANTIC_AI_MODEL (for example, openai:gpt-4o-mini) and configure its provider credentials."
        )

    ticket_ids = [ticket_id] if ticket_id is not None else await list_open_ticket_ids()
    run_id = str(uuid.uuid4())
    mcp_server = create_mcp_toolset()
    async with mcp_server:
        reports = []
        for current_ticket_id in ticket_ids:
            reports.append(
                await _run_ticket(current_ticket_id, run_id, model_name, mcp_server, progress)
            )
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs PydanticAI agent team.")
    parser.add_argument("--ticket-id", type=int, help="Process one ticket; default is every open ticket.")
    args = parser.parse_args()
    reports = asyncio.run(run_team(args.ticket_id))
    for report in reports:
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
