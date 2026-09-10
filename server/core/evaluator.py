"""Free-text evaluation boundary.

The first vertical slice uses a transparent fallback evaluator. A model-backed
adapter can replace it later without changing API or scenario state ownership.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    passed: bool
    interpretation: str
    feedback: str
    policy_clause_ids: list[str]
    mode: str = "fallback"


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


class FallbackTextEvaluator:
    """Auditable keyword-group fallback; never labelled as AI output."""

    def evaluate(self, rule: str, text: str) -> EvaluationResult:
        if rule == "clarify_context":
            groups = [
                _contains_any(text, ("谁付款", "谁买单", "付款方", "who pays", "paying")),
                _contains_any(text, ("审批", "续约", "采购", "决定", "approval", "renewal")),
                _contains_any(text, ("参与", "谁去", "哪些人", "attend", "participants")),
                _contains_any(text, ("政策", "制度", "记录", "policy", "record")),
            ]
            passed = sum(groups) >= 2
            return EvaluationResult(
                passed=passed,
                interpretation=(
                    "回答主动补充了至少两类关键事实。"
                    if passed
                    else "回答尚未同时覆盖付款方、参与者、待决事项或适用制度中的至少两类。"
                ),
                feedback=(
                    "你在下结论前先补齐了关键情境。"
                    if passed
                    else "先确认谁付款、谁参加、是否存在待审批事项，以及适用什么制度。"
                ),
                policy_clause_ids=["ETH-03"],
            )
        if rule == "conflict_awareness":
            business_link = _contains_any(
                text, ("审批", "续约", "采购", "投标", "决定", "approval", "renewal", "tender")
            )
            transparency = _contains_any(
                text, ("隐瞒", "记录", "报销", "透明", "hide", "record", "expense")
            )
            action = _contains_any(
                text, ("暂停", "不接受", "拒绝", "咨询", "报告", "查询", "pause", "decline", "consult")
            )
            passed = business_link and action and transparency
            return EvaluationResult(
                passed=passed,
                interpretation=(
                    "回答识别了待决业务关系、透明度风险，并提出暂停或咨询。"
                    if passed
                    else "回答未同时连接待决业务关系、隐瞒要求和合适的下一步。"
                ),
                feedback=(
                    "你指出了具体风险信号，并给出了暂停和咨询的下一步。"
                    if passed
                    else "请同时考虑待决业务事项、要求隐瞒或绕过记录，以及暂停并咨询的行动。"
                ),
                policy_clause_ids=["ETH-01", "ETH-02"],
            )
        if rule == "communicate_boundary":
            boundary = _contains_any(text, ("暂不", "不接受", "先不", "pause", "decline"))
            reason = _contains_any(text, ("审批", "政策", "制度", "利益", "合规", "policy", "approval"))
            next_step = _contains_any(text, ("咨询", "确认", "查询", "记录", "consult", "check"))
            passed = boundary and reason and next_step
            return EvaluationResult(
                passed=passed,
                interpretation=(
                    "回复包含清晰边界、原因和可执行下一步。"
                    if passed
                    else "回复尚未同时包含边界、原因和下一步。"
                ),
                feedback=(
                    "表达清晰：先说明边界，再解释原因，并给出继续合作的下一步。"
                    if passed
                    else "试着用三部分表达：暂不接受、说明需要确认的原因、提出查询或咨询的下一步。"
                ),
                policy_clause_ids=["DEV-01"],
            )
        raise ValueError(f"Unknown text evaluation rule: {rule}")
