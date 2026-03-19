#!/bin/bash
set -e

echo "=== NodeWatch Agent Installer ==="
echo ""

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "Error: Please run as root (sudo)"
    exit 1
fi

API_ENDPOINT="${1:-http://37.27.189.23:9081/api/v1/metrics}"
INSTALL_DIR="/opt/nodewatch"

echo "[1/5] Installing dependencies..."
pip3 install psutil --break-system-packages -q 2>/dev/null || pip3 install psutil -q

echo "[2/5] Downloading NodeWatch agent..."
mkdir -p "$INSTALL_DIR"
curl -sSL http://37.27.189.23:9080/install/monitor.py -o "$INSTALL_DIR/monitor.py"

echo "[3/5] Configuring..."
cat > "$INSTALL_DIR/config.json" << EOF
{
    "api_endpoint": "$API_ENDPOINT",
    "interval": "60",
    "log_level": "INFO"
}
EOF

echo "[4/5] Setting up systemd service..."
cat > /etc/systemd/system/nodewatch.service << EOF
[Unit]
Description=NodeWatch Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $INSTALL_DIR/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nodewatch
systemctl start nodewatch

echo "[5/5] Verifying..."
sleep 3
if systemctl is-active --quiet nodewatch; then
    SERVER_ID=$(cat ~/.nodewatch_id 2>/dev/null || echo "unknown")
    echo ""
    echo "=== NodeWatch installed successfully! ==="
    echo "Server ID: $SERVER_ID"
    echo "API Endpoint: $API_ENDPOINT"
    echo "Status: $(systemctl is-active nodewatch)"
    echo ""
    echo "Commands:"
    echo "  systemctl status nodewatch    # Check status"
    echo "  journalctl -u nodewatch -f    # View logs"
    echo "  systemctl stop nodewatch      # Stop agent"
else
    echo "Error: Service failed to start. Check: journalctl -u nodewatch"
    exit 1
fi
