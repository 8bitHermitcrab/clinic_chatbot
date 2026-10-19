"""대화 한 턴을 처리한다: 분류 → 시술명 추출 → 처리 방식 결정 → 답변.

되묻기 중인 상태(pending)를 기억해서, 사용자가 버튼을 누르거나
"매몰이요"처럼 짧게 답해도 앞 질문과 이어서 처리한다.
화면(Streamlit 등)과 분리되어 있어서 모델 없이도 테스트할 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app import responder
from app.extractor import ProcedureExtractor
from app.router import NEEDS_PROCEDURE, Decision, decide


@dataclass
class Turn:
    reply: responder.Reply
    decision: Decision
    probs: dict = field(default_factory=dict)        # 판단 과정 보기용
    extracted: dict = field(default_factory=dict)


class Chatbot:
    def __init__(self, classifier=None, extractor=None):
        if classifier is None:
            from app.classifier import IntentClassifier   # torch 를 쓰는 무거운 import 는 필요할 때만
            classifier = IntentClassifier()
        self.classifier = classifier
        self.extractor = extractor or ProcedureExtractor()
        self.pending = None   # {"type": "intent"|"procedure", "intent": ..., "extracted": ...}

    def reset(self):
        self.pending = None

    # ----- 사용자가 글을 입력했을 때 -----
    def respond(self, text: str) -> Turn:
        probs = self.classifier.predict_proba(text)
        extracted = self.extractor.extract(text)

        # 시술을 되묻는 중에 "매몰이요"처럼 시술명만 답한 경우 → 앞 질문 의도로 이어서 답변
        if (self.pending and self.pending["type"] == "procedure"
                and extracted["procedures"] and probs.get("side_effect", 0) < 0.3):
            return self._answer_pending_procedure(extracted["procedures"], probs, extracted)

        decision = decide(probs, extracted)
        return self._finish(decision, probs, extracted)

    # ----- 사용자가 되묻기 버튼을 눌렀을 때 -----
    def choose(self, payload: dict) -> Turn:
        if not self.pending:
            return self._finish(Decision("answer", "out_of_scope"), {}, {})

        if payload["type"] == "intent":
            intent = payload["value"]
            extracted = self.pending["extracted"]
            procs = extracted.get("procedures", [])
            if intent in NEEDS_PROCEDURE and not procs and not extracted.get("unsupported"):
                decision = Decision("clarify_procedure", intent, options=extracted.get("ambiguous", []),
                                    reason="의도 선택 후 시술명 필요")
            else:
                decision = Decision("answer", intent, procedures=procs,
                                    unsupported=extracted.get("unsupported", []), reason="사용자가 의도 선택")
            return self._finish(decision, {}, extracted)

        return self._answer_pending_procedure([payload["value"]], {}, {})

    # ----- 내부 -----
    def _answer_pending_procedure(self, procedures, probs, extracted) -> Turn:
        decision = Decision("answer", self.pending["intent"], procedures=procedures,
                            reason="되묻기에 대한 답")
        return self._finish(decision, probs, extracted)

    def _finish(self, decision: Decision, probs: dict, extracted: dict) -> Turn:
        if decision.action == "clarify_intent":
            self.pending = {"type": "intent", "intent": None, "extracted": extracted}
        elif decision.action == "clarify_procedure":
            self.pending = {"type": "procedure", "intent": decision.intent, "extracted": extracted}
        else:
            self.pending = None
        return Turn(responder.render(decision), decision, probs, extracted)
