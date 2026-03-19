# Node-Watch API

A FastAPI-based infrastructure monitoring API for collecting and analyzing server metrics.

## Features

- **Metrics Collection**: Receive and store server metrics (CPU, memory, disk, network, processes)
- **Server Monitoring**: Track server health status with configurable thresholds
- **Time-Series Data**: Query historical metrics data
- **Alert Configuration**: Set custom thresholds for different metrics
- **Health Monitoring**: Automatic health status calculation (healthy/warning/critical)

## API Endpoints

### Authentication
- POST endpoints require `X-API-Key` header
- GET endpoints are read-only (no authentication required)

### Endpoints

#### Health Check
- `GET /health` - API health status

#### Metrics
- `POST /api/v1/metrics` - Submit server metrics
- `GET /api/v1/servers/{server_id}/metrics?hours=24` - Get time-series metrics

#### Servers
- `GET /api/v1/servers` - List all monitored servers
- `GET /api/v1/servers/{server_id}/status` - Get server health status

#### Alerts
- `POST /api/v1/alerts/configure` - Configure alert thresholds

## Health Status Logic

- **Healthy**: CPU <80%, RAM <85%, disk <90%, last seen <5 minutes
- **Warning**: One metric exceeds threshold OR last seen 5-15 minutes
- **Critical**: Multiple metrics exceed thresholds OR last seen >15 minutes

## Quick Start

### Using Docker Compose
```bash
# Start the service
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Using Docker
```bash
# Build image
docker build -t node-watch-api .

# Run container
docker run -d \
  --name node-watch-api \
  -p 9081:9081 \
  -e API_KEY=your-secret-key \
  -v $(pwd)/data:/app/data \
  node-watch-api
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export API_KEY=your-secret-key

# Run the application
python main.py
```

## Configuration

### Environment Variables
- `API_KEY`: Authentication key for POST endpoints (default: `nodewatch-secret-key-2024`)

### Database
- SQLite database auto-created on startup
- Stored in `/app/data/nodewatch.db` (Docker) or current directory

## Example Usage

### Submit Metrics
```bash
curl -X POST http://localhost:9081/api/v1/metrics \
  -H "Content-Type: application/json" \
  -H "X-API-Key: nodewatch-secret-key-2024" \
  -d '{
    "server_id": "web-01",
    "hostname": "web-server-01",
    "timestamp": "2024-01-01T12:00:00Z",
    "cpu_percent": 75.5,
    "memory_percent": 80.2,
    "disk_percent": 45.0,
    "load_avg": 2.1,
    "network_sent": 1024000,
    "network_recv": 2048000,
    "processes": [
      {"pid": 1234, "name": "nginx", "cpu": 10.5, "memory": 128.5}
    ]
  }'
```

### Get Server Status
```bash
curl http://localhost:9081/api/v1/servers/web-01/status
```

### List Servers
```bash
curl http://localhost:9081/api/v1/servers
```

### Configure Alerts
```bash
curl -X POST http://localhost:9081/api/v1/alerts/configure \
  -H "Content-Type: application/json" \
  -H "X-API-Key: nodewatch-secret-key-2024" \
  -d '{
    "server_id": "web-01",
    "metric_name": "cpu_percent",
    "threshold": 85.0,
    "email": "admin@example.com"
  }'
```

## Production Deployment

The application is production-ready with:
- Multi-stage Docker build for minimal image size
- Non-root user execution
- Health checks
- Resource limits
- Logging configuration
- Error handling and logging
- Database connection pooling
- Graceful error responses

## License

MIT License