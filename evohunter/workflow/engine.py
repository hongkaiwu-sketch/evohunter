from __future__ import annotations

import time
from typing import Any

from evohunter.workflow.base import BaseWorkflowNode
from evohunter.workflow.models import (
    WorkflowContext,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowValidationError,
)


class WorkflowEngine:
    """DAG orchestrator — runs nodes in topological order.

    Each node's dependencies must complete before it executes.
    If a dependency fails, downstream nodes are skipped.
    """

    def __init__(self, definition: WorkflowDefinition) -> None:
        self._definition = definition
        self._nodes: dict[str, BaseWorkflowNode] = {}
        self._order: list[str] = definition.topological_sort()

    def register_node(self, node: BaseWorkflowNode) -> None:
        """Register a node implementation for a node_id in the definition."""
        if node.node_id not in self._definition.nodes:
            raise WorkflowValidationError(
                f"node_id '{node.node_id}' not in workflow definition"
            )
        self._nodes[node.node_id] = node

    def get_node(self, node_id: str) -> BaseWorkflowNode | None:
        """Get a registered node by ID."""
        return self._nodes.get(node_id)

    def execute(self, context: WorkflowContext) -> WorkflowResult:
        """Execute the workflow DAG synchronously."""
        start_time = _now_iso()
        node_ids = list(self._order)

        for node_id in node_ids:
            wf_node = self._definition.nodes[node_id]

            # Check if all deps completed
            deps_failed = False
            for dep_id in wf_node.deps:
                dep_status = context.node_status.get(dep_id, "pending")
                if dep_status in ("failed", "skipped"):
                    deps_failed = True
                    break

            if deps_failed:
                context.set_node_status(node_id, "skipped")
                context.add_error(
                    node_id,
                    f"skipped because dependency failed: {wf_node.deps}",
                )
                continue

            # Get or default the node implementation
            node = self._nodes.get(node_id)
            if node is None:
                context.set_node_status(node_id, "skipped")
                context.add_error(
                    node_id,
                    f"no implementation registered for node '{node_id}'",
                )
                continue

            # Execute
            context.set_node_status(node_id, "running")
            try:
                node.validate_input(context)
                if wf_node.timeout_seconds > 0:
                    result = node._execute_with_timeout(context, wf_node.timeout_seconds)
                else:
                    result = node.execute(context)
                context.set_node_result(node_id, result)
                context.set_node_status(node_id, "completed")
            except Exception as exc:
                recovery = node.on_error(exc, context)
                context.set_node_result(node_id, recovery)
                context.set_node_status(node_id, "failed")
                context.add_error(node_id, str(exc))

        # Determine overall status
        statuses = [
            context.node_status.get(nid, "pending") for nid in node_ids
        ]
        if all(s == "completed" for s in statuses):
            overall = "completed"
        elif any(s == "failed" for s in statuses):
            overall = "failed" if statuses.count("failed") >= len(statuses) / 2 else "partial"
        else:
            overall = "partial"

        return WorkflowResult(
            workflow_id=context.workflow_id,
            status=overall,
            node_status=dict(context.node_status),
            node_results=dict(context.node_results),
            errors=list(context.errors),
            start_time=context.metadata.get("start_time", start_time),
            end_time=_now_iso(),
        )


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
