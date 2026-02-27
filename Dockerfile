# Stage 1: Python Build
FROM python:3.12-slim AS python-builder
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --upgrade pip build
ARG APP_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${APP_VERSION}
RUN python -m build

# Stage 2: Final Python Application
FROM python:3.12-slim
WORKDIR /app
# Install system dependencies
# gcc and libmariadb-dev-compat are often needed for mysqlclient/mariadb driver compilation if binaries aren't available
RUN apt-get update && \
    apt-get install -y --no-install-recommends pkg-config libmariadb-dev-compat gcc libcurl4 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy built wheel from builder stage
COPY --from=python-builder /app/dist/ /app/dist/

# Install the package (this will pull bsm-frontend from PyPI)
RUN pip install --no-cache-dir /app/dist/*.whl[mysql,mariadb,postgresql] && \
    rm -rf /app/dist

# Set default environment variables
ENV HOST=0.0.0.0
ENV PORT=11325

# Expose ports
EXPOSE 11325
EXPOSE 19132/udp
EXPOSE 19133/udp

# Command to run the application
CMD ["/bin/sh", "-c", "exec bedrock-server-manager web start --host $HOST --port $PORT"]
