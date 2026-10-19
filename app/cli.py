"""터미널에서 질문을 입력해 분류 결과와 처리 방식을 확인한다.

실행: 프로젝트 폴더에서
    python -m app.cli
"""
from app.classifier import IntentClassifier
from app.extractor import ProcedureExtractor
from app.router import INTENT_LABELS_KO, decide


def main():
    print("모델 불러오는 중...")
    clf = IntentClassifier()
    ext = ProcedureExtractor()
    print("질문을 입력하세요. 종료: q\n")

    while True:
        text = input("질문> ").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        if not text:
            continue

        probs = clf.predict_proba(text)
        extracted = ext.extract(text)
        d = decide(probs, extracted)

        top3 = ", ".join(f"{k} {v:.2f}" for k, v in list(probs.items())[:3])
        names = [ext.name(p) for p in extracted["procedures"]]
        amb = [ext.name(p) for p in extracted["ambiguous"]]
        print(f"  의도 확률  : {top3}")
        print(f"  시술       : {names or '-'}" + (f"  (애매: {amb})" if amb else "")
              + (f"  (안 하는 수술: {extracted['unsupported']})" if extracted["unsupported"] else ""))
        print(f"  처리       : {d.action}  [{d.reason}]")
        if d.action == "clarify_intent":
            print("  → 되묻기  :", " / ".join(INTENT_LABELS_KO[o] for o in d.options))
        elif d.action == "clarify_procedure":
            opts = " / ".join(ext.name(o) for o in d.options) or "시술 목록 보여주기"
            print("  → 되묻기  : 어떤 수술이 궁금하세요?", opts)
        print()


if __name__ == "__main__":
    main()
