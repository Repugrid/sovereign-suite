# Multi-stage build for Node-Watch API
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd -r nodewatch && useradd -r -g nodewatch nodewatch

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=builder /root/.local /home/nodewatch/.local

# Copy application code
COPY main.py database.py ./

# Create data directory for SQLite database
RUN mkdir -p /app/data && chown -R nodewatch:nodewatch /app

# Switch to non-root user
USER nodewatch

# Add local bin to PATH
ENV PATH=/home/nodewatch/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9081/health')" || exit 1

# Expose port
EXPOSE 9081

# Set default environment variables
ENV API_KEY=nodewatch-secret-key-2024

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9081", "--workers", "1"]