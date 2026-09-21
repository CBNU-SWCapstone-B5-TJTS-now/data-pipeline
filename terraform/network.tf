# 계정 기본 VPC를 사용 (별도 VPC 구성은 이 프로젝트 범위 밖)
data "aws_vpc" "default" {
  default = true
}

resource "aws_security_group" "pipeline" {
  name        = "${var.project_name}-sg"
  description = "Nowhere data-pipeline EC2 보안 그룹 (백엔드와 별도 인스턴스/그룹)"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  ingress {
    description = "Streamlit 대시보드 (nginx 리버스 프록시 경유)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = var.project_name
  }
}
