"""
기상청 공공데이터포털 - 초단기실황조회(getUltraSrtNcst) API 연동
청주 격자좌표: nx=69, ny=90

실행 전: conda activate bigdata
API 키, DB 비밀번호는 .env 파일(WEATHER_API_KEY, CROWD_APP_PW)에서 읽음 (python-dotenv).
cron에서 매시간 실행 예정.
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

API_KEY = os.environ.get("WEATHER_API_KEY", "")
DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

NX, NY = 69, 90  # 청주
ENDPOINT = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"

CATEGORY_NAMES = {
    "T1H": "기온(C)", "RN1": "1시간강수량(mm)", "UUU": "동서바람성분(m/s)",
    "VVV": "남북바람성분(m/s)", "REH": "습도(%)", "PTY": "강수형태",
    "VEC": "풍향(deg)", "WSD": "풍속(m/s)",
}


def get_base_datetime(now: datetime) -> tuple[str, str]:
    """초단기실황은 매시 40분에 관측값이 생성됨 -> 40분 이전이면 이전 시각 데이터 사용"""
    if now.minute < 40:
        now = now - timedelta(hours=1)
    return now.strftime("%Y%m%d"), now.strftime("%H00")


def fetch_weather(base_date: str, base_time: str) -> list[dict]:
    if not API_KEY:
        raise RuntimeError("WEATHER_API_KEY가 설정되지 않았습니다 (.env 확인)")

    params = {
        "serviceKey": API_KEY,
        "pageNo": "1",
        "numOfRows": "10",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": NX,
        "ny": NY,
    }
    resp = requests.get(ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()

    try:
        body = resp.json()
    except ValueError:
        raise RuntimeError(f"JSON 파싱 실패 (인증키 미승인/오류 가능성). 원본 응답:\n{resp.text[:500]}")

    header = body.get("response", {}).get("header", {})
    result_code = header.get("resultCode")
    if result_code != "00":
        raise RuntimeError(f"API 오류 [{result_code}] {header.get('resultMsg')}")

    items = body["response"]["body"]["items"]["item"]
    return items


def save_to_db(items: list[dict], base_date: str, base_time: str):
    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weather_observations (
                id SERIAL PRIMARY KEY,
                base_date VARCHAR(8) NOT NULL,
                base_time VARCHAR(4) NOT NULL,
                nx INTEGER NOT NULL,
                ny INTEGER NOT NULL,
                category VARCHAR(10) NOT NULL,
                category_name VARCHAR(30),
                obs_value VARCHAR(20),
                fetched_at TIMESTAMP NOT NULL DEFAULT now(),
                UNIQUE (base_date, base_time, nx, ny, category)
            );
        """))
        for item in items:
            category = item["category"]
            conn.execute(text("""
                INSERT INTO weather_observations
                    (base_date, base_time, nx, ny, category, category_name, obs_value)
                VALUES (:base_date, :base_time, :nx, :ny, :category, :category_name, :obs_value)
                ON CONFLICT (base_date, base_time, nx, ny, category)
                DO UPDATE SET obs_value = EXCLUDED.obs_value, fetched_at = now();
            """), {
                "base_date": base_date, "base_time": base_time,
                "nx": NX, "ny": NY, "category": category,
                "category_name": CATEGORY_NAMES.get(category, category),
                "obs_value": item["obsrValue"],
            })
        conn.commit()


def main():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    base_date, base_time = get_base_datetime(now)
    print(f"[{now.isoformat()}] 조회 기준: base_date={base_date}, base_time={base_time}, nx={NX}, ny={NY}")

    items = fetch_weather(base_date, base_time)
    print(f"수신 항목 {len(items)}건:")
    for item in items:
        name = CATEGORY_NAMES.get(item["category"], item["category"])
        print(f"  - {name}: {item['obsrValue']}")

    save_to_db(items, base_date, base_time)
    print("weather_observations 테이블 저장 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"오류 발생: {e}", file=sys.stderr)
        sys.exit(1)
