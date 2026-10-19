"""터미널에서 챗봇과 대화해 본다. 되묻기 선택지는 번호로 고른다.

실행: 프로젝트 폴더에서
    python -m app.cli
"""
from app.chatbot import Chatbot
from app.router import INTENT_LABELS_KO


def print_turn(turn, bot):
    d = turn.decision
    if turn.probs:
        top3 = ", ".join(f"{k} {v:.2f}" for k, v in list(turn.probs.items())[:3])
        print(f"  [의도] {top3}")
    ex = turn.extracted or {}
    if any(ex.get(k) for k in ("procedures", "ambiguous", "unsupported")):
        print(f"  [시술] {[bot.extractor.name(p) for p in ex.get('procedures', [])]}"
              f" 애매:{[bot.extractor.name(p) for p in ex.get('ambiguous', [])]}"
              f" 안 함:{ex.get('unsupported', [])}")
    print(f"  [처리] {d.action} ({d.reason})\n")
    print(turn.reply.text.replace("\\~", "~"))
    for i, (label, _) in enumerate(turn.reply.buttons, 1):
        print(f"   {i}. {label}")
    print()


def main():
    print("모델 불러오는 중...")
    bot = Chatbot()
    print("질문을 입력하세요. 선택지가 나오면 번호를 입력하세요. 종료: q\n")

    last_buttons = []
    while True:
        text = input("나> ").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        if not text:
            continue
        if text.isdigit() and last_buttons and 1 <= int(text) <= len(last_buttons):
            turn = bot.choose(last_buttons[int(text) - 1][1])
        else:
            turn = bot.respond(text)
        print_turn(turn, bot)
        last_buttons = turn.reply.buttons


if __name__ == "__main__":
    main()
