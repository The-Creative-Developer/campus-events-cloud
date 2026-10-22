# Monitoring: alarms that page a human, plus a dashboard for the event day.
# Rule of thumb used here: alarm on what STUDENTS feel (errors, slowness,
# lost emails), not on every internal blip.

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

locals {
  alarms = {
    api-5xx = {
      description = "Students are seeing server errors (HTTP 5xx) from the API."
      namespace   = "AWS/ApiGateway"
      metric      = "5xx"
      dimensions  = { ApiId = aws_apigatewayv2_api.http.id }
      statistic   = "Sum"
      threshold   = 5
    }
    lambda-errors = {
      description = "The API function is throwing unhandled exceptions."
      namespace   = "AWS/Lambda"
      metric      = "Errors"
      dimensions  = { FunctionName = aws_lambda_function.api.function_name }
      statistic   = "Sum"
      threshold   = 3
    }
    lambda-throttles = {
      description = "Lambda hit its concurrency limit - requests are being rejected. Check the account concurrency quota."
      namespace   = "AWS/Lambda"
      metric      = "Throttles"
      dimensions  = { FunctionName = aws_lambda_function.api.function_name }
      statistic   = "Sum"
      threshold   = 1
    }
    emails-dead-lettered = {
      description = "Confirmation emails failed 5 times and were moved to the DLQ."
      namespace   = "AWS/SQS"
      metric      = "ApproximateNumberOfMessagesVisible"
      dimensions  = { QueueName = aws_sqs_queue.confirmations_dlq.name }
      statistic   = "Maximum"
      threshold   = 1
    }
    enqueue-failures = {
      description = "Registrations succeeded but their email could not be queued (see API logs)."
      namespace   = "CampusEvents"
      metric      = "EnqueueFailures"
      dimensions  = {}
      statistic   = "Sum"
      threshold   = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "this" {
  for_each = local.alarms

  alarm_name          = "${local.name}-${each.key}"
  alarm_description   = each.value.description
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  dimensions          = each.value.dimensions
  statistic           = each.value.statistic
  period              = 300
  evaluation_periods  = 1
  threshold           = each.value.threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching" # no traffic at 3 a.m. is not an outage
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# Latency uses a percentile, not an average: an average hides the 5% of
# students who waited 4 seconds.
resource "aws_cloudwatch_metric_alarm" "api_latency_p95" {
  alarm_name          = "${local.name}-api-latency-p95"
  alarm_description   = "5% of API requests are slower than 1.5 s."
  namespace           = "AWS/ApiGateway"
  metric_name         = "Latency"
  dimensions          = { ApiId = aws_apigatewayv2_api.http.id }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  threshold           = 1500
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

# Turns a specific log message into a number we can alarm on.
resource "aws_cloudwatch_log_metric_filter" "enqueue_failures" {
  name           = "${local.name}-enqueue-failures"
  log_group_name = aws_cloudwatch_log_group.api.name
  pattern        = "{ $.message = \"Failed to enqueue confirmation email\" }"

  metric_transformation {
    name      = "EnqueueFailures"
    namespace = "CampusEvents"
    value     = "1"
  }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = local.name
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "API requests and errors"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", aws_apigatewayv2_api.http.id],
            [".", "4xx", ".", "."],
            [".", "5xx", ".", "."],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "API latency (ms)"
          region = var.aws_region
          period = 60
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiId", aws_apigatewayv2_api.http.id, { stat = "p50" }],
            ["...", { stat = "p95" }],
            ["...", { stat = "p99" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "Lambda concurrency, throttles, errors"
          region = var.aws_region
          period = 60
          metrics = [
            ["AWS/Lambda", "ConcurrentExecutions", "FunctionName", aws_lambda_function.api.function_name, { stat = "Maximum" }],
            [".", "Throttles", ".", ".", { stat = "Sum" }],
            [".", "Errors", ".", ".", { stat = "Sum" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "Email queue backlog"
          region = var.aws_region
          stat   = "Maximum"
          period = 60
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.confirmations.name],
            ["...", aws_sqs_queue.confirmations_dlq.name],
          ]
        }
      },
    ]
  })
}
