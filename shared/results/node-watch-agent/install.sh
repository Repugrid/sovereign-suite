#!/bin/bash

# NodeWatch Agent Installation Script
# This script installs and configures the NodeWatch monitoring agent

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NODEWATCH_DIR="/opt/nodewatch"
SERVICE_FILE="nodewatch.service"
LOG_FILE="/var/log/nodewatch-install.log"
NODEWATCH_USER="nodewatch"
NODEWATCH_GROUP="nodewatch"
API_ENDPOINT="${NODEWATCH_API_ENDPOINT:-http://37.27.189.23:9081/api/v1/metrics}"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
    log "INFO: $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    log "SUCCESS: $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    log "ERROR: $1"
}

# Check if script is run as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check if systemd is available
    if ! command -v systemctl >/dev/null 2>&1; then
        print_error "systemctl not found. This script requires systemd."
        exit 1
    fi
    
    # Check Python version
    if ! command -v python3 >/dev/null 2>&1; then
        print_error "Python 3 is required but not installed."
        exit 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_status "Found Python $python_version"
    
    # Check if pip is available
    if ! command -v pip3 >/dev/null 2>&1 && ! python3 -m pip --version >/dev/null 2>&1; then
        print_error "pip3 is required but not installed. Please install python3-pip."
        exit 1
    fi
    
    print_success "System requirements check passed"
}

# Install psutil
install_psutil() {
    print_status "Installing psutil Python package..."
    
    # Try pip3 first, then python3 -m pip
    if command -v pip3 >/dev/null 2>&1; then
        pip3 install psutil --upgrade || {
            print_error "Failed to install psutil with pip3"
            return 1
        }
    else
        python3 -m pip install psutil --upgrade || {
            print_error "Failed to install psutil with python3 -m pip"
            return 1
        }
    fi
    
    # Verify installation
    python3 -c "import psutil; print(f'psutil {psutil.__version__} installed successfully')" || {
        print_error "psutil installation verification failed"
        return 1
    }
    
    print_success "psutil installed successfully"
}

# Create nodewatch user and group
create_user() {
    print_status "Creating nodewatch user and group..."
    
    # Create group if it doesn't exist
    if ! getent group "$NODEWATCH_GROUP" >/dev/null 2>&1; then
        groupadd --system "$NODEWATCH_GROUP" || {
            print_error "Failed to create group $NODEWATCH_GROUP"
            return 1
        }
        print_status "Created group $NODEWATCH_GROUP"
    else
        print_status "Group $NODEWATCH_GROUP already exists"
    fi
    
    # Create user if it doesn't exist
    if ! getent passwd "$NODEWATCH_USER" >/dev/null 2>&1; then
        useradd --system \
                --gid "$NODEWATCH_GROUP" \
                --no-create-home \
                --home-dir /nonexistent \
                --shell /usr/sbin/nologin \
                --comment "NodeWatch monitoring agent" \
                "$NODEWATCH_USER" || {
            print_error "Failed to create user $NODEWATCH_USER"
            return 1
        }
        print_status "Created user $NODEWATCH_USER"
    else
        print_status "User $NODEWATCH_USER already exists"
    fi
    
    print_success "User and group configuration completed"
}

# Create directories
create_directories() {
    print_status "Creating NodeWatch directories..."
    
    # Create main directory
    mkdir -p "$NODEWATCH_DIR" || {
        print_error "Failed to create directory $NODEWATCH_DIR"
        return 1
    }
    
    # Set ownership and permissions
    chown root:root "$NODEWATCH_DIR"
    chmod 755 "$NODEWATCH_DIR"
    
    # Ensure log directory exists and is writable
    mkdir -p /var/log
    touch /var/log/nodewatch.log
    chown "$NODEWATCH_USER:$NODEWATCH_GROUP" /var/log/nodewatch.log
    chmod 640 /var/log/nodewatch.log
    
    print_success "Directories created and configured"
}

