# Lets GitHub Actions deploy WITHOUT storing any AWS keys in GitHub.
#
# GitHub issues the workflow a short-lived OIDC token saying "I am repo X,
# running in environment production". AWS checks that claim against the
# trust policy below and hands back temporary credentials (valid ~1 hour).
# Nothing long-lived exists that could leak.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only jobs in OUR repo that run in the protected "production"
    # environment - not forks, not other branches' pull requests.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:environment:production"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${local.name}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

# The pipeline can ship code. It cannot change infrastructure, read the
# database, or touch IAM - those stay with reviewed `terraform apply` runs.
data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart", "ecr:DescribeImages",
    ]
    resources = [aws_ecr_repository.api.arn]
  }
  statement {
    sid = "ReleaseLambda"
    actions = [
      "lambda:UpdateFunctionCode", "lambda:PublishVersion", "lambda:GetFunction",
      "lambda:GetFunctionConfiguration", "lambda:GetAlias", "lambda:UpdateAlias", "lambda:InvokeFunction",
    ]
    resources = [
      aws_lambda_function.api.arn, "${aws_lambda_function.api.arn}:*",
      aws_lambda_function.worker.arn, "${aws_lambda_function.worker.arn}:*",
    ]
  }
  statement {
    sid       = "UploadSite"
    actions   = ["s3:ListBucket", "s3:PutObject", "s3:DeleteObject"]
    resources = [aws_s3_bucket.site.arn, "${aws_s3_bucket.site.arn}/*"]
  }
  statement {
    sid       = "InvalidateCache"
    actions   = ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"]
    resources = [aws_cloudfront_distribution.site.arn]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
