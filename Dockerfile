# syntax=docker/dockerfile:1

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system nutrition \
    && adduser --system --ingroup nutrition nutrition

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data/foods_v2.json ./data/foods_v2.json

RUN python -m pip install --no-cache-dir . \
    && mkdir -p /app/data/runtime \
    && chown -R nutrition:nutrition /app/data/runtime

USER nutrition

EXPOSE 8000

CMD ["nutrition-bot"]
