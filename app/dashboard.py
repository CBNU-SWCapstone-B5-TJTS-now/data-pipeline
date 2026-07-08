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
import base64
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import matplotlib.pyplot as plt

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
)
DARK = dict(
    bg="#101216", card="#1C1F26", text1="#F2F4F6", text2="#B0B8C1", text3="#7C8592",
    border="#2B2F38", blue="#5B9DFF", blue_dark="#3182F6", mint="#2FE1C4", gray="#545B66",
    badge_bg="#1A2C4A", shadow="rgba(0,0,0,0.35)", header_bg="#101216",
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

P = DARK if st.session_state.dark_mode else LIGHT

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
.block-container {{ padding-top: 1.8rem; max-width: 1180px; }}

header[data-testid="stHeader"] {{ background: {P['header_bg']}; }}
header[data-testid="stHeader"] * {{ color: {P['text1']} !important; }}

.eyebrow {{
    font-size: 14px; font-weight: 700; color: {P['blue']};
    letter-spacing: 0.3px; margin-top: 8px; margin-bottom: 8px;
}}
.page-title {{
    font-size: 30px; font-weight: 800; letter-spacing: -0.6px;
    color: {P['text1']}; margin-bottom: 4px; line-height: 1.35;
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

.stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: transparent; margin-bottom: 22px; }}
.stTabs [data-baseweb="tab-highlight"] {{ display: none; }}
.stTabs [data-baseweb="tab-border"] {{ display: none; }}
.stTabs [data-baseweb="tab"] {{
    background: {P['card']}; border-radius: 999px; padding: 10px 22px;
    font-weight: 600; font-size: 14.5px; color: {P['text3']}; border: 1px solid {P['border']};
    display: flex; align-items: center; gap: 6px; line-height: 1.3;
}}
.stTabs [data-baseweb="tab"] p {{ display: flex; align-items: center; gap: 6px; margin: 0; }}
.stTabs [aria-selected="true"] {{ background: {P['text1']} !important; color: {P['bg']} !important; border-color: {P['text1']} !important; }}

div[data-testid="stExpander"] {{ border-radius: 16px; border: 1px solid {P['border']}; background: {P['card']}; }}
div[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; }}
div[data-testid="stAlert"] {{ border-radius: 14px; }}

/* 라이트/다크 토글 버튼 (앱 전체에서 유일한 st.button) */
div[data-testid="stButton"] {{
    position: fixed; bottom: 24px; right: 24px; z-index: 9999; width: auto;
}}
div[data-testid="stButton"] button {{
    border-radius: 50%; width: 52px; height: 52px; padding: 0;
    background: {P['card']}; border: 1px solid {P['border']};
    box-shadow: 0 4px 14px {P['shadow']}; font-size: 20px;
}}
</style>
""", unsafe_allow_html=True)


def toggle_theme():
    st.session_state.dark_mode = not st.session_state.dark_mode


st.button("🌙" if not st.session_state.dark_mode else "☀️", on_click=toggle_theme,
          help="라이트/다크 모드 전환")


def fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor=P["card"])
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def hero_card_number(label: str, number: str, unit: str, desc: str):
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-label">{label}</div>
        <div class="hero-main"><span class="hero-number">{number}</span><span class="hero-place">{unit}</span></div>
        <div class="hero-desc">{desc}</div>
    </div>
    """, unsafe_allow_html=True)


def stat_card(label: str, number: str, sub: str, positive: bool = False):
    cls = "stat-number positive" if positive else "stat-number"
    st.markdown(f"""
    <div class="stat-card">
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
# 헤더
# =========================================================
st.markdown('<div class="eyebrow">NOWHERE DATA PIPELINE</div>', unsafe_allow_html=True)
st.markdown('<div class="page-title">Trust Score, 어떤 기준이 가장 정확할까요?</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Geofencing 기반 혼잡도 제보 시스템의 Peer Review 임계값을 '
    '시뮬레이션 데이터로 검증하고, 시공간 혼잡도 패턴까지 함께 살펴봐요</div>',
    unsafe_allow_html=True,
)

tab_a, tab_b, tab_about = st.tabs(["Trust Score 임계값", "혼잡도 패턴", "프로젝트 개요"])

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
            stat_card("최적값 상관계수", f"{best_corr:.3f}", f"반대 {best_th}개 기준", positive=True)

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
            f"{busiest['avg_reported_congestion']:.1f}", f"/ 5.0 · {busiest['location_name']} {int(busiest['hour'])}시",
            "점심(12-13시)과 저녁(18-19시)에 전체 장소에서 공통적으로 붐볐어요.",
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
                color = "red" if avg_c >= 3.5 else ("orange" if avg_c >= 2.5 else "green")
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
        <div class="section-title">이 프로젝트를 시작한 이유</div>
        <div class="section-desc" style="margin-bottom:0;">
            CBNU SW캡스톤 졸업 프로젝트 <b>Nowhere</b>(Geofencing 기반 혼잡도 제보 앱)는
            Geofence로 현장 인증된 유저들의 동의·반대 투표로 제보자의 Trust Score를 조정하는
            Peer Review 시스템을 갖고 있어요. 그런데 서비스가 아직 런칭 전이라 실사용자 데이터가 없다 보니,
            Trust Score의 반대 임계값(지금 설계로는 3개 초과분마다 감점)이 정말 합리적인 값인지
            확인할 방법이 없었어요. 이 파이프라인은 그 빈틈을 시뮬레이션 데이터로 채워보려고 만들었어요.
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
    st.markdown(f"""
    <div class="section-card">
        <div class="section-title">데이터, 솔직하게 말씀드릴게요</div>
        <div class="section-desc">
            이 대시보드의 모든 수치는 <b>합성(시뮬레이션) 데이터</b>를 기준으로 해요. 서비스가 아직
            런칭 전이라 실사용자 데이터가 없는 콜드스타트 상황이라, 실제 백엔드와 똑같은 스키마와
            정책을 반영해서 만들었어요. 서비스가 런칭되면 같은 파이프라인에 실데이터를 흘려보내서
            정책을 다시 검증(재조정)할 수 있게 설계해뒀어요.
        </div>
        <a href="https://github.com/CBNU-SWCapstone-B5-TJTS-now/data-pipeline"
           style="color:{P['blue']}; font-weight:600; font-size:14.5px; text-decoration:none;">
           → GitHub repository에서 전체 코드와 README를 확인해보세요</a>
    </div>
    """, unsafe_allow_html=True)
