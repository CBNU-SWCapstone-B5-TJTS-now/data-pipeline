"""
Nowhere Data Pipeline - Streamlit 대시보드
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

st.set_page_config(page_title="Nowhere Data Pipeline", layout="wide")

# ---- DB 연결 ----
DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
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

st.title("🗺️ Nowhere Data Pipeline")
st.caption("Geofencing 기반 혼잡도 제보 시스템 — Trust Score 임계값 분석 & 시공간 혼잡도 패턴")

tab_a, tab_b, tab_about = st.tabs(["트랙 A: Trust Score 임계값", "트랙 B: 시공간 혼잡도 패턴", "프로젝트 개요"])

# =========================================================
# 트랙 A
# =========================================================
with tab_a:
    st.header("Trust Score 반대(disagree) 임계값 분석")
    st.markdown(
        "반대 임계값(3개까지 무사, 초과분마다 -1)을 1~10까지 바꿔가며 "
        "**Trust Score와 실제 정확도(true_accuracy)의 상관관계**를 비교합니다."
    )

    if table_exists(engine, "threshold_summary"):
        # threshold_summary: 다중 시드(10회) 평균/표준편차 집계 (threshold, mean_corr, std_corr)
        df_a = pd.read_sql("SELECT * FROM threshold_summary ORDER BY threshold", engine)

        col1, col2 = st.columns([2, 1])
        with col1:
            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(df_a["threshold"], df_a["mean_corr"], marker="o", color="#DD6B20", linewidth=2)
            ax.fill_between(
                df_a["threshold"],
                df_a["mean_corr"] - df_a["std_corr"],
                df_a["mean_corr"] + df_a["std_corr"],
                color="#DD6B20", alpha=0.15, label="±1 표준편차 (10개 시드)",
            )
            ax.axvline(x=3, color="#718096", linestyle="--", alpha=0.7, label="현재 정책값 (3)")
            best_th = df_a.loc[df_a["mean_corr"].idxmax(), "threshold"]
            ax.axvline(x=best_th, color="#38A169", linestyle="--", alpha=0.7, label=f"최적값 ({int(best_th)})")
            ax.set_xlabel("반대(disagree) 임계값")
            ax.set_ylabel("Trust Score - 실제정확도 평균 상관계수")
            ax.legend()
            ax.grid(alpha=0.3)
            st.pyplot(fig)
        with col2:
            st.metric("가장 높은 평균 상관계수", f"{df_a['mean_corr'].max():.3f}",
                       f"임계값 = {int(best_th)}")
            st.dataframe(df_a, use_container_width=True, hide_index=True)

        with st.expander("시드별 원본 결과 (threshold_results)"):
            if table_exists(engine, "threshold_results"):
                df_raw = pd.read_sql(
                    "SELECT * FROM threshold_results ORDER BY threshold, seed", engine
                )
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

# =========================================================
# 트랙 B
# =========================================================
with tab_b:
    st.header("시공간 혼잡도 패턴 분석")
    st.markdown("장소×시간대별 혼잡도 패턴과 날씨 데이터를 함께 살펴봅니다.")

    if table_exists(engine, "congestion_hourly_summary"):
        df_b = pd.read_sql("SELECT * FROM congestion_hourly_summary", engine)

        # 히트맵은 장소x시간대 기준 — 요일(day_of_week)은 평균으로 눌러서 표시
        pivot = df_b.pivot_table(index="location_name", columns="hour", values="avg_reported_congestion", aggfunc="mean")
        fig2, ax2 = plt.subplots(figsize=(10, 4))
        im = ax2.imshow(pivot.values, cmap="YlOrRd", aspect="auto")
        ax2.set_xticks(range(len(pivot.columns)))
        ax2.set_xticklabels(pivot.columns)
        ax2.set_yticks(range(len(pivot.index)))
        ax2.set_yticklabels(pivot.index)
        ax2.set_xlabel("시간대")
        plt.colorbar(im, ax=ax2, label="평균 혼잡도 (제보 기준)")
        st.pyplot(fig2)

        st.subheader("장소별 지도")
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
            st_folium(m, width=900, height=450)
        except ImportError:
            st.info("folium / streamlit-folium 설치 후 지도가 표시됩니다.")

        if table_exists(engine, "weather_observations"):
            st.subheader("날씨 관측 데이터 (기상청 공공데이터)")
            st.caption(
                "long-format 저장 — 관측 시각(base_date/base_time)마다 항목(category)별로 한 행씩 저장됨"
            )
            df_w = pd.read_sql(
                "SELECT base_date, base_time, category_name, obs_value, fetched_at "
                "FROM weather_observations ORDER BY fetched_at DESC LIMIT 40",
                engine,
            )
            st.dataframe(df_w, use_container_width=True, hide_index=True)
    else:
        st.warning(
            "congestion_hourly_summary 테이블이 아직 없습니다. "
            "analysis/track_b_spatiotemporal.py 를 먼저 실행해주세요."
        )

# =========================================================
# 프로젝트 개요
# =========================================================
with tab_about:
    st.header("프로젝트 개요")
    st.markdown("""
    이 파이프라인은 CBNU SW캡스톤 졸업 프로젝트 **Nowhere**(Geofencing 기반 혼잡도
    제보 앱)의 Peer Review / Trust Score 기능을 대상으로, 서비스 런칭 전 콜드스타트
    상황에서 정책(임계값)을 데이터로 검증하기 위한 시뮬레이션 파이프라인입니다.

    - **트랙 A**: Trust Score 반대 임계값 최적화
    - **트랙 B**: 시공간 혼잡도 패턴 + 날씨 상관관계 (B2G 리포트 기반)

    자세한 내용은 [README](https://github.com/CBNU-SWCapstone-B5-TJTS-now/data-pipeline)를 참고하세요.
    """)
