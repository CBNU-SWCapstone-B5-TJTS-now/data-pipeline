-- crowd_pipeline DB 스키마 (vm-03 실제 배포 상태 기준, psql \d 출력을 그대로 DDL화)
--
-- 참고:
-- * sim_* 4개 테이블은 pandas.DataFrame.to_sql(if_exists="replace")로 생성되므로
--   컬럼 타입이 pandas 추론 결과(bigint/double precision/text)를 따르며 PK/FK 제약이 없음.
--   이 파일은 재현(문서화) 용도이며, 실제 파이프라인 실행 시에는
--   scripts/generate_simulation_data.py가 테이블을 다시 만들어 덮어쓴다.
-- * threshold_results 역시 트랙 A 스크립트(analysis/track_a_threshold.py)가 to_sql로 생성.
-- * congestion_hourly_summary는 트랙 B 스크립트(analysis/track_b_spatiotemporal.py)가
--   CREATE TABLE ... AS SELECT로 생성.
-- * weather_observations / threshold_summary만 명시적 DDL(PK/UNIQUE 포함)로 생성됨.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- 1. 시뮬레이션 유저 (generate_simulation_data.py 생성)
--    true_accuracy: 숨겨진 정답값(0~1) — 분석 검증용, 실제 서비스 테이블엔 없음
-- ============================================================
CREATE TABLE sim_users (
    user_id        BIGINT,
    true_accuracy  DOUBLE PRECISION,
    trust_score    BIGINT
);

-- ============================================================
-- 2. 장소 (실제 캠퍼스 4곳, DataInitializer.java 기준 좌표)
--    geom은 적재 후 UPDATE로 ST_MakePoint(longitude, latitude) 값을 채움
-- ============================================================
CREATE TABLE sim_locations (
    location_id        BIGINT,
    name               TEXT,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    category           TEXT,                    -- 'SCHOOL' | 'CAFE'
    geofence_radius_m  BIGINT,                  -- 100(SCHOOL) / 80(CAFE)
    geom               geography(Point, 4326)
);

-- ============================================================
-- 3. 혼잡도 제보 (시뮬레이션)
--    report_lat/lon/geom, day_of_week는 트랙 B 스크립트가 ALTER TABLE로 추가
--    (제보 GPS 좌표 = 장소 중심 + 오차, ST_DWithin geofence 판정에 사용)
-- ============================================================
CREATE TABLE sim_reports (
    report_id            BIGINT,
    reporter_id          BIGINT,
    location_id          BIGINT,
    hour                 BIGINT,               -- 8~21
    true_congestion      DOUBLE PRECISION,     -- 숨겨진 정답 혼잡도 (1~5 연속값)
    true_accuracy        DOUBLE PRECISION,     -- 제보자의 true_accuracy 스냅샷
    reported_congestion  BIGINT,               -- 제보된 혼잡도 (1~5)
    report_lat           DOUBLE PRECISION,
    report_lon           DOUBLE PRECISION,
    report_geom          geography(Point, 4326),
    day_of_week          SMALLINT              -- 0~6
);

-- ============================================================
-- 4. 동의/반대 투표 (시뮬레이션)
--    report_id가 double precision인 것은 pandas to_sql 타입 추론의 산물
--    (조인 시 캐스팅 없이 동작하지만, 재설계 시 BIGINT 권장)
-- ============================================================
CREATE TABLE sim_votes (
    vote_id    BIGINT,
    report_id  DOUBLE PRECISION,
    voter_id   BIGINT,
    vote_type  TEXT                             -- 'agree' | 'disagree'
);

-- ============================================================
-- 5. 트랙 A: 시드×임계값별 원본 결과 (track_a_threshold.py 생성)
-- ============================================================
CREATE TABLE threshold_results (
    seed          BIGINT,
    threshold     BIGINT,
    pearson_corr  DOUBLE PRECISION,
    n_users       BIGINT
);

-- ============================================================
-- 6. 트랙 A: 임계값별 집계 (10개 시드 평균/표준편차)
-- ============================================================
CREATE TABLE threshold_summary (
    threshold  INTEGER PRIMARY KEY,
    mean_corr  DOUBLE PRECISION,
    std_corr   DOUBLE PRECISION
);

-- ============================================================
-- 7. 트랙 B: 장소×요일×시간대 혼잡도 집계 + 시간대별 평균 기온
--    (track_b_spatiotemporal.py가 CREATE TABLE AS로 생성)
-- ============================================================
CREATE TABLE congestion_hourly_summary (
    location_id              BIGINT,
    location_name            TEXT,
    category                 TEXT,
    day_of_week              SMALLINT,
    hour                     BIGINT,
    report_count             BIGINT,
    avg_reported_congestion  NUMERIC,
    avg_true_congestion      NUMERIC,
    avg_temp_c               DOUBLE PRECISION   -- weather_observations T1H 조인 결과 (없으면 NULL)
);

-- ============================================================
-- 8. 날씨 관측값 (기상청 초단기실황, fetch_weather.py가 매시간 적재)
--    long-format: 관측 시각마다 항목(category)별 한 행
-- ============================================================
CREATE TABLE weather_observations (
    id             SERIAL PRIMARY KEY,
    base_date      VARCHAR(8)  NOT NULL,        -- YYYYMMDD
    base_time      VARCHAR(4)  NOT NULL,        -- HH00
    nx             INTEGER     NOT NULL,        -- 기상청 격자 X (청주=69)
    ny             INTEGER     NOT NULL,        -- 기상청 격자 Y (청주=90)
    category       VARCHAR(10) NOT NULL,        -- T1H/RN1/REH/PTY/UUU/VVV/VEC/WSD
    category_name  VARCHAR(30),
    obs_value      VARCHAR(20),
    fetched_at     TIMESTAMP   NOT NULL DEFAULT now(),
    UNIQUE (base_date, base_time, nx, ny, category)
);
