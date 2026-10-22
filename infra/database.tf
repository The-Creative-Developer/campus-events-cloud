# DynamoDB: fully managed NoSQL. Chosen over RDS because
#  * on-demand mode scales instantly from 0 to thousands of writes/sec and
#    costs nothing when idle (a college site is idle most of the year),
#  * data is replicated across 3 Availability Zones automatically,
#  * no servers, patching, or connection pools to manage from Lambda.

resource "aws_dynamodb_table" "events" {
  name                        = "${local.name}-events"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "event_id"
  deletion_protection_enabled = var.deletion_protection

  attribute {
    name = "event_id"
    type = "S"
  }

  # Continuous backups: restore to any second in the last 35 days.
  point_in_time_recovery {
    enabled = true
  }

  # Encryption at rest with an AWS-managed KMS key.
  server_side_encryption {
    enabled = true
  }
}

resource "aws_dynamodb_table" "registrations" {
  name                        = "${local.name}-registrations"
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "event_id"
  range_key                   = "email"
  deletion_protection_enabled = var.deletion_protection

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "email"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
