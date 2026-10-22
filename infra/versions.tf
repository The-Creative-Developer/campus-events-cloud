terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Remote state: the record of what Terraform has created lives in S3, not
  # on one person's laptop, so the whole team (and CI) share one source of
  # truth. use_lockfile stops two people applying at the same time.
  # Values are supplied at init time:  terraform init -backend-config=backend.hcl
  backend "s3" {
    key          = "campus-events/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  # Every resource gets these tags, which makes cost reports and clean-up easy.
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# CloudFront is a global service: its TLS certificate and WAF must live in
# us-east-1 no matter where the rest of the stack runs.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name = "${var.project}-${var.environment}"
}
