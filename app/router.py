"""의도 확률 + 추출한 시술명을 보고 챗봇이 무엇을 할지 정한다.

action 종류
    escalate           위험 질문. 답변하지 않고 바로 병원 연락 안내
    clarify_intent     의도가 애매함. 후보 의도 중에서 고르게 함
    clarify_procedure  의도는 알지만 어떤 시술인지 모름. 시술을 고르게 함
    answer             바로 답변 (템플릿 / RAG / 상담 연결 / 거절은 다음 단계에서 의도별로 처리)

임계값은 임시값이다. 검증 데이터로 "되묻는 비율 vs 정확도"를 재보고 조정할 것.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DANGER = "side_effect"

# 위험 의도는 1등이 아니어도 확률이 이 정도면 위험으로 처리 (놓치는 것보다 과하게 잡는 게 안전)
SIDE_EFFECT_THRESHOLD = 0.30
# 1등 확률이 이보다 낮거나, 1등과 2등 차이가 작으면 의도를 되묻는다
CONFIDENCE_THRESHOLD = 0.70
MARGIN_THRESHOLD = 0.15
# 어떤 시술인지 알아야 답할 수 있는 의도
NEEDS_PROCEDURE = {"aftercare", "procedure_info"}

INTENT_LABELS_KO = {
    "location": "위치·주차",
    "phone": "전화번호·연락처",
    "hours": "진료시간",
    "procedure_list": "가능한 수술 종류",
    "aftercare": "수술 후 관리",
    "procedure_info": "수술 정보·가격",
    "consult_booking": "상담·예약",
    "side_effect": "수술 후 이상 증상",
    "out_of_scope": "기타",
}


@dataclass
class Decision:
    action: str
    intent: str | None = None
    options: list = field(default_factory=list)      # 되물을 때 보여줄 선택지
    procedures: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)  # 이 병원에서 안 하는 수술 (답변 단계에서 안내)
    reason: str = ""


def decide(probs: dict, extracted: dict) -> Decision:
    """probs: {"의도": 확률}, extracted: ProcedureExtractor.extract() 결과"""
    ranked = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    (top, p1), (second, p2) = ranked[0], ranked[1]
    procedures = extracted.get("procedures", [])
    ambiguous = extracted.get("ambiguous", [])
    unsupported = extracted.get("unsupported", [])

    # 1) 안전 우선: 위험 가능성이 있으면 되묻지도 않는다
    if probs.get(DANGER, 0.0) >= SIDE_EFFECT_THRESHOLD:
        return Decision("escalate", DANGER, procedures=procedures + ambiguous,
                        reason=f"side_effect 확률 {probs[DANGER]:.2f}")

    # 2) 의도가 애매함
    if p1 < CONFIDENCE_THRESHOLD or p1 - p2 < MARGIN_THRESHOLD:
        return Decision("clarify_intent", options=[top, second], procedures=procedures + ambiguous,
                        reason=f"{top} {p1:.2f} vs {second} {p2:.2f}")

    # 3) 시술 정보가 필요한데 없거나 애매함 (안 하는 수술을 물은 거면 되묻지 않고 답변 단계에서 안내)
    if top in NEEDS_PROCEDURE and not procedures and not unsupported:
        return Decision("clarify_procedure", top, options=ambiguous,
                        reason="시술명이 애매함" if ambiguous else "시술명 없음")

    return Decision("answer", top, procedures=procedures, unsupported=unsupported,
                    reason=f"{top} {p1:.2f}")
