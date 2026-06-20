from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class WorkflowValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowNode:
    node_id: str
    node_type: str  # "input" | "process" | "output" | "decision"
    deps: list[str]  # node_ids this node depends on
    config: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 300
    retry_policy: str = "none"  # "none" | "once" | "exponential"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowNode":
        if not isinstance(data, dict):
            raise WorkflowValidationError("WorkflowNode data must be a dict")
        return cls(
            node_id=_require_string(data, "node_id"),
            node_type=_require_string(data, "node_type"),
            deps=data.get("deps", []),
            config=data.get("config", {}),
            timeout_seconds=int(data.get("timeout_seconds", 300)),
            retry_policy=data.get("retry_policy", "none"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "deps": list(self.deps),
            "config": dict(self.config),
            "timeout_seconds": self.timeout_seconds,
            "retry_policy": self.retry_policy,
        }


@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    name: str
    version: str
    nodes: dict[str, WorkflowNode]  # node_id -> WorkflowNode
    edges: list[tuple[str, str]]  # (from_node_id, to_node_id)
    entry_points: list[str]  # root node_ids (no deps)

    def validate(self) -> None:
        """Raise WorkflowValidationError on cycles or disconnected nodes."""
        # Check all edge endpoints reference known nodes
        node_ids = set(self.nodes.keys())
        for src, dst in self.edges:
            if src not in node_ids:
                raise WorkflowValidationError(f"edge source '{src}' not in nodes")
            if dst not in node_ids:
                raise WorkflowValidationError(f"edge target '{dst}' not in nodes")

        # Check entry points are valid
        for ep in self.entry_points:
            if ep not in node_ids:
                raise WorkflowValidationError(f"entry point '{ep}' not in nodes")

        # Check for cycles via topological sort
        try:
            self.topological_sort()
        except WorkflowValidationError:
            raise
        except Exception as exc:
            raise WorkflowValidationError(f"workflow has a cycle: {exc}") from exc

    def topological_sort(self) -> list[str]:
        """Kahn's algorithm — returns nodes in dependency order."""
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}

        for src, dst in self.edges:
            if dst not in in_degree:
                in_degree[dst] = 0
            in_degree[dst] += 1
            if src not in adj:
                adj[src] = []
            adj[src].append(dst)

        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result: list[str] = []

        while queue:
            node = queue.pop(0)
            result.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise WorkflowValidationError(
                f"cycle detected: only {len(result)}/{len(self.nodes)} nodes sorted"
            )

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowDefinition":
        if not isinstance(data, dict):
            raise WorkflowValidationError("WorkflowDefinition data must be a dict")
        nodes_raw = data.get("nodes", {})
        nodes = {
            str(k): WorkflowNode.from_dict(v)
            for k, v in nodes_raw.items()
        }
        edges_raw = data.get("edges", [])
        edges = [
            (str(e[0]), str(e[1]))
            for e in edges_raw
        ]
        definition = cls(
            workflow_id=_require_string(data, "workflow_id"),
            name=_require_string(data, "name"),
            version=data.get("version", "1.0.0"),
            nodes=nodes,
            edges=edges,
            entry_points=data.get("entry_points", []),
        )
        definition.validate()
        return definition

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "version": self.version,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [list(e) for e in self.edges],
            "entry_points": list(self.entry_points),
        }


@dataclass
class WorkflowContext:
    workflow_id: str
    input_data: dict[str, Any] = field(default_factory=dict)
    node_results: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    node_status: dict[str, str] = field(default_factory=dict)

    def get_node_result(self, node_id: str) -> Any:
        return self.node_results.get(node_id)

    def set_node_result(self, node_id: str, result: Any) -> None:
        self.node_results[node_id] = result

    def get_input(self, key: str, default: Any = None) -> Any:
        return self.input_data.get(key, default)

    def add_error(self, node_id: str, error: str) -> None:
        import time
        self.errors.append({
            "node_id": node_id,
            "error": error,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    def set_node_status(self, node_id: str, status: str) -> None:
        self.node_status[node_id] = status


@dataclass(frozen=True)
class WorkflowResult:
    workflow_id: str
    status: str  # "completed" | "partial" | "failed"
    node_status: dict[str, str]
    node_results: dict[str, Any]
    errors: list[dict[str, Any]]
    start_time: str
    end_time: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "node_status": dict(self.node_status),
            "node_results": dict(self.node_results),
            "errors": list(self.errors),
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


def _require_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowValidationError(f"{field_name} must be a non-empty string")
    return value.strip()
