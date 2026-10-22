# Amazon Cognito: login for event organisers (club co-heads), not students.
# Students register without an account - lower friction during the rush.
# Organisers sign in, get a JWT, and only tokens from users in the
# "organisers" group can create events.

resource "aws_cognito_user_pool" "organisers" {
  name = "${local.name}-organisers"

  # Organisers are invited by an admin; nobody can sign themselves up.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]
}

resource "aws_cognito_user_group" "organisers" {
  name         = "organisers"
  user_pool_id = aws_cognito_user_pool.organisers.id
  description  = "May create and manage events"
}

# Public client (no secret): used by the admin page / CLI to obtain tokens.
resource "aws_cognito_user_pool_client" "admin" {
  name                          = "${local.name}-admin"
  user_pool_id                  = aws_cognito_user_pool.organisers.id
  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  access_token_validity         = 1 # hours
  id_token_validity             = 1
}
