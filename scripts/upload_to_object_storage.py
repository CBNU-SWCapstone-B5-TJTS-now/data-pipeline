"""
vm-03 실행용: 시뮬레이션 데이터 및 분석 결과를 OCI Object Storage에 백업

사전 준비:
1. OCI CLI 설정 완료 (oci setup config), 또는 vm-03이 Instance Principal로 인증 가능해야 함
2. 버킷이 없으면 먼저 생성:
   oci os bucket create --compartment-id <compartment-ocid> --name nowhere-pipeline-data
"""
import os
import subprocess
import pandas as pd
from sqlalchemy import create_engine

DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

BUCKET_NAME = "nowhere-pipeline-data"
EXPORT_DIR = "/home/opc/nowhere-pipeline/exports"

TABLES_TO_EXPORT = [
    "sim_users", "sim_locations", "sim_reports", "sim_votes",
    "weather_observations",
    # 아래 두 테이블은 트랙 A/B 분석 스크립트 실행 후 생성됨
    "threshold_results", "congestion_hourly_summary",
]


def export_tables_to_csv(engine):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    exported = []
    for table in TABLES_TO_EXPORT:
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", engine)
            path = os.path.join(EXPORT_DIR, f"{table}.csv")
            df.to_csv(path, index=False)
            exported.append(path)
            print(f"  {table}: {len(df)}행 -> {path}")
        except Exception as e:
            print(f"  {table}: 건너뜀 (테이블 없음 또는 에러: {e})")
    return exported


def upload_to_object_storage(file_paths):
    for path in file_paths:
        object_name = os.path.basename(path)
        cmd = [
            "oci", "os", "object", "put",
            "--bucket-name", BUCKET_NAME,
            "--file", path,
            "--name", object_name,
            "--force",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  업로드 완료: {object_name}")
        else:
            print(f"  업로드 실패: {object_name}\n{result.stderr}")


def main():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    print("=== 1. DB 테이블 CSV export ===")
    exported_files = export_tables_to_csv(engine)

    print(f"\n=== 2. Object Storage 버킷({BUCKET_NAME})에 업로드 ===")
    upload_to_object_storage(exported_files)

    print("\n완료.")


if __name__ == "__main__":
    main()
