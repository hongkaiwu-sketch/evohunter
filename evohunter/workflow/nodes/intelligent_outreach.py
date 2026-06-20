from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from evohunter.ai import DEFAULT_MODEL
from evohunter.mcp.models import MCPToolCall
from evohunter.mcp.tool_registry import MCPToolRegistry
from evohunter.outreach import draft_outreach
from evohunter.workflow.base import BaseWorkflowNode
from evohunter.workflow.models import WorkflowContext


@dataclass
class OutreachMessage:
    message_id: str
    sender: str  # "recruiter" | "candidate"
    channel: str  # "email" | "im"
    content: str
    sent_at: str
    mcp_tool_id: str | None = None


@dataclass
class OutreachThread:
    thread_id: str
    candidate_id: str
    job_id: str
    messages: list[OutreachMessage] = field(default_factory=list)
    status: str = "draft"  # "draft" | "sent" | "replied" | "scheduled" | "closed"
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "messages": [
                {
                    "message_id": m.message_id,
                    "sender": m.sender,
                    "channel": m.channel,
                    "content": m.content,
                    "sent_at": m.sent_at,
                    "mcp_tool_id": m.mcp_tool_id,
                }
                for m in self.messages
            ],
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class IntelligentOutreachNode(BaseWorkflowNode):
    """Node ③: Intelligent Outreach & Interview.

    Extends the existing ``outreach.draft_outreach()`` with:
    - MCP-based email/IM sending
    - Multi-round communication thread tracking
    - Interview scheduling via calendar tools

    Degrades gracefully without MCP: generates draft only.
    """

    def __init__(
        self,
        mcp_registry: MCPToolRegistry | None = None,
        ai_client: Any | None = None,
        model: str = DEFAULT_MODEL,
        node_id: str = "intelligent_outreach",
    ) -> None:
        super().__init__(node_id, {"model": model})
        self._mcp = mcp_registry
        self._ai = ai_client
        self._model = model

    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        assessment = context.get_node_result("resume_parsing") or {}
        jd_result = context.get_node_result("jd_generation") or {}

        # Check if human review is required
        if assessment.get("requires_human_input"):
            return {
                "status": "requires_human_review",
                "message": assessment.get("conclusion", "Match degree too low"),
                "thread": None,
            }

        job_gene = jd_result.get("job_gene", {})
        candidate_gene = assessment.get("candidate_gene", {})
        match_result = {
            "candidate_id": candidate_gene.get("candidate_hash", ""),
            "job_id": job_gene.get("job_id", ""),
            "match_score": assessment.get("match_degree", 0) / 10.0,
            "score_detail": {},
            "recommendation_reason": assessment.get("conclusion", ""),
        }

        # Step 1: Generate draft (reuse existing)
        draft = {}
        try:
            draft = draft_outreach(
                job_gene=job_gene,
                candidate_gene=candidate_gene,
                match_result=match_result,
                client=self._ai,
                model=self._model,
            )
        except Exception:
            draft = {
                "subject": f"Opportunity: {job_gene.get('job_title', '')}",
                "message_body": assessment.get("recommendation_text", ""),
                "rationale": assessment.get("conclusion", ""),
            }

        # Step 2: Try MCP send
        delivery_status = False
        delivery_error: str | None = None
        channel = context.get_input("outreach_channel", "email")
        recipient = context.get_input("candidate_email", "")
        use_mcp = context.get_input("use_mcp", False)

        if use_mcp and self._mcp is not None and recipient:
            try:
                if channel == "email":
                    result = self._mcp.execute_tool(
                        MCPToolCall(
                            tool_id="email_send",
                            parameters={
                                "to": recipient,
                                "subject": draft.get("subject", ""),
                                "body": draft.get("message_body", ""),
                            },
                        )
                    )
                else:
                    result = self._mcp.execute_tool(
                        MCPToolCall(
                            tool_id="im_send",
                            parameters={
                                "platform": context.get_input("im_platform", ""),
                                "to": recipient,
                                "body": draft.get("message_body", ""),
                            },
                        )
                    )
                delivery_status = result.success
                delivery_error = result.error
            except Exception as exc:
                delivery_error = str(exc)

        # Step 3: Create thread
        now = datetime.now(timezone.utc).isoformat()
        thread = OutreachThread(
            thread_id=f"thread_{uuid.uuid4().hex[:12]}",
            candidate_id=match_result.get("candidate_id", "unknown"),
            job_id=match_result.get("job_id", "unknown"),
            messages=[
                OutreachMessage(
                    message_id=f"msg_{uuid.uuid4().hex[:8]}",
                    sender="recruiter",
                    channel=channel,
                    content=draft.get("message_body", ""),
                    sent_at=now,
                    mcp_tool_id=f"{channel}_send" if delivery_status else None,
                )
            ],
            status="sent" if delivery_status else "draft",
            created_at=now,
            updated_at=now,
        )

        return {
            "thread": thread.to_dict(),
            "draft": draft,
            "delivery_status": delivery_status,
            "delivery_error": delivery_error,
            "channel": channel,
        }

    def handle_reply(
        self, thread: OutreachThread, reply_text: str, channel: str = "email"
    ) -> OutreachThread:
        """Record a candidate reply in the thread."""
        now = datetime.now(timezone.utc).isoformat()
        thread.messages.append(
            OutreachMessage(
                message_id=f"msg_{uuid.uuid4().hex[:8]}",
                sender="candidate",
                channel=channel,
                content=reply_text,
                sent_at=now,
            )
        )
        thread.status = "replied"
        thread.updated_at = now
        return thread

    def schedule_interview(
        self,
        thread: OutreachThread,
        title: str,
        start_time: str,
        end_time: str,
        attendees: list[str] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """Schedule an interview via MCP calendar tool."""
        if self._mcp is None:
            return {"success": False, "error": "No MCP registry configured"}

        result = self._mcp.execute_tool(
            MCPToolCall(
                tool_id="calendar_create_event",
                parameters={
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                    "attendees": attendees or [],
                    "description": description,
                    "send_invites": True,
                },
            )
        )

        if result.success:
            thread.status = "scheduled"
            thread.updated_at = datetime.now(timezone.utc).isoformat()

        return {
            "success": result.success,
            "error": result.error,
            "data": result.data,
        }
