#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Install the systemd service
# Run as: sudo bash deploy/install-service.sh
# ══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/visa-bot.service"

echo "📋 Installing systemd service..."
cp "$SERVICE_FILE" /etc/systemd/system/visa-bot.service
systemctl daemon-reload
systemctl enable visa-bot
systemctl start visa-bot

echo ""
echo "✅ Service installed and started!"
echo ""
echo "Useful commands:"
echo "  Status:   sudo systemctl status visa-bot"
echo "  Logs:     journalctl -u visa-bot -f"
echo "  Restart:  sudo systemctl restart visa-bot"
echo "  Stop:     sudo systemctl stop visa-bot"
