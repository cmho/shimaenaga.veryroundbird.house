#!/usr/bin/env bash

# Ensure script is present
if [ ! -f "$STATUS_SCRIPT_PATH" ]; then
  echo "Error: $STATUS_SCRIPT_PATH not found."
  exit 1
fi

if [[ -z "$STATUS_SERVICE_PATH" || -z "$STATUS_TIMER_PATH" || -z "$STATUS_OUTPUT_PATH" ]]; then
  echo "Error: One or more required variables are not set"
  exit 1
fi

# Create systemd service file
cat <<EOF | tee "$STATUS_SERVICE_PATH" > /dev/null
[Unit]
Description=Generate server status HTML page
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 $STATUS_SCRIPT_PATH --pds-config /pds/pds.env --output $STATUS_OUTPUT_PATH
User=root
EOF

# Create systemd timer file
cat <<EOF | tee "$STATUS_TIMER_PATH" > /dev/null
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
