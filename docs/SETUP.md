# Setup Guide

How to bring this project back up later. Each level builds on the one before, so stop at the level you need:

| Level | What you get | Cost | Time |
|---|---|---|---|
| 1. Run locally | Working site + API on your laptop | Free | 5 min |
| 2. Develop and test | Run tests, edit code, rebuild docs | Free | 10 min |
| 3. GitHub pipeline | CI on every push (already working) | Free | 5 min |
| 4. Deploy to AWS | Real public website | Mostly free tier; ~US$8/month if WAF is on | 1–2 hours |

---

## Level 1: Run it locally

**You need:** Docker Desktop and Git.

```bash
git clone https://github.com/The-Creative-Developer/campus-events-cloud.git
cd campus-events-cloud
open -a Docker              # macOS: start Docker Desktop, wait for the whale icon to settle
docker compose up --build   # first build takes a few minutes; later ones are fast
```

Open:
- http://localhost:8080: the website, with two sample events
- http://localhost:8080/api/docs: interactive API docs (you can create events here; admin auth is off locally)

In a second terminal, run the registration-rush demo (50 students, 3 seats):

```bash
python3 scripts/concurrency_test.py
```

It prints `PASS: no overbooking`. Run it only once per fresh start, because the bootcamp event is then full. Restart with `docker compose down -v && docker compose up` to reset the data.

**Stop everything:**

```bash
docker compose down -v      # -v also deletes the local database
```

Optionally quit Docker Desktop. To also free disk space, remove the built images:

```bash
docker image rm campus-events-cloud-api campus-events-cloud-seed
```

---

## Level 2: Develop and test

**You need:** Python **3.12** (matches Lambda; 3.13+ also works for tests).

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

ruff check . && ruff format --check .        # lint
pytest --cov=app --cov-report=term-missing   # 17 tests, expect ~87% coverage
```

Other useful commands, run from the repo root:

| Task | Command |
|---|---|
| Run the API without Docker (needs DynamoDB Local running) | `cd backend && DYNAMODB_ENDPOINT=http://localhost:8001 ADMIN_AUTH_DISABLED=true uvicorn app.main:app --reload` |
| Test the production Lambda image | `docker build -t campus-events-api:test ./backend && scripts/lambda_smoke_test.sh campus-events-api:test` |
| Scan the image for vulnerabilities | `docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.1 image --severity CRITICAL,HIGH --ignore-unfixed campus-events-api:test` |
| Check Terraform without installing it | `docker run --rm -v "$PWD/infra":/infra -w /infra --entrypoint sh hashicorp/terraform:latest -c "terraform fmt -check && terraform init -backend=false && terraform validate"` |
| Regenerate the diagrams | `python3 docs/diagrams/make_diagrams.py` (writes SVGs; open them in Chrome to export PNGs) |
| Rebuild the PDFs after editing docs | `pip install markdown-it-py && python3 scripts/build_pdfs.py` (needs Google Chrome) |

DynamoDB Local isn't exposed on a host port by default. To use it outside Docker, add `ports: ["8001:8000"]` under the `dynamodb` service in `docker-compose.yml`.

**Typical change workflow** (the one described in Task 3):

```bash
git switch -c my-change
# edit code, then run tests
git commit -am "Describe the change"
git push -u origin my-change
gh pr create --fill          # CI runs on the pull request; merge when green
```

---

## Level 3: GitHub pipeline

Already working: every push and pull request runs lint, tests, the image build and scan, the rush test and the Terraform checks. The **Deploy** job is skipped until Level 4 is done.

Recommended, in the repo's **Settings → Branches → Add rule** for `main`:
- Require a pull request before merging
- Require status checks to pass: the `ci-cd` jobs

Watch runs at https://github.com/The-Creative-Developer/campus-events-cloud/actions, or locally with `gh run list` / `gh run watch`.

---

## Level 4: Deploy to AWS (optional, uses real money)

> Do this only when you actually want it live (e.g. for a real club event), not for the recruitment submission.

### 4.1 Make the AWS account safe first
1. Turn on **MFA for the root user**, then stop using root.
2. Create an admin identity through **IAM Identity Center**, and run `aws configure sso` on your laptop.
3. Create an **AWS Budget** with an email alert, e.g. US$5. This is your safety net against surprise bills.
4. Check the Lambda concurrency quota in **Service Quotas → AWS Lambda → Concurrent executions**. It should be 1,000. New accounts can start lower; request an increase if so.

### 4.2 Tools
AWS CLI v2, Terraform ≥ 1.10 (`brew install hashicorp/tap/terraform`), and Docker.

### 4.3 One-time: a bucket for Terraform state
```bash
BUCKET=campus-events-tfstate-$(aws sts get-caller-identity --query Account --output text)
aws s3api create-bucket --bucket "$BUCKET" --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
echo "$BUCKET"
```

