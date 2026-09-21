"""
EC2 실행용: 시뮬레이션 데이터 및 분석 결과를 AWS S3에 백업

사전 준비:
1. EC2 인스턴스에 S3 접근 권한이 있는 IAM 역할(Instance Profile)을 연결하거나,
   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY 환경변수를 설정해야 함
2. 버킷이 없으면 먼저 생성:
   aws s3 mb s3://nowhere-pipeline-data --region ap-northeast-2
"""
import os
import pandas as pd
import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine

DB_USER = "crowd_app"
DB_PASSWORD = os.environ.get("CROWD_APP_PW", "")
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "crowd_pipeline"

BUCKET_NAME = os.environ.get("AWS_S3_BUCKET", "nowhere-pipeline-data")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
EXPORT_DIR = "/home/ec2-user/nowhere-pipeline/exports"

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


def upload_to_s3(file_paths):
    s3 = boto3.client("s3", region_name=AWS_REGION)
    for path in file_paths:
        object_name = os.path.basename(path)
        try:
            s3.upload_file(path, BUCKET_NAME, object_name)
            print(f"  업로드 완료: {object_name}")
        except ClientError as e:
            print(f"  업로드 실패: {object_name}\n{e}")


def main():
    engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

    print("=== 1. DB 테이블 CSV export ===")
    exported_files = export_tables_to_csv(engine)

    print(f"\n=== 2. S3 버킷({BUCKET_NAME})에 업로드 ===")
    upload_to_s3(exported_files)

    print("\n완료.")


if __name__ == "__main__":
    main()