variable "aws_region" {
  description = "리소스를 생성할 AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "project_name" {
  description = "리소스 이름/태그에 붙일 프로젝트 식별자"
  type        = string
  default     = "nowhere-pipeline"
}

variable "instance_type" {
  description = "EC2 인스턴스 타입 (프리티어: t2.micro 또는 t3.micro, 리전별 프리티어 대상 확인 필요)"
  type        = string
  default     = "t3.micro"
}

variable "root_volume_size_gb" {
  description = "루트 EBS 볼륨 크기(GB)"
  type        = number
  default     = 20
}

variable "key_pair_name" {
  description = "SSH 접속용 기존 EC2 키페어 이름 (AWS 콘솔에서 미리 생성 필요)"
  type        = string
}

variable "ssh_allowed_cidr" {
  description = "SSH(22번 포트) 접속을 허용할 CIDR (본인 IP/32 권장, 0.0.0.0/0 비권장)"
  type        = string
}

variable "s3_bucket_name" {
  description = "백업용 S3 버킷 이름 (전역적으로 유일해야 함)"
  type        = string
  default     = "nowhere-pipeline-data"
}
