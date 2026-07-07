"""
2단계 (트랙 A): 여러 반대 임계값으로 Trust Score를 계산해보고,
각 임계값에서 trust_score가 실제 정확도(true_accuracy)를 얼마나 잘 반영하는지 비교한다.

핵심 질문: "반대가 몇 개 이상일 때 감점해야, trust_score가 실제로 신뢰할 만한 유저를 잘 구별하는가?"
"""
import pandas as pd
import numpy as np
from scipy.stats import pearsonr

users = pd.read_csv("/home/claude/sim_users.csv")
votes = pd.read_csv("/home/claude/sim_votes.csv")


def calc_trust_score(disagree_threshold, agree_increment=1, disagree_penalty=1, base_score=50):
    """
    현재 백로그 정책을 임계값만 바꿔서 재현:
    - 기본 점수 base_score
    - 제보 하나당 '동의' 수만큼 +agree_increment
    - 제보 하나당 '반대' 수가 disagree_threshold 이상이면 -disagree_penalty
    """
    scores = {uid: base_score for uid in users["user_id"]}

    # 유저별로 자신이 올린 제보들에 대한 투표 결과를 집계해야 하므로,
    # report_id 기준으로 reporter_id를 다시 붙인다.
    reports = pd.read_csv("/home/claude/sim_reports.csv")[["report_id", "reporter_id"]]
    v = votes.merge(reports, on="report_id")

    # 제보(report_id)별로 동의/반대 수 집계
    vote_counts = v.groupby(["report_id", "reporter_id", "vote_type"]).size().unstack(fill_value=0)
    if "agree" not in vote_counts.columns:
        vote_counts["agree"] = 0
    if "disagree" not in vote_counts.columns:
        vote_counts["disagree"] = 0

    for (report_id, reporter_id), row in vote_counts.iterrows():
        scores[reporter_id] += row["agree"] * agree_increment
        if row["disagree"] >= disagree_threshold:
            scores[reporter_id] -= disagree_penalty

    return pd.Series(scores, name="trust_score")


# ---- 여러 임계값으로 반복 실험 ----
thresholds_to_test = [1, 2, 3, 4, 5, 7, 10]
results = []

for th in thresholds_to_test:
    trust = calc_trust_score(disagree_threshold=th)
    merged = users.set_index("user_id").drop(columns=["trust_score"]).join(trust)
    corr, pval = pearsonr(merged["true_accuracy"], merged["trust_score"])
    results.append({
        "disagree_threshold": th,
        "correlation_with_true_accuracy": round(corr, 4),
        "p_value": round(pval, 4),
        "trust_score_mean": round(merged["trust_score"].mean(), 1),
        "trust_score_std": round(merged["trust_score"].std(), 1),
    })

result_df = pd.DataFrame(results)
print("=== 임계값별 Trust Score vs 실제 정확도 상관관계 ===")
print(result_df.to_string(index=False))
print()

best = result_df.loc[result_df["correlation_with_true_accuracy"].idxmax()]
print(f"가장 상관관계가 높은 임계값: 반대 {int(best['disagree_threshold'])}개 "
      f"(상관계수 {best['correlation_with_true_accuracy']})")
print(f"→ (참고) 현재 백로그 정책값: 반대 3개")

result_df.to_csv("/home/claude/track_a_results.csv", index=False)
