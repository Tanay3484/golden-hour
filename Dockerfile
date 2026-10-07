FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PORT=8000
CMD ["sh", "-c", "uvicorn golden_hour.main:app --host 0.0.0.0 --port ${PORT}"]
