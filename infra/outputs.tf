# Values the CI/CD pipeline needs. Copy them into GitHub repository
# variables (Settings -> Secrets and variables -> Actions -> Variables).
# None of these are secrets.

output "site_url" {
  value = local.use_domain ? "https://${var.domain_name}" : "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "AWS_REGION" {
  value = var.aws_region
}

output "AWS_DEPLOY_ROLE_ARN" {
  value = aws_iam_role.github_deploy.arn
}

output "ECR_REPOSITORY" {
  value = aws_ecr_repository.api.name
}

output "API_FUNCTION_NAME" {
  value = aws_lambda_function.api.function_name
}

output "WORKER_FUNCTION_NAME" {
  value = aws_lambda_function.worker.function_name
}

output "SITE_BUCKET" {
  value = aws_s3_bucket.site.bucket
}

output "CLOUDFRONT_DISTRIBUTION_ID" {
  value = aws_cloudfront_distribution.site.id
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.organisers.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.admin.id
}
