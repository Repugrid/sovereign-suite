#!/bin/bash
set -e

echo "╔══════════════════════════════════════╗"
echo "║   Sovereign Vault — Installer        ║"
echo "║   Automated Backup & Recovery         ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: Please run as root (sudo)"
    exit 1
fi

API_ENDPOINT="${1:-https://repugrid.com/api/v1/metrics}"
INSTALL_DIR="/opt/sovereign-vault"
BACKUP_DIR="/var/backups/sovereign-vault"

echo "[1/6] Installing dependencies..."
apt-get update -qq > /dev/null 2>&1 || yum -q makecache > /dev/null 2>&1
pip3 install psutil requests cryptography --break-system-packages -q 2>/dev/null || pip3 install psutil requests cryptography -q

echo "[2/6] Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BACKUP_DIR"
mkdir -p "$INSTALL_DIR/snapshots"

echo "[3/6] Downloading Vault agent..."
curl -sSL https://repugrid.com/install/vault-agent.py -o "$INSTALL_DIR/vault-agent.py"

echo "[4/6] Generating encryption key..."
python3 -c "
from cryptography.fernet import Fernet
key = Fernet.generate_key()
with open('$INSTALL_DIR/vault.key', 'wb') as f:
    f.write(key)
print('Encryption key generated')
"
chmod 600 "$INSTALL_DIR/vault.key"

echo "[5/6] Configuring..."
SERVER_ID="vault-$(hostname | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')-$(head -c 4 /dev/urandom | xxd -p)"
cat > "$INSTALL_DIR/config.json" << EOF
{
    "server_id": "$SERVER_ID",
    "api_endpoint": "$API_ENDPOINT",
    "backup_dir": "$BACKUP_DIR",
    "snapshot_dir": "$INSTALL_DIR/snapshots",
    "backup_interval": 3600,
    "max_snapshots": 48,
    "encrypt": true,
    "paths_to_backup": [
        "/etc",
        "/var/www",
        "/opt",
        "/home"
    ],
    "exclude_patterns": [
        "*.log",
        "*.tmp",
        "node_modules",
        ".cache",
        "__pycache__"
    ]
}
EOF

echo "[6/6] Setting up systemd service..."
cat > /etc/systemd/system/sovereign-vault.service << EOF
[Unit]
Description=Sovereign Vault — Automated Backup & Recovery Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/vault-agent.py
Restart=always
RestartSec=30
Environment=VAULT_CONFIG=$INSTALL_DIR/config.json
Environment=VAULT_KEY=$INSTALL_DIR/vault.key

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable sovereign-vault
systemctl start sovereign-vault

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Sovereign Vault installed!          ║"
echo "╠══════════════════════════════════════╣"
echo "║   Server ID: $SERVER_ID"
echo "║   Backups:   $BACKUP_DIR"
echo "║   Config:    $INSTALL_DIR/config.json"
echo "║   Key:       $INSTALL_DIR/vault.key"
echo "║   Status:    systemctl status sovereign-vault"
echo "╚══════════════════════════════════════╝"
echo ""
echo "First backup will run in 60 seconds."
echo "Check status: systemctl status sovereign-vault"
