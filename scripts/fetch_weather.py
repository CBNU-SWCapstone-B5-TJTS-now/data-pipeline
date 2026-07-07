"""
vm-03 실행용: 기상청 공공데이터(초단기실황) API 연동
- 혼잡도 시계열(sim_reports)과 시간대별 날씨 데이터를 조인하여 상관관계 분석
- 이걸로 "수집(Collect)" 요구사항의 실제 공공 API 소스를 충족시킴

실행 전: export WEATHER_API_KEY="발급받은_일반인증키(Decoding)"
"""
import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# 청주 지역 기상청 격자 좌표 (nx, ny) - 공공데이터포털 "기상청 단기예보 조회서비스" 격자변환표 기준
NX, NY = 69, 90  # 충북 청주 흥덕구 인근

BASE_URL = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"


def fetch_current_weather():
    """초단기실황: 현재 시각 기준 최신 관측값 (기온, 강수형태, 습도 등)"""
    now = datetime.now()
    # 초단기실황은 매시 40분 이후 그 시각 데이터가 생성됨 -> 안전하게 1시간 전 데이터 요청
    base_time_dt = now - timedelta(hours=1)
    base_date = base_time_dt.strftime("%Y%m%d")
    base_time = base_time_dt.strftime("%H00")

    params = {
        "serviceKey": WEATHER_API_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": NX,
        "ny": NY,
    }
    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    items = data["response"]["body"]["items"]["item"]
    result = {item["category"]: item["obsrValue"] for item in items}
    # T1H: 기온(C), RN1: 1시간 강수량(mm), REH: 습도(%), PTY: 강수형태코드
    return {
        "observed_at": base_time_dt,
        "temperature": float(result.get("T1H", "nan")),
        "precipitation_mm": float(result.get("RN1", "0").replace("강수없음", "0")) if "RN1" in result else 0.0,
        "humidity": float(result.get("REH", "nan")),
        "precip_type_code": result.get("PTY", "0"),
    }


def main():
    if not WEATHER_API_KEY:
        print("경고: WEATHER_API_KEY 환경변수가 설정되지 않았습니다.")
        print("export WEATHER_API_KEY='발급받은 키' 로 설정 후 재실행하세요.")
        return

    weather = fetch_current_weather()
    print("=== 현재 날씨 관측값 ===")
    print(weather)

    # 날씨 스냅샷을 DB에 저장 (누적 - 매시간 cron으로 실행하면 시계열이 쌓임)
    df = pd.DataFrame([weather])
    df.to_sql("weather_observations", engine, if_exists="append", index=False)
    print("weather_observations 테이블에 저장 완료")

    # ---- 참고용: 혼잡도 시뮬레이션 데이터의 시간대별 평균과 비교(현재 시점 데이터 1건 기준 예시) ----
    reports = pd.read_sql("SELECT hour, reported_congestion FROM sim_reports", engine)
    hourly_avg = reports.groupby("hour")["reported_congestion"].mean()
    current_hour = weather["observed_at"].hour
    if current_hour in hourly_avg.index:
        print(f"\n참고: 현재 시간대({current_hour}시)의 시뮬레이션 평균 혼잡도 = {hourly_avg[current_hour]:.2f}")
        print("(날씨 데이터가 매시간 누적되면, 추후 온도/강수와 혼잡도의 상관관계 분석 가능)")


if __name__ == "__main__":
    main()
