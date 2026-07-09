"""
Nowhere Data Pipeline - Streamlit 대시보드 (Toss 스타일 리포트형 UI, 라이트/다크 토글)

실행: streamlit run app/dashboard.py --server.port 8501

구현 노트:
- Streamlit은 st.markdown()으로 연 <div>를 다른 st.* 호출 사이에 두고 별도
  st.markdown()으로 닫을 수 없다 (각 호출이 독립된 DOM으로 렌더링되어 카드가
  빈 채로 쪼개짐). 카드 안에 차트가 들어가는 경우 matplotlib figure를 base64
  PNG로 변환해 설명 텍스트와 하나의 st.markdown() 호출로 묶는다.
- 라이트/다크 모드는 st.session_state로 전환하며, 우측 하단 원형 버튼(유일한
  st.button)으로 토글한다. 팔레트를 딕셔너리로 분리해 CSS와 matplotlib 차트
  양쪽에 동일하게 적용한다.
"""
import os
import io
import re
import html
import base64
import streamlit as st
import pandas as pd
import anthropic
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import matplotlib.pyplot as plt

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False

st.set_page_config(page_title="Nowhere Data Pipeline", layout="wide", page_icon="🗺️")

DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = 5432
DB_NAME = "crowd_pipeline"


@st.cache_resource
def get_engine():
    return create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def table_exists(engine, table_name: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
        ), {"t": table_name})
        return result.scalar()


engine = get_engine()

