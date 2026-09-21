# Terraform - Nowhere Data Pipeline AWS 인프라

데이터 파이프라인용 AWS 리소스(EC2, S3, IAM 역할, 보안 그룹, Elastic IP)를 코드로 정의합니다.
백엔드([backend](https://github.com/CBNU-SWCapstone-B5-TJTS-now/backend))가 이미 사용 중인 EC2와는
별도의 인스턴스/보안 그룹으로 생성됩니다 (백엔드 서버는 메모리 여유가 없어 서비스를 추가할 수 없음).

## 사전 준비

1. AWS 계정 및 자격증명 (`aws configure`로 설정하거나 환경변수 `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` 설정)
2. [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
3. AWS 콘솔 > EC2 > 키 페어에서 SSH용 키 페어를 미리 생성 (`.pem` 파일은 안전하게 보관)
4. 본인 접속 IP 확인 (`curl ifconfig.me`) - 보안 그룹 SSH 허용 범위로 사용

## 사용법

```bash
cd terraform

# 1. 변수 파일 준비
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars를 열어 key_pair_name, ssh_allowed_cidr 등 실제 값으로 수정

# 2. 초기화
terraform init

# 3. 생성될 리소스 확인
terraform plan

# 4. 적용 (실제 AWS 리소스 생성 - 과금 발생)
terraform apply
```

적용이 끝나면 `public_ip`, `ssh_command` 등이 출력됩니다. 이후 `scripts/setup_postgis.md`를
참고해 PostgreSQL+PostGIS를 설치하거나, `docker-compose.yml`로 컨테이너를 띄우면 됩니다.

## 리소스 정리

더 이상 필요 없을 때:

```bash
terraform destroy
```

## 주의사항

- `terraform.tfvars`와 `*.tfstate`는 민감 정보(리소스 ID 등)를 포함할 수 있어 git에 커밋되지 않습니다.
- 상태 파일(`terraform.tfstate`)을 로컬에만 두면 여러 사람이 동시에 `apply`할 때 충돌할 수 있습니다.
  팀에서 계속 사용할 경우 S3 backend 등 원격 상태 저장소 구성을 검토하세요 (현재는 로컬 상태 기준).
