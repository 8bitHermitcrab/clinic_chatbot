"""모델 대신 가짜 분류기로 대화 흐름을 테스트한다. 실행: python tests/test_chatbot.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chatbot import Chatbot

LABELS = ["location", "phone", "hours", "procedure_list", "aftercare",
          "procedure_info", "consult_booking", "side_effect", "out_of_scope"]


class FakeClassifier:
    """문장별로 정해 둔 확률을 돌려준다."""
    def __init__(self, table):
        self.table = table

    def predict_proba(self, text):
        probs = {l: 0.0 for l in LABELS}
        probs.update(self.table.get(text, {"out_of_scope": 0.99}))
        return dict(sorted(probs.items(), key=lambda x: x[1], reverse=True))


def make_bot(table):
    return Chatbot(classifier=FakeClassifier(table))


def test_template_answers():
    bot = make_bot({"어디예요": {"location": 0.98}, "몇시까지": {"hours": 0.98}, "번호": {"phone": 0.98}})
    assert "강남대로" in bot.respond("어디예요").reply.text
    assert "휴진" in bot.respond("몇시까지").reply.text
    assert "02-0000-1234" in bot.respond("번호").reply.text


def test_escalate_has_no_advice_and_phone():
    bot = make_bot({"피가 안 멈춰요": {"side_effect": 0.9}})
    t = bot.respond("피가 안 멈춰요")
    assert t.decision.action == "escalate" and "02-0000-1234" in t.reply.text and "119" in t.reply.text
    assert not t.reply.buttons


def test_clarify_procedure_by_button():
    bot = make_bot({"쌍수 붓기 언제 빠져요": {"aftercare": 0.97}})
    t = bot.respond("쌍수 붓기 언제 빠져요")
    assert t.decision.action == "clarify_procedure"
    assert [b[1]["value"] for b in t.reply.buttons] == ["EYE01", "EYE02"]
    t = bot.choose({"type": "procedure", "value": "EYE01"})
    assert t.decision.action == "answer" and "매몰법 쌍꺼풀 수술 후 관리" in t.reply.text
    assert bot.pending is None


def test_clarify_procedure_by_typing():
    bot = make_bot({"가격 얼마예요": {"procedure_info": 0.97}, "코끝이요": {"procedure_info": 0.6, "procedure_list": 0.3}})
    t = bot.respond("가격 얼마예요")
    assert t.decision.action == "clarify_procedure" and len(t.reply.buttons) == 11
    t = bot.respond("코끝이요")     # 확신도가 낮아도 되묻기에 대한 답으로 처리
    assert t.decision.intent == "procedure_info" and "코끝 성형" in t.reply.text and "만 원" in t.reply.text


def test_clarify_intent_then_answer():
    bot = make_bot({"토요일 상담 돼요?": {"hours": 0.48, "consult_booking": 0.41}})
    t = bot.respond("토요일 상담 돼요?")
    assert t.decision.action == "clarify_intent"
    assert [b[1]["value"] for b in t.reply.buttons] == ["hours", "consult_booking"]
    t = bot.choose({"type": "intent", "value": "consult_booking"})
    assert t.decision.intent == "consult_booking" and "예약 방법" in t.reply.text


def test_clarify_intent_then_needs_procedure():
    bot = make_bot({"쌍수 궁금해요": {"aftercare": 0.5, "procedure_info": 0.45}})
    bot.respond("쌍수 궁금해요")
    t = bot.choose({"type": "intent", "value": "procedure_info"})
    assert t.decision.action == "clarify_procedure" and len(t.reply.buttons) == 2
    t = bot.choose({"type": "procedure", "value": "EYE02"})
    assert "절개법 쌍꺼풀" in t.reply.text


def test_unsupported_procedure():
    bot = make_bot({"뒷트임도 하나요": {"procedure_list": 0.97}, "양악 얼마예요": {"procedure_info": 0.95}})
    t = bot.respond("뒷트임도 하나요")
    assert "하지 않아요" in t.reply.text and "앞트임" in t.reply.text
    assert "하지 않는 수술" in bot.respond("양악 얼마예요").reply.text


def test_side_effect_interrupts_pending():
    bot = make_bot({"쌍수 붓기": {"aftercare": 0.97}, "매몰했는데 피가 계속 나요": {"side_effect": 0.9}})
    bot.respond("쌍수 붓기")
    t = bot.respond("매몰했는데 피가 계속 나요")   # 시술명이 있어도 위험 질문이면 병원 연결
    assert t.decision.action == "escalate"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
