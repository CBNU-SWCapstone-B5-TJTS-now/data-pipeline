data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "pipeline" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.pipeline.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_pipeline.name

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
  }

  tags = {
    Name    = "${var.project_name}-ec2"
    Project = var.project_name
  }

  lifecycle {
    # AMI는 최초 생성 시점 기준으로 고정한다. most_recent = true인 data source를
    # 그대로 두면, 이후 AWS가 새 AL2023 AMI를 배포했을 때 보안 그룹 등 무관한
    # 변경만으로도 apply할 때 인스턴스 전체가 교체(destroy + create)되어
    # 인스턴스에 설치한 모든 것이 날아가는 사고로 이어진다.
    ignore_changes = [ami]
  }
}

resource "aws_eip" "pipeline" {
  instance = aws_instance.pipeline.id
  domain   = "vpc"

  tags = {
    Name    = "${var.project_name}-eip"
    Project = var.project_name
  }
}
