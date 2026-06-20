from __future__ import annotations

import hashlib
import re
from typing import Any

from evohunter.core.genes import CompanyGene, CandidateGene, MarketGene

# PII patterns that should be stripped before sharing.
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?86)?1[3-9]\d{9}")
_NAME_PATTERNS = [
    # Chinese names (2-4 chars, common surnames)
    re.compile(
        r"(?:王|李|张|刘|陈|杨|黄|赵|周|吴|徐|孙|马|朱|胡|郭|何|高|林|罗|郑|梁|谢|宋|唐|韩|曹|许|邓|冯|萧|程|"
        r"蔡|彭|潘|袁|于|董|余|苏|叶|吕|魏|蒋|田|杜|丁|沈|姜|范|江|傅|钟|卢|汪|戴|崔|任|陆|廖|姚|方|金|丘|"
        r"夏|谭|韦|贾|邹|石|熊|孟|秦|阎|薛|侯|雷|白|龙|段|郝|孔|邵|史|毛|常|万|顾|赖|武|康|贺|严|尹|钱|"
        r"施|牛|洪|龚"
        r")[一-鿿]{1,3}"
    ),
    # English names (first + last)
    re.compile(r"[A-Z][a-z]+ [A-Z][a-z]+"),
]
_URL_RE = re.compile(r"https?://[^\s]+")
_QQ_RE = re.compile(r"[1-9]\d{4,10}")  # QQ numbers


def content_hash(data: dict[str, Any] | str) -> str:
    """SHA-256 hash of canonical JSON, used as de-identified ID."""
    import json
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def strip_pii(text: str) -> str:
    """Remove personally identifiable information from free text."""
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _URL_RE.sub("[URL]", text)
    text = _QQ_RE.sub("[QQ]", text)
    for pattern in _NAME_PATTERNS:
        text = pattern.sub("[NAME]", text)
    return text


def anonymize_text(text: str) -> str:
    """Alias for strip_pii."""
    return strip_pii(text)


def disguise_company_name(name: str) -> str:
    """Replace company name with a content hash, preserving industry if possible."""
    if not name.strip():
        return ""
    return f"co_{content_hash(name.strip().lower())}"


def disguise_candidate_identity(name: str, contact: str = "") -> str:
    """Create a de-identified hash from name and optional contact info."""
    payload = name.strip().lower()
    if contact.strip():
        payload += "|" + contact.strip().lower()
    return f"cand_{content_hash(payload)}"


def anonymize_company_gene(gene: CompanyGene) -> CompanyGene:
    """Return a shareable copy of a CompanyGene."""
    return gene.anonymize()


def anonymize_candidate_gene(gene: CandidateGene) -> CandidateGene:
    """Return a shareable copy of a CandidateGene."""
    return gene.anonymize()


def anonymize_market_gene(gene: MarketGene) -> MarketGene:
    """MarketGene is inherently anonymous — returned unchanged."""
    return gene


def anonymize_match_result(match_result: dict[str, Any]) -> dict[str, Any]:
    """Strip PII from a match result dict, keeping only dimensional scores and outcome."""
    return {
        "pattern_hash": content_hash({
            "score_detail": match_result.get("score_detail", {}),
        }),
        "dimensions": match_result.get("score_detail", {}),
        "result": match_result.get("result", match_result.get("event_type", "unknown")),
        "confidence": match_result.get("confidence_score", 1.0),
    }


def build_anonymous_match_patterns(
    match_results: list[dict[str, Any]],
    feedback_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine match results with feedback events, strip PII, return shareable patterns."""
    patterns: dict[str, dict[str, Any]] = {}

    for mr in match_results:
        dims = mr.get("score_detail", {})
        pattern_key = content_hash(
            {k: round(float(v), 2) for k, v in sorted(dims.items())}
        )
        if pattern_key not in patterns:
            patterns[pattern_key] = {
                "pattern_hash": pattern_key,
                "dimensions": {k: round(float(v), 4) for k, v in dims.items()},
                "results": {},
            }

    for fe in feedback_events:
        # Match feedback to a candidate's match result via candidate_id
        cid = fe.get("candidate_id", "unknown")
        event_type = fe.get("event_type", "unknown")
        # Find the corresponding match result for this candidate
        for mr in match_results:
            if mr.get("candidate_id") == cid:
                dims = mr.get("score_detail", {})
                pattern_key = content_hash(
                    {k: round(float(v), 2) for k, v in sorted(dims.items())}
                )
                if pattern_key in patterns:
                    patterns[pattern_key]["results"][event_type] = (
                        patterns[pattern_key]["results"].get(event_type, 0) + 1
                    )

    output = []
    for pattern in patterns.values():
        results = pattern.pop("results", {})
        if results:
            dominant = max(results, key=results.get)
            pattern["result"] = dominant
            pattern["count"] = sum(results.values())
            pattern["confidence"] = round(
                results[dominant] / pattern["count"], 2
            )
            output.append(pattern)

    return output
