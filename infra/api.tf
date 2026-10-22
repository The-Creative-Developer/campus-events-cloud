# Backend: container image in ECR -> Lambda -> API Gateway (HTTP API).
#
# Who owns what:
#   Terraform  creates the infrastructure (function, permissions, alias, API).
#   CI/CD      ships new code: pushes an image, publishes a Lambda version,
#              smoke-tests it, then moves the "live" alias to it.
# That's why image_uri and the alias version are in ignore_changes below -
# otherwise every `terraform apply` would roll production back to the
# bootstrap image.

# ---------- Container registry ----------

resource "aws_ecr_repository" "api" {
  name = local.name
  # A tag (git SHA) can never be overwritten, so "what is running" is always
  # traceable to exactly one commit.
  image_tag_mutability = "IMMUTABLE"
  # Allow `terraform destroy` to delete stored images only when protection is off.
  force_delete = !var.deletion_protection

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 20 most recent images (enough to roll back), delete older ones"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 20 }
      action       = { type = "expire" }
    }]
  })
}

# ---------- IAM: least privilege for the API function ----------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${local.name}-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "api_logs" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "api_xray" {
  role       = aws_iam_role.api.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Only the exact actions the code uses, only on our two tables and one queue.
# No Scan on registrations, no DeleteItem anywhere, no access to other tables.
data "aws_iam_policy_document" "api" {
  statement {
    sid       = "ReadEvents"
    actions   = ["dynamodb:GetItem", "dynamodb:Scan", "dynamodb:DescribeTable"]
    resources = [aws_dynamodb_table.events.arn]
  }
  statement {
    sid       = "WriteEventsAndRegistrations"
    actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.events.arn, aws_dynamodb_table.registrations.arn]
  }
  statement {
    sid       = "QueueConfirmationEmails"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.confirmations.arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "app-permissions"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

# ---------- Lambda function ----------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = 30 # logs cost money; 30 days covers any investigation
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name}-api"
  role          = aws_iam_role.api.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 512 # Lambda gives CPU in proportion to memory; 512 MB keeps p95 latency low
  timeout       = 10  # API Gateway gives up at 30 s; fail fast well before that
  publish       = true

  environment {
    variables = {
      EVENTS_TABLE        = aws_dynamodb_table.events.name
      REGISTRATIONS_TABLE = aws_dynamodb_table.registrations.name
      QUEUE_URL           = aws_sqs_queue.confirmations.url
    }
  }

  tracing_config {
    mode = "Active" # X-Ray: see time spent in Lambda vs DynamoDB vs SQS per request
  }

  depends_on = [aws_cloudwatch_log_group.api, aws_iam_role_policy_attachment.api_logs]

  lifecycle {
    ignore_changes = [image_uri] # releases are done by CI/CD, see top of file
  }
}

# API Gateway calls the "live" alias, never $LATEST. A release is just moving
# this pointer, and a rollback is moving it back - instant, no rebuild.
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.api.function_name
  function_version = aws_lambda_function.api.version

  lifecycle {
    ignore_changes = [function_version] # moved by CI/CD
  }
}

# ---------- API Gateway (HTTP API) ----------

resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name}-http"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_alias.live.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 12000
}

# Public routes: everything under /api.
resource "aws_apigatewayv2_route" "public" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "ANY /api/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# Creating events is organiser-only. API Gateway validates the Cognito JWT
# itself and rejects bad tokens with 401 before Lambda is ever invoked
# (so attackers can't even make us pay for a Lambda run).
resource "aws_apigatewayv2_route" "create_event" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "POST /api/events"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.http.id
  name             = "cognito-organisers"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = "https://${aws_cognito_user_pool.organisers.endpoint}"
    audience = [aws_cognito_user_pool_client.admin.id]
  }
}

resource "aws_cloudwatch_log_group" "api_access" {
  name              = "/aws/apigateway/${local.name}-http"
  retention_in_days = 30
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  # Throttling protects the backend (and the bill) from floods: beyond this
  # rate API Gateway answers 429 Too Many Requests without invoking Lambda.
  default_route_settings {
    throttling_rate_limit    = var.api_throttle_rate
    throttling_burst_limit   = var.api_throttle_burst
    detailed_metrics_enabled = true
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      method         = "$context.httpMethod"
      path           = "$context.path"
      status         = "$context.status"
      latencyMs      = "$context.responseLatency"
      integrationErr = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  qualifier     = aws_lambda_alias.live.name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
