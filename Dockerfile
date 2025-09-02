# Stage 1: Frontend Build
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python Build
FROM python:3.12-slim AS python-builder
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY --from=frontend-builder /app/src/bedrock_server_manager/web/static/js/dist/bundle.js /app/src/bedrock_server_manager/web/static/js/dist/bundle.js
COPY --from=frontend-builder /app/src/bedrock_server_manager/web/static/js/dist/bundle.js.map /app/src/bedrock_server_manager/web/static/js/dist/bundle.js.map
RUN pip install build
RUN python -m build

# Stage 3: Final Python Application
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y pkg-config libmariadb-dev gcc libcurl4 && rm -rf /var/lib/apt/lists/*
COPY --from=python-builder /app/dist/ /app/dist/
RUN for f in /app/dist/*.whl; do pip install "$f[mysql,mariadb,postgresql]"; done
EXPOSE 11325
CMD ["bedrock-server-manager", "web", "start", "--host", "0.0.0.0"]
