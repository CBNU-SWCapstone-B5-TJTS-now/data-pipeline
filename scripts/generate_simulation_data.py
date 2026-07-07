"""
vm-03 실행용: 시뮬레이션 데이터 생성 + PostgreSQL(crowd_pipeline) 적재
실행 전: conda activate bigdata && pip install psycopg2-binary sqlalchemy --break-system-packages

최종 확정 스펙 반영:
- Trust Score 기본값 50, 범위 0~100
- 반대 임계값: 3개까지 무사, 초과분마다 -1 (최종 설계)
- 동의 1개당 +1
- 실제 캠퍼스 장소 4곳 (DataInitializer.java 기준 실좌표)
"""
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

# ---- DB 접속 정보 (crowd_app 계정, 비밀번호는 환경변수로 관리 권장) ----
import os
DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")  # 실행 전 export CROWD_APP_PW=... 로 설정
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

np.random.seed(42)

# ============================================================
# 1. 유저 생성 (기본 Trust Score 50)
# ============================================================
N_USERS = 200
users = pd.DataFrame({
    "user_id": range(1, N_USERS + 1),
    "true_accuracy": np.concatenate([
        np.random.beta(8, 2, int(N_USERS * 0.85)),   # 성실 유저 85%
        np.random.beta(2, 5, int(N_USERS * 0.15)),    # 어뷰징성 유저 15%
    ])
})
users["true_accuracy"] = users["true_accuracy"].clip(0.05, 0.98)
users["trust_score"] = 50  # 최종 설계 기본값

# ============================================================
# 2. 장소 (실제 코드 DataInitializer.java 기준 실좌표)
# ============================================================
locations = pd.DataFrame({
    "location_id": [1, 2, 3, 4],
    "name": ["한빛식당", "중앙도서관", "라운지", "로이작업실"],
    "latitude": [36.6276540, 36.6281650, 36.6275070, 36.6322380],
    "longitude": [127.4589540, 127.4580790, 127.4586380, 127.4575860],
    "category": ["SCHOOL", "SCHOOL", "CAFE", "CAFE"],
    "geofence_radius_m": [100, 100, 80, 80],
})

# ============================================================
# 3. 제보 생성
# ============================================================
N_REPORTS = 800
reports = pd.DataFrame({
    "report_id": range(1, N_REPORTS + 1),
    "reporter_id": np.random.choice(users["user_id"], N_REPORTS),
    "location_id": np.random.choice(locations["location_id"], N_REPORTS),
    "hour": np.random.choice(range(8, 22), N_REPORTS),
})

def true_congestion(hour, location_id):
    base = 2.0
    if 12 <= hour <= 13:
        base += 2.0
    if 18 <= hour <= 19:
        base += 1.0
    if location_id == 1:  # 한빛식당(SCHOOL, 학식)은 항상 더 혼잡
        base += 0.5
    noise = np.random.normal(0, 0.4)
    return float(np.clip(base + noise, 1, 5))

reports["true_congestion"] = reports.apply(
    lambda r: true_congestion(r["hour"], r["location_id"]), axis=1
)
reports = reports.merge(users[["user_id", "true_accuracy"]], left_on="reporter_id", right_on="user_id")
reports["reported_congestion"] = reports.apply(
    lambda r: round(np.clip(r["true_congestion"] + np.random.normal(0, (1 - r["true_accuracy"]) * 3), 1, 5)),
    axis=1
)
reports = reports.drop(columns=["user_id"])

# ============================================================
# 4. 투표 생성
# ============================================================
votes_list = []
vote_id = 1
for _, rep in reports.iterrows():
    n_voters = np.random.randint(3, 10)
    voters = np.random.choice(users["user_id"], n_voters, replace=False)
    for voter_id in voters:
        voter_acc = users.loc[users["user_id"] == voter_id, "true_accuracy"].values[0]
        is_report_accurate = abs(rep["reported_congestion"] - rep["true_congestion"]) <= 1
        agree_prob = voter_acc if is_report_accurate else (1 - voter_acc)
        vote_type = "agree" if np.random.random() < agree_prob else "disagree"
        votes_list.append({
            "vote_id": vote_id, "report_id": rep["report_id"],
            "voter_id": voter_id, "vote_type": vote_type
        })
        vote_id += 1
votes = pd.DataFrame(votes_list)

# ============================================================
# 5. Trust Score 계산 (최종 설계: 반대 3개 초과분마다 -1, 동의 1개당 +1, 0~100 클리핑)
# ============================================================
def calc_trust_scores(disagree_threshold=3, agree_increment=1, base_score=50, floor=0, ceiling=100):
    scores = {uid: base_score for uid in users["user_id"]}
    vote_counts = votes.merge(reports[["report_id", "reporter_id"]], on="report_id") \
        .groupby(["report_id", "reporter_id", "vote_type"]).size().unstack(fill_value=0)
    if "agree" not in vote_counts.columns: vote_counts["agree"] = 0
    if "disagree" not in vote_counts.columns: vote_counts["disagree"] = 0
    for (report_id, reporter_id), row in vote_counts.iterrows():
        scores[reporter_id] += row["agree"] * agree_increment
        excess = max(0, row["disagree"] - disagree_threshold)
        scores[reporter_id] -= excess
    for uid in scores:
        scores[uid] = max(floor, min(ceiling, scores[uid]))
    return scores

final_scores = calc_trust_scores()
users["trust_score"] = users["user_id"].map(final_scores)

# ============================================================
# 6. DB 적재
# ============================================================
print("DB 적재 시작...")
locations.to_sql("sim_locations", engine, if_exists="replace", index=False)
users.to_sql("sim_users", engine, if_exists="replace", index=False)
reports.to_sql("sim_reports", engine, if_exists="replace", index=False)
votes.to_sql("sim_votes", engine, if_exists="replace", index=False)
print(f"완료: users={len(users)}, locations={len(locations)}, reports={len(reports)}, votes={len(votes)}")

# ============================================================
# 7. 위경도를 PostGIS geography 컬럼으로 변환 (sim_locations에 geom 추가)
# ============================================================
with engine.connect() as conn:
    from sqlalchemy import text
    conn.execute(text("""
        ALTER TABLE sim_locations ADD COLUMN IF NOT EXISTS geom geography(Point, 4326);
    """))
    conn.execute(text("""
        UPDATE sim_locations
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography;
    """))
    conn.commit()
print("PostGIS geom 컬럼 생성 및 좌표 반영 완료")