# =========================================================
# 라이트/다크 팔레트
# =========================================================
LIGHT = dict(
    bg="#F2F4F6", card="#FFFFFF", text1="#191F28", text2="#4E5968", text3="#8B95A1",
    border="#E5E8EB", blue="#3182F6", blue_dark="#1B64DA", mint="#05A88E", gray="#B0B8C1",
    badge_bg="#E8F3FF", shadow="rgba(0,0,0,0.04)", header_bg="#F2F4F6",
    info_bg="#E8F3FF", info_text="#1B64DA", mint_rgb="5,168,142", blue_rgb="49,130,246",
)
DARK = dict(
    bg="#101216", card="#1C1F26", text1="#F2F4F6", text2="#B0B8C1", text3="#7C8592",
    border="#2B2F38", blue="#5B9DFF", blue_dark="#3182F6", mint="#2FE1C4", gray="#545B66",
    badge_bg="#1A2C4A", shadow="rgba(0,0,0,0.35)", header_bg="#101216",
    info_bg="#1A2C4A", info_text="#EAF2FF", mint_rgb="47,225,196", blue_rgb="91,157,255",
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

P = DARK if st.session_state.dark_mode else LIGHT
# 메인 타이틀: 다크모드에서는 화이트 계열로, 라이트모드에서는 기존 진한 텍스트 톤 유지
title_color = "#FFFFFF" if st.session_state.dark_mode else P["text1"]

# =========================================================
# 전역 CSS 주입 (팔레트 변수 반영)
# =========================================================
st.markdown(f"""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

html, body, [class*="css"] {{
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}}

.stApp {{ background: {P['bg']}; }}
.block-container {{ padding-top: 2.2rem; max-width: 1180px; }}

/* Streamlit 기본 상단바(햄버거 메뉴/Deploy 버튼 등, [data-testid="stToolbar"]를 담고 있는 요소)
   완전히 숨김 — 개발자도구로 실제 selector(header[data-testid="stHeader"]) 확인 후 적용.
   .streamlit/config.toml의 toolbarMode="minimal"과 이중 안전장치. */
header[data-testid="stHeader"] {{ display: none !important; }}

.eyebrow {{
    font-size: 14px; font-weight: 700; color: {P['blue']};
    letter-spacing: 0.3px; margin-top: 8px; margin-bottom: 8px;
}}
.page-title {{
    font-size: 30px; font-weight: 800; letter-spacing: -0.6px;
    color: {title_color}; margin-bottom: 4px; line-height: 1.35;
}}
.page-subtitle {{ font-size: 15.5px; color: {P['text2']}; margin-bottom: 28px; }}

.hero-card {{
    background: linear-gradient(135deg, {P['blue']} 0%, {P['blue_dark']} 100%);
    border-radius: 24px; padding: 36px 40px; color: white;
    margin-bottom: 18px; box-shadow: 0 8px 24px rgba(49,130,246,0.22);
}}
.hero-label {{ font-size: 14.5px; font-weight: 600; opacity: 0.88; margin-bottom: 10px; }}
.hero-main {{ display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }}
.hero-number {{ font-size: 52px; font-weight: 800; letter-spacing: -1.2px;
    font-variant-numeric: tabular-nums; line-height: 1; }}
.hero-place {{ font-size: 26px; font-weight: 700; opacity: 0.95; }}
.hero-desc {{ font-size: 14.5px; opacity: 0.92; margin-top: 14px; line-height: 1.6; }}

.stat-card {{
    background: {P['card']}; border-radius: 18px; padding: 22px 26px;
    box-shadow: 0 2px 8px {P['shadow']}; height: 100%; border: 1px solid {P['border']};
}}
.stat-label {{ font-size: 13.5px; color: {P['text3']}; font-weight: 600; margin-bottom: 6px; }}
.stat-number {{ font-size: 28px; font-weight: 800; letter-spacing: -0.8px; color: {P['text1']}; }}
.stat-number.positive {{ color: {P['mint']}; }}
.stat-sub {{ font-size: 12.5px; color: {P['text3']}; margin-top: 5px; }}

.section-card {{
    background: {P['card']}; border-radius: 20px; padding: 30px 32px;
    margin-bottom: 18px; box-shadow: 0 2px 8px {P['shadow']}; border: 1px solid {P['border']};
}}
.section-title {{ font-size: 18.5px; font-weight: 700; color: {P['text1']}; margin-bottom: 8px; }}
.section-desc {{ font-size: 14.5px; color: {P['text2']}; line-height: 1.75; margin-bottom: 18px; }}
.section-card img {{ width: 100%; border-radius: 12px; margin-top: 4px; }}

.badge {{
    display: inline-block; background: {P['badge_bg']}; color: {P['blue']};
    font-size: 12px; font-weight: 700; padding: 3px 11px; border-radius: 999px;
    margin-left: 6px; vertical-align: middle;
}}

/* GNB 탭: 꽉 찬 사각형/캡슐 배경 대신 하단 밑줄 하이라이트 방식의 플랫 GNB 스타일
   (Streamlit 최신 버전은 data-baseweb="tab" 대신 data-testid="stTab" / role="tablist"를 사용) */
.stTabs [role="tablist"] {{
    gap: 28px; background: transparent; margin-bottom: 26px;
    border-bottom: 1px solid {P['border']};
}}
.stTabs [data-testid="stTab"] {{
    background: transparent !important; border-radius: 0; padding: 10px 2px 14px 2px !important;
    font-weight: 600; font-size: 15px; color: {P['text2']} !important; border: none !important;
    border-bottom: 2px solid transparent !important;
    display: flex; align-items: center; line-height: 1.3;
    transition: color 0.15s ease, border-color 0.15s ease;
}}
.stTabs [data-testid="stTab"] * {{ color: inherit !important; }}
.stTabs [data-testid="stTab"]:hover {{ color: {P['text1']} !important; }}
.stTabs [data-testid="stTab"] p {{
    display: flex; align-items: center; gap: 7px; margin: 0; color: inherit;
}}
/* 활성 탭: 배경 없이 밝은 글자 + 톤다운된 블루 밑줄만 (다크모드에서 흰 박스로 튀어 보이던 것 수정,
   원색 그대로면 너무 튀어서 opacity를 낮춰 톤다운) */
.stTabs [data-testid="stTab"][aria-selected="true"] {{
    background: transparent !important; color: {P['text1']} !important;
    border-bottom: 2px solid rgba({P['blue_rgb']}, 0.55) !important;
}}

/* 아코디언(Expander): 헤더 배경/글자/화살표 아이콘 명도 대비 확보 (다크모드에서 텍스트가 안 보이던 문제 수정) */
div[data-testid="stExpander"] {{ border-radius: 16px; border: 1px solid {P['border']}; background: {P['card']}; overflow: hidden; }}
div[data-testid="stExpander"] summary {{ background: {P['card']} !important; color: {P['text1']} !important; }}
div[data-testid="stExpander"] summary:hover {{ background: {P['bg']} !important; }}
div[data-testid="stExpander"] summary p {{ color: {P['text1']} !important; font-weight: 600; }}
div[data-testid="stExpander"] summary svg {{ fill: {P['text1']} !important; color: {P['text1']} !important; }}
div[data-testid="stExpander"] details {{ background: {P['card']}; }}

div[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}

/* 경고/안내 배너(st.info 등): 배경-글자 명도 대비 확보 (다크모드에서 어두운 파랑끼리 겹쳐 안 보이던 문제 수정) */
div[data-testid="stAlert"] {{
    border-radius: 14px; background: {P['info_bg']} !important; border: 1px solid {P['border']};
}}
div[data-testid="stAlert"] p {{ color: {P['info_text']} !important; }}
div[data-testid="stAlert"] svg {{ color: {P['info_text']} !important; fill: {P['info_text']} !important; }}

/* 차트/이미지 우측 상단의 Streamlit 기본 툴바(전체화면 버튼 등) 정돈 — 본문과 겹치지 않게 카드 톤에 맞춤 */
[data-testid="StyledFullScreenButton"], [data-testid="stElementToolbar"] {{
    background: {P['card']} !important; border: 1px solid {P['border']}; border-radius: 8px;
    top: 10px !important; right: 10px !important;
}}
[data-testid="StyledFullScreenButton"] svg, [data-testid="stElementToolbar"] svg {{
    fill: {P['text2']} !important; color: {P['text2']} !important;
}}

/* 결론 강조 카드: 히어로 카드(파랑)와 색으로 연결되도록 최적값 카드에 민트 테두리/글로우 부여 */
.stat-card.highlight {{
    border: 1.5px solid {P['mint']};
    box-shadow: 0 0 0 3px rgba({P['mint_rgb']}, 0.12);
}}

/* 플로팅 채팅 토글 버튼: 화면 우측 하단 상시 고정 (제일 아래) */
.st-key-chat_toggle_btn {{
    position: fixed; bottom: 28px; right: 28px; z-index: 9999; width: auto;
}}
.st-key-chat_toggle_btn button {{
    border-radius: 50%; width: 50px; height: 50px; padding: 0;
    background: #FFFFFF; border: 1.5px solid {P['border']}; color: {P['blue']};
    box-shadow: 0 6px 18px rgba(0,0,0,0.18); font-size: 21px;
}}

/* 라이트/다크 토글 버튼: 채팅 버튼 바로 위에 쌓아서 배치 */
.st-key-theme_toggle_btn {{
    position: fixed; bottom: 90px; right: 28px; z-index: 9999; width: auto;
}}
.st-key-theme_toggle_btn button {{
    border-radius: 50%; width: 50px; height: 50px; padding: 0;
    background: #FFFFFF; border: 1.5px solid {P['border']}; color: {P['blue']};
    box-shadow: 0 4px 14px rgba(0,0,0,0.15); font-size: 21px;
}}

/* 플로팅 채팅 패널: 흰 배경 + 카카오톡 스타일 말풍선 */
.st-key-chat_popup_container {{
    position: fixed !important; bottom: 152px; right: 28px; z-index: 9998;
    width: 420px; max-height: 700px;
    background: #FFFFFF !important;
    border: 1px solid #E5E8EB !important; border-radius: 20px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.16) !important;
    overflow: hidden !important; padding: 0 !important;
}}
@media (max-width: 480px) {{
    .st-key-chat_popup_container {{ width: calc(100vw - 40px); right: 20px; bottom: 148px; }}
}}
/* 닫기(✕) 버튼: 소형 투명 버튼 */
.st-key-chat_close_btn button {{
    background: transparent !important; border: none !important;
    color: #8B95A1 !important; font-size: 14px !important;
    padding: 4px 8px !important; border-radius: 6px !important;
    min-height: unset !important; height: 32px !important;
}}
.st-key-chat_close_btn button:hover {{ background: #F2F4F6 !important; color: #191F28 !important; }}
/* 채팅 입력창: 패널 하단에 구분선 + 둥근 모서리 */
.st-key-chat_popup_container [data-testid="stChatInput"] {{
    border-top: 1px solid #E5E8EB !important;
    border-radius: 0 0 20px 20px !important;
    background: #FAFAFA !important;
    padding: 6px 14px 10px !important;
}}
</style>
""", unsafe_allow_html=True)


def toggle_theme():
    st.session_state.dark_mode = not st.session_state.dark_mode


def toggle_chat():
    st.session_state.chat_open = not st.session_state.chat_open


if "chat_open" not in st.session_state:
    st.session_state.chat_open = False
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "_pending_q" not in st.session_state:
    st.session_state._pending_q = None


def fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=P["card"])
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def file_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def hero_card_number(label: str, number: str, unit: str, desc: str):
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-label">{label}</div>
        <div class="hero-main"><span class="hero-number">{number}</span><span class="hero-place">{unit}</span></div>
        <div class="hero-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def stat_card(label: str, number: str, sub: str, positive: bool = False, highlight: bool = False):
    cls = "stat-number positive" if positive else "stat-number"
    card_cls = "stat-card highlight" if highlight else "stat-card"
    st.markdown(f"""
    <div class="{card_cls}">
        <div class="stat-label">{label}</div>
        <div class="{cls}">{number}</div>
        <div class="stat-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def section_card_with_image(title: str, desc: str, fig, badge: str = ""):
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    b64 = fig_to_base64(fig)
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">{title}{badge_html}</div>
        <div class="section-desc">{desc}</div>
        <img src="data:image/png;base64,{b64}">
    </div>
    """, unsafe_allow_html=True)


