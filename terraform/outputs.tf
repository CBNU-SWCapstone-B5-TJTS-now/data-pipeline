output "instance_id" {
  description = "생성된 EC2 인스턴스 ID"
  value       = aws_instance.pipeline.id
}

output "public_ip" {
  description = "Elastic IP (고정 퍼블릭 IP)"
  value       = aws_eip.pipeline.public_ip
}

output "s3_bucket_name" {
  description = "백업용 S3 버킷 이름"
  value       = aws_s3_bucket.pipeline_data.bucket
}

output "security_group_id" {
  description = "EC2 보안 그룹 ID"
  value       = aws_security_group.pipeline.id
}

output "ssh_command" {
  description = "SSH 접속 명령 예시"
  value       = "ssh -i <key_pair_name>.pem ec2-user@${aws_eip.pipeline.public_ip}"
}
