variable "project" {
  description = "Short name used as a prefix for every resource."
  type        = string
  default     = "campus-events"
}

variable "environment" {
  description = "Deployment environment, e.g. prod or staging."
  type        = string
  default     = "prod"
}

variable "aws_region" {
  description = "Main region. ap-south-1 (Mumbai) is closest to Pune, so lowest latency for students."
  type        = string
  default     = "ap-south-1"
}

variable "image_tag" {
  description = "Container image tag used when the Lambda functions are first created. Later releases are done by the CI/CD pipeline."
  type        = string
  default     = "bootstrap"
}

variable "github_repo" {
  description = "GitHub repository allowed to deploy, as owner/name."
  type        = string
  default     = "The-Creative-Developer/campus-events-cloud"
}

variable "github_oidc_subject_prefix" {
  description = <<-EOT
    The repo part of the GitHub OIDC "sub" claim. Leave empty for the classic
    "repo:owner/name" form. Repos with immutable subjects need the ID form; get
    it with: gh api repos/OWNER/REPO/actions/oidc/customization/sub
  EOT
  type        = string
  default     = "repo:The-Creative-Developer@191368524/campus-events-cloud@1430000104"
}

variable "alert_email" {
  description = "Email that receives CloudWatch alarm notifications. Empty = no subscription."
  type        = string
  default     = ""
}

variable "sender_email" {
  description = "Verified SES address confirmation emails are sent from. Empty = emails are logged, not sent."
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Optional custom domain, e.g. events.example.edu. Empty = use the default *.cloudfront.net address."
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for domain_name. Required only when domain_name is set."
  type        = string
  default     = ""
}

variable "enable_waf" {
  description = "Attach AWS WAF to CloudFront (about USD 5/month + USD 1 per rule)."
  type        = bool
  default     = true
}

variable "waf_rate_limit" {
  description = <<-EOT
    Max API requests per IP in any 5-minute window. Kept generous on purpose:
    a whole campus Wi-Fi can share ONE public IP (NAT), so a strict per-IP
    limit would block every student at once during the registration rush.
  EOT
  type        = number
  default     = 2000
}

variable "api_throttle_rate" {
  description = "Steady-state requests/second API Gateway lets through before returning 429."
  type        = number
  default     = 200
}

variable "api_throttle_burst" {
  description = "Short burst of requests API Gateway allows above the steady rate."
  type        = number
  default     = 400
}

variable "deletion_protection" {
  description = "Protect the DynamoDB tables, site bucket and image registry from accidental terraform destroy."
  type        = bool
  default     = true
}
