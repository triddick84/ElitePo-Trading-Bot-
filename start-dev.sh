#!/bin/bash
# Quick start script for development (Mac/Linux)

echo "🚀 Starting Pocket Option Signal Bot..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down services...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start MongoDB (if not running)
if ! pgrep -x "mongod" > /dev/null; then
    echo "Starting MongoDB..."
    mongod --dbpath ./data/db --fork --logpath ./data/mongodb.log
    sleep 2
else
    echo -e "${GREEN}✓ MongoDB already running${NC}"
fi

# Start Backend
echo "Starting Backend..."
cd backend
source venv/bin/activate 2>/dev/null || echo "Virtual environment not found"
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!
cd ..

sleep 3
echo -e "${GREEN}✓ Backend started on http://localhost:8001${NC}"

# Start Frontend
echo "Starting Frontend..."
cd frontend
yarn start &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}✅ All services started!${NC}"
echo ""
echo "📍 Frontend: http://localhost:3000"
echo "📍 Backend:  http://localhost:8001"
echo "📍 API Docs: http://localhost:8001/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for processes
wait
