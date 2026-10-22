# Campus Events: serverless event registration on AWS

A college event-registration website designed to survive a registration rush, keep student data safe and stay available. It covers two Co-Head technical tasks for the AWS Student Builder Group at VIT Pune:

| Task | Document |
|---|---|
| **Task 1: Cloud Architecture Case Study** | [docs/task1-architecture.md](docs/task1-architecture.md) |
| **Task 3: DevOps and Deployment Workflow** | [docs/task3-devops-workflow.md](docs/task3-devops-workflow.md) |
| Interview preparation and Q&A | [docs/INTERVIEW_GUIDE.md](docs/INTERVIEW_GUIDE.md) |

![Architecture](docs/diagrams/architecture.png)

## What's in the repo

```
backend/            FastAPI app that runs on AWS Lambda (and locally)
  app/main.py         HTTP routes, request logging, Lambda handler
  app/repository.py   DynamoDB access, incl. the no-overbooking transaction
  app/worker.py       SQS-triggered email sender
  tests/              17 unit tests (pytest + moto)
  Dockerfile          multi-stage: `local` target and Lambda target
frontend/           Static site (HTML/CSS/JS) served from S3 + CloudFront
infra/              Terraform for every AWS resource
.github/workflows/  CI/CD pipeline (GitHub Actions)
scripts/            Lambda smoke test, registration-rush concurrency test
local/              nginx config that mimics CloudFront routing locally
docs/               Task write-ups, diagrams (generated from code), interview guide
```

## Run it locally (no AWS account needed)

Requires Docker.

```bash
docker compose up --build
```

- Website: http://localhost:8080
- Interactive API docs: http://localhost:8080/api/docs
- Registration-rush test (50 students, 3 seats): `python3 scripts/concurrency_test.py`

Unit tests:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && pytest --cov=app
```

## API

| Method | Path | Who | Purpose |
|---|---|---|---|
| GET | `/api/health` | anyone | Liveness; returns running Git SHA |
| GET | `/api/health/ready` | anyone | Readiness; checks DynamoDB |
| GET | `/api/events` | anyone | List events with seats left |
| GET | `/api/events/{id}` | anyone | One event |
| POST | `/api/events/{id}/registrations` | students | Register (201, or 409 if full or duplicate) |
| POST | `/api/events` | organisers (Cognito JWT) | Create an event |

## Deploying to AWS

> Not deployed for the recruitment submission, per the guideline not to buy cloud services. Terraform is validated in CI. These are the exact steps to deploy.

Prerequisites: an AWS account, AWS CLI v2, Terraform ≥ 1.10, Docker, and an S3 bucket for Terraform state.

```bash
cd infra
cp backend.hcl.example backend.hcl            # set your state bucket
cp terraform.tfvars.example terraform.tfvars  # set github_repo, alert_email, ...
terraform init -backend-config=backend.hcl

# 1) Lambda needs an image before it can be created, so create the registry first.
terraform apply -target=aws_ecr_repository.api

# 2) Push a first ("bootstrap") image. Build for x86_64: an Apple-silicon Mac builds
#    arm64 by default, and Lambda would fail with "exec format error".
REPO=$(terraform output -raw ECR_REPOSITORY)
REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-south-1.amazonaws.com
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"
docker build --platform linux/amd64 --provenance=false -t "$REGISTRY/$REPO:bootstrap" ../backend
docker push "$REGISTRY/$REPO:bootstrap"

# 3) Everything else.
terraform plan -out=tfplan && terraform apply tfplan
terraform output
```

Then, in GitHub:
1. Create an environment named `production`, with yourself as a required reviewer.
2. Add repository **variables** (not secrets; none of these are sensitive) from `terraform output`:
   - `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `ECR_REPOSITORY`
   - `API_FUNCTION_NAME`, `WORKER_FUNCTION_NAME`
   - `SITE_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `SITE_URL`
   - `DEPLOY_ENABLED=true`
3. Push to `main`. The pipeline tests, builds and deploys.

Organiser accounts:

```bash
aws cognito-idp admin-create-user --user-pool-id <id> --username organiser@example.edu
aws cognito-idp admin-add-user-to-group --user-pool-id <id> --username organiser@example.edu --group-name organisers
```

Emails: SES starts in *sandbox* mode and only sends to verified addresses. Request production access before a real event.

Tear down: `terraform destroy`. Set `deletion_protection = false` first; the tables are protected on purpose.
