"""
트랙 A: Trust Score 반대(disagree) 임계값 1~10에 대해,
사용자의 (숨겨진) true_accuracy와 최종 trust_score의 상관관계를 검증해
어떤 임계값이 실제 정확도를 가장 잘 반영하는지 확인한다.

다중 시드(10회) 반복: 매번 유저/제보/투표를 새로 시뮬레이션해서
특정 난수 draw에 의한 우연이 아니라 임계값 선택의 효과가 안정적인지 검증.

결과는 threshold_results 테이블(seed, threshold, pearson_corr, n_users)에 저장.

최종 설계 반영: Trust Score 기본값 50, 범위 0~100 클리핑,
반대 임계값 T까지 무사·초과분마다 -1, 동의 1개당 +1.
혼잡도는 generate_simulation_data.py와 동일하게 LOW/MEDIUM/HIGH 3단계(순서형 1/2/3)로
표현하고, 투표 정확도는 "정확히 일치"할 때만 정확한 제보로 판정한다.
(generate_simulation_data.py와 동일한 시뮬레이션 로직 — 유저/제보/투표 생성 규칙만 재사용,
 여기서는 DB의 sim_* 테이블과 무관하게 독립적으로 반복 시뮬레이션한다.)
"""
import os

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

N_USERS = 200
N_REPORTS = 800
THRESHOLDS = range(1, 11)
SEEDS = range(1, 11)  # 다중 시드 10회

CONGESTION_LEVELS = ["LOW", "MEDIUM", "HIGH"]
CONGESTION_ORD = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
ORD_TO_LEVEL = {v: k for k, v in CONGESTION_ORD.items()}


def simulate_one_seed(seed: int):
    rng = np.random.default_rng(seed)

    users = pd.DataFrame({
        "user_id": range(1, N_USERS + 1),
        "true_accuracy": np.concatenate([
            rng.beta(8, 2, int(N_USERS * 0.85)),
            rng.beta(2, 5, int(N_USERS * 0.15)),
        ]),
    })
    users["true_accuracy"] = users["true_accuracy"].clip(0.05, 0.98)

    locations_ids = [1, 2, 3, 4]
    reports = pd.DataFrame({
        "report_id": range(1, N_REPORTS + 1),
        "reporter_id": rng.choice(users["user_id"], N_REPORTS),
        "location_id": rng.choice(locations_ids, N_REPORTS),
        "hour": rng.choice(range(8, 22), N_REPORTS),
    })

    def true_congestion_probs(hour, location_id):
        is_peak = (12 <= hour <= 13) or (18 <= hour <= 19)
        probs = np.array([0.15, 0.35, 0.50]) if is_peak else np.array([0.50, 0.35, 0.15])
        if location_id == 1:
            probs = np.clip(probs + np.array([-0.10, 0.0, 0.10]), 0.05, None)
            probs = probs / probs.sum()
        return probs

    def sample_true_congestion(hour, location_id):
        probs = true_congestion_probs(hour, location_id)
        return rng.choice(CONGESTION_LEVELS, p=probs)

    reports["true_congestion"] = reports.apply(
        lambda r: sample_true_congestion(r["hour"], r["location_id"]), axis=1
    )
    reports = reports.merge(users[["user_id", "true_accuracy"]], left_on="reporter_id", right_on="user_id")

    def sample_reported_congestion(true_level, true_accuracy):
        true_ord = CONGESTION_ORD[true_level]
        noise = rng.normal(0, (1 - true_accuracy) * 1.2)
        reported_ord = int(np.clip(round(true_ord + noise), 1, 3))
        return ORD_TO_LEVEL[reported_ord]

    reports["reported_congestion"] = reports.apply(
        lambda r: sample_reported_congestion(r["true_congestion"], r["true_accuracy"]), axis=1,
    )
    reports = reports.drop(columns=["user_id"])

    votes_list = []
    vote_id = 1
    for _, rep in reports.iterrows():
        n_voters = rng.integers(3, 10)
        voters = rng.choice(users["user_id"], n_voters, replace=False)
        for voter_id in voters:
            voter_acc = users.loc[users["user_id"] == voter_id, "true_accuracy"].values[0]
            # 3단계 척도에서는 "정확히 일치"할 때만 정확한 제보로 판정
            is_report_accurate = rep["reported_congestion"] == rep["true_congestion"]
            agree_prob = voter_acc if is_report_accurate else (1 - voter_acc)
            vote_type = "agree" if rng.random() < agree_prob else "disagree"
            votes_list.append({
                "vote_id": vote_id, "report_id": rep["report_id"],
                "voter_id": voter_id, "vote_type": vote_type,
            })
            vote_id += 1
    votes = pd.DataFrame(votes_list)

    return users, reports, votes


def calc_trust_scores(users, reports, votes, disagree_threshold, agree_increment=1, base_score=50, floor=0, ceiling=100):
    scores = {uid: base_score for uid in users["user_id"]}
    vote_counts = votes.merge(reports[["report_id", "reporter_id"]], on="report_id") \
        .groupby(["report_id", "reporter_id", "vote_type"]).size().unstack(fill_value=0)
    if "agree" not in vote_counts.columns:
        vote_counts["agree"] = 0
    if "disagree" not in vote_counts.columns:
        vote_counts["disagree"] = 0
    for (report_id, reporter_id), row in vote_counts.iterrows():
        scores[reporter_id] += row["agree"] * agree_increment
        excess = max(0, row["disagree"] - disagree_threshold)
        scores[reporter_id] -= excess
    for uid in scores:
        scores[uid] = max(floor, min(ceiling, scores[uid]))
    return scores


def main():
    results = []
    for seed in SEEDS:
        users, reports, votes = simulate_one_seed(seed)
        for threshold in THRESHOLDS:
            scores = calc_trust_scores(users, reports, votes, threshold)
            trust = users["user_id"].map(scores)
            corr = float(np.corrcoef(trust, users["true_accuracy"])[0, 1])
            results.append({
                "seed": seed, "threshold": threshold,
                "pearson_corr": corr, "n_users": N_USERS,
            })
            print(f"seed={seed:2d} threshold={threshold:2d}  pearson_corr={corr:+.4f}")

    results_df = pd.DataFrame(results)

    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    results_df.to_sql("threshold_results", engine, if_exists="replace", index=False)

    summary = results_df.groupby("threshold")["pearson_corr"].agg(["mean", "std"]).reset_index()
    summary = summary.sort_values("mean", ascending=False)
    best = summary.iloc[0]

    print("\n=== 임계값별 평균 상관계수 (10개 시드) ===")
    print(summary.to_string(index=False))
    print(f"\n최적 임계값: {int(best['threshold'])} (평균 pearson_corr={best['mean']:.4f}, std={best['std']:.4f})")

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS threshold_summary (
                threshold INTEGER PRIMARY KEY,
                mean_corr DOUBLE PRECISION,
                std_corr DOUBLE PRECISION
            );
        """))
        conn.execute(text("TRUNCATE threshold_summary;"))
        for _, row in summary.iterrows():
            conn.execute(text("""
                INSERT INTO threshold_summary (threshold, mean_corr, std_corr)
                VALUES (:threshold, :mean_corr, :std_corr);
            """), {
                "threshold": int(row["threshold"]),
                "mean_corr": float(row["mean"]),
                "std_corr": float(row["std"]),
            })
        conn.commit()
    print("threshold_results, threshold_summary 테이블 저장 완료")


if __name__ == "__main__":
    main()
