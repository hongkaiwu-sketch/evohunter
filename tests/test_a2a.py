import pytest

from evohunter.core.protocol import A2AEnvelope, EvolutionEvent, generate_evolution_id


class TestA2AEnvelope:
    def test_create_sets_protocol_and_version(self):
        envelope = A2AEnvelope.create(
            message_type="hello",
            sender_id="node_test",
            payload={"hello": "world"},
        )
        assert envelope.protocol == "gep-a2a"
        assert envelope.protocol_version == "1.0.0"
        assert envelope.message_type == "hello"
        assert envelope.sender_id == "node_test"

    def test_create_generates_message_id(self):
        envelope = A2AEnvelope.create("publish", "node_x", {})
        assert envelope.message_id.startswith("msg_")

    def test_to_dict_contains_all_fields(self):
        envelope = A2AEnvelope.create("fetch", "node_y", {"limit": 3})
        d = envelope.to_dict()
        assert d["protocol"] == "gep-a2a"
        assert d["message_type"] == "fetch"
        assert d["sender_id"] == "node_y"
        assert d["payload"]["limit"] == 3


class TestA2AClient:
    def test_send_raises_connection_error_without_server(self):
        from evohunter.core.evolution.a2a import A2AClient, A2AConnectionError
        client = A2AClient(sender_id="node_test", base_url="http://localhost:1")
        with pytest.raises(A2AConnectionError):
            client.hello()

    def test_publish_fails_gracefully_without_server(self):
        from evohunter.core.evolution.a2a import A2AClient, A2AConnectionError
        client = A2AClient(sender_id="node_test", base_url="http://localhost:1")
        with pytest.raises(A2AConnectionError):
            client.publish(
                {"evolution_id": "ev_001", "intent": "recruiting_weight_tuning"},
                {"generation": 1, "skill_weight": 0.4},
            )


class TestEvolutionEvent:
    def test_generate_evolution_id(self):
        ev_id = generate_evolution_id()
        assert ev_id.startswith("ev_")
        assert len(ev_id) == 15  # "ev_" + 12 hex chars

    def test_evolution_event_round_trip(self):
        ev = EvolutionEvent(
            evolution_id=generate_evolution_id(),
            cycle_number=1,
            intent="recruiting_weight_tuning",
            strategy="balanced",
            capsule_id=None,
            genes_used=[{"skill_weight": 0.4}],
            outcome={"weight_config": {"generation": 1}},
            mutations_tried=5,
            total_cycles=1,
            created_at="2026-06-20T12:00:00.000Z",
        )
        d = ev.to_dict()
        assert d["evolution_id"].startswith("ev_")
        assert d["intent"] == "recruiting_weight_tuning"
        assert d["cycle_number"] == 1
