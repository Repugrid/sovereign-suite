#!/usr/bin/env python3
"""
Sovereign Vault — Backup & Recovery Agent
Automated encrypted backups with intelligent scheduling.
"""

import json
import hashlib
import os
import sys
import tarfile
import time
import socket
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
    from cryptography.fernet import Fernet
except ImportError:
    print("Missing dependencies. Run: pip3 install requests cryptography")
    sys.exit(1)

CONFIG_PATH = os.environ.get("VAULT_CONFIG", "/opt/sovereign-vault/config.json")
KEY_PATH = os.environ.get("VAULT_KEY", "/opt/sovereign-vault/vault.key")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_key():
    with open(KEY_PATH, "rb") as f:
        return f.read()


def get_system_info():
    """Collect basic system info for reporting."""
    import psutil
    return {
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
    }


def create_backup(config, fernet):
    """Create an encrypted backup of configured paths."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snapshot_dir = Path(config["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    tar_path = snapshot_dir / f"backup-{timestamp}.tar.gz"
    enc_path = snapshot_dir / f"backup-{timestamp}.tar.gz.enc"

    # Create tar archive
    paths_backed_up = 0
    total_size = 0
    exclude = config.get("exclude_patterns", [])

    def should_exclude(name):
        for pattern in exclude:
            if pattern.startswith("*"):
                if name.endswith(pattern[1:]):
                    return True
            elif pattern in name:
                return True
        return False

    with tarfile.open(str(tar_path), "w:gz") as tar:
        for backup_path in config.get("paths_to_backup", []):
            if not os.path.exists(backup_path):
                continue
            for root, dirs, files in os.walk(backup_path):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if not should_exclude(d)]
                for f in files:
                    if should_exclude(f):
                        continue
                    full_path = os.path.join(root, f)
                    try:
                        stat = os.stat(full_path)
                        if stat.st_size > 100 * 1024 * 1024:  # Skip files > 100MB
                            continue
                        tar.add(full_path)
                        paths_backed_up += 1
                        total_size += stat.st_size
                    except (PermissionError, OSError):
                        continue

    # Encrypt if configured
    if config.get("encrypt", True) and fernet:
        with open(tar_path, "rb") as f:
            encrypted = fernet.encrypt(f.read())
        with open(enc_path, "wb") as f:
            f.write(encrypted)
        os.remove(tar_path)
        final_path = enc_path
    else:
        final_path = tar_path

    # Calculate checksum
    with open(final_path, "rb") as f:
        checksum = hashlib.sha256(f.read()).hexdigest()

    # Cleanup old snapshots
    max_snapshots = config.get("max_snapshots", 48)
    snapshots = sorted(snapshot_dir.glob("backup-*"), key=lambda p: p.stat().st_mtime)
    while len(snapshots) > max_snapshots:
        oldest = snapshots.pop(0)
        oldest.unlink()

    return {
        "timestamp": timestamp,
        "path": str(final_path),
        "files_backed_up": paths_backed_up,
        "total_size_bytes": total_size,
        "encrypted": config.get("encrypt", True),
        "checksum_sha256": checksum,
        "snapshot_size_bytes": final_path.stat().st_size,
    }


def report_status(config, backup_result=None):
    """Report status to central API."""
    try:
        sys_info = get_system_info()
        payload = {
            "server_id": config["server_id"],
            "hostname": sys_info["hostname"],
            "cpu_percent": sys_info["cpu_percent"],
            "memory_percent": sys_info["memory_percent"],
            "disk_percent": sys_info["disk_percent"],
            "type": "vault",
        }
        if backup_result:
            payload["last_backup"] = backup_result

        requests.post(
            config["api_endpoint"],
            json=payload,
            timeout=10,
        )
    except Exception as e:
        print(f"[Vault] Report failed: {e}")


def main():
    print("[Vault] Sovereign Vault agent starting...")
    config = load_config()
    key = load_key()
    fernet = Fernet(key)

    server_id = config["server_id"]
    interval = config.get("backup_interval", 3600)

    print(f"[Vault] Server ID: {server_id}")
    print(f"[Vault] Backup interval: {interval}s")
    print(f"[Vault] Paths: {config.get('paths_to_backup', [])}")

    # Initial status report
    report_status(config)
    print("[Vault] Initial status reported. First backup in 60s...")
    time.sleep(60)

    while True:
        try:
            print(f"[Vault] Starting backup at {datetime.now(timezone.utc).isoformat()}")
            result = create_backup(config, fernet)
            print(f"[Vault] Backup complete: {result['files_backed_up']} files, "
                  f"{result['snapshot_size_bytes'] / 1024 / 1024:.1f}MB")
            report_status(config, result)
        except Exception as e:
            print(f"[Vault] Backup failed: {e}")
            report_status(config)

        time.sleep(interval)


if __name__ == "__main__":
    main()
