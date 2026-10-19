"""라우터가 정한 처리 방식(Decision)을 실제 답변 문장으로 바꾼다.

- 위치·전화·진료시간·예약 → hospital.json 으로 템플릿 답변
- 시술 목록·시술 정보·수술 후 관리 → procedures.json 에서 해당 항목을 보여줌
  (다음 단계에서 수술 후 관리·시술 정보는 RAG로 바꿔 질문에 맞는 부분만 답하게 할 예정)
- 위험 질문 → 답변 없이 병원 연락 안내
- 되묻기 → 선택지 버튼
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.router import INTENT_LABELS_KO  # noqa: F401  (화면에서도 씀)

ROOT = Path(__file__).resolve().parent.parent
HOSPITAL = json.loads((ROOT / "data" / "hospital.json").read_text(encoding="utf-8"))
PROC_DATA = json.loads((ROOT / "data" / "procedures.json").read_text(encoding="utf-8"))
PROCEDURES = {p["id"]: p for p in PROC_DATA["procedures"]}

PHONE = HOSPITAL["contact"]["phone"]
MEDICAL_DISCLAIMER = "※ 일반적인 안내이며, 개인 상태에 따라 다를 수 있어요. 정확한 내용은 진료 시 의료진과 확인해 주세요."
DAYS_KO = {"mon": "월", "tue": "화", "wed": "수", "thu": "목", "fri": "금", "sat": "토", "sun": "일"}



@dataclass
class Reply:
    text: str
    buttons: list = field(default_factory=list)   # [(버튼 글자, {"type": "intent"|"procedure", "value": ...})]


def _won(n: int) -> str:
    return f"{n // 10000:,}만 원"


# ---------- 병원 정보 ----------

def location() -> str:
    loc = HOSPITAL["location"]
    stations = "\n".join(f"- {s['line']} {s['station']} {s['exit']} (도보 약 {s['walk_minutes']}분)"
                         for s in loc["nearest_station"])
    parking = loc["parking"]["detail"] if loc["parking"]["available"] else "주차는 어려워요."
    return (f"**{HOSPITAL['name']}** 오시는 길이에요.\n\n"
            f"📍 {loc['address']}\n\n{loc['directions']}\n\n"
            f"**가까운 역**\n{stations}\n\n**주차** {parking}")


def phone() -> str:
    c = HOSPITAL["contact"]
    return (f"📞 대표번호: **{c['phone']}**\n\n"
            f"💬 카카오톡 채널: {c['kakao_channel']}\n\n{c['consult_hours_note']}")


def hours() -> str:
    h = HOSPITAL["hours"]
    lines = []
    for key, ko in DAYS_KO.items():
        day = h.get(key)
        if day:
            note = f" ({day['note']})" if day.get("note") else ""
            lines.append(f"- {ko}: {day['open']} ~ {day['close']}{note}")
        else:
            lines.append(f"- {ko}: 휴진")
    lunch = h["lunch_break"]
    return ("🕐 **진료시간**\n\n" + "\n".join(lines) +
            f"\n\n점심시간: 평일 {lunch['start']} ~ {lunch['end']}\n\n{h['holidays']}")


def consult_booking() -> str:
    r = HOSPITAL["reservation"]
    return ("상담·예약을 도와드릴게요.\n\n"
            f"**예약 방법**: {', '.join(r['methods'])}\n\n"
            f"📞 {PHONE} 로 전화 주시면 상담 직원이 바로 안내해 드려요.\n\n"
            f"- {r['first_visit_note']}\n- {r['cancellation_policy']}\n\n"
            "수술 결과가 걱정되시거나 내 경우에 맞는 수술이 궁금하시면, 의료진이 직접 보고 안내해 드릴게요.")


# ---------- 시술 ----------

def procedure_list(procedures: list, unsupported: list) -> str:
    parts = []
    if procedures:
        names = ", ".join(PROCEDURES[p]["name"] for p in procedures)
        parts.append(f"네, **{names}** 수술을 하고 있어요.")
    if unsupported:
        parts.append(f"죄송하지만 **{', '.join(unsupported)}**은(는) 저희 병원에서 하지 않아요.")
    if not procedures:
        by_cat = {}
        for p in PROCEDURES.values():
            by_cat.setdefault(p["category"], []).append(p["name"])
        listing = "\n".join(f"- **{cat}**: {', '.join(names)}" for cat, names in by_cat.items())
        parts.append(f"저희 병원은 눈·코 수술을 전문으로 해요.\n\n{listing}")
    return "\n\n".join(parts)


def procedure_info(procedures: list, unsupported: list) -> str:
    parts = []
    for pid in procedures:
        p = PROCEDURES[pid]
        lo, hi = p["price_range_krw"]
        parts.append(
            f"### {p['name']}\n{p['description']}\n\n"
            f"- **이런 분께**: {p['suitable_for']}\n"
            f"- **마취**: {p['anesthesia']}\n"
            f"- **수술 시간**: 약 {p['surgery_time_min']}분 · {p['hospital_stay']}\n"
            f"- **실밥**: {p['stitch_removal']}\n"
            f"- **비용**: {_won(lo)} ~ {_won(hi)}"
            + (f"\n- {p['insurance_note']}" if p.get("insurance_note") else ""))
    if unsupported:
        parts.append(f"**{', '.join(unsupported)}**은(는) 저희 병원에서 하지 않는 수술이에요.")
    if procedures:
        parts.append(f"※ {PROC_DATA['common_policy']['price_disclaimer']}\n\n{MEDICAL_DISCLAIMER}")
    return "\n\n".join(parts)


def aftercare(procedures: list) -> str:
    parts = []
    for pid in procedures:
        p = PROCEDURES[pid]
        r = p["recovery"]
        care = "\n".join(f"- {c}" for c in p["aftercare"])
        warn = ", ".join(p["warning_signs"])
        parts.append(
            f"### {p['name']} 수술 후 관리\n{care}\n\n"
            f"**회복 과정**: 붓기는 {r['swelling_peak']}에 가장 심하고, 일상생활은 {r['daily_life']}, "
            f"자연스러워지기까지 {r['natural_look']} 정도 걸려요.\n\n"
            f"⚠️ **{warn}** 같은 증상이 있으면 기다리지 말고 바로 병원({PHONE})으로 연락해 주세요.")
    parts.append(MEDICAL_DISCLAIMER)
    return "\n\n".join(parts)


# ---------- 안전 / 기타 ----------

def escalate() -> str:
    return ("말씀하신 증상은 챗봇이 안내해 드리기 어려워요. **바로 의료진 확인이 필요해요.**\n\n"
            f"📞 지금 병원으로 연락해 주세요: **{PHONE}**\n\n"
            "진료시간이 아니거나 출혈이 멈추지 않는 경우, 숨쉬기 힘들거나 앞이 잘 보이지 않는 경우에는 "
            "**119** 또는 가까운 응급실로 가 주세요.")


def out_of_scope() -> str:
    return ("죄송하지만 그 질문에는 답변드리기 어려워요. 🙏\n\n"
            "저는 병원 위치·진료시간·연락처, 눈·코 수술 정보, 수술 후 관리, 상담 예약을 안내해 드릴 수 있어요.")


def clarify_intent(options: list) -> Reply:
    return Reply("어떤 내용이 궁금하신지 골라 주세요.",
                 [(INTENT_LABELS_KO[o], {"type": "intent", "value": o}) for o in options])


def clarify_procedure(intent: str, options: list) -> Reply:
    ids = options or list(PROCEDURES)
    topic = "수술 후 관리" if intent == "aftercare" else "수술 정보"
    return Reply(f"어떤 수술의 {topic}가 궁금하세요?",
                 [(PROCEDURES[i]["name"], {"type": "procedure", "value": i}) for i in ids])


def render(decision) -> Reply:
    """router.Decision → Reply. 마크다운에서 '2~3일 … 1~2주'가 취소선이 되지 않게 ~ 를 이스케이프한다."""
    reply = _render(decision)
    reply.text = reply.text.replace("~", "\\~")
    return reply


def _render(decision) -> Reply:
    a, intent = decision.action, decision.intent
    if a == "escalate":
        return Reply(escalate())
    if a == "clarify_intent":
        return clarify_intent(decision.options)
    if a == "clarify_procedure":
        return clarify_procedure(intent, decision.options)

    procs, unsup = decision.procedures, decision.unsupported
    handlers = {
        "location": location,
        "phone": phone,
        "hours": hours,
        "consult_booking": consult_booking,
        "out_of_scope": out_of_scope,
        "procedure_list": lambda: procedure_list(procs, unsup),
        "procedure_info": lambda: procedure_info(procs, unsup),
        "aftercare": lambda: aftercare(procs) if procs else procedure_info([], unsup),
        "side_effect": escalate,
    }
    return Reply(handlers[intent]())
