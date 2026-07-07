"""
3단계 (트랙 B): 장소x시간대별 혼잡도를 집계해서 패턴을 찾는다.
실제로는 PostGIS의 ST_DWithin으로 geofence 반경 내 제보를 묶지만,
여기서는 이미 location_id로 정리된 데이터를 그대로 groupby 집계한다.
(→ 실제 프로젝트에서는 위경도 좌표 → geofence 매칭이 이 groupby 이전 단계에서 PostGIS가 처리)
"""
import pandas as pd

reports = pd.read_csv("/home/claude/sim_reports.csv")
locations = pd.read_csv("/home/claude/sim_locations.csv")

reports = reports.merge(locations, on="location_id")

# 장소 x 시간대별 평균 혼잡도(제보값 기준) 집계
pivot = reports.pivot_table(
    index="name", columns="hour", values="reported_congestion", aggfunc="mean"
).round(2)

print("=== 장소 x 시간대별 평균 혼잡도 (제보 기준) ===")
print(pivot)
print()

# 가장 혼잡한 시간대/장소 Top 5
melted = reports.groupby(["name", "hour"])["reported_congestion"].mean().reset_index()
top5 = melted.sort_values("reported_congestion", ascending=False).head(5)
print("=== 혼잡도 Top 5 (장소 x 시간대) ===")
print(top5.to_string(index=False))
print()

# 장소별 하루 평균 혼잡도
by_location = reports.groupby("name")["reported_congestion"].mean().sort_values(ascending=False).round(2)
print("=== 장소별 하루 평균 혼잡도 ===")
print(by_location)

pivot.to_csv("/home/claude/track_b_pivot.csv")
melted.to_csv("/home/claude/track_b_melted.csv", index=False)
