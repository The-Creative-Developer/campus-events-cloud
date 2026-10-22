#!/usr/bin/env bash
# Runs the production Lambda image locally and sends it the same API Gateway
# event AWS would send. Proves the image starts, the handler path is right,
# and Mangum + FastAPI answer correctly - before anything reaches AWS.
#
#   scripts/lambda_smoke_test.sh <image>
set -euo pipefail

IMAGE="${1:?usage: lambda_smoke_test.sh <image>}"
NAME="lambda-smoke-$$"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# The AWS base image includes the Runtime Interface Emulator on port 8080.
docker run -d --name "$NAME" -p 9000:8080 \
  -e AWS_REGION=ap-south-1 -e AWS_ACCESS_KEY_ID=x -e AWS_SECRET_ACCESS_KEY=x \
  "$IMAGE" >/dev/null

URL="http://localhost:9000/2015-03-31/functions/function/invocations"
for _ in $(seq 1 20); do
  if RESPONSE=$(curl -sf -X POST "$URL" -d @"$SCRIPT_DIR/health-event.json"); then
    break
  fi
  sleep 1
done

echo "Lambda response: ${RESPONSE:-<none>}"
STATUS=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["statusCode"])' "${RESPONSE:-{\}}" 2>/dev/null || echo "none")
if [[ "$STATUS" != "200" ]]; then
  echo "FAIL: expected statusCode 200, got $STATUS"
  docker logs "$NAME"
  exit 1
fi
echo "PASS: Lambda image answered /api/health"
