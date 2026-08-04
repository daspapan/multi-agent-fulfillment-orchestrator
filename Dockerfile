# Orchestrator service container. Runs on ECS Fargate (see infra-cdk/).
# Multi-stage isn't needed here -- pure Python, no compiled deps beyond
# what pip already resolves as wheels.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONPATH=/app
EXPOSE 8080

# ANTHROPIC_API_KEY is injected at deploy time via Secrets Manager (see
# infra-cdk/lib/compute-stack.ts) -- never baked into the image.
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
