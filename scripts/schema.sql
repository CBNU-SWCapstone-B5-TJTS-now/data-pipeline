-- crowd_pipeline DB 스키마
-- 트랙 A (trust score 임계값 최적화) + 트랙 B (혼잡도 패턴 리포트) 공용

CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. 사용자 테이블
CREATE TABLE users (
    user_id        SERIAL PRIMARY KEY,
    trust_score    INTEGER NOT NULL DEFAULT 50,   -- 초기 신뢰도 50 가정
    -- 시뮬레이션 전용 컬럼: 실제 서비스 테이블엔 없음, 분석 검증용 "정답값"
    true_accuracy  NUMERIC(4,3),                   -- 0~1, 이 유저가 실제로 정확하게 제보하는 비율 (숨겨진 값)
    created_at     TIMESTAMP DEFAULT now()
);

-- 2. 장소(geofence) 테이블 - 학교 내 주요 지점들
CREATE TABLE locations (
    location_id    SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,           -- 예: '학생회관 1층', '도서관 열람실A'
    geom           GEOGRAPHY(POINT, 4326) NOT NULL, -- 위경도 좌표
    geofence_radius_m INTEGER NOT NULL DEFAULT 100   -- 100m 고정
);

-- 3. 혼잡도 제보 테이블
CREATE TABLE reports (
    report_id      SERIAL PRIMARY KEY,
    user_id        INTEGER REFERENCES users(user_id),
    location_id    INTEGER REFERENCES locations(location_id),
    reported_at    TIMESTAMP NOT NULL,
    congestion_level SMALLINT NOT NULL CHECK (congestion_level BETWEEN 1 AND 5), -- 1=여유 ~ 5=매우혼잡
    -- 시뮬레이션 전용: 실제 그 시간 그 장소의 "정답" 혼잡도 (분석 검증용)
    true_congestion_level SMALLINT,
    trust_score_at_report INTEGER  -- 제보 당시 유저의 trust_score (스냅샷)
);

-- 4. 동의/비동의 투표 테이블
CREATE TABLE votes (
    vote_id        SERIAL PRIMARY KEY,
    report_id      INTEGER REFERENCES reports(report_id),
    voter_user_id  INTEGER REFERENCES users(user_id),
    vote_type      VARCHAR(10) NOT NULL CHECK (vote_type IN ('agree', 'disagree')),
    voted_at       TIMESTAMP NOT NULL
);

-- 5. (트랙 A용) 임계값 시뮬레이션 결과 비교 테이블
CREATE TABLE threshold_experiments (
    experiment_id      SERIAL PRIMARY KEY,
    disagree_threshold INTEGER NOT NULL,   -- 비동의 몇 개부터 감소시켰는지
    agree_increment    INTEGER NOT NULL,   -- 동의 1개당 증가량
    disagree_penalty   INTEGER NOT NULL,   -- 비동의 임계 도달시 감소량
    -- 평가 지표: 이 설정으로 계산했을 때 trust_score와 true_accuracy의 상관관계
    correlation_score  NUMERIC(5,4),
    notes              TEXT
);

-- 공간 인덱스 (geofence 검색 성능)
CREATE INDEX idx_locations_geom ON locations USING GIST (geom);

-- 자주 쓸 공간 쿼리 예시: 특정 좌표 100m 반경 내 location 찾기
-- SELECT * FROM locations
-- WHERE ST_DWithin(geom, ST_MakePoint(:lng, :lat)::geography, geofence_radius_m);
