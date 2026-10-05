FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/onboarding.db \
    POLICY_CORPUS_PATH=/app/docs/policies

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser docs/policies ./docs/policies

USER 10001
EXPOSE 8080

CMD ["uvicorn", "app.infrastructure.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
