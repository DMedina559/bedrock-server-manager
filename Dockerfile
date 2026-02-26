# Stage 1: Frontend Build
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy package files for both frontends to leverage caching
COPY frontend/legacy/package.json frontend/legacy/package-lock.json ./legacy/
COPY frontend/v2/package.json frontend/v2/package-lock.json ./v2/

# Install Legacy dependencies
WORKDIR /app/frontend/legacy
RUN npm install

# Install V2 dependencies
WORKDIR /app/frontend/v2
RUN npm install

# Copy frontend source code
WORKDIR /app/frontend
COPY frontend/ ./

# Ensure output directories exist
RUN mkdir -p /app/src/bedrock_server_manager/web/static/js/dist
RUN mkdir -p /app/src/bedrock_server_manager/web/static/v2

# Build Legacy Frontend
WORKDIR /app/frontend/legacy
RUN npm run build

# Build V2 Frontend
WORKDIR /app/frontend/v2
RUN npm run build

# Stage 2: Python Build
FROM python:3.12-slim AS python-builder
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/
# Copy Legacy Build Artifacts
COPY --from=frontend-builder /app/src/bedrock_server_manager/web/static/js/dist/bundle.js /app/src/bedrock_server_manager/web/static/js/dist/bundle.js
COPY --from=frontend-builder /app/src/bedrock_server_manager/web/static/js/dist/bundle.js.map /app/src/bedrock_server_manager/web/static/js/dist/bundle.js.map
# Copy V2 Build Artifacts
COPY --from=frontend-builder /app/src/bedrock_server_manager/web/static/v2 /app/src/bedrock_server_manager/web/static/v2
RUN pip install build
ARG APP_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${APP_VERSION}
RUN python -m build

# Stage 3: Final Python Application
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y pkg-config libmariadb-dev-compat gcc libcurl4 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=python-builder /app/dist/ /app/dist/
RUN for f in /app/dist/*.whl; do pip install "$f[mysql,mariadb,postgresql]"; done && rm -rf /app/dist
ENV HOST=0.0.0.0
ENV PORT=11325
EXPOSE 11325
EXPOSE 19132/udp
EXPOSE 19133/udp
CMD ["/bin/sh", "-c", "exec bedrock-server-manager web start --host $HOST --port $PORT"]
