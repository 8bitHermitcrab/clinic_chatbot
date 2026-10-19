"""성형외과 상담 챗봇 데모 화면.

실행: 프로젝트 폴더에서
    streamlit run streamlit_app.py
"""
import streamlit as st

from app.chatbot import Chatbot
from app.responder import HOSPITAL, INTENT_LABELS_KO

st.set_page_config(page_title=f"{HOSPITAL['name']} 상담 챗봇", page_icon="💬")

WELCOME = (f"안녕하세요, **{HOSPITAL['name']}** 상담 챗봇이에요. 😊\n\n"
           "병원 위치·진료시간, 눈·코 수술 정보, 수술 후 관리, 상담 예약을 안내해 드려요.")
EXAMPLES = ["강남역 몇 번 출구로 가요?", "쌍수 붓기 언제 빠져요", "매몰이랑 절개 차이가 뭐예요",
            "지재 하고 렌즈 언제 껴도 돼요", "뒷트임도 하나요?", "수술 부위에서 피가 계속 나요"]
ACTION_KO = {"answer": "바로 답변", "escalate": "⚠️ 병원 연결 (위험 질문)",
             "clarify_intent": "되묻기 (의도가 애매함)", "clarify_procedure": "되묻기 (시술명 필요)"}


@st.cache_resource(show_spinner="모델을 불러오는 중이에요...")
def load_classifier():
    """모델은 무거우니 한 번만 불러와서 모든 사용자가 같이 쓴다."""
    from app.classifier import IntentClassifier
    return IntentClassifier()


# 대화 상태(되묻기 중인지 등)는 사용자마다 따로 가진다
if "bot" not in st.session_state:
    st.session_state.bot = Chatbot(classifier=load_classifier())
    st.session_state.messages = [{"role": "assistant", "text": WELCOME}]
bot: Chatbot = st.session_state.bot


def add_turn(user_text: str, turn):
    st.session_state.messages.append({"role": "user", "text": user_text})
    st.session_state.messages.append({
        "role": "assistant", "text": turn.reply.text, "buttons": turn.reply.buttons,
        "debug": {"action": turn.decision.action, "intent": turn.decision.intent,
                  "reason": turn.decision.reason, "probs": turn.probs, "extracted": turn.extracted},
    })


def show_debug(d: dict):
    with st.expander("🔍 판단 과정"):
        st.caption(f"처리 방식: **{ACTION_KO.get(d['action'], d['action'])}** — {d['reason']}")
        for intent, p in list(d["probs"].items())[:3]:
            st.progress(float(p), text=f"{INTENT_LABELS_KO.get(intent, intent)} ({intent}) {p:.2f}")
        ex = d["extracted"] or {}
        names = [bot.extractor.name(p) for p in ex.get("procedures", [])]
        amb = [bot.extractor.name(p) for p in ex.get("ambiguous", [])]
        st.caption(f"찾은 시술: {', '.join(names) or '-'}"
                   + (f" · 애매함: {', '.join(amb)}" if amb else "")
                   + (f" · 안 하는 수술: {', '.join(ex['unsupported'])}" if ex.get("unsupported") else ""))


# ----- 사이드바 -----
with st.sidebar:
    st.subheader(HOSPITAL["name"])
    st.caption("포트폴리오용 데모예요. 병원·연락처·가격은 모두 가상 정보이며, 안내 내용은 진료를 대신하지 않아요.")
    debug_on = st.toggle("판단 과정 보기", value=True)
    st.divider()
    st.caption("이런 질문을 해보세요")
    for ex in EXAMPLES:
        if st.button(ex, width="stretch"):
            add_turn(ex, bot.respond(ex))
            st.rerun()
    st.divider()
    if st.button("대화 새로 시작", width="stretch"):
        bot.reset()
        st.session_state.messages = [{"role": "assistant", "text": WELCOME}]
        st.rerun()

# ----- 대화 -----
messages = st.session_state.messages
for i, m in enumerate(messages):
    with st.chat_message(m["role"]):
        st.markdown(m["text"])
        if debug_on and m.get("debug"):
            show_debug(m["debug"])
        # 되묻기 버튼은 마지막 답변에만 보여준다
        if m.get("buttons") and i == len(messages) - 1:
            cols = st.columns(min(len(m["buttons"]), 3))
            for j, (label, payload) in enumerate(m["buttons"]):
                if cols[j % len(cols)].button(label, key=f"btn-{i}-{j}", width="stretch"):
                    add_turn(label, bot.choose(payload))
                    st.rerun()

if text := st.chat_input("궁금한 점을 입력하세요"):
    add_turn(text, bot.respond(text))
    st.rerun()
