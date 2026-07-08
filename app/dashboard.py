"""
Nowhere Data Pipeline - Streamlit 대시보드 (Toss 스타일 리포트형 UI)
트랙 A(Trust Score 임계값) / 트랙 B(시공간 혼잡도 패턴) 탭으로 구성.

실행: streamlit run app/dashboard.py --server.port 8501

주의: 아래 쿼리들은 트랙 A/B 분석 스크립트(analysis/track_a_threshold.py,
analysis/track_b_spatiotemporal.py)가 결과 테이블(threshold_results/threshold_summary,
congestion_hourly_summary)을 만들어 둔 뒤에 정상 동작합니다.
아직 결과 테이블이 없다면 해당 탭에 안내 메시지가 표시됩니다.
"""
import os
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

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

html, body, [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
}

.stApp { background: #F2F4F6; }
.block-container { padding-top: 2.5rem; max-width: 1180px; }

.eyebrow {
    font-size: 14px; font-weight: 700; color: #3182F6;
    letter-spacing: 0.3px; margin-bottom: 6px;
}
.page-title {
    font-size: 30px; font-weight: 800; letter-spacing: -0.6px;
    color: #191F28; margin-bottom: 4px; line-height: 1.35;
}
.page-subtitle { font-size: 15.5px; color: #4E5968; margin-bottom: 28px; }

.hero-card {
    background: linear-gradient(135deg, #3182F6 0%, #1B64DA 100%);
    border-radius: 24px; padding: 36px 40px; color: white;
    margin-bottom: 18px; box-shadow: 0 8px 24px rgba(49,130,246,0.22);
}
.hero-label { font-size: 14.5px; font-weight: 600; opacity: 0.88; margin-bottom: 10px; }
.hero-number { font-size: 56px; font-weight: 800; letter-spacing: -1.5px;
    font-variant-numeric: tabular-nums; line-height: 1; }
.hero-unit { font-size: 22px; font-weight: 600; opacity: 0.9; margin-left: 4px; }
.hero-desc { font-size: 14.5px; opacity: 0.92; margin-top: 14px; line-height: 1.6; }

.stat-card {
    background: white; border-radius: 18px; padding: 22px 26px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04); height: 100%;
}
.stat-label { font-size: 13.5px; color: #8B95A1; font-weight: 600; margin-bottom: 6px; }
.stat-number { font-size: 28px; font-weight: 800; letter-spacing: -0.8px; color: #191F28; }
.stat-number.positive { color: #05A88E; }
.stat-sub { font-size: 12.5px; color: #8B95A1; margin-top: 5px; }

.section-card {
    background: white; border-radius: 20px; padding: 30px 32px;
    margin-bottom: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.section-title { font-size: 18.5px; font-weight: 700; color: #191F28; margin-bottom: 8px; }
.section-desc { font-size: 14.5px; color: #4E5968; line-height: 1.75; margin-bottom: 18px; }

.badge {
    display: inline-block; background: #E8F3FF; color: #3182F6;
    font-size: 12px; font-weight: 700; padding: 3px 11px; border-radius: 999px;
    margin-left: 6px; vertical-align: middle;
}

.stTabs [data-baseweb="tab-list"] { gap: 6px; background: transparent; margin-bottom: 22px; }
.stTabs [data-baseweb="tab"] {
    background: white; border-radius: 999px; padding: 10px 22px;
    font-weight: 600; font-size: 14.5px; color: #8B95A1; border: none;
}
.stTabs [aria-selected="true"] { background: #191F28 !important; color: white !important; }

div[data-testid="stExpander"] { border-radius: 16px; border: 1px solid #E5E8EB; background: white; }
div[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }
div[data-testid="stAlert"] { border-radius: 14px; }
</style>
""", unsafe_allow_html=True)


def hero_card(label: str, number: str, unit: str, desc: str):
    st.markdown(f"""
    <div class="hero-card">
        <div class="hero-label">{label}</div>
        <div><span class="hero-number">{number}</span><span class="hero-unit">{unit}</span></div>
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


def section_header(title: str, desc: str, badge: str = ""):
    badge_html = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="section-title">{title}{badge_html}</div>
    <div class="section-desc">{desc}</div>
    """, unsafe_allow_html=True)


TOSS_BLUE = "#3182F6"
TOSS_MINT = "#05A88E"
TOSS_GRAY = "#B0B8C1"


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#E5E8EB")
    ax.spines["bottom"].set_color("#E5E8EB")
    ax.tick_params(colors="#8B95A1")
    ax.xaxis.label.set_color("#4E5968")
    ax.yaxis.label.set_color("#4E5968")
    ax.grid(alpha=0.25, color="#E5E8EB")


st.markdown('<div class="eyebrow">NOWHERE DATA PIPELINE</div>', unsafe_allow_html=True)
st.markdown('<div class="page-title">Trust Score, 어떤 기준이 가장 정확할까요?</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Geofencing 기반 혼잡도 제보 시스템 — 시뮬레이션 데이터로 검증한 '
    'Peer Review 임계값 분석과 시공간 혼잡도 패턴</div>',
    unsafe_allow_html=True,
)

tab_a, tab_b, tab_about = st.tabs(["📊  Trust Score 임계값", "🕐  혼잡도 패턴", "📁  프로젝트 개요"])

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
            f"현재 정책(반대 3개)보다 상관계수가 {improve_pct:.0f}% 더 높습니다 · "
            f"10회 반복 시뮬레이션에서 매번 1위"
            if improve_pct is not None
            else "10회 반복 시뮬레이션 기준 가장 안정적으로 높은 상관계수를 기록했습니다."
        )
        hero_card("가장 신뢰도 높은 반대 임계값", str(best_th), "개", hero_desc)

        col1, col2 = st.columns(2)
        with col1:
            stat_card("현재 정책값 상관계수", f"{policy_corr:.3f}" if policy_corr else "-", "반대 3개 기준")
        with col2:
            stat_card("최적값 상관계수", f"{best_corr:.3f}", f"반대 {best_th}개 기준", positive=True)

        st.write("")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_header(
            "이게 왜 중요한가요?",
            "제보에 반대가 몇 개 이상 모이면 신뢰도를 깎아야 할까요? 지금은 \"3개\"로 정해져 있지만, "
            "시뮬레이션으로 여러 값을 실험해보니 <b>더 엄격한 기준</b>일 때 실제로 정확한 사람과 "
            "부정확한 사람을 더 잘 구별해냈습니다. 아래 그래프는 임계값을 1~10까지 바꿔가며 "
            "10번씩 반복 시뮬레이션한 평균 결과입니다.",
        )

        c1, c2 = st.columns([3, 2])
        with c1:
            fig, ax = plt.subplots(figsize=(9, 5.5))
            ax.plot(df_a["threshold"], df_a["mean_corr"], marker="o", color=TOSS_BLUE,
                    linewidth=2.5, markersize=7, markerfacecolor="white", markeredgewidth=2)
            ax.fill_between(
                df_a["threshold"],
                df_a["mean_corr"] - df_a["std_corr"],
                df_a["mean_corr"] + df_a["std_corr"],
                color=TOSS_BLUE, alpha=0.10, label="±1 표준편차 (10개 시드)",
            )
            ax.axvline(x=3, color=TOSS_GRAY, linestyle="--", alpha=0.8, label="현재 정책값 (3)")
            ax.axvline(x=best_th, color=TOSS_MINT, linestyle="--", alpha=0.9, label=f"최적값 ({best_th})")
            ax.set_xlabel("반대(disagree) 임계값")
            ax.set_ylabel("Trust Score - 실제정확도 평균 상관계수")
            style_axes(ax)
            ax.legend(frameon=False, fontsize=10)
            fig.tight_layout()
            st.pyplot(fig, use_container_width=False)
        with c2:
            st.dataframe(
                df_a.rename(columns={"threshold": "임계값", "mean_corr": "평균 상관계수", "std_corr": "표준편차"}),
                use_container_width=True, hide_index=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("시드별 원본 결과 보기 (threshold_results)"):
            if table_exists(engine, "threshold_results"):
                df_raw = pd.read_sql("SELECT * FROM threshold_results ORDER BY threshold, seed", engine)
                st.dataframe(df_raw, use_container_width=True, hide_index=True)

        st.info(
            "⚠️ 이 결과는 합성(시뮬레이션) 데이터 기준입니다. "
            "서비스 런칭 후 실데이터로 재조정(recalibration)이 필요합니다."
        )
    else:
        st.warning(
            "threshold_summary 테이블이 아직 없습니다. "
            "analysis/track_a_threshold.py 를 먼저 실행해주세요."
        )

with tab_b:
    if table_exists(engine, "congestion_hourly_summary"):
        df_b = pd.read_sql("SELECT * FROM congestion_hourly_summary", engine)

        busiest = df_b.loc[df_b["avg_reported_congestion"].idxmax()]
        hero_card(
            "가장 혼잡한 시간대",
            f"{busiest['location_name']}", f" · {int(busiest['hour'])}시",
            f"평균 혼잡도 {busiest['avg_reported_congestion']:.1f} / 5.0 — "
            f"점심(12-13시)·저녁(18-19시) 피크가 전체 장소에서 공통적으로 관찰됩니다.",
        )

        col1, col2 = st.columns(2)
        with col1:
            stat_card("측정 장소 수", f"{df_b['location_name'].nunique()}곳",
                       "한빛식당·중앙도서관·라운지·로이작업실")
        with col2:
            quietest = df_b.loc[df_b["avg_reported_congestion"].idxmin()]
            stat_card("가장 여유로운 시간대", f"{int(quietest['hour'])}시",
                       f"{quietest['location_name']} 기준", positive=True)

        st.write("")
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_header(
            "언제 어디가 가장 붐빌까요?",
            "장소별로 100m(학식·도서관) 또는 80m(카페) geofence 반경 내 제보만 걸러내어, "
            "시간대별 평균 혼잡도를 집계했습니다. 색이 진할수록 혼잡한 시간대입니다.",
            badge="트랙 B",
        )
        pivot = df_b.pivot_table(index="location_name", columns="hour",
                                  values="avg_reported_congestion", aggfunc="mean")
        fig2, ax2 = plt.subplots(figsize=(12, 4.3))
        im = ax2.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
        ax2.set_xticks(range(len(pivot.columns)))
        ax2.set_xticklabels(pivot.columns)
        ax2.set_yticks(range(len(pivot.index)))
        ax2.set_yticklabels(pivot.index)
        ax2.set_xlabel("시간대")
        for spine in ax2.spines.values():
            spine.set_visible(False)
        cbar = plt.colorbar(im, ax=ax2, label="평균 혼잡도 (제보 기준)", fraction=0.025, pad=0.02)
        cbar.outline.set_visible(False)
        fig2.tight_layout()

        col_l, col_mid, col_r = st.columns([1, 10, 1])
        with col_mid:
            st.pyplot(fig2, use_container_width=False)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        section_header(
            "장소별 지도",
            "실제 캠퍼스 좌표 위에 장소를 표시했습니다. 마커를 클릭하면 평균 혼잡도를 확인할 수 있습니다.",
        )
        try:
            import folium
            from streamlit_folium import st_folium

            locations = pd.read_sql("SELECT name, latitude, longitude, category FROM sim_locations", engine)
            m = folium.Map(location=[locations["latitude"].mean(), locations["longitude"].mean()], zoom_start=16)
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
        st.markdown("</div>", unsafe_allow_html=True)

        if table_exists(engine, "weather_observations"):
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            section_header(
                "날씨 관측 데이터",
                "기상청 공공데이터포털(초단기실황)에서 매시간 자동으로 수집한 관측값입니다. "
                "혼잡도와의 상관관계는 데이터가 더 쌓이면 함께 분석할 예정입니다.",
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
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning(
            "congestion_hourly_summary 테이블이 아직 없습니다. "
            "analysis/track_b_spatiotemporal.py 를 먼저 실행해주세요."
        )

with tab_about:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    section_header(
        "이 프로젝트를 시작한 이유",
        "CBNU SW캡스톤 졸업 프로젝트 <b>Nowhere</b>(Geofencing 기반 혼잡도 제보 앱)는 "
        "Geofence로 현장 인증된 유저들의 동의·반대 투표로 제보자의 Trust Score를 조정하는 "
        "Peer Review 시스템을 갖고 있습니다. 그러나 서비스가 아직 런칭 전이라 실사용자 데이터가 없고, "
        "Trust Score의 반대 임계값(현재 설계: 3개 초과분마다 감점)이 실제로 합리적인 값인지 "
        "검증할 데이터가 없는 상태였습니다. 이 파이프라인은 그 공백을 시뮬레이션 데이터로 채우기 위해 만들었습니다.",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="section-card" style="height:100%;">', unsafe_allow_html=True)
        section_header(
            "트랙 A — 신뢰도 임계값 최적화",
            "시뮬레이션 데이터로 여러 반대 임계값을 실험하여, 어떤 값이 실제로 정확한 제보자와 "
            "부정확한(어뷰징) 제보자를 가장 잘 구별하는지 검증합니다.",
            badge="Trust Score",
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="section-card" style="height:100%;">', unsafe_allow_html=True)
        section_header(
            "트랙 B — 시공간 혼잡도 패턴",
            "장소×시간대별 혼잡도 패턴을 분석하고 기상청 공공데이터(날씨)를 결합하여, "
            "향후 B2G(학교 행정실 대상) 리포트 제공의 기반을 마련합니다.",
            badge="혼잡도 패턴",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    section_header(
        "데이터에 대한 정직한 설명",
        "이 대시보드의 모든 수치는 <b>합성(시뮬레이션) 데이터</b> 기준입니다. 서비스가 런칭 전이라 "
        "실사용자 데이터가 없는 콜드스타트 상황에 대한 표준적인 접근으로, 실제 백엔드와 동일한 스키마와 "
        "정책을 반영해 만들었습니다. 서비스 런칭 이후에는 같은 파이프라인에 실데이터를 흘려보내 "
        "정책을 재조정(recalibration)할 수 있도록 설계했습니다.",
    )
    st.markdown(
        '<a href="https://github.com/CBNU-SWCapstone-B5-TJTS-now/data-pipeline" '
        'style="color:#3182F6; font-weight:600; font-size:14.5px; text-decoration:none;">'
        '→ GitHub repository에서 전체 코드와 README 보기</a>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
