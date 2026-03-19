import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import os

logger = logging.getLogger(__name__)

class ServerInfo(BaseModel):
    server_id: str
    hostname: str
    first_seen: datetime
    last_seen: datetime

class AlertConfig(BaseModel):
    server_id: str
    metric_name: str  # cpu_percent, memory_percent, disk_percent, load_avg
    threshold: float
    email: str

class MetricData(BaseModel):
    timestamp: datetime
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    load_avg: Optional[float] = None
    network_sent: Optional[int] = None
    network_recv: Optional[int] = None
    processes_json: Optional[str] = None

class Database:
    def __init__(self, db_path: str = "nodewatch.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database with required tables"""
        try:
            with self.get_connection() as conn:
                # Create metrics table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        server_id TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        disk_percent REAL,
                        load_avg REAL,
                        network_sent INTEGER,
                        network_recv INTEGER,
                        processes_json TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create servers table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS servers (
                        server_id TEXT PRIMARY KEY,
                        hostname TEXT NOT NULL,
                        first_seen DATETIME NOT NULL,
                        last_seen DATETIME NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create alerts table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        server_id TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        threshold REAL NOT NULL,
                        email TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(server_id, metric_name, email)
                    )
                """)
                
                # Create indexes for better performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_server_timestamp ON metrics(server_id, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_servers_last_seen ON servers(last_seen)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_server ON alerts(server_id)")
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise
    
    def store_metrics(self, server_id: str, hostname: str, timestamp: datetime,
                     cpu_percent: float, memory_percent: float, disk_percent: float,
                     load_avg: Optional[float], network_sent: int, network_recv: int,
                     processes: List[Dict[str, Any]]):
        """Store metrics in database"""
        try:
            with self.get_connection() as conn:
                # Convert processes to JSON string
                processes_json = json.dumps(processes) if processes else None
                
                # Insert metric record
                conn.execute("""
                    INSERT INTO metrics (
                        server_id, timestamp, cpu_percent, memory_percent,
                        disk_percent, load_avg, network_sent, network_recv, processes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    server_id, timestamp, cpu_percent, memory_percent,
                    disk_percent, load_avg, network_sent, network_recv, processes_json
                ))
                
                # Update or insert server record
                conn.execute("""
                    INSERT INTO servers (server_id, hostname, first_seen, last_seen)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(server_id) DO UPDATE SET
                        hostname = excluded.hostname,
                        last_seen = excluded.last_seen
                """, (server_id, hostname, timestamp, timestamp))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing metrics: {str(e)}")
            raise
    
    def get_all_servers(self) -> List[ServerInfo]:
        """Get all servers with their info"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT server_id, hostname, first_seen, last_seen
                    FROM servers
                    ORDER BY last_seen DESC
                """)
                
                servers = []
                for row in cursor.fetchall():
                    servers.append(ServerInfo(
                        server_id=row['server_id'],
                        hostname=row['hostname'],
                        first_seen=datetime.fromisoformat(row['first_seen']),
                        last_seen=datetime.fromisoformat(row['last_seen'])
                    ))
                
                return servers
                
        except Exception as e:
            logger.error(f"Error retrieving servers: {str(e)}")
            raise
    
    def get_server_info(self, server_id: str) -> Optional[ServerInfo]:
        """Get server information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT server_id, hostname, first_seen, last_seen
                    FROM servers
                    WHERE server_id = ?
                """, (server_id,))
                
                row = cursor.fetchone()
                if row:
                    return ServerInfo(
                        server_id=row['server_id'],
                        hostname=row['hostname'],
                        first_seen=datetime.fromisoformat(row['first_seen']),
                        last_seen=datetime.fromisoformat(row['last_seen'])
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving server info: {str(e)}")
            raise
    
    def get_server_metrics(self, server_id: str, hours: int) -> List[MetricData]:
        """Get time-series metrics for a server"""
        try:
            with self.get_connection() as conn:
                since = datetime.utcnow() - timedelta(hours=hours)
                
                cursor = conn.execute("""
                    SELECT timestamp, cpu_percent, memory_percent, disk_percent,
                           load_avg, network_sent, network_recv, processes_json
                    FROM metrics
                    WHERE server_id = ? AND timestamp >= ?
                    ORDER BY timestamp ASC
                """, (server_id, since))
                
                metrics = []
                for row in cursor.fetchall():
                    metrics.append(MetricData(
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        cpu_percent=row['cpu_percent'],
                        memory_percent=row['memory_percent'],
                        disk_percent=row['disk_percent'],
                        load_avg=row['load_avg'],
                        network_sent=row['network_sent'],
                        network_recv=row['network_recv'],
                        processes_json=row['processes_json']
                    ))
                
                return metrics
                
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
            raise
    
    def get_latest_metrics(self, server_id: str) -> Optional[MetricData]:
        """Get the latest metrics for a server"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT timestamp, cpu_percent, memory_percent, disk_percent,
                           load_avg, network_sent, network_recv, processes_json
                    FROM metrics
                    WHERE server_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (server_id,))
                
                row = cursor.fetchone()
                if row:
                    return MetricData(
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        cpu_percent=row['cpu_percent'],
                        memory_percent=row['memory_percent'],
                        disk_percent=row['disk_percent'],
                        load_avg=row['load_avg'],
                        network_sent=row['network_sent'],
                        network_recv=row['network_recv'],
                        processes_json=row['processes_json']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving latest metrics: {str(e)}")
            raise
    
    def store_alert_config(self, alert_config: AlertConfig):
        """Store alert configuration"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO alerts (server_id, metric_name, threshold, email)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(server_id, metric_name, email) DO UPDATE SET
                        threshold = excluded.threshold
                """, (
                    alert_config.server_id, alert_config.metric_name,
                    alert_config.threshold, alert_config.email
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error storing alert config: {str(e)}")
            raise
    
    def get_alert_configs(self, server_id: str) -> List[AlertConfig]:
        """Get alert configurations for a server"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT server_id, metric_name, threshold, email
                    FROM alerts
                    WHERE server_id = ?
                """, (server_id,))
                
                configs = []
                for row in cursor.fetchall():
                    configs.append(AlertConfig(
                        server_id=row['server_id'],
                        metric_name=row['metric_name'],
                        threshold=row['threshold'],
                        email=row['email']
                    ))
                
                return configs
                
        except Exception as e:
            logger.error(f"Error retrieving alert configs: {str(e)}")
            raise
    
    def cleanup_old_metrics(self, days: int = 30):
        """Clean up old metrics data"""
        try:
            with self.get_connection() as conn:
                cutoff = datetime.utcnow() - timedelta(days=days)
                
                cursor = conn.execute("""
                    DELETE FROM metrics
                    WHERE timestamp < ?
                """, (cutoff,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                logger.info(f"Cleaned up {deleted_count} old metric records")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error cleaning up old metrics: {str(e)}")
            raise