"""질문에서 시술명을 찾아 procedures.json 의 시술 ID로 바꾼다.

예) "쌍수 붓기 언제 빠져요"   → ambiguous: ["EYE01", "EYE02"] (매몰인지 절개인지 모름)
    "지재 하고 렌즈 껴도 돼요" → procedures: ["EYE07"]
    "뒷트임도 하나요"          → unsupported: ["뒷트임"] (이 병원에서 안 하는 수술)

모델 없이 사전(동의어 목록)으로 찾는 방식. 나중에 NER 모델과 비교할 기준선이 된다.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCEDURES_PATH = ROOT / "data" / "procedures.json"

# procedures.json 에 없는 줄임말·오타
EXTRA_ALIASES = {
    "지재": "EYE07",
    "눈밑지방": "EYE07",
    "부분매몰": "EYE01",
    "콧대수술": "NOSE01",
    "코끝수술": "NOSE02",
    # 시술명 대신 고민(증상)으로 말하는 경우
    "안검하수": "EYE03",
    "몽고주름": "EYE04",
    "처진눈꺼풀": "EYE05",
    "눈밑꺼진": "EYE07",
    "다크서클": "EYE07",
    "복코": "NOSE02",
    "코높이": "NOSE01",
    "코막힘": "NOSE04",
    # 이 병원에서 보형물을 쓰는 수술은 콧대뿐
    "보형물": "NOSE01",
    "실리콘": "NOSE01",
}

# 어떤 시술인지 하나로 정할 수 없는 표현. 매칭되면 사용자에게 되물어야 한다.
AMBIGUOUS_ALIASES = {
    "쌍수": ["EYE01", "EYE02"],
    "쌍꺼풀": ["EYE01", "EYE02"],
    "쌍커풀": ["EYE01", "EYE02"],
}

# 이 병원에서 하지 않는 수술. '뒷트임'이 '트임'·'앞트임'으로 잘못 잡히지 않게 먼저 걸러낸다
UNSUPPORTED = ["뒷트임", "뒤트임", "밑트임", "부분절개", "자연유착", "눈썹거상", "안면거상",
               "지방이식", "지방흡입", "양악", "윤곽", "광대", "사각턱", "콧볼축소", "가슴성형", "가슴수술"]


def _normalize(text: str) -> str:
    """띄어쓰기를 지워서 '눈밑 지방재배치'와 '눈밑지방재배치'를 같게 본다."""
    return re.sub(r"\s+", "", text)


class ProcedureExtractor:
    def __init__(self, path=PROCEDURES_PATH):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.procedures = {p["id"]: p for p in data["procedures"]}

        alias_to_ids = {}
        for p in data["procedures"]:
            for alias in [p["name"], *p.get("synonyms", [])]:
                alias_to_ids[_normalize(alias)] = [p["id"]]
        for alias, pid in EXTRA_ALIASES.items():
            alias_to_ids[_normalize(alias)] = [pid]
        # 애매한 표현은 개별 시술 동의어보다 우선 (procedures.json 에 '쌍수'가 EYE01로 들어가 있어도 덮어씀)
        for alias, ids in AMBIGUOUS_ALIASES.items():
            alias_to_ids[_normalize(alias)] = ids

        for alias in UNSUPPORTED:
            alias_to_ids[_normalize(alias)] = ["UNSUPPORTED:" + alias]

        # 긴 표현부터 찾아야 '매부리코'가 '매부리'보다 먼저 잡힌다
        self.aliases = sorted(alias_to_ids.items(), key=lambda x: len(x[0]), reverse=True)

    def extract(self, text: str) -> dict:
        norm = _normalize(text)
        used = [False] * len(norm)
        found, ambiguous, unsupported = [], [], []

        for alias, ids in self.aliases:
            start = norm.find(alias)
            while start != -1:
                end = start + len(alias)
                if not any(used[start:end]):          # 이미 더 긴 표현으로 잡힌 자리는 건너뜀
                    used[start:end] = [True] * len(alias)
                    if ids[0].startswith("UNSUPPORTED:"):
                        unsupported.append(ids[0].split(":", 1)[1])
                        start = norm.find(alias, end)
                        continue
                    target = found if len(ids) == 1 else ambiguous
                    for pid in ids:
                        if pid not in target:
                            target.append(pid)
                start = norm.find(alias, end)

        # '절개 쌍꺼풀'처럼 구체적인 표현이 같이 있으면 애매함이 풀림
        ambiguous = [] if any(pid in found for pid in ambiguous) else ambiguous
        return {"procedures": found, "ambiguous": ambiguous, "unsupported": unsupported}

    def name(self, pid: str) -> str:
        return self.procedures[pid]["name"]