### 4.4 Configure and create the infrastructure
```bash
cd infra
cp backend.hcl.example backend.hcl            # put the bucket name from 4.3
cp terraform.tfvars.example terraform.tfvars  # set alert_email, sender_email; enable_waf = false to save ~$8/month
terraform init -backend-config=backend.hcl

# Step 1: create only the image registry, because Lambda needs an image to exist first
terraform apply -target=aws_ecr_repository.api

# Step 2: push a first image. --platform matters on Apple-silicon Macs.
REPO=$(terraform output -raw ECR_REPOSITORY)
REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-south-1.amazonaws.com
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin "$REGISTRY"
docker build --platform linux/amd64 --provenance=false -t "$REGISTRY/$REPO:bootstrap" ../backend
docker push "$REGISTRY/$REPO:bootstrap"

# Step 3: everything else. Review the plan before applying.
terraform plan -out=tfplan
terraform apply tfplan
terraform output
```

Confirm the SNS email subscription (check your inbox) so alarms reach you.

### 4.5 Connect GitHub to AWS
In the repo's **Settings → Environments**, create `production` and add yourself as a required reviewer.

In **Settings → Secrets and variables → Actions → Variables**, add the following (none of them are secret):

| Variable | Value |
|---|---|
| `AWS_REGION` | `terraform output -raw AWS_REGION` |
| `AWS_DEPLOY_ROLE_ARN` | `terraform output -raw AWS_DEPLOY_ROLE_ARN` |
| `ECR_REPOSITORY` | `terraform output -raw ECR_REPOSITORY` |
| `API_FUNCTION_NAME` | `terraform output -raw API_FUNCTION_NAME` |
| `WORKER_FUNCTION_NAME` | `terraform output -raw WORKER_FUNCTION_NAME` |
| `SITE_BUCKET` | `terraform output -raw SITE_BUCKET` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `terraform output -raw CLOUDFRONT_DISTRIBUTION_ID` |
| `SITE_URL` | `terraform output -raw site_url` |
| `DEPLOY_ENABLED` | `true` |

Or set them all from the terminal:

```bash
cd infra
for v in AWS_REGION AWS_DEPLOY_ROLE_ARN ECR_REPOSITORY API_FUNCTION_NAME WORKER_FUNCTION_NAME SITE_BUCKET CLOUDFRONT_DISTRIBUTION_ID; do
  gh variable set "$v" --body "$(terraform output -raw $v)"
done
gh variable set SITE_URL --body "$(terraform output -raw site_url)"
gh variable set DEPLOY_ENABLED --body true
```

Then push any commit to `main` (or use **Actions → ci-cd → Run workflow**) and approve the deployment when asked. The deploy job:
1. pushes the image
2. publishes and smoke-tests a new Lambda version
3. switches the `live` alias
4. uploads the site
5. checks `SITE_URL/api/health`

### 4.6 Before a real event
- **Emails:** SES starts in sandbox mode, which only sends to verified addresses. Verify `sender_email` (click the link AWS emails you), then **request SES production access** in the SES console.
- **Organiser login:**
  ```bash
  POOL=$(terraform output -raw cognito_user_pool_id)
  aws cognito-idp admin-create-user --user-pool-id "$POOL" --username you@example.edu
  aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username you@example.edu --group-name organisers
  ```
- **Create the event** with `POST /api/events`, sending the organiser's token in the `Authorization` header.
- Run a load test against the live URL a few days before. Watch the CloudWatch dashboard `campus-events-prod` during the rush.

### 4.7 Approximate cost
| Item | Monthly |
|---|---|
| Lambda, API Gateway, DynamoDB, SQS, S3, CloudFront, SES at club scale | Free tier to a few cents |
| CloudWatch logs and alarms | Free tier to < US$1 |
| AWS WAF (`enable_waf = true`) | ~US$8 |
| Route 53 hosted zone (only with a custom domain) | US$0.50 |

Check with the AWS Pricing Calculator for your numbers.

### 4.8 Tear it all down
```bash
cd infra
# 1) Switch off the protection (it's on by default on purpose)
terraform apply -var deletion_protection=false
# 2) Delete everything, including stored images and website files
terraform destroy -var deletion_protection=false
```

Finally, delete the state bucket from 4.3 if you don't need it any more.

---

## Common problems

| Symptom | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | Start Docker Desktop (`open -a Docker`) and wait ~30 s |
| Port 8080 or 8000 already in use | Stop the other app, or change `ports:` in `docker-compose.yml` |
| Rush test says `FAIL` | The event was already full from a previous run: `docker compose down -v` and start again |
| `exec format error` in Lambda | Image built for arm64 on a Mac; rebuild with `--platform linux/amd64` |
| `terraform apply`: image does not exist | Do steps 1 and 2 in 4.4 before the full apply |
| `Error acquiring the state lock` | Another apply is running; wait. If it crashed: `terraform force-unlock <id>` |
| Deploy job: `Not authorized to perform sts:AssumeRoleWithWebIdentity` | The OIDC subject in the role's trust policy doesn't match what GitHub sends. Run `gh api repos/OWNER/REPO/actions/oidc/customization/sub`; if `use_immutable_subject` is true, set `github_oidc_subject_prefix` to its `sub_claim_prefix`. Also check the job runs in the `production` environment |
| Site shows old version | CloudFront cache: the invalidation step must succeed; hard-refresh the browser |
| Emails not arriving | SES sandbox (see 4.6), or check the dead-letter queue |