# Download and install monitor.py
install_monitor() {
    print_status "Downloading and installing monitor.py..."
    
    # First, try to use local file if available
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local monitor_source="$script_dir/monitor.py"
    
    if [[ -f "$monitor_source" ]]; then
        print_status "Using local monitor.py file"
        cp "$monitor_source" "$NODEWATCH_DIR/monitor.py" || {
            print_error "Failed to copy monitor.py to $NODEWATCH_DIR"
            return 1
        }
    else
        # Download from server
        print_status "Downloading monitor.py from server..."
        if command -v curl >/dev/null 2>&1; then
            curl -fsSL "http://37.27.189.23:9080/node-watch/monitor.py" -o "$NODEWATCH_DIR/monitor.py" || {
                print_error "Failed to download monitor.py with curl"
                return 1
            }
        elif command -v wget >/dev/null 2>&1; then
            wget -q "http://37.27.189.23:9080/node-watch/monitor.py" -O "$NODEWATCH_DIR/monitor.py" || {
                print_error "Failed to download monitor.py with wget"
                return 1
            }
        else
            print_error "Neither curl nor wget available for downloading monitor.py"
            return 1
        fi
    fi
    
    # Set permissions
    chown root:root "$NODEWATCH_DIR/monitor.py"
    chmod 755 "$NODEWATCH_DIR/monitor.py"
    
    print_success "monitor.py installed successfully"
}

# Install systemd service
install_service() {
    print_status "Creating systemd service..."
    
    # Create service file with correct configuration
    cat > "/etc/systemd/system/$SERVICE_FILE" << EOF
[Unit]
Description=NodeWatch Monitoring Agent
Documentation=https://nodewatch.io/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$NODEWATCH_USER
Group=$NODEWATCH_GROUP
ExecStart=/usr/bin/python3 $NODEWATCH_DIR/monitor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nodewatch

# Environment variables
Environment=NODEWATCH_API_ENDPOINT=$API_ENDPOINT
Environment=NODEWATCH_INTERVAL=60
Environment=NODEWATCH_LOG_LEVEL=INFO

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log

[Install]
WantedBy=multi-user.target
EOF
    
    # Set permissions
    chown root:root "/etc/systemd/system/$SERVICE_FILE"
    chmod 644 "/etc/systemd/system/$SERVICE_FILE"
    
    # Reload systemd
    systemctl daemon-reload || {
        print_error "Failed to reload systemd"
        return 1
    }
    
    # Enable service
    systemctl enable nodewatch.service || {
        print_error "Failed to enable nodewatch service"
        return 1
    }
    
    print_success "Systemd service installed and enabled"
}

# Start the service
start_service() {
    print_status "Starting NodeWatch service..."
    
    # Start the service
    systemctl start nodewatch.service || {
        print_error "Failed to start nodewatch service"
        print_error "Check logs with: journalctl -u nodewatch.service"
        return 1
    }
    
    # Wait a moment and check status
    sleep 3
    
    if systemctl is-active --quiet nodewatch.service; then
        print_success "NodeWatch service started successfully"
    else
        print_error "NodeWatch service failed to start"
        print_error "Check status with: systemctl status nodewatch.service"
        print_error "Check logs with: journalctl -u nodewatch.service"
        return 1
    fi
}

