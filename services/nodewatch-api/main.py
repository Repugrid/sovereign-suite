from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import sqlite3
import json
import logging
import os
import urllib.request
from database import Database, ServerInfo, AlertConfig, MetricData

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Configuration
API_KEY = os.getenv("API_KEY", "nodewatch-secret-key-2024")
api_key_header = APIKeyHeader(name="X-API-Key")

app = FastAPI(
    title="Node-Watch API",
    description="Infrastructure monitoring API for server metrics and alerts",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database with persistent path
db = Database(db_path="/app/data/nodewatch.db")

# Telegram notifications for new servers
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
_known_servers: set[str] = set()


def _tg_notify(text: str):
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        payload = json.dumps({"chat_id": TG_CHAT, "text": text, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key for POST endpoints"""
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    return api_key

# Agent payload models (matching agent format)
class AgentMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_avg: List[float]
    network_bytes_sent: int
    network_bytes_recv: int
    top_processes: List[Dict[str, Any]]

class AgentPayload(BaseModel):
    server_id: str
    timestamp: datetime
    metrics: AgentMetrics

# API Response models
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime

class ServerStatus(BaseModel):
    server_id: str
    hostname: str
    status: str  # healthy, warning, critical
    last_seen: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    load_avg: Optional[float] = None
    details: List[str] = []

class ServerListResponse(BaseModel):
    servers: List[ServerInfo]

class MetricsResponse(BaseModel):
    server_id: str
    metrics: List[MetricData]
    count: int

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow()
    )

@app.post("/api/v1/metrics")
async def receive_metrics(payload: AgentPayload):
    """Receive and store metric payloads from monitoring agents"""
    try:
        # Extract hostname from server_id (format: hostname-uuid)
        hostname = payload.server_id.split('-')[0] if '-' in payload.server_id else payload.server_id
        
        # Store metrics in database
        db.store_metrics(
            server_id=payload.server_id,
            hostname=hostname,
            timestamp=payload.timestamp,
            cpu_percent=payload.metrics.cpu_percent,
            memory_percent=payload.metrics.memory_percent,
            disk_percent=payload.metrics.disk_percent,
            load_avg=payload.metrics.load_avg[0] if payload.metrics.load_avg else None,
            network_sent=payload.metrics.network_bytes_sent,
            network_recv=payload.metrics.network_bytes_recv,
            processes=payload.metrics.top_processes
        )
        
        logger.info(f"Stored metrics for server {payload.server_id}")

        # Notify on NEW server registration
        if payload.server_id not in _known_servers:
            _known_servers.add(payload.server_id)
            # Check if truly new (not just a restart)
            info = db.get_server_info(payload.server_id)
            if info and info.first_seen == info.last_seen:
                _tg_notify(
                    "🚀 *New server registered!*\n"
                    f"ID: `{payload.server_id}`\n"
                    f"Host: {hostname}\n"
                    f"CPU: {payload.metrics.cpu_percent}% | "
                    f"RAM: {payload.metrics.memory_percent}% | "
                    f"Disk: {payload.metrics.disk_percent}%"
                )

        return {"status": "success", "message": "Metrics stored successfully"}
        
    except Exception as e:
        logger.error(f"Error storing metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store metrics: {str(e)}"
        )

@app.get("/api/v1/servers", response_model=ServerListResponse)
async def list_servers():
    """List all servers with last-seen timestamps"""
    try:
        servers = db.get_all_servers()
        return ServerListResponse(servers=servers)
    except Exception as e:
        logger.error(f"Error retrieving servers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve servers: {str(e)}"
        )

@app.get("/api/v1/servers/{server_id}/metrics", response_model=MetricsResponse)
async def get_server_metrics(server_id: str, hours: int = 24):
    """Get time-series metrics for a specific server"""
    try:
        if hours <= 0 or hours > 168:  # Max 7 days
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hours must be between 1 and 168"
            )
        
        metrics = db.get_server_metrics(server_id, hours)
        return MetricsResponse(
            server_id=server_id,
            metrics=metrics,
            count=len(metrics)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving metrics for {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )

@app.get("/api/v1/servers/{server_id}/status", response_model=ServerStatus)
async def get_server_status(server_id: str):
    """Get health status for a specific server"""
    try:
        server_info = db.get_server_info(server_id)
        if not server_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Server not found"
            )
        
        # Get latest metrics
        latest_metrics = db.get_latest_metrics(server_id)
        
        # Calculate status (strip timezone info for comparison)
        now = datetime.utcnow()
        last_seen = server_info.last_seen.replace(tzinfo=None) if server_info.last_seen.tzinfo else server_info.last_seen

        # Time since last seen
        time_diff = (now - last_seen).total_seconds() / 60  # minutes
        
        status_result = "healthy"
        details = []
        
        # Check time threshold
        if time_diff > 15:
            status_result = "critical"
            details.append(f"No data for {time_diff:.1f} minutes")
        elif time_diff > 5:
            status_result = "warning"
            details.append(f"Stale data ({time_diff:.1f} minutes old)")
        
        # Check metric thresholds if we have recent data
        if latest_metrics and time_diff <= 15:
            threshold_violations = 0
            
            if latest_metrics.cpu_percent and latest_metrics.cpu_percent >= 80:
                threshold_violations += 1
                details.append(f"High CPU: {latest_metrics.cpu_percent:.1f}%")
            
            if latest_metrics.memory_percent and latest_metrics.memory_percent >= 85:
                threshold_violations += 1
                details.append(f"High Memory: {latest_metrics.memory_percent:.1f}%")
            
            if latest_metrics.disk_percent and latest_metrics.disk_percent >= 90:
                threshold_violations += 1
                details.append(f"High Disk: {latest_metrics.disk_percent:.1f}%")
            
            # Determine status based on violations
            if threshold_violations >= 2:
                status_result = "critical"
            elif threshold_violations == 1 and status_result == "healthy":
                status_result = "warning"
        
        return ServerStatus(
            server_id=server_id,
            hostname=server_info.hostname,
            status=status_result,
            last_seen=last_seen,
            cpu_percent=latest_metrics.cpu_percent if latest_metrics else None,
            memory_percent=latest_metrics.memory_percent if latest_metrics else None,
            disk_percent=latest_metrics.disk_percent if latest_metrics else None,
            load_avg=latest_metrics.load_avg if latest_metrics else None,
            details=details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for {server_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get server status: {str(e)}"
        )

@app.post("/api/v1/alerts/configure")
async def configure_alerts(
    alert_config: AlertConfig,
    api_key: str = Depends(verify_api_key)
):
    """Configure alert thresholds"""
    try:
        db.store_alert_config(alert_config)
        logger.info(f"Configured alert for {alert_config.server_id}")
        return {"status": "success", "message": "Alert configuration stored"}
    except Exception as e:
        logger.error(f"Error configuring alert: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure alert: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9081)