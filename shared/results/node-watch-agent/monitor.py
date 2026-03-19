#!/usr/bin/env python3
"""
Node-Watch Monitoring Agent
A lightweight system monitoring agent that collects and reports system metrics.
"""

import json
import logging
import os
import platform
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

try:
    import psutil
except ImportError:
    print("Error: psutil library is required. Install with: pip install psutil")
    sys.exit(1)


class Config:
    """Configuration management for the monitoring agent."""
    
    def __init__(self):
        self.api_endpoint = self._get_config('API_ENDPOINT', 'http://localhost:8080/api/v1/metrics')
        self.interval = int(self._get_config('INTERVAL', '60'))
        self.max_buffer_size = int(self._get_config('MAX_BUFFER_SIZE', '100'))
        self.retry_attempts = int(self._get_config('RETRY_ATTEMPTS', '3'))
        self.retry_delay = int(self._get_config('RETRY_DELAY', '5'))
        self.log_level = self._get_config('LOG_LEVEL', 'INFO')
        
    def _get_config(self, key: str, default: str) -> str:
        """Get configuration value from environment or config file."""
        # Check environment variable first
        env_value = os.environ.get(f'NODEWATCH_{key}')
        if env_value:
            return env_value
        
        # Check config file
        config_file = Path('/opt/nodewatch/config.json')
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    return config_data.get(key.lower(), default)
            except (json.JSONDecodeError, IOError):
                pass
        
        return default


class ServerIdentity:
    """Manages unique server identification."""
    
    def __init__(self):
        self.id_file = Path.home() / '.nodewatch_id'
        self.server_id = self._get_or_create_id()
    
    def _get_or_create_id(self) -> str:
        """Get existing server ID or create a new one."""
        if self.id_file.exists():
            try:
                with open(self.id_file, 'r') as f:
                    return f.read().strip()
            except IOError:
                pass
        
        # Create new ID
        hostname = platform.node() or socket.gethostname()
        server_id = f"{hostname}-{str(uuid.uuid4())[:8]}"
        
        try:
            with open(self.id_file, 'w') as f:
                f.write(server_id)
            os.chmod(self.id_file, 0o600)  # Read/write for owner only
        except IOError as e:
            logging.warning(f"Could not save server ID to file: {e}")
        
        return server_id


class MetricsCollector:
    """Collects system metrics using psutil."""
    
    @staticmethod
    def collect() -> Dict:
        """Collect all system metrics."""
        # Get network stats before other operations
        net_io = psutil.net_io_counters()
        
        metrics = {
            'cpu_percent': round(psutil.cpu_percent(interval=1), 1),
            'memory_percent': round(psutil.virtual_memory().percent, 1),
            'disk_percent': round(psutil.disk_usage('/').percent, 1),
            'load_avg': list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0.0, 0.0, 0.0],
            'network_bytes_sent': net_io.bytes_sent,
            'network_bytes_recv': net_io.bytes_recv,
            'top_processes': MetricsCollector._get_top_processes()
        }
        
        return metrics
    
    @staticmethod
    def _get_top_processes() -> List[Dict]:
        """Get top 5 processes by CPU usage."""
        try:
            processes = []
            for proc in psutil.process_iter(['name', 'cpu_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent'] is not None:
                        processes.append({
                            'name': proc_info['name'],
                            'cpu': round(proc_info['cpu_percent'], 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage and return top 5
            processes.sort(key=lambda x: x['cpu'], reverse=True)
            return processes[:5]
        except Exception:
            return []


class MetricsBuffer:
    """Buffers metrics when API is unavailable."""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.buffer: List[Dict] = []
    
    def add(self, data: Dict) -> None:
        """Add data to buffer, removing oldest if at capacity."""
        self.buffer.append(data)
        if len(self.buffer) > self.max_size:
            self.buffer.pop(0)
    
    def get_all(self) -> List[Dict]:
        """Get all buffered data and clear buffer."""
        data = self.buffer.copy()
        self.buffer.clear()
        return data
    
    def size(self) -> int:
        """Get current buffer size."""
        return len(self.buffer)


class APIClient:
    """Handles API communication with retry logic."""
    
    def __init__(self, endpoint: str, retry_attempts: int = 3, retry_delay: int = 5):
        self.endpoint = endpoint
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
    
    def send_metrics(self, data: Dict) -> bool:
        """Send metrics to API with retry logic."""
        for attempt in range(self.retry_attempts):
            try:
                json_data = json.dumps(data).encode('utf-8')
                request = Request(
                    self.endpoint,
                    data=json_data,
                    headers={
                        'Content-Type': 'application/json',
                        'User-Agent': 'NodeWatch-Agent/1.0'
                    },
                    method='POST'
                )
                
                with urlopen(request, timeout=30) as response:
                    if response.getcode() in (200, 201, 202):
                        logging.debug(f"Metrics sent successfully (HTTP {response.getcode()})")
                        return True
                    else:
                        logging.warning(f"API returned HTTP {response.getcode()}")
                
            except HTTPError as e:
                logging.error(f"HTTP error on attempt {attempt + 1}: {e}")
            except URLError as e:
                logging.error(f"Connection error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            
            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        
        return False
    
    def send_batch(self, data_list: List[Dict]) -> Tuple[int, int]:
        """Send multiple metrics, return (success_count, total_count)."""
        success_count = 0
        for data in data_list:
            if self.send_metrics(data):
                success_count += 1
        return success_count, len(data_list)


class NodeWatchAgent:
    """Main monitoring agent class."""
    
    def __init__(self):
        self.config = Config()
        self.server_identity = ServerIdentity()
        self.metrics_collector = MetricsCollector()
        self.buffer = MetricsBuffer(self.config.max_buffer_size)
        self.api_client = APIClient(
            self.config.api_endpoint,
            self.config.retry_attempts,
            self.config.retry_delay
        )
        self.running = False
        
        # Setup logging
        self._setup_logging()
        
        logging.info(f"NodeWatch Agent initialized")
        logging.info(f"Server ID: {self.server_identity.server_id}")
        logging.info(f"API Endpoint: {self.config.api_endpoint}")
        logging.info(f"Collection Interval: {self.config.interval}s")
    
    def _setup_logging(self):
        """Configure logging."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/var/log/nodewatch.log', mode='a')
            ]
        )
    
    def _create_payload(self, metrics: Dict) -> Dict:
        """Create API payload from metrics."""
        return {
            'server_id': self.server_identity.server_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'metrics': metrics
        }
    
    def _collect_and_send(self) -> None:
        """Collect metrics and attempt to send to API."""
        try:
            # Collect current metrics
            metrics = self.metrics_collector.collect()
            payload = self._create_payload(metrics)
            
            logging.debug("Collected metrics successfully")
            
            # Try to send buffered data first
            if self.buffer.size() > 0:
                buffered_data = self.buffer.get_all()
                success_count, total_count = self.api_client.send_batch(buffered_data)
                if success_count > 0:
                    logging.info(f"Sent {success_count}/{total_count} buffered metrics")
                if success_count < total_count:
                    # Re-buffer failed sends
                    for i in range(success_count, total_count):
                        self.buffer.add(buffered_data[i])
            
            # Send current metrics
            if self.api_client.send_metrics(payload):
                logging.debug("Current metrics sent successfully")
            else:
                # Buffer current metrics if send failed
                self.buffer.add(payload)
                logging.warning(f"Metrics buffered (buffer size: {self.buffer.size()})")
                
        except Exception as e:
            logging.error(f"Error during metrics collection/send: {e}")
    
    def start(self) -> None:
        """Start the monitoring agent."""
        self.running = True
        logging.info("NodeWatch Agent started")
        
        try:
            while self.running:
                start_time = time.time()
                
                self._collect_and_send()
                
                # Calculate sleep time to maintain interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.config.interval - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logging.warning(f"Collection took {elapsed:.1f}s, longer than interval")
                    
        except KeyboardInterrupt:
            logging.info("Received shutdown signal")
        except Exception as e:
            logging.error(f"Fatal error: {e}")
            raise
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the monitoring agent."""
        self.running = False
        
        # Try to send any remaining buffered data
        if self.buffer.size() > 0:
            logging.info(f"Attempting to send {self.buffer.size()} buffered metrics before shutdown")
            buffered_data = self.buffer.get_all()
            success_count, total_count = self.api_client.send_batch(buffered_data)
            logging.info(f"Sent {success_count}/{total_count} metrics on shutdown")
        
        logging.info("NodeWatch Agent stopped")


def main():
    """Main entry point."""
    try:
        agent = NodeWatchAgent()
        agent.start()
    except Exception as e:
        logging.error(f"Failed to start agent: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()