FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN pip install --no-cache-dir .
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && if [ \"${RUN_WORKER:-false}\" = \"true\" ]; then python -m fluxqueue.worker & fi; exec uvicorn fluxqueue.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
