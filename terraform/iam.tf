# EC2가 인스턴스 자체 자격증명(IAM 역할)으로 S3에 백업할 수 있게 하는 역할.
# scripts/upload_to_object_storage.py 실행 시 AWS_ACCESS_KEY_ID/SECRET 없이도 동작함.

resource "aws_iam_role" "ec2_pipeline" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "s3_backup" {
  name = "${var.project_name}-s3-backup"
  role = aws_iam_role.ec2_pipeline.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.pipeline_data.arn,
        "${aws_s3_bucket.pipeline_data.arn}/*",
      ]
    }]
  })
}

resource "aws_iam_instance_profile" "ec2_pipeline" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_pipeline.name
}
