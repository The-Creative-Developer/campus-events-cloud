# Confirmation emails: API -> SQS queue -> worker Lambda -> SES.
# The queue decouples the two: a burst of 2,000 registrations becomes 2,000
# queued messages that are emailed steadily, instead of 2,000 slow email
# calls blocking the API during the rush.

resource "aws_sqs_queue" "confirmations_dlq" {
  name                      = "${local.name}-confirmations-dlq"
  message_retention_seconds = 1209600 # 14 days to investigate and replay
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "confirmations" {
  name                    = "${local.name}-confirmations"
  sqs_managed_sse_enabled = true
  # Must be >= 6x the worker timeout (AWS guidance) so a message isn't handed
  # to a second worker while the first is still processing it.
  visibility_timeout_seconds = 180

  # After 5 failed attempts, park the message in the dead-letter queue
  # instead of retrying forever.
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.confirmations_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_iam_role" "worker" {
  name               = "${local.name}-worker"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "worker_logs" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "ConsumeQueue"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.confirmations.arn]
  }
  statement {
    sid       = "SendEmail"
    actions   = ["ses:SendEmail"]
    resources = ["*"]
    # Can only send *from* our own address, even though SES needs "*" here.
    condition {
      test     = "StringEquals"
      variable = "ses:FromAddress"
      values   = [var.sender_email == "" ? "none@invalid" : var.sender_email]
    }
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "app-permissions"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${local.name}-worker"
  retention_in_days = 30
}

# Same image as the API, different entry point.
resource "aws_lambda_function" "worker" {
  function_name = "${local.name}-worker"
  role          = aws_iam_role.worker.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
  architectures = ["x86_64"]
  memory_size   = 256
  timeout       = 30

  image_config {
    command = ["app.worker.handler"]
  }

  environment {
    variables = {
      SENDER_EMAIL = var.sender_email
    }
  }

  depends_on = [aws_cloudwatch_log_group.worker, aws_iam_role_policy_attachment.worker_logs]

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_event_source_mapping" "confirmations" {
  event_source_arn        = aws_sqs_queue.confirmations.arn
  function_name           = aws_lambda_function.worker.arn
  batch_size              = 10
  function_response_types = ["ReportBatchItemFailures"] # retry only the failed messages

  # Cap parallel email senders so we stay under the SES sending rate.
  scaling_config {
    maximum_concurrency = 5
  }
}

resource "aws_ses_email_identity" "sender" {
  count = var.sender_email == "" ? 0 : 1
  email = var.sender_email
}
