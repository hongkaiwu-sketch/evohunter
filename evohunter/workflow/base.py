from __future__ import annotations

import signal
from abc import ABC, abstractmethod
from typing import Any

from evohunter.workflow.models import WorkflowContext


class NodeTimeoutError(RuntimeError):
    pass


class BaseWorkflowNode(ABC):
    """Abstract base for all workflow nodes.

    Each node represents a single step in the headhunting pipeline.
    Subclasses must implement ``execute()``.
    """

    def __init__(self, node_id: str, config: dict[str, Any] | None = None) -> None:
        self.node_id = node_id
        self.config = config or {}

    @abstractmethod
    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        """Execute the node. Must return a dict for ``context.node_results``."""
        ...

    def validate_input(self, context: WorkflowContext) -> None:
        """Override to raise ``WorkflowValidationError`` if required inputs are missing."""

    def on_error(self, error: Exception, context: WorkflowContext) -> dict[str, Any]:
        """Return a partial/failure result for error recovery.

        The default returns an error dict. Override for node-specific recovery.
        """
        return {"error": str(error), "partial": True}

    def _execute_with_timeout(
        self, context: WorkflowContext, timeout_seconds: int
    ) -> dict[str, Any]:
        """Execute with a timeout using SIGALRM (Unix-only).

        Falls back to direct execution on platforms without SIGALRM.
        """
        if not hasattr(signal, "SIGALRM"):
            return self.execute(context)

        original_handler = signal.getsignal(signal.SIGALRM)
        result_holder: dict[str, Any] = {}
        error_holder: Exception | None = None

        def _handle_timeout(signum, frame):
            raise NodeTimeoutError(
                f"node '{self.node_id}' timed out after {timeout_seconds}s"
            )

        try:
            signal.signal(signal.SIGALRM, _handle_timeout)
            signal.alarm(timeout_seconds)
            try:
                result_holder = self.execute(context)
            finally:
                signal.alarm(0)
        except NodeTimeoutError as exc:
            error_holder = exc
        finally:
            signal.signal(signal.SIGALRM, original_handler)

        if error_holder is not None:
            return self.on_error(error_holder, context)

        return result_holder