# Get and display server ID
display_server_id() {
    print_status "Retrieving server ID..."
    
    # Wait for service to generate ID file
    local max_wait=30
    local wait_time=0
    local server_id_file
    
    # Check multiple possible locations for the ID file
    local id_locations=("/home/$NODEWATCH_USER/.nodewatch_id" "/root/.nodewatch_id" "/var/lib/nodewatch/.nodewatch_id")
    
    while [[ $wait_time -lt $max_wait ]]; do
        for location in "${id_locations[@]}"; do
            if [[ -f "$location" ]]; then
                server_id_file="$location"
                break 2
            fi
        done
        sleep 1
        ((wait_time++))
    done
    
    if [[ -n "$server_id_file" && -f "$server_id_file" ]]; then
        local server_id=$(cat "$server_id_file")
        print_success "Server ID: $server_id"
        echo
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "${GREEN}  NodeWatch Agent Installation Complete  ${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "Server ID: ${YELLOW}$server_id${NC}"
        echo -e "Status:    ${GREEN}Running${NC}"
        echo -e "API:       ${BLUE}$API_ENDPOINT${NC}"
        echo -e "Logs:      ${BLUE}journalctl -u nodewatch.service -f${NC}"
        echo -e "Config:    ${BLUE}$NODEWATCH_DIR/config.json${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
    else
        print_warning "Server ID not found after $max_wait seconds"
        print_status "The service may still be starting up"
        print_status "Check service status with: systemctl status nodewatch.service"
        print_status "Check logs with: journalctl -u nodewatch.service -f"
    fi
}

# Create configuration file
create_config() {
    print_status "Creating configuration file..."
    
    cat > "$NODEWATCH_DIR/config.json" << EOF
{
  "api_endpoint": "$API_ENDPOINT",
  "interval": 60,
  "max_buffer_size": 100,
  "retry_attempts": 3,
  "retry_delay": 5,
  "log_level": "INFO"
}
EOF
    
    chown root:root "$NODEWATCH_DIR/config.json"
    chmod 644 "$NODEWATCH_DIR/config.json"
    
    print_status "Configuration file created at $NODEWATCH_DIR/config.json"
}

# Error handling
handle_error() {
    local line_no=$1
    local error_code=$2
    print_error "Installation failed at line $line_no with error code $error_code"
    print_error "Check the log file: $LOG_FILE"
    exit $error_code
}

# Set up error trapping
trap 'handle_error $LINENO $?' ERR

# Main installation function
main() {
    echo -e "${BLUE}"
    echo "=================================================="
    echo "       NodeWatch Agent Installation Script       "
    echo "=================================================="
    echo -e "${NC}"
    
    print_status "API Endpoint: $API_ENDPOINT"
    echo
    
    # Initialize log file
    echo "Installation started at $(date)" > "$LOG_FILE"
    
    # Run installation steps
    check_root
    check_requirements
    install_psutil
    create_user
    create_directories
    install_monitor
    create_config
    install_service
    start_service
    display_server_id
    
    print_success "Installation completed successfully!"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "NodeWatch Agent Installation Script"
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "This script installs the NodeWatch monitoring agent as a systemd service."
        echo ""
        echo "Environment Variables:"
        echo "  NODEWATCH_API_ENDPOINT    API endpoint (default: http://37.27.189.23:9081/api/v1/metrics)"
        echo ""
        echo "Options:"
        echo "  --help, -h    Show this help message"
        echo "  --uninstall   Remove the NodeWatch agent"
        echo ""
        echo "The script will:"
        echo "  1. Install required dependencies (psutil)"
        echo "  2. Create nodewatch user and group"
        echo "  3. Download and install monitor.py to /opt/nodewatch/"
        echo "  4. Install and start systemd service"
        echo "  5. Display the server ID for monitoring dashboard"
        exit 0
        ;;
    --uninstall)
        print_status "Uninstalling NodeWatch agent..."
        systemctl stop nodewatch.service 2>/dev/null || true
        systemctl disable nodewatch.service 2>/dev/null || true
        rm -f /etc/systemd/system/nodewatch.service
        systemctl daemon-reload
        rm -rf /opt/nodewatch
        userdel nodewatch 2>/dev/null || true
        groupdel nodewatch 2>/dev/null || true
        rm -f /var/log/nodewatch.log
        print_success "NodeWatch agent uninstalled"
        exit 0
        ;;
    "")
        # No arguments, proceed with installation
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac