"""모델 없이 돌아가는 테스트. 실행: python -m pytest tests  (또는 python tests/test_extractor_router.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extractor import ProcedureExtractor
from app.router import decide

ext = ProcedureExtractor()


def probs(**kw):
    """지정 안 한 의도는 0으로 채운 확률 dict"""
    labels = ["location", "phone", "hours", "procedure_list", "aftercare",
              "procedure_info", "consult_booking", "side_effect", "out_of_scope"]
    return {l: kw.get(l, 0.0) for l in labels}


def test_extract_synonym_and_spacing():
    assert ext.extract("지재 하고 렌즈 언제 껴요")["procedures"] == ["EYE07"]
    assert ext.extract("눈밑 지방재배치 가격")["procedures"] == ["EYE07"]
    assert ext.extract("매부리코 교정 얼마예요")["procedures"] == ["NOSE03"]


def test_extract_ambiguous():
    r = ext.extract("쌍수 붓기 언제 빠져요")
    assert r["procedures"] == [] and r["ambiguous"] == ["EYE01", "EYE02"]
    # 구체적인 표현이 있으면 애매함이 풀림
    r = ext.extract("절개 쌍꺼풀 실밥 언제 풀어요")
    assert r["procedures"] == ["EYE02"] and r["ambiguous"] == []


def test_extract_multiple_and_none():
    assert set(ext.extract("콧대랑 코끝 같이 하면 얼마예요")["procedures"]) == {"NOSE01", "NOSE02"}
    assert ext.extract("병원 몇 시까지 해요") == {"procedures": [], "ambiguous": [], "unsupported": []}


def test_extract_unsupported():
    r = ext.extract("뒷트임도 하나요")
    assert r["procedures"] == [] and r["unsupported"] == ["뒷트임"]
    r = ext.extract("앞트임이랑 뒤트임 같이 돼요?")
    assert r["procedures"] == ["EYE04"] and r["unsupported"] == ["뒤트임"]


def test_router_escalate_even_if_not_top():
    d = decide(probs(aftercare=0.6, side_effect=0.35), {"procedures": [], "ambiguous": []})
    assert d.action == "escalate"


def test_router_clarify_intent():
    d = decide(probs(hours=0.48, consult_booking=0.41), {"procedures": [], "ambiguous": []})
    assert d.action == "clarify_intent" and d.options == ["hours", "consult_booking"]


def test_router_clarify_procedure():
    d = decide(probs(aftercare=0.95), ext.extract("쌍수 붓기 언제 빠져요"))
    assert d.action == "clarify_procedure" and d.options == ["EYE01", "EYE02"]
    d = decide(probs(procedure_info=0.95), ext.extract("가격 얼마예요"))
    assert d.action == "clarify_procedure" and d.options == []


def test_router_answer():
    d = decide(probs(aftercare=0.95), ext.extract("매몰 렌즈 언제부터"))
    assert d.action == "answer" and d.procedures == ["EYE01"]
    d = decide(probs(hours=0.97), ext.extract("토요일 해요?"))
    assert d.action == "answer" and d.intent == "hours"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
