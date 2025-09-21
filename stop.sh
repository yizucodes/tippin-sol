#!/bin/bash

echo "🛑 Stopping Coral Protocol + Mistral AI Tipping System"
echo "====================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_step "Stopping agents..."

# Stop all agents
agents=("console" "validation" "transaction" "notification")

for agent in "${agents[@]}"; do
    if [ -f "agents/$agent/agent.pid" ]; then
        pid=$(cat "agents/$agent/agent.pid")
        if kill -0 "$pid" 2>/dev/null; then
            print_status "Stopping $agent agent (PID: $pid)..."
            kill "$pid"
        fi
        rm -f "agents/$agent/agent.pid"
    fi
done

print_step "Stopping Coral Server..."

# Stop Coral Server
pkill -f "coral-server" || print_status "Coral Server was not running"

print_step "Cleanup..."

# Kill any remaining processes
pkill -f "main.py" || true
pkill -f "gradlew" || true

print_status "✅ System stopped successfully!"
