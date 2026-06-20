from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from evohunter.core.protocol import A2AEnvelope

A2A_BASE_URL = "https://evomap.ai/a2a"
DEFAULT_TIMEOUT = 10  # seconds


class A2AConnectionError(RuntimeError):
    """Raised when A2A network communication fails."""


class A2AClient:
    """Client for EvoMap A2A protocol (publish, fetch, hello, report).

    All network calls raise ``A2AConnectionError`` on failure so callers
    can degrade gracefully.
    """

    def __init__(
        self,
        sender_id: str,
        api_key: str | None = None,
        base_url: str = A2A_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._sender_id = sender_id
        self._api_key = api_key or os.environ.get("EVOMAP_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # -- Public API -----------------------------------------------------

    def hello(self) -> dict[str, Any]:
        """Register this node with the EvoMap Hub."""
        envelope = self._build_envelope("hello", {
            "node_version": "evohunter-1.0.0",
            "capabilities": ["recruiting_weight_tuning", "gene_exchange"],
        })
        return self._send(envelope)

    def publish(
        self,
        evolution_event: dict[str, Any],
        weight_config: dict[str, Any],
    ) -> dict[str, Any]:
        """Publish an evolution event and its resulting weight config (legacy)."""
        payload = {
            "evolution_event": evolution_event,
            "weight_config": weight_config,
            "gene_type": "Gene",
            "gene_category": "optimize",
            "intent": "recruiting_weight_tuning",
        }
        envelope = self._build_envelope("publish", payload)
        return self._send(envelope)

    def publish_genes(
        self,
        company_gene: dict[str, Any] | None = None,
        candidate_gene: dict[str, Any] | None = None,
        market_gene: dict[str, Any] | None = None,
        evolution_event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish anonymized three-party genes to the Hub.

        Each gene is independently anonymized before publishing.
        At least one gene must be provided.
        """
        payload: dict[str, Any] = {
            "gene_type": "GeneBundle",
            "gene_category": "recruiting",
            "intent": "three_party_gene_exchange",
        }

        if company_gene:
            payload["company_gene"] = company_gene
        if candidate_gene:
            payload["candidate_gene"] = candidate_gene
        if market_gene:
            payload["market_gene"] = market_gene
        if evolution_event:
            payload["evolution_event"] = evolution_event

        if not any([company_gene, candidate_gene, market_gene]):
            raise A2AConnectionError("publish_genes requires at least one gene")

        envelope = self._build_envelope("publish", payload)
        return self._send(envelope)

    def fetch(self, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch top weight configs from the network (legacy)."""
        envelope = self._build_envelope("fetch", {
            "intent": "recruiting_weight_tuning",
            "limit": limit,
        })
        response = self._send(envelope)
        configs = response.get("payload", {}).get("configs", [])
        if not isinstance(configs, list):
            return []
        return configs

    def fetch_genes(
        self,
        gene_types: list[str] | None = None,
        limit: int = 5,
    ) -> dict[str, list[dict[str, Any]]]:
        """Fetch anonymized three-party genes from the Hub.

        Args:
            gene_types: list of gene types to fetch, e.g. ["CompanyGene", "CandidateGene", "MarketGene"].
                        Defaults to all three.
            limit: max results per type.

        Returns dict with keys "company_genes", "candidate_genes", "market_genes".
        """
        if gene_types is None:
            gene_types = ["CompanyGene", "CandidateGene", "MarketGene"]

        envelope = self._build_envelope("fetch", {
            "intent": "three_party_gene_exchange",
            "gene_types": gene_types,
            "limit": limit,
        })
        response = self._send(envelope)
        payload = response.get("payload", {})
        return {
            "company_genes": payload.get("company_genes", []),
            "candidate_genes": payload.get("candidate_genes", []),
            "market_genes": payload.get("market_genes", []),
        }

    def report(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """Report performance metrics to the Hub."""
        envelope = self._build_envelope("report", {
            "metrics": metrics,
        })
        return self._send(envelope)

    # -- Internal helpers -----------------------------------------------

    def _build_envelope(
        self,
        message_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return A2AEnvelope.create(
            message_type=message_type,
            sender_id=self._sender_id,
            payload=payload,
        ).to_dict()

    def _send(self, envelope: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{envelope['message_type']}"
        body = json.dumps(envelope, ensure_ascii=False).encode("utf-8")

        headers: dict[str, str] = {
            "Content-Type": "application/json; charset=utf-8",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            request = Request(url, data=body, headers=headers, method="POST")
            with urlopen(request, timeout=self._timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except (URLError, OSError, json.JSONDecodeError) as exc:
            raise A2AConnectionError(
                f"A2A {envelope['message_type']} failed: {exc}"
            ) from exc
