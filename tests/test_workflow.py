import pytest

from evohunter.workflow import (
    WorkflowContext,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowNode,
    WorkflowResult,
)
from evohunter.workflow.base import BaseWorkflowNode
from evohunter.workflow.models import WorkflowValidationError


def test_workflow_definition_topological_sort_linear():
    definition = WorkflowDefinition(
        workflow_id="test_linear",
        name="Linear Test",
        version="1.0.0",
        nodes={
            "a": WorkflowNode("a", "process", [], {}),
            "b": WorkflowNode("b", "process", ["a"], {}),
            "c": WorkflowNode("c", "process", ["b"], {}),
        },
        edges=[("a", "b"), ("b", "c")],
        entry_points=["a"],
    )
    order = definition.topological_sort()
    assert order == ["a", "b", "c"]


def test_workflow_definition_cycle_detection():
    with pytest.raises(WorkflowValidationError):
        definition = WorkflowDefinition(
            workflow_id="test_cycle",
            name="Cycle Test",
            version="1.0.0",
            nodes={
                "a": WorkflowNode("a", "process", ["b"], {}),
                "b": WorkflowNode("b", "process", ["a"], {}),
            },
            edges=[("a", "b"), ("b", "a")],
            entry_points=["a"],
        )
        definition.validate()


def test_workflow_definition_diamond_dag():
    """A -> B, A -> C, B -> D, C -> D"""
    definition = WorkflowDefinition(
        workflow_id="test_diamond",
        name="Diamond DAG",
        version="1.0.0",
        nodes={
            "a": WorkflowNode("a", "process", [], {}),
            "b": WorkflowNode("b", "process", ["a"], {}),
            "c": WorkflowNode("c", "process", ["a"], {}),
            "d": WorkflowNode("d", "process", ["b", "c"], {}),
        },
        edges=[("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
        entry_points=["a"],
    )
    order = definition.topological_sort()
    assert order[0] == "a"
    assert order[3] == "d"
    assert set(order[1:3]) == {"b", "c"}


def test_workflow_definition_from_dict():
    data = {
        "workflow_id": "from_dict_test",
        "name": "From Dict",
        "version": "1.0.0",
        "nodes": {
            "a": {"node_id": "a", "node_type": "process", "deps": [], "config": {}},
            "b": {"node_id": "b", "node_type": "process", "deps": ["a"], "config": {}},
        },
        "edges": [["a", "b"]],
        "entry_points": ["a"],
    }
    definition = WorkflowDefinition.from_dict(data)
    assert definition.workflow_id == "from_dict_test"
    assert len(definition.nodes) == 2


def test_workflow_engine_linear_execution():
    """Execute A -> B -> C with counting nodes."""
    counts: dict[str, int] = {}

    class CounterNode(BaseWorkflowNode):
        def execute(self, context):
            counts[self.node_id] = counts.get(self.node_id, 0) + 1
            return {"count": counts[self.node_id]}

    definition = WorkflowDefinition(
        workflow_id="exec_linear",
        name="Exec Linear",
        version="1.0.0",
        nodes={
            "a": WorkflowNode("a", "process", [], {}),
            "b": WorkflowNode("b", "process", ["a"], {}),
            "c": WorkflowNode("c", "process", ["b"], {}),
        },
        edges=[("a", "b"), ("b", "c")],
        entry_points=["a"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(CounterNode("a"))
    engine.register_node(CounterNode("b"))
    engine.register_node(CounterNode("c"))

    context = WorkflowContext(workflow_id="exec_linear")
    result = engine.execute(context)

    assert result.status == "completed"
    assert counts == {"a": 1, "b": 1, "c": 1}
    assert context.node_status["a"] == "completed"
    assert context.node_status["b"] == "completed"
    assert context.node_status["c"] == "completed"


def test_workflow_engine_failed_dep_skips_downstream():
    """If node A fails, B and C (dep on A) are skipped."""

    class FailNode(BaseWorkflowNode):
        def execute(self, context):
            raise RuntimeError("boom")

    class PassNode(BaseWorkflowNode):
        def execute(self, context):
            return {"ok": True}

    definition = WorkflowDefinition(
        workflow_id="exec_fail",
        name="Exec Fail",
        version="1.0.0",
        nodes={
            "a": WorkflowNode("a", "process", [], {}),
            "b": WorkflowNode("b", "process", ["a"], {}),
            "c": WorkflowNode("c", "process", ["b"], {}),
        },
        edges=[("a", "b"), ("b", "c")],
        entry_points=["a"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(FailNode("a"))
    engine.register_node(PassNode("b"))
    engine.register_node(PassNode("c"))

    context = WorkflowContext(workflow_id="exec_fail")
    result = engine.execute(context)

    assert result.status in ("failed", "partial")
    assert context.node_status["a"] == "failed"
    assert context.node_status["b"] == "skipped"
    assert context.node_status["c"] == "skipped"


def test_workflow_engine_partial_completion():
    """Independent nodes: A fails, B succeeds independently."""

    class FailNode(BaseWorkflowNode):
        def execute(self, context):
            raise RuntimeError("boom")

    class PassNode(BaseWorkflowNode):
        def execute(self, context):
            return {"ok": True}

    definition = WorkflowDefinition(
        workflow_id="exec_partial",
        name="Exec Partial",
        version="1.0.0",
        nodes={
            "a": WorkflowNode("a", "process", [], {}),
            "b": WorkflowNode("b", "process", [], {}),
        },
        edges=[],
        entry_points=["a", "b"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(FailNode("a"))
    engine.register_node(PassNode("b"))

    context = WorkflowContext(workflow_id="exec_partial")
    result = engine.execute(context)

    assert result.status in ("partial", "failed")
    assert context.node_status["a"] == "failed"
    assert context.node_status["b"] == "completed"


def test_workflow_result_to_dict():
    result = WorkflowResult(
        workflow_id="test",
        status="completed",
        node_status={"a": "completed", "b": "completed"},
        node_results={"a": {"x": 1}, "b": {"y": 2}},
        errors=[],
        start_time="2026-01-01T00:00:00Z",
        end_time="2026-01-01T00:01:00Z",
    )
    d = result.to_dict()
    assert d["workflow_id"] == "test"
    assert d["status"] == "completed"
    assert d["node_status"]["a"] == "completed"


def test_workflow_context_data_flow():
    """Test that nodes can pass data via context."""
    results_passed: list[str] = []

    class ProducerNode(BaseWorkflowNode):
        def execute(self, context):
            return {"data": "from_producer"}

    class ConsumerNode(BaseWorkflowNode):
        def execute(self, context):
            dep_result = context.get_node_result("producer")
            results_passed.append(dep_result["data"])
            return {"received": dep_result["data"]}

    definition = WorkflowDefinition(
        workflow_id="dataflow",
        name="Data Flow",
        version="1.0.0",
        nodes={
            "producer": WorkflowNode("producer", "process", [], {}),
            "consumer": WorkflowNode("consumer", "process", ["producer"], {}),
        },
        edges=[("producer", "consumer")],
        entry_points=["producer"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(ProducerNode("producer"))
    engine.register_node(ConsumerNode("consumer"))

    context = WorkflowContext(workflow_id="dataflow")
    result = engine.execute(context)

    assert result.status == "completed"
    assert results_passed == ["from_producer"]
