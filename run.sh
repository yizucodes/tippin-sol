#!/bin/bash

echo "🚀 Starting Coral Protocol + Mistral AI Tipping System"
echo "======================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found!"
    echo "Please create .env file with your Mistral API key:"
    echo "MISTRAL_API_KEY=your_mistral_api_key_here"
    echo "MODEL_NAME=mistral-small"
    echo "MODEL_PROVIDER=mistral"
    exit 1
fi

# Check if Mistral API key is set
if ! grep -q "MISTRAL_API_KEY=" .env || grep -q "MISTRAL_API_KEY=your_mistral_api_key_here" .env; then
    print_error "Mistral API key not configured!"
    echo "Please set your Mistral API key in .env file"
    exit 1
fi

print_step "Starting Coral Server..."

# Start Coral Server
cd coral-server
REGISTRY_FILE_PATH="../registry.toml" ./gradlew run &
CORAL_SERVER_PID=$!
cd ..

# Wait for Coral Server to start
print_status "Waiting for Coral Server to start..."
sleep 30

# Check if Coral Server is running
print_status "Checking Coral Server health..."
for i in {1..10}; do
    if curl -f http://localhost:5555/health >/dev/null 2>&1; then
        print_status "✅ Coral Server is running"
        break
    else
        print_status "Attempt $i/10: Coral Server not ready yet, waiting..."
        sleep 5
    fi
    
    if [ $i -eq 10 ]; then
        print_error "❌ Coral Server failed to start after 50 seconds"
        print_error "Check coral-server logs for details"
        kill $CORAL_SERVER_PID 2>/dev/null
        exit 1
    fi
done

print_step "Starting agents..."

# Start all agents in background
agents=("validation" "transaction" "notification")

for agent in "${agents[@]}"; do
    print_status "Starting $agent agent..."
    cd "agents/$agent"
    ./run_agent.sh main.py &
    echo $! > agent.pid
    cd ../..
    sleep 3
done

print_status "✅ All agents started successfully!"

print_step "Starting console interface..."

# Start console interface (foreground)
cd agents/console
print_status "🎮 Console interface ready!"
print_status "💡 Type /help for available commands"
echo ""
./run_agent.sh main.py
