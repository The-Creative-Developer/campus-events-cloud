# One Dockerfile, two build targets:
#   docker build --target local  .   -> runs as a normal web server (uvicorn) for laptops
#   docker build                 .   -> (default, last stage) the image AWS Lambda runs
# Both share the "base" stage, so the code and dependencies are byte-for-byte
# the same; only the start command differs.

# AWS's official Lambda base image: Amazon Linux + Python 3.12 + the Lambda
# Runtime Interface Client. It also bundles the Runtime Interface Emulator,
# which lets us invoke the Lambda image locally / in CI exactly as AWS would.
FROM public.ecr.aws/lambda/python:3.12 AS base

# Copy requirements first and install them in their own layer. Docker caches
# layers, so when only app code changes, this slow step is skipped.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY app ${LAMBDA_TASK_ROOT}/app

# Git commit SHA injected by CI (docker build --build-arg APP_VERSION=...).
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}


FROM base AS local
RUN pip install --no-cache-dir uvicorn==0.54.0
EXPOSE 8000
# The Lambda base image's entrypoint starts the Lambda runtime; clear it so
# we can run a plain web server instead.
ENTRYPOINT []
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM base AS lambda
# "module.function" that Lambda calls for each request.
CMD ["app.main.handler"]
