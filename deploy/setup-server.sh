#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# Oracle Cloud ARM (Seoul) — One-time server setup
#
# Run as: sudo bash setup-server.sh
#
# This installs: Python 3.12, Chromium (ARM), ChromeDriver, and project deps.
# ══════════════════════════════════════════════════════════════════════════════

set -e

echo "🔧 Updating system..."
apt-get update && apt-get upgrade -y

echo "🐍 Installing Python 3.12..."
apt-get install -y python3 python3-pip python3-venv git

echo "🌐 Installing Chromium (ARM-compatible)..."
apt-get install -y chromium-browser chromium-chromedriver

# Verify
echo "=== Versions ==="
python3 --version
chromium-browser --version 2>/dev/null || chromium --version
chromedriver --version 2>/dev/null || echo "ChromeDriver at: $(which chromedriver)"

echo "👤 Creating bot user..."
useradd -m -s /bin/bash botuser 2>/dev/null || echo "botuser already exists"

echo "📂 Setting up project directory..."
su - botuser << 'EOF'
cd ~

# Clone repo (replace with your actual URL)
if [ ! -d "korea-visa-bot" ]; then
    git clone https://github.com/YOUR_USERNAME/korea-visa-bot.git
fi

cd korea-visa-bot

# Create venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory
mkdir -p data

echo "✅ Project setup complete"
echo "⚠️  Don't forget to create your .env file:"
echo "    cp .env.example .env"
echo "    nano .env"
EOF

echo ""
echo "══════════════════════════════════════════════════"
echo "✅ Server setup complete!"
echo ""
echo "Next steps:"
echo "  1. Switch to botuser:  su - botuser"
echo "  2. Create .env:        cd korea-visa-bot && cp .env.example .env && nano .env"
echo "  3. Install service:    sudo bash deploy/install-service.sh"
echo "══════════════════════════════════════════════════"
