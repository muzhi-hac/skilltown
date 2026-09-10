"""Small, audited policy-card registry for the hackathon scenario."""

POLICY_CARDS = {
    "ETH-01": {
        "clause_id": "ETH-01",
        "title": "待决业务事项",
        "text": "利益与本人正在参与的采购、续约、审批或评价有关时，先暂停接受并确认适用流程。",
        "fictional": True,
    },
    "ETH-02": {
        "clause_id": "ETH-02",
        "title": "透明与记录",
        "text": "要求隐瞒、绕过报销或省略记录，是需要停止并咨询指定内部渠道的风险信号。",
        "fictional": True,
    },
    "ETH-03": {
        "clause_id": "ETH-03",
        "title": "结合情境判断",
        "text": "聚餐或礼物本身不自动等于违规；应考虑提供方、付款方、时间、业务关系和透明度。",
        "fictional": True,
    },
    "DEV-01": {
        "clause_id": "DEV-01",
        "title": "表达边界",
        "text": "说明暂不接受、需要确认的原因和合适下一步，有助于兼顾边界与合作关系。",
        "fictional": True,
    },
}


def get_policy_cards(clause_ids: list[str]) -> list[dict]:
    return [POLICY_CARDS[clause_id] for clause_id in clause_ids if clause_id in POLICY_CARDS]
