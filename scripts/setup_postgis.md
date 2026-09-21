# EC2 (Amazon Linux 2023) - PostgreSQL + PostGIS 설치

## 1. PostgreSQL 공식 repo 등록 (AL2023은 기본 repo 버전이 낮아서 PGDG repo 권장)

```bash
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# 기본 모듈(appstream)의 postgresql이 충돌하므로 비활성화
sudo dnf -qy module disable postgresql
```

## 2. PostgreSQL 16 설치

```bash
sudo dnf install -y postgresql16-server postgresql16-contrib

# 초기화
sudo /usr/pgsql-16/bin/postgresql-16-setup initdb

# 서비스 등록 및 시작
sudo systemctl enable --now postgresql-16
sudo systemctl status postgresql-16
```

## 3. PostGIS 설치

```bash
sudo dnf install -y postgis34_16
```

## 4. 비밀번호 설정 및 외부 접속 허용

```bash
sudo -i -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'YOUR_PASSWORD';"
```

`postgresql.conf` 수정 (보통 `/var/lib/pgsql/16/data/postgresql.conf`):
```
listen_addresses = '*'
```

`pg_hba.conf` 수정 (같은 디렉토리):
```
# 맨 아래에 추가 (외부에서 접속 허용, 필요시 IP 범위 제한 권장)
host    all             all             0.0.0.0/0               scram-sha-256
```

```bash
sudo systemctl restart postgresql-16
```

## 5. 방화벽 설정 (OS 레벨 firewalld + AWS 보안 그룹 2단계)

```bash
# firewalld (OS 레벨, AL2023은 기본 비활성화인 경우가 많음 - 필요 시에만)
sudo firewall-cmd --permanent --add-port=5432/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

AWS 콘솔(EC2 > 보안 그룹)에서 인바운드 규칙에 PostgreSQL(5432) 포트 추가
(소스는 필요한 IP 대역으로 제한 권장, 웹(80/443) 포트도 별도로 허용)

## 6. DB 및 PostGIS extension 생성

```bash
sudo -i -u postgres psql

CREATE DATABASE crowd_pipeline;
\c crowd_pipeline
CREATE EXTENSION postgis;

-- 설치 확인
SELECT postgis_version();
```

## 7. Python에서 접속 테스트용 패키지 (conda bigdata 환경)

```bash
conda activate bigdata
pip install psycopg2-binary sqlalchemy geoalchemy2
```

## 트러블슈팅

- `dnf install postgis34_16` 에서 의존성 에러 나면 EPEL repo도 필요할 수 있음:
  ```bash
  sudo dnf install -y epel-release
  ```
- PostGIS 버전(`postgis34`)은 PostgreSQL 16용 버전 번호. PostgreSQL 다른 버전 쓰면 숫자 맞춰야 함 (예: PG15 -> postgis33_15 계열, 설치 전 `dnf search postgis` 로 사용 가능한 패키지명 확인 권장)
