"""
트랙 B: 장소×시간대(요일 포함) 혼잡도 패턴 분석 + 날씨 결합

1. sim_reports에 제보 GPS 좌표(location 중심 + 오차)를 시뮬레이션으로 부여하고,
   PostGIS ST_DWithin으로 sim_locations.geom 기준 geofence 반경(100m/80m) 내
   제보만 유효 제보로 그룹핑 (실제 백엔드가 geofence를 통과한 제보만 인정하는 것과 동일한 로직).
2. day_of_week(요일)을 제보별로 부여해 장소×요일×시간대 평균 혼잡도 집계.
3. weather_observations(기온 T1H)를 시간(hour) 단위로 조인 — 관측 데이터가 아직
   몇 시간치뿐이라 상관계수 계산 대신 "조인이 정상적으로 되는지"만 확인.
4. 결과를 congestion_hourly_summary 테이블로 저장.
"""
import os

from sqlalchemy import create_engine, text

DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def step1_add_report_geo_columns(conn):
    """제보에 GPS 좌표/geom/요일 컬럼 추가 (없으면) + 시뮬레이션 값 채우기"""
    conn.execute(text("""
        ALTER TABLE sim_reports
            ADD COLUMN IF NOT EXISTS report_lat DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS report_lon DOUBLE PRECISION,
            ADD COLUMN IF NOT EXISTS report_geom geography(Point, 4326),
            ADD COLUMN IF NOT EXISTS day_of_week SMALLINT;
    """))
    # 장소 중심 좌표에 GPS 오차(약 -83m~+83m, 위경도 각각) 부여.
    # geofence 반경(80~100m)을 벗어나는 경우도 자연스럽게 발생하도록 함.
    conn.execute(text("""
        UPDATE sim_reports r
        SET report_lat = l.latitude + (random() - 0.5) * 0.0015,
            report_lon = l.longitude + (random() - 0.5) * 0.0015,
            day_of_week = floor(random() * 7)::smallint
        FROM sim_locations l
        WHERE r.location_id = l.location_id
          AND r.report_lat IS NULL;
    """))
    conn.execute(text("""
        UPDATE sim_reports
        SET report_geom = ST_SetSRID(ST_MakePoint(report_lon, report_lat), 4326)::geography
        WHERE report_geom IS NULL;
    """))
    conn.commit()


def step2_geofence_check(conn):
    """ST_DWithin으로 geofence 반경 내 제보 여부 확인 (요약 출력용)"""
    result = conn.execute(text("""
        SELECT
            l.name,
            l.geofence_radius_m,
            count(*) AS total_reports,
            count(*) FILTER (
                WHERE ST_DWithin(l.geom, r.report_geom, l.geofence_radius_m)
            ) AS within_geofence,
            round(avg(ST_Distance(l.geom, r.report_geom))::numeric, 1) AS avg_distance_m
        FROM sim_reports r
        JOIN sim_locations l ON r.location_id = l.location_id
        GROUP BY l.name, l.geofence_radius_m
        ORDER BY l.name;
    """))
    print("=== Geofence(ST_DWithin) 판정 요약 ===")
    for row in result:
        print(f"  {row.name:<8} 반경{row.geofence_radius_m:>3}m  "
              f"전체 {row.total_reports:>3}건 중 geofence 내 {row.within_geofence:>3}건 "
              f"(평균 거리 {row.avg_distance_m}m)")


def step3_build_summary(conn):
    """geofence 통과 제보만으로 장소×요일×시간대 집계 + 날씨(기온) 조인"""
    conn.execute(text("DROP TABLE IF EXISTS congestion_hourly_summary;"))
    conn.execute(text("""
        CREATE TABLE congestion_hourly_summary AS
        WITH valid_reports AS (
            SELECT r.*, l.name AS location_name, l.category
            FROM sim_reports r
            JOIN sim_locations l ON r.location_id = l.location_id
            WHERE ST_DWithin(l.geom, r.report_geom, l.geofence_radius_m)
        ),
        agg AS (
            SELECT
                location_id,
                location_name,
                category,
                day_of_week,
                hour,
                count(*) AS report_count,
                round(avg(reported_congestion)::numeric, 2) AS avg_reported_congestion,
                round(avg(true_congestion)::numeric, 2) AS avg_true_congestion
            FROM valid_reports
            GROUP BY location_id, location_name, category, day_of_week, hour
        ),
        hourly_temp AS (
            SELECT
                (base_time::int / 100) AS hour,
                avg(obs_value::double precision) AS avg_temp_c
            FROM weather_observations
            WHERE category = 'T1H'
            GROUP BY (base_time::int / 100)
        )
        SELECT
            a.*,
            h.avg_temp_c
        FROM agg a
        LEFT JOIN hourly_temp h ON a.hour = h.hour
        ORDER BY a.location_id, a.day_of_week, a.hour;
    """))
    conn.commit()


def step4_report(conn):
    total = conn.execute(text("SELECT count(*) FROM congestion_hourly_summary;")).scalar()
    matched = conn.execute(text(
        "SELECT count(*) FROM congestion_hourly_summary WHERE avg_temp_c IS NOT NULL;"
    )).scalar()
    print(f"\ncongestion_hourly_summary 저장 완료: 총 {total}행, "
          f"날씨(기온) 조인된 행 {matched}행 (관측 데이터가 소수 시간대뿐이라 대부분 NULL — 정상)")

    print("\n=== 샘플 (기온이 조인된 행 우선) ===")
    result = conn.execute(text("""
        SELECT location_name, day_of_week, hour, report_count,
               avg_reported_congestion, avg_true_congestion, avg_temp_c
        FROM congestion_hourly_summary
        ORDER BY (avg_temp_c IS NULL), location_id, day_of_week, hour
        LIMIT 10;
    """))
    for row in result:
        print(f"  {row.location_name:<8} dow={row.day_of_week} hour={row.hour:>2}  "
              f"제보수={row.report_count:>2}  평균혼잡(제보)={row.avg_reported_congestion}  "
              f"평균혼잡(실제)={row.avg_true_congestion}  기온={row.avg_temp_c}")


def main():
    with engine.connect() as conn:
        step1_add_report_geo_columns(conn)
        step2_geofence_check(conn)
        step3_build_summary(conn)
        step4_report(conn)


if __name__ == "__main__":
    main()
