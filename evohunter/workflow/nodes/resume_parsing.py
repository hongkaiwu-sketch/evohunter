from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from evohunter.ai import DEFAULT_MODEL, complete_chat
from evohunter.workflow.base import BaseWorkflowNode
from evohunter.workflow.models import WorkflowContext


@dataclass(frozen=True)
class RecruiterAssessment:
    candidate_name: str
    match_degree: int  # 1-10
    hard_match_score: float  # 70%
    hr_bonus_score: float  # 30%
    main_match_points: list[str] = field(default_factory=list)
    main_deductions: list[str] = field(default_factory=list)
    conclusion: str = ""
    background_summary: str = ""
    reasons_for_recommendation: list[str] = field(default_factory=list)
    tech_tags: list[str] = field(default_factory=list)
    current_salary: str = ""
    current_level: str = ""
    reason_for_leaving: str = ""
    recommendation_text: str | None = None
    requires_human_input: bool = False
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "candidate_name": self.candidate_name,
            "match_degree": self.match_degree,
            "hard_match_score": self.hard_match_score,
            "hr_bonus_score": self.hr_bonus_score,
            "main_match_points": list(self.main_match_points),
            "main_deductions": list(self.main_deductions),
            "conclusion": self.conclusion,
            "background_summary": self.background_summary,
            "reasons_for_recommendation": list(self.reasons_for_recommendation),
            "tech_tags": list(self.tech_tags),
            "current_salary": self.current_salary,
            "current_level": self.current_level,
            "reason_for_leaving": self.reason_for_leaving,
            "requires_human_input": self.requires_human_input,
            "missing_fields": list(self.missing_fields),
        }
        if self.recommendation_text is not None:
            result["recommendation_text"] = self.recommendation_text
        return result


