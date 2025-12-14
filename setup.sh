#!/bin/bash
# Local Development Setup Script for Mac/Linux

echo "🚀 Pocket Option Signal Bot - Local Setup"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found. Please install Node.js 16+${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js found${NC}"

# Check if MongoDB is installed
if ! command -v mongod &> /dev/null; then
    echo -e "${YELLOW}⚠️  MongoDB not found. Please install MongoDB Community Edition${NC}"
else
    echo -e "${GREEN}✓ MongoDB found${NC}"
fi

echo ""
echo "📦 Installing Backend Dependencies..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Backend dependencies installed${NC}"
else
    echo -e "${RED}❌ Failed to install backend dependencies${NC}"
    exit 1
fi

# Setup .env file
if [ ! -f ".env" ]; then
    echo "Creating backend .env file from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please edit backend/.env with your configuration${NC}"
fi

cd ..

echo ""
echo "📦 Installing Frontend Dependencies..."
cd frontend

# Check if yarn is installed
if command -v yarn &> /dev/null; then
    yarn install
else
    npm install
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
else
    echo -e "${RED}❌ Failed to install frontend dependencies${NC}"
    exit 1
fi

# Setup .env file
if [ ! -f ".env" ]; then
    echo "Creating frontend .env file from template..."
    cp .env.example .env
fi

cd ..

echo ""
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "📝 Next Steps:"
echo "   1. Edit backend/.env with your configuration"
echo "   2. Start MongoDB: mongod --dbpath ./data/db"
echo "   3. Start Backend: cd backend && source venv/bin/activate && python -m uvicorn server:app --reload --port 8001"
echo "   4. Start Frontend: cd frontend && yarn start"
echo "   5. Open http://localhost:3000 in your browser"
echo ""
echo "💡 Or use VS Code:"
echo "   - Open this folder in VS Code"
echo "   - Press F5 to start debugging"
echo "   - Select 'Full Stack (Backend + Frontend)'"
echo ""
