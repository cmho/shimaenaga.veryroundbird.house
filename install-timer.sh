#!/usr/bin/env bash

SERVICE_PATH="/etc/systemd/system/status-report.service"
TIMER_PATH="/etc/systemd/system/status-report.timer"
SCRIPT_PATH="/usr/local/bin/generate-status.py"
OUTPUT_PATH="/pds/caddy/webroot/status.html"

# Ensure script is present
if [ ! -f "$SCRIPT_PATH" ]; then
  echo "Error: $SCRIPT_PATH not found. Please place your script there or edit this installer."
  exit 1
fi

# Create systemd service file
cat <<EOF | tee "$SERVICE_PATH" > /dev/null
[Unit]
Description=Generate server status HTML page
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $SCRIPT_PATH --pds-path /pds --output $OUTPUT_PATH
User=root
EOF

# Create systemd timer file
cat <<EOF | tee "$TIMER_PATH" > /dev/null
[Unit]
Description=Run status-report.service every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit=status-report.service

[Install]
WantedBy=timers.target
EOF

# Reload systemd and start timer
systemctl daemon-reload
systemctl enable --now status-report.timer

echo "Systemd timer and service installed and activated."
