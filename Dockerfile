# syntax=docker/dockerfile:1

# Frontend --------------------------------------------------------------------
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
ENV PUBLIC_API_URL=
RUN npm run build

# Backend ---------------------------------------------------------------------
FROM python:3.13-slim AS runtime
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
COPY server/ server/
COPY cli/ cli/
COPY samples/ samples/

RUN uv sync --frozen --package promptuna-server --no-dev

COPY --from=frontend /app/frontend/build /app/static

ENV PROMPTUNA_PROJECTS_ROOT=/app/samples \
    PROMPTUNA_STATIC_DIR=/app/static

EXPOSE 8080

CMD ["uv", "run", "--frozen", "--no-dev", "uvicorn", "promptuna_server.main:app", "--host", "0.0.0.0", "--port", "8080"]