class RecruiterAssessmentNode(BaseWorkflowNode):
    """Node ②: Resume Parsing & Recruiter Assessment.

    Uses the tech recruiter prompt to:
    1. Parse resume into structured candidate info
    2. Assess match degree against JD (10-point scale)
    3. Generate recommendation text if score >= 7
    4. Flag missing info (salary, level, leaving reason)

    Reuses ``llm_parser`` for struct extraction and feeds
    results into the right-brain ``GEPEvaluator`` for scoring logs.
    """

    def __init__(
        self,
        ai_client: Any | None = None,
        model: str = DEFAULT_MODEL,
        node_id: str = "resume_parsing",
    ) -> None:
        super().__init__(node_id, {"model": model})
        self._ai = ai_client
        self._model = model

    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        jd = context.get_node_result("jd_generation")
        jd_text = ""
        if isinstance(jd, dict):
            jd_text = json.dumps(jd.get("job_gene", jd), ensure_ascii=False)
        resume_text = context.get_input("resume_text", "")
        language = context.get_input("language", "zh")
        user_notes = context.get_input("user_notes", "")

        if not jd_text:
            return {
                "error": "no_jd",
                "message": "请先提供 JD 后再评估候选人" if language == "zh" else "Please provide JD first",
            }

        if not resume_text.strip():
            return {
                "error": "no_resume",
                "message": "请提供候选人简历" if language == "zh" else "Please provide resume",
            }

        assessment = self._assess(jd_text, resume_text, user_notes, language)
        return assessment.to_dict()

    def _assess(
        self,
        jd_text: str,
        resume_text: str,
        user_notes: str,
        language: str,
    ) -> RecruiterAssessment:
        system_prompt = _build_recruiter_prompt(language)
        user_prompt = _build_user_prompt(jd_text, resume_text, user_notes)

        raw = complete_chat(
            model=self._model,
            client=self._ai,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        parsed = _parse_assessment_response(raw)
        return self._apply_rules(parsed, language)

    def _apply_rules(
        self, data: dict[str, Any], language: str
    ) -> RecruiterAssessment:
        match_degree = int(data.get("match_degree", 0))
        hard_match = float(data.get("hard_match_score", match_degree * 0.7))
        hr_bonus = float(data.get("hr_bonus_score", match_degree * 0.3))

        # Pre-checks
        missing: list[str] = []
        salary = data.get("current_salary", "")
        level = data.get("current_level", "")
        leaving = data.get("reason_for_leaving", "")

        if language == "zh":
            if not salary:
                missing.append("当前薪资 / 职级")
            if not level:
                missing.append("当前职级")
            if not leaving:
                missing.append("看机会原因")
        else:
            if not salary:
                missing.append("current_salary")
            if not level:
                missing.append("current_level")
            if not leaving:
                missing.append("reason_for_leaving")

        requires_human = match_degree < 7
        rec_text: str | None = None

        if match_degree >= 7:
            if missing:
                # Missing info but score is high → ask user first
                requires_human = True
            else:
                # All info present → generate recommendation
                rec_text = data.get("recommendation_text", "") or _assemble_recommendation(data)

        return RecruiterAssessment(
            candidate_name=data.get("candidate_name", ""),
            match_degree=match_degree,
            hard_match_score=round(hard_match, 2),
            hr_bonus_score=round(hr_bonus, 2),
            main_match_points=data.get("main_match_points", []),
            main_deductions=data.get("main_deductions", []),
            conclusion=data.get("conclusion", _conclusion_label(match_degree, language)),
            background_summary=data.get("background_summary", ""),
            reasons_for_recommendation=data.get("reasons_for_recommendation", []),
            tech_tags=data.get("tech_tags", []),
            current_salary=salary,
            current_level=level,
            reason_for_leaving=leaving,
            recommendation_text=rec_text,
            requires_human_input=requires_human,
            missing_fields=missing,
        )


# ── Prompt builders ────────────────────────────────────────────────────


def _build_recruiter_prompt(language: str) -> str:
    if language == "en":
        return _EN_PROMPT
    return _ZH_PROMPT


def _build_user_prompt(jd_text: str, resume_text: str, user_notes: str) -> str:
    parts = [
        f"## JD\n{jd_text}",
        f"## 简历\n{resume_text}",
    ]
    if user_notes.strip():
        parts.append(f"## 用户补充\n{user_notes}")
    return "\n\n".join(parts)


# ── Response parsing ───────────────────────────────────────────────────


def _parse_assessment_response(raw: str) -> dict[str, Any]:
    """Extract JSON from LLM response."""
    text = raw.strip()

    # Try fenced code block
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    if fence:
        text = fence.group(1).strip()

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON object from text
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                return decoder.raw_decode(text[i:])[0]
            except json.JSONDecodeError:
                continue

    # Return empty dict as fallback
    return {}


def _assemble_recommendation(data: dict[str, Any]) -> str:
    """Assemble recommendation text from structured fields."""
    lines = [data.get("candidate_name", "")]
    if data.get("background_summary"):
        lines.append("\n" + data["background_summary"])
    if data.get("reasons_for_recommendation"):
        lines.append("\n推荐理由\n" + "\n".join(
            f"{i + 1} {r}"
            for i, r in enumerate(data["reasons_for_recommendation"])
        ))
    if data.get("tech_tags"):
        lines.append("\n技术标签：" + " | ".join(data["tech_tags"]))
    if data.get("current_salary") or data.get("current_level"):
        salary_info = f"\n薪资情况：{data.get('current_salary', '')} {data.get('current_level', '')}"
        lines.append(salary_info.strip())
    if data.get("reason_for_leaving"):
        lines.append(f"\n看机会原因：{data['reason_for_leaving']}")
    return "\n".join(lines)


def _conclusion_label(score: int, language: str) -> str:
    if language == "en":
        if score <= 5:
            return "Not qualified"
        if score == 6:
            return "Worth trying"
        if score == 7:
            return "Recommendable"
        return "Strong match"
    if score <= 5:
        return "不合格"
    if score == 6:
        return "可尝试"
    if score == 7:
        return "可推荐"
    return "强匹配"


# ── System prompts ─────────────────────────────────────────────────────

_ZH_PROMPT = """你是一名科技行业猎头顾问，需要根据候选人简历和 JD 判断匹配度，并决定是否生成推荐词。

## 执行顺序

1. 先判断匹配度，不要直接生成推荐词
2. 匹配度按 10 分制输出：

评分标准：
- 70% 看 JD 与简历的硬匹配度（技能、经验、薪资、地点、职级）
- 30% 看 HR 加分项（学校、公司背景、稳定性、成长性）

分数解释：
- 5分及以下：不合格
- 6分：可尝试
- 7分：可推荐
- 8分及以上：强匹配

## 推荐词触发规则

1. 若匹配度 ≥ 7 分，且以下信息齐全，生成推荐词：
   - 当前薪资 / 职级
   - 看机会原因 / 离职原因
   若缺失，在 missing_fields 中标明。

2. 若匹配度 < 7 分，不生成推荐词，结论写"该人选当前匹配度低于 7 分，是否仍需生成推荐词？"

## 推荐词原则

1. 只能基于简历和 JD 提供的信息生成，不允许虚构
2. 不允许脑补项目、职责、业绩或动机
3. 推荐词必须去套话、去销售腔，只保留可核验事实
4. 禁止使用：事实支撑、高度匹配、非常优秀、强烈推荐、稀缺人才、学习能力强、沟通能力强

## 推荐词固定格式

候选人姓名

第一段：背景概述（2-3句），包括教育背景、工作年限、核心技术方向、代表公司经历

推荐理由
1 每条推荐理由为一句能力判断 + 一句具体经历描述，控制在2-3行
2 共3-4条
3 必须具体，不能空泛

技术标签：输出5-8个技术关键词，用 | 分隔

薪资情况：当前公司 + 职级 + 薪资范围

看机会原因：1-2句

## 输出格式（JSON only）

返回纯 JSON，不要加解释文字：

{
  "candidate_name": "姓名",
  "match_degree": 7,
  "hard_match_score": 5.6,
  "hr_bonus_score": 1.4,
  "main_match_points": ["匹配点1", "匹配点2"],
  "main_deductions": ["扣分项1"],
  "conclusion": "可推荐",
  "background_summary": "2-3句背景概述",
  "reasons_for_recommendation": ["理由1", "理由2", "理由3"],
  "tech_tags": ["Python", "LLM", "Kubernetes", "Go", "PostgreSQL"],
  "current_salary": "当前薪资（从简历提取，若没有则留空）",
  "current_level": "当前职级（从简历提取，若没有则留空）",
  "reason_for_leaving": "看机会原因（从简历提取，若没有则留空）",
  "recommendation_text": "（仅匹配度≥7且信息齐全时填写）完整推荐词",
  "missing_fields": ["当前薪资 / 职级"]
}
"""

_EN_PROMPT = """You are a tech industry headhunter. Assess candidate resumes against JDs.

## Process

1. Determine match degree on a 10-point scale:
   - 70% hard match (skills, experience, salary, location, seniority)
   - 30% HR bonus (education, company background, stability, growth potential)

Score interpretation:
- ≤5: Not qualified
- 6: Worth trying
- 7: Recommendable
- 8+: Strong match

2. If score ≥ 7 AND current salary/level + reason for leaving are available, generate recommendation text.
   If info missing, flag in missing_fields.

3. If score < 7, do NOT generate recommendation. Set conclusion accordingly.

## Recommendation Rules

- Only use information from the resume and JD — no fabrication
- No fluff, no sales tone
- Banned phrases: outstanding, exceptional, top-tier, highly recommended, quick learner

## Output Format (JSON only)

{
  "candidate_name": "...",
  "match_degree": 7,
  "hard_match_score": 5.6,
  "hr_bonus_score": 1.4,
  "main_match_points": ["..."],
  "main_deductions": ["..."],
  "conclusion": "Recommendable",
  "background_summary": "...",
  "reasons_for_recommendation": ["...", "...", "..."],
  "tech_tags": ["Python", "LLM"],
  "current_salary": "...",
  "current_level": "...",
  "reason_for_leaving": "...",
  "recommendation_text": "...",
  "missing_fields": []
}
"""