def section_text_card(title: str, desc: str, badge: str = ""):
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="section-card" style="margin-bottom: 8px;">
        <div class="section-title">{title}{badge_html}</div>
        <div class="section-desc" style="margin-bottom: 0;">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def style_axes(ax):
    ax.set_facecolor(P["card"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(P["border"])
    ax.spines["bottom"].set_color(P["border"])
    ax.tick_params(colors=P["text3"])
    ax.xaxis.label.set_color(P["text2"])
    ax.yaxis.label.set_color(P["text2"])
    ax.grid(alpha=0.25, color=P["border"])


# =========================================================
# 프로젝트 개요 탭 하단 Q&A 위젯용 시스템 프롬프트 (Claude Haiku)
# =========================================================
QA_SYSTEM_PROMPT = """당신은 "Nowhere Data Pipeline" 대시보드에 내장된 안내 도우미입니다.
이 프로젝트를 처음 접하는 평가자, 교수님, 발표 관람자의 질문에
아래에 제공된 사실만을 근거로, '-입니다'체를 사용하여 답변하십시오.
발표자가 청중에게 차분하게 설명하는 톤으로 답변하십시오.

[반드시 지켜야 할 형식 규칙]
- 마크다운 헤딩(#, ##, ###)은 절대 사용하지 마십시오.
- 마크다운을 적극 활용하십시오. 나열할 항목이 3개 이상이면 리스트(-, 1.)로 정리하고, 핵심 키워드나 수치는 **볼드**로 강조하십시오.
- 문단은 2~3문장 이내로 짧게 끊으십시오.
- 인사말("안녕하세요" 등)로 시작하지 말고 바로 질문에 답변하십시오.

아래에 명시되지 않은 내용은 추측하지 말고
"이 부분은 정확한 내용을 파악하기 어렵습니다. README나 보고서를 참고해 주십시오."라고 말씀드리십시오.

## 프로젝트 개요
Nowhere는 CBNU SW캡스톤 졸업 프로젝트로 만든 Geofencing 기반 실시간 혼잡도 제보
앱이다. 학식·도서관·카페 같은 캠퍼스 거점의 혼잡도를 사용자가 제보하면, 근처의
다른 사용자들이 "맞아요/틀려요"로 검증한다(Peer Review). 이 검증 결과에 따라
제보자의 신뢰도 점수(Trust Score)가 조정된다.

## 이 파이프라인이 존재하는 이유
서비스가 아직 런칭 전이라 실사용자 데이터가 없다. Trust Score의 반대 임계값을
얼마로 정해야 합리적인지 검증할 데이터가 없었기 때문에, 실제 백엔드 스키마와
정책을 기반으로 시뮬레이션 데이터를 만들어 미리 검증했다.

## 실제 서비스 동작 흐름
1. 사용자 A가 혼잡도를 제보하면 지도에 즉시 반영된다
2. 근처의 사용자 B, C, D가 그 제보를 검증한다 (맞아요/틀려요)
3. 검증 결과는 SSE(실시간 스트리밍)로 접속 중인 모든 사용자에게 전달된다
4. 제보 유효시간이 끝나면 서버가 배치로 제보자의 Trust Score를 자동 갱신한다

## 트랙 A - Trust Score 임계값 분석
- 질문: "반대가 몇 개 모이면 신뢰도를 깎아야 할까?"
- 방법: 시뮬레이션 데이터로 반대 임계값을 1~10까지 바꿔가며, Trust Score가
  유저의 실제 정확도(true_accuracy, 숨겨진 정답값)와 얼마나 상관관계가 있는지 검증
- 결과: 임계값 1이 10회 반복 시뮬레이션에서 항상 1등이었다 (현재 정책값인 3보다
  실제 정확도를 더 잘 구별함)
- Trust Score 설계: 기본점수 50, 만점 100, 동의 1개당 +1, 반대 3개까지는 무사,
  초과분마다 -1 (이는 팀이 검토 중인 확장 설계이며, 현재 배포된 코드의 정책과는
  다를 수 있음 - 현재 배포 코드는 기본값 0, 동의 미반영, 반대 3개 이상이면
  flat -1)

## 트랙 B - 시공간 혼잡도 패턴 분석
- 방법: 장소×시간대별 혼잡도 패턴을 PostGIS 공간 쿼리로 분석하고, 기상청
  공공데이터(날씨)를 결합
- 혼잡도는 실제 서비스와 동일하게 LOW/MEDIUM/HIGH 3단계 카테고리로 표현
- 결과: 점심시간(12-13시)과 저녁시간(18-19시)에 전체 장소에서 공통적으로 혼잡도가
  높아지는 패턴이 뚜렷하게 관찰됨. 한빛식당(학식)의 혼잡도가 전반적으로 높음
- 날씨 데이터는 기상청 공공데이터포털 API로 매시간 자동 수집(cron)하지만, 혼잡도
  데이터가 합성(시뮬레이션)이라 날씨와의 실질적 상관관계 분석은 아직 하지 않음

## 인프라
OCI vm-03(Oracle Linux 8, 2 OCPU/16GB) 위에 PostgreSQL 16 + PostGIS로 데이터를
저장하고, Python으로 시뮬레이션 데이터를 생성·분석했다. Streamlit으로 대시보드를
만들고 nginx 리버스 프록시로 외부에 공개했다. Object Storage에 원본 데이터를
백업한다.

## 데이터에 대한 중요한 한계
모든 수치는 합성(시뮬레이션) 데이터 기준이며 실사용자 데이터가 아니다. 서비스
런칭 후 같은 파이프라인에 실데이터를 흘려보내 정책을 재조정할 계획이다.

## 관련 링크
GitHub: https://github.com/CBNU-SWCapstone-B5-TJTS-now/data-pipeline
"""


def _md_to_html(text: str) -> str:
    """Claude 응답의 마크다운을 HTML로 변환 (헤딩·굵게·기울임·취소선·코드·줄바꿈)"""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 헤딩 — 줄바꿈 변환 전에 처리해야 ^ $ 앵커가 정상 작동함
    _h = 'font-weight:700;display:block;margin:6px 0 2px;'
    text = re.sub(r'^### (.+)$', rf'<span style="{_h}font-size:13px">\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$',  rf'<span style="{_h}font-size:13.5px">\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$',   rf'<span style="{_h}font-size:14px">\1</span>',   text, flags=re.MULTILINE)
    # 리스트 아이템 (-/* unordered, 1. ordered) — 줄바꿈 변환 전에 처리
    _li = 'display:block;padding-left:14px;text-indent:-10px;margin:1px 0;'
    text = re.sub(r'^[-*] (.+)$', rf'<span style="{_li}">&#8226;&ensp;\1</span>', text, flags=re.MULTILINE)
    text = re.sub(r'^(\d+)\. (.+)$', rf'<span style="{_li}">\1.&ensp;\2</span>', text, flags=re.MULTILINE)
    # 인라인 서식
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
    text = re.sub(r'\*((?!\s)[^*]+(?<!\s))\*', r'<em>\1</em>', text)
    text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
    text = re.sub(
        r'`([^`]+)`',
        r'<code style="background:#F2F4F6;padding:1px 5px;border-radius:4px;font-size:12px">\1</code>',
        text,
    )
    text = text.replace("\n\n", '<br>').replace("\n", '<br>')
    return text


# ── 말풍선 HTML 스니펫 ────────────────────────────────────────────────
_BUBBLE_USER = (
    '<div style="display:flex;justify-content:flex-end;padding:3px 16px 3px;">'
    '<div style="background:#DCF8C6;border-radius:18px 4px 18px 18px;'
    'padding:10px 14px;max-width:78%;font-size:13.5px;color:#191F28;line-height:1.6;">'
    '{content}</div></div>'
)
_BUBBLE_BOT = (
    '<div style="display:flex;justify-content:flex-start;padding:3px 16px 3px;">'
    '<div style="background:#F2F4F6;border:1px solid #E5E8EB;border-radius:4px 18px 18px 18px;'
    'padding:10px 14px;max-width:78%;font-size:13.5px;color:#4E5968;line-height:1.5;">'
    '{content}</div></div>'
)


def render_floating_chat():
    """화면 우측 하단 상시 고정 채팅 버블.
    with tab_x: 블록 밖(페이지 전역)에서 호출해야 탭을 바꿔도 계속 보인다."""
    st.button("💬", on_click=toggle_chat, help="이 프로젝트에 대해 물어보기", key="chat_toggle_btn")

    if not st.session_state.chat_open:
        return

    with st.container(key="chat_popup_container"):
        # ── 헤더: 제목 + 닫기(✕) 버튼 ──────────────────────────────
        col_title, col_close = st.columns([6, 1])
        with col_title:
            st.markdown("""
            <div style="padding:16px 4px 6px 20px;">
                <div style="font-size:15px; font-weight:700; color:#191F28; line-height:1.4;">
                    💬 이 프로젝트에 대해 물어보세요
                </div>
                <div style="font-size:12px; color:#8B95A1; margin-top:3px;">
                    Claude(Anthropic)가 이 대시보드 내용을 바탕으로 답변해드립니다.
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_close:
            st.button("✕", on_click=toggle_chat, key="chat_close_btn")

        # ── 대화 이력 (카카오톡 스타일 말풍선, flex-column-reverse로 최신글 항상 하단 표시) ──
        if not st.session_state.qa_history and not st.session_state._pending_q:
            st.markdown(
                '<div style="padding:6px 20px 8px;font-size:12.5px;color:#8B95A1;line-height:1.8;">'
                "예시 질문:<br>"
                "· Nowhere가 무슨 프로젝트인가요?<br>"
                "· 트랙 A 결과가 무슨 의미인가요?<br>"
                "· 어떤 기술 스택을 사용했나요?"
                "</div>",
                unsafe_allow_html=True,
            )

        # flex-direction:column-reverse 로 최신 Q&A 쌍이 항상 하단에 보이게 함.
        # 각 쌍을 <div>로 래핑해야 column-reverse가 쌍 간 순서만 역전시키고
        # 쌍 내부(user→bot)의 순서는 그대로 유지된다.
        history_html = "".join(
            '<div>'
            + _BUBBLE_USER.format(content=html.escape(item["q"]))
            + _BUBBLE_BOT.format(content=_md_to_html(item["a"]))
            + '</div>'
            for item in reversed(st.session_state.qa_history)
        )
        if history_html:
            st.markdown(
                '<div style="max-height:420px;overflow-y:auto;padding:4px 0;'
                'display:flex;flex-direction:column-reverse;">'
                f'{history_html}</div>',
                unsafe_allow_html=True,
            )

        # ── 대기 중인 질문 처리 (입력창 위 위치에서 스트리밍) ──────────
        # st.chat_input() 보다 먼저 렌더링되어야 스트리밍이 입력창 아래로 튀지 않음
        if st.session_state._pending_q:
            pending_q = st.session_state._pending_q
            st.session_state._pending_q = None  # 중복 실행 방지

            st.markdown(
                _BUBBLE_USER.format(content=html.escape(pending_q)),
                unsafe_allow_html=True,
            )

            stream_slot = st.empty()
            full_text = ""
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")

            if not api_key:
                full_text = "⚠️ ANTHROPIC_API_KEY가 설정되어 있지 않습니다. .env 파일을 확인해 주세요."
                stream_slot.markdown(
                    _BUBBLE_BOT.format(content=html.escape(full_text)),
                    unsafe_allow_html=True,
                )
            else:
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    with client.messages.stream(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=1000,
                        system=QA_SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": pending_q}],
                    ) as stream:
                        for chunk in stream.text_stream:
                            full_text += chunk
                            stream_slot.markdown(
                                _BUBBLE_BOT.format(content=html.escape(full_text) + " ▌"),
                                unsafe_allow_html=True,
                            )
                    stream_slot.markdown(
                        _BUBBLE_BOT.format(content=_md_to_html(full_text)),
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    full_text = f"⚠️ 답변을 가져오는 중 문제가 발생했습니다: {e}"
                    stream_slot.markdown(
                        _BUBBLE_BOT.format(content=html.escape(full_text)),
                        unsafe_allow_html=True,
                    )

            st.session_state.qa_history.append({"q": pending_q, "a": full_text})
            st.rerun()

        # ── 입력창 ────────────────────────────────────────────────────
        if question := st.chat_input("질문을 입력하세요...", key="chat_main_input"):
            st.session_state._pending_q = question
            st.rerun()


# =========================================================
# 헤더
# =========================================================
st.markdown('<div class="eyebrow">NOWHERE DATA PIPELINE</div>', unsafe_allow_html=True)
st.markdown('<div class="page-title">Trust Score, 어떤 기준이 가장 정확할까요?</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Geofencing 기반 혼잡도 제보 시스템의 Peer Review 임계값을 '
    '시뮬레이션 데이터로 검증하고, 시공간 혼잡도 패턴까지 함께 살펴봐요</div>',
    unsafe_allow_html=True,
)

tab_about, tab_a, tab_b = st.tabs(["📁 프로젝트 개요", "📊 Trust Score 임계값", "🕐 혼잡도 패턴"])

# =========================================================
# 트랙 A
# =========================================================
with tab_a:
    if table_exists(engine, "threshold_summary"):
        df_a = pd.read_sql("SELECT * FROM threshold_summary ORDER BY threshold", engine)

        best_row = df_a.loc[df_a["mean_corr"].idxmax()]
        best_th = int(best_row["threshold"])
        best_corr = best_row["mean_corr"]
        policy_row = df_a[df_a["threshold"] == 3]
        policy_corr = policy_row["mean_corr"].values[0] if len(policy_row) else None
        improve_pct = ((best_corr - policy_corr) / policy_corr * 100) if policy_corr else None

        hero_desc = (
            f"현재 정책(반대 3개)보다 상관계수가 {improve_pct:.0f}% 더 높아요 · "
            f"10회 반복 시뮬레이션에서 매번 1등이에요"
            if improve_pct is not None
            else "10회 반복 시뮬레이션 기준 가장 안정적으로 높은 상관계수를 기록했어요."
        )
        hero_card_number("가장 신뢰도 높은 반대 임계값", str(best_th), "개", hero_desc)

        col1, col2 = st.columns(2)
        with col1:
            stat_card("현재 정책값 상관계수", f"{policy_corr:.3f}" if policy_corr else "-", "반대 3개 기준")
        with col2:
            stat_card("최적값 상관계수", f"{best_corr:.3f}", f"반대 {best_th}개 기준", positive=True, highlight=True)

        st.write("")

        fig, ax = plt.subplots(figsize=(9, 5.2))
        fig.patch.set_facecolor(P["card"])
        ax.plot(df_a["threshold"], df_a["mean_corr"], marker="o", color=P["blue"],
                linewidth=2.5, markersize=7, markerfacecolor=P["card"], markeredgewidth=2)
        ax.fill_between(
            df_a["threshold"],
            df_a["mean_corr"] - df_a["std_corr"],
            df_a["mean_corr"] + df_a["std_corr"],
            color=P["blue"], alpha=0.12, label="±1 표준편차 (10개 시드)",
        )
        ax.axvline(x=3, color=P["gray"], linestyle="--", alpha=0.8, label="현재 정책값 (3)")
        ax.axvline(x=best_th, color=P["mint"], linestyle="--", alpha=0.9, label=f"최적값 ({best_th})")
        ax.set_xlabel("반대(disagree) 임계값")
        ax.set_ylabel("Trust Score - 실제정확도 평균 상관계수")
        style_axes(ax)
        ax.legend(frameon=False, fontsize=10, labelcolor=P["text2"])
        fig.tight_layout()

        section_card_with_image(
            "이게 왜 중요한가요?",
            "제보에 반대가 몇 개 이상 모이면 신뢰도를 깎아야 할까요? 지금은 \"3개\"로 정해져 있는데, "
            "시뮬레이션으로 여러 값을 실험해봤더니 <b>더 엄격한 기준</b>일 때 정확한 사람과 "
            "부정확한 사람을 더 잘 구별해냈어요. 아래 그래프는 임계값을 1~10까지 바꿔가며 "
            "10번씩 반복 시뮬레이션한 평균 결과예요.",
            fig,
        )
        plt.close(fig)

        with st.expander("임계값별 원본 수치 / 시드별 결과 보기"):
            st.dataframe(
                df_a.rename(columns={"threshold": "임계값", "mean_corr": "평균 상관계수", "std_corr": "표준편차"}),
                use_container_width=True, hide_index=True,
            )
            if table_exists(engine, "threshold_results"):
                df_raw = pd.read_sql("SELECT * FROM threshold_results ORDER BY threshold, seed", engine)
                st.dataframe(df_raw, use_container_width=True, hide_index=True)

        st.info(
            "⚠️ 이 결과는 합성(시뮬레이션) 데이터를 기준으로 해요. "
            "서비스 런칭 후에는 실데이터로 다시 검증(재조정)할 예정이에요."
        )
    else:
        st.warning(
            "threshold_summary 테이블이 아직 없습니다. "
            "analysis/track_a_threshold.py 를 먼저 실행해주세요."
        )

# =========================================================
# 트랙 B
# =========================================================
with tab_b:
    if table_exists(engine, "congestion_hourly_summary"):
        df_b = pd.read_sql("SELECT * FROM congestion_hourly_summary", engine)

        busiest = df_b.loc[df_b["avg_reported_congestion"].idxmax()]
        quietest = df_b.loc[df_b["avg_reported_congestion"].idxmin()]

        hero_card_number(
            "가장 혼잡한 시간대의 평균 혼잡도",
            f"{busiest['avg_reported_congestion']:.1f}", f"/ 3.0 · {busiest['location_name']} {int(busiest['hour'])}시",
            "점심(12-13시)과 저녁(18-19시)에 전체 장소에서 공통적으로 붐볐어요. "
            "(혼잡도는 LOW=1 · MEDIUM=2 · HIGH=3 순서형 점수 기준)",
        )

        col1, col2 = st.columns(2)
        with col1:
            stat_card("측정 장소 수", f"{df_b['location_name'].nunique()}곳",
                       "한빛식당·중앙도서관·라운지·로이작업실")
        with col2:
            stat_card("가장 여유로운 시간대", f"{int(quietest['hour'])}시",
                       f"{quietest['location_name']} 기준 (혼잡도 {quietest['avg_reported_congestion']:.1f})",
                       positive=True)

        st.write("")

        pivot = df_b.pivot_table(index="location_name", columns="hour",
                                  values="avg_reported_congestion", aggfunc="mean")
        fig2, ax2 = plt.subplots(figsize=(11, 4.0))
        fig2.patch.set_facecolor(P["card"])
        im = ax2.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
        ax2.set_xticks(range(len(pivot.columns)))
        ax2.set_xticklabels(pivot.columns, color=P["text3"])
        ax2.set_yticks(range(len(pivot.index)))
        ax2.set_yticklabels(pivot.index, color=P["text3"])
        ax2.set_xlabel("시간대", color=P["text2"])
        for spine in ax2.spines.values():
            spine.set_visible(False)
        cbar = plt.colorbar(im, ax=ax2, label="평균 혼잡도 (제보 기준)", fraction=0.025, pad=0.02)
        cbar.outline.set_visible(False)
        cbar.ax.yaxis.label.set_color(P["text2"])
        cbar.ax.tick_params(colors=P["text3"])
        fig2.tight_layout()

        section_card_with_image(
            "언제 어디가 가장 붐빌까요?",
            "장소별로 100m(학식·도서관) 또는 80m(카페) geofence 반경 안의 제보만 걸러내서, "
            "시간대별 평균 혼잡도를 모아봤어요. 색이 진할수록 혼잡한 시간대예요.",
            fig2,
            badge="트랙 B",
        )
        plt.close(fig2)

        section_text_card(
            "장소별 지도",
            "실제 캠퍼스 좌표 위에 장소를 표시했어요. 마커를 클릭하면 평균 혼잡도를 볼 수 있어요.",
        )
        try:
            import folium
            from streamlit_folium import st_folium

            locations = pd.read_sql("SELECT name, latitude, longitude, category FROM sim_locations", engine)
            m = folium.Map(location=[locations["latitude"].mean(), locations["longitude"].mean()],
                            zoom_start=16)
            for _, loc in locations.iterrows():
                avg_c = df_b[df_b["location_name"] == loc["name"]]["avg_reported_congestion"].mean()
                # 혼잡도 1~3 순서형 척도 기준 (LOW=1, MEDIUM=2, HIGH=3)
                color = "red" if avg_c >= 2.5 else ("orange" if avg_c >= 1.5 else "green")
                folium.CircleMarker(
                    location=[loc["latitude"], loc["longitude"]],
                    radius=15, color=color, fill=True, fill_color=color,
                    popup=f"{loc['name']} ({loc['category']}): 평균 혼잡도 {avg_c:.2f}",
                ).add_to(m)
            st_folium(m, width=1080, height=420)
        except ImportError:
            st.info("folium / streamlit-folium 설치 후 지도가 표시됩니다.")

        st.write("")

        if table_exists(engine, "weather_observations"):
            section_text_card(
                "날씨 관측 데이터",
                "기상청 공공데이터포털(초단기실황)에서 매시간 자동으로 모으고 있는 관측값이에요. "
                "혼잡도와의 상관관계는 데이터가 더 쌓이면 함께 살펴볼 예정이에요.",
                badge="cron 자동수집",
            )
            df_w = pd.read_sql(
                "SELECT base_date, base_time, category_name, obs_value, fetched_at "
                "FROM weather_observations ORDER BY fetched_at DESC LIMIT 40",
                engine,
            )
            st.dataframe(
                df_w.rename(columns={
                    "base_date": "관측일", "base_time": "관측시각", "category_name": "항목",
                    "obs_value": "값", "fetched_at": "수집시각",
                }),
                use_container_width=True, hide_index=True,
            )
    else:
        st.warning(
            "congestion_hourly_summary 테이블이 아직 없습니다. "
            "analysis/track_b_spatiotemporal.py 를 먼저 실행해주세요."
        )

# =========================================================
# 프로젝트 개요
# =========================================================
with tab_about:
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">이 프로젝트는 무엇인가요?</div>
        <div class="section-desc" style="margin-bottom:0;">
            Nowhere는 CBNU SW캡스톤 졸업 프로젝트로 만든 Geofencing 기반 실시간 혼잡도 제보
            앱이에요. 학식·도서관·카페 같은 캠퍼스 거점의 혼잡도를 사용자들이 직접 제보하고,
            근처에 있는 다른 사용자들이 그 제보가 맞는지 검증해요. 이 검증 과정을 Peer Review라고
            부르고, 검증 결과에 따라 제보자의 신뢰도 점수(Trust Score)가 오르내려요.
            이 페이지는 그 Peer Review 시스템의 핵심 질문 — "반대가 몇 개 모이면 신뢰도를
            깎아야 할까?" — 를 실제 서비스가 런칭되기 전에 시뮬레이션 데이터로 미리 검증해본
            결과예요.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">실제 서비스는 이렇게 동작해요</div>
        <div class="section-desc" style="margin-bottom:0;">
            <ol style="margin:0; padding-left:20px;">
                <li>사용자 A가 혼잡도를 제보하면 지도에 바로 반영돼요</li>
                <li>근처에 있는 사용자 B, C, D가 그 제보를 보고 "맞아요" 또는 "틀려요"로 검증해요</li>
                <li>이 결과는 SSE(실시간 스트리밍)로 접속 중인 모든 사용자에게 즉시 전달돼요</li>
                <li>제보 유효시간이 끝나면, 서버가 자동으로 제보자의 Trust Score를 갱신해요</li>
            </ol>
            <div style="margin-top:14px;">이 흐름에서 "반대가 몇 개면 감점할지"를 정하는 게 이 프로젝트가 답하려는 질문이에요.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        <div class="section-card" style="height:100%;">
            <div class="section-title">트랙 A — 신뢰도 임계값 최적화<span class="badge">Trust Score</span></div>
            <div class="section-desc" style="margin-bottom:0;">
                시뮬레이션 데이터로 여러 반대 임계값을 실험해서, 어떤 값이 정확한 제보자와
                부정확한(어뷰징) 제보자를 가장 잘 구별하는지 확인해요.
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="section-card" style="height:100%;">
            <div class="section-title">트랙 B — 시공간 혼잡도 패턴<span class="badge">혼잡도 패턴</span></div>
            <div class="section-desc" style="margin-bottom:0;">
                장소×시간대별 혼잡도 패턴을 분석하고 기상청 공공데이터(날씨)를 더해서,
                앞으로 B2G(학교 행정실 대상) 리포트를 만들 수 있는 기반을 마련해요.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    diagram_path = "docs/workflow_diagram.png"
    diagram_html = (
        f'<img src="data:image/png;base64,{file_to_base64(diagram_path)}">'
        if os.path.exists(diagram_path) else ""
    )
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">어떻게 만들었나요</div>
        <div class="section-desc">
            OCI 가상서버(vm-03) 위에 PostgreSQL+PostGIS로 데이터를 저장하고, Python으로
            시뮬레이션 데이터를 만들어서 분석했어요. 기상청 공공데이터도 매시간 자동으로
            모으고 있고요. 이 페이지는 nginx를 통해 외부에 공개돼 있어요. 전체 구조는 아래
            그림에서 확인할 수 있어요.
        </div>
        {diagram_html}
    </div>
    """, unsafe_allow_html=True)

    st.write("")
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">데이터, 솔직하게 말씀드릴게요</div>
        <div class="section-desc">
            이 대시보드의 모든 수치는 <b>합성(시뮬레이션) 데이터</b>를 기준으로 해요. 서비스가 아직
            런칭 전이라 실사용자 데이터가 없는 콜드스타트 상황이라, 실제 백엔드와 똑같은 스키마와
            정책을 반영해서 만들었어요. 서비스가 런칭되면 같은 파이프라인에 실데이터를 흘려보내서
            정책을 다시 검증(재조정)할 수 있게 설계해뒀어요.<br><br>
            실제 서비스의 혼잡도는 LOW/MEDIUM/HIGH 3단계로 표현되는데, 이 시뮬레이션은
            통계 분석 편의를 위해 이 3단계를 그대로 순서형 점수로 다뤘어요.<br>
            Trust Score의 기본점수(50)와 동의 반영(+1) 규칙은 현재 배포된 코드가 아니라
            팀이 다음 단계로 검토 중인 확장 설계를 기준으로 시뮬레이션했어요.
        </div>
        <a href="https://github.com/CBNU-SWCapstone-B5-TJTS-now/data-pipeline" target="_blank"
           style="display:inline-block; margin-top:6px; padding:11px 22px; background:{P['blue']};
                  color:#FFFFFF; font-weight:700; font-size:14.5px; border-radius:12px;
                  text-decoration:none;">
           GitHub Repository 방문하기</a>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# 페이지 전역 푸터: 데이터 출처 / 기술 스택
# (탭 안이 아니라 st.tabs() 밖에서 호출 — 어느 탭에 있든 페이지 맨 아래에 항상 보이게)
# 짙은 박스 배경 없이 본문 배경 위에 투명하게 얹고, 구분선만으로 영역을 나눔
# =========================================================
st.write("")
st.markdown(f"""
<div style="border-top: 1px solid {P['border']}; margin-top: 8px; padding-top: 28px;">
    <div style="display:flex; gap:48px; flex-wrap:wrap;">
        <div style="flex:1; min-width:220px;">
            <div style="font-size:13.5px; font-weight:700; color:{P['text1']}; margin-bottom:12px; letter-spacing:0.3px;">🌐 데이터 출처</div>
            <div style="color:{P['text2']}; font-size:14.5px; line-height:2;">
                기상청 공공데이터포털 — 초단기실황 조회 API<br>
                시뮬레이션 데이터 (실제 백엔드 스키마 기반 합성 생성)
            </div>
        </div>
        <div style="flex:1; min-width:220px;">
            <div style="font-size:13.5px; font-weight:700; color:{P['text1']}; margin-bottom:12px; letter-spacing:0.3px;">🛠️ 기술 스택</div>
            <div style="color:{P['text2']}; font-size:14.5px; line-height:2;">
                수집·처리 — Python, pandas, requests<br>
                저장 — PostgreSQL 16 + PostGIS, OCI Block Volume, Object Storage<br>
                시각화 — Streamlit, matplotlib, folium
            </div>
        </div>
    </div>
    <div style="text-align:center; font-size:12.5px; color:{P['text3']}; margin-top:28px; padding: 16px 0 24px;">
        충북대학교 소프트웨어학과 · Cloud 기반 데이터AI 파이프라인구축 · 2026
    </div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# 라이트/다크 토글 + 플로팅 채팅 위젯
# (둘 다 탭 밖에서 호출 — 어느 탭에 있든 항상 우측 하단에 고정, 토글 버튼이 채팅 버튼 위에 쌓임)
# =========================================================
st.button("🌙" if not st.session_state.dark_mode else "☀️", on_click=toggle_theme,
          help="라이트/다크 모드 전환", key="theme_toggle_btn")
render_floating_chat()
