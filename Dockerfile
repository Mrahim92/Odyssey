FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY theaters.yaml .
COPY config.yaml .

ENV PYTHONPATH=src

# Restart policy handled by docker compose / orchestrator
CMD ["python", "-m", "odyssey_bot", "run"]
