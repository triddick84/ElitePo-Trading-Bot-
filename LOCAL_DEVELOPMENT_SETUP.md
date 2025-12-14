# 🖥️ Local Development Setup for Visual Studio Code

Complete guide to run the Pocket Option Signal Bot on your local machine with VS Code.

---

## 📋 Prerequisites

### Required Software
- **Visual Studio Code**: [Download here](https://code.visualstudio.com/)
- **Python 3.9+**: [Download here](https://www.python.org/downloads/)
- **Node.js 16+**: [Download here](https://nodejs.org/)
- **MongoDB**: [Download here](https://www.mongodb.com/try/download/community)
- **Git**: [Download here](https://git-scm.com/downloads)

### Recommended VS Code Extensions
```
Python (ms-python.python)
Pylance (ms-python.vscode-pylance)
ES7+ React/Redux/React-Native snippets (dsznajder.es7-react-js-snippets)
ESLint (dbaeumer.vscode-eslint)
Prettier (esbenp.prettier-vscode)
GitLens (eamodio.gitlens)
Thunder Client (rangav.vscode-thunder-client) - for API testing
```

---

## 🚀 Quick Start

### 1. Clone/Copy Project
```bash
# If you have git access
git clone <your-repo-url>
cd pocket-option-signal-bot

# OR copy from current deployment
# (Already done if you're reading this from /app)
```

### 2. Install Dependencies

#### Backend (Python)
```bash
cd backend
pip install -r requirements.txt
```

#### Frontend (React)
```bash
cd frontend
yarn install
# OR
npm install
```

### 3. Start MongoDB
```bash
# Windows
mongod --dbpath C:\data\db

# Mac/Linux
mongod --dbpath /usr/local/var/mongodb
```

### 4. Configure Environment Variables
```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your settings

# Frontend
cd frontend
cp .env.example .env
# Edit .env with your settings
```

### 5. Start Development Servers

#### Terminal 1 - Backend
```bash
cd backend
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8001
```

#### Terminal 2 - Frontend
```bash
cd frontend
yarn start
# OR
npm start
```

### 6. Open in Browser
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

---

## 📁 Project Structure

```
pocket-option-signal-bot/
├── backend/
│   ├── server.py                              # FastAPI main server
│   ├── requirements.txt                       # Python dependencies
│   ├── .env                                   # Environment variables
│   ├── .env.example                          # Environment template
│   │
│   ├── # Strategy Files
│   ├── force_signal_generator.py
│   ├── enhanced_1m_rsi_bb_volume_v2.py
│   ├── enhanced_1m_stoch_macd_pattern_v2.py
│   ├── pocket_option_1m_rsi_bb_volume.py
│   ├── pocket_option_1m_stoch_macd_pattern.py
│   ├── signal_setup_validator.py
│   │
│   ├── # Service Files
│   ├── trading_bot_service.py
│   ├── signal_validator.py
│   ├── pocket_option_timing_sync.py
│   └── ...
│
├── frontend/
│   ├── package.json                          # Node dependencies
│   ├── .env                                  # Frontend environment
│   ├── .env.example                         # Environment template
│   │
│   ├── public/
│   │   └── index.html
│   │
│   └── src/
│       ├── App.js                           # Main React app
│       ├── index.js                         # Entry point
│       │
│       └── components/
│           ├── Dashboard.js
│           ├── StrategySelector.js          # Strategy selection
│           ├── LiveSignalsDisplay.js
│           └── ...
│
├── .vscode/
│   ├── settings.json                        # VS Code settings
│   ├── launch.json                          # Debug configurations
│   ├── extensions.json                      # Recommended extensions
│   └── tasks.json                           # Build tasks
│
├── docker-compose.yml                        # Docker setup (optional)
├── LOCAL_DEVELOPMENT_SETUP.md               # This file
└── README.md                                # Main documentation
```

---

## 🔧 VS Code Configuration

### Settings.json
Location: `.vscode/settings.json`
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/backend/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": false,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    "**/node_modules": true,
    "**/.git": true
  }
}
```

### Launch.json (Debugging)
Location: `.vscode/launch.json`
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "server:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8001"
      ],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "React: Frontend",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:3000",
      "webRoot": "${workspaceFolder}/frontend/src"
    }
  ]
}
```

---

## 🗄️ MongoDB Setup

### Windows
```bash
# 1. Download MongoDB Community Server
# 2. Install with default settings
# 3. Create data directory
mkdir C:\data\db

# 4. Start MongoDB
"C:\Program Files\MongoDB\Server\7.0\bin\mongod.exe" --dbpath="C:\data\db"

# 5. (Optional) Install MongoDB Compass GUI
```

### Mac
```bash
# Using Homebrew
brew tap mongodb/brew
brew install mongodb-community@7.0

# Start MongoDB
brew services start mongodb-community@7.0

# Or manually
mongod --config /usr/local/etc/mongod.conf
```

### Linux (Ubuntu)
```bash
# Import MongoDB public key
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu $(lsb_release -cs)/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list

# Install MongoDB
sudo apt-get update
sudo apt-get install -y mongodb-org

# Start MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
```

### Verify MongoDB is Running
```bash
# Connect to MongoDB shell
mongosh

# OR using Python
python -c "from pymongo import MongoClient; print(MongoClient('mongodb://localhost:27017').server_info())"
```

---

## ⚙️ Environment Variables

### Backend (.env)
```env
# MongoDB
MONGO_URL=mongodb://localhost:27017
DB_NAME=trading_signals

# API Keys (Optional - for data sources)
FINNHUB_API_KEY=your_key_here
ALPHAVANTAGE_API_KEY=your_key_here

# Pocket Option Integration
POCKET_OPTION_SSID=your_ssid_here
POCKET_OPTION_UID=your_uid_here
POCKET_OPTION_EMAIL=your_email@example.com
POCKET_OPTION_PASSWORD=your_password

# Bot Configuration
MIN_PROBABILITY_THRESHOLD=85
DEFAULT_STAKE=2.0
MAX_DAILY_TRADES=10

# Server
HOST=0.0.0.0
PORT=8001
DEBUG=True
```

### Frontend (.env)
```env
REACT_APP_BACKEND_URL=http://localhost:8001
REACT_APP_WS_URL=ws://localhost:8001/ws
REACT_APP_ENV=development
```

---

## 🐛 Debugging in VS Code

### Debug Backend (FastAPI)
1. Open `backend/server.py`
2. Set breakpoints (click left of line numbers)
3. Press `F5` or click "Run and Debug" → "Python: FastAPI"
4. Backend starts with debugger attached
5. Make API request to trigger breakpoint

### Debug Frontend (React)
1. Start frontend: `yarn start`
2. Open Chrome DevTools (F12)
3. Use React DevTools extension
4. OR use VS Code debugger:
   - Press `F5` → "React: Frontend"
   - Chrome opens with debugger attached

### Common Debugging Tasks
```bash
# Test backend endpoint
curl http://localhost:8001/api/config

# Check backend logs
# (In VS Code terminal where backend is running)

# Check MongoDB data
mongosh
use trading_signals
db.configurations.find()
db.signals.find().limit(5)
```

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
# OR
python -m pytest -v
```

### Frontend Tests
```bash
cd frontend
yarn test
# OR
npm test
```

### Manual API Testing
Use Thunder Client extension in VS Code:
1. Install Thunder Client
2. Create new request
3. Test endpoints:
   - GET http://localhost:8001/api/config
   - POST http://localhost:8001/api/signals/force-generate
   - GET http://localhost:8001/api/signals/statistics

---

## 🔄 Development Workflow

### Starting Development Session
```bash
# Terminal 1 - MongoDB
mongod --dbpath /path/to/data

# Terminal 2 - Backend
cd backend
python -m uvicorn server:app --reload --port 8001

# Terminal 3 - Frontend
cd frontend
yarn start

# VS Code will open browser automatically at http://localhost:3000
```

### Making Changes

**Backend Changes:**
1. Edit Python file
2. Save (auto-reload with --reload flag)
3. Test API endpoint
4. Check terminal for errors

**Frontend Changes:**
1. Edit React component
2. Save (auto-reload via webpack)
3. See changes in browser instantly
4. Check browser console for errors

### Adding New Dependencies

**Backend:**
```bash
cd backend
pip install <package>
pip freeze > requirements.txt
```

**Frontend:**
```bash
cd frontend
yarn add <package>
# OR
npm install <package>
```

---

## 🐳 Docker Alternative (Optional)

If you prefer Docker:

### docker-compose.yml
```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: trading_signals

  backend:
    build: ./backend
    ports:
      - "8001:8001"
    volumes:
      - ./backend:/app/backend
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=trading_signals
    depends_on:
      - mongodb
    command: uvicorn server:app --reload --host 0.0.0.0 --port 8001

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app/frontend
      - /app/frontend/node_modules
    environment:
      - REACT_APP_BACKEND_URL=http://localhost:8001
    command: yarn start

volumes:
  mongodb_data:
```

### Run with Docker
```bash
docker-compose up -d
```

---

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Windows
netstat -ano | findstr :8001
taskkill /PID <PID> /F

# Mac/Linux
lsof -ti:8001 | xargs kill -9
```

### MongoDB Connection Error
```bash
# Check if MongoDB is running
ps aux | grep mongod

# Start MongoDB
mongod --dbpath /path/to/data

# Check connection
mongosh
```

### Python Import Errors
```bash
# Ensure you're in correct directory
cd backend

# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

### Frontend Won't Start
```bash
# Clear cache
rm -rf node_modules package-lock.json
npm install

# OR with yarn
rm -rf node_modules yarn.lock
yarn install
```

### Hot Reload Not Working
- **Backend**: Make sure using `--reload` flag
- **Frontend**: Check if `FAST_REFRESH` is enabled in webpack config

---

## 📝 Common Development Tasks

### Create New Strategy
1. Create file: `backend/my_new_strategy.py`
2. Implement strategy class with `generate_signal()` method
3. Add to `force_signal_generator.py` imports
4. Add strategy config to `StrategySelector.js`
5. Test with force generate endpoint

### Add New API Endpoint
1. Open `backend/server.py`
2. Add route with `@api_router.get()` or `@api_router.post()`
3. Implement handler function
4. Test with Thunder Client
5. Update frontend API calls if needed

### Add New Component
1. Create file: `frontend/src/components/MyComponent.js`
2. Import React and necessary components
3. Implement component
4. Import in parent component
5. Test in browser

### Database Schema Changes
1. Update model in backend
2. (Optional) Create migration script
3. Update API endpoints
4. Update frontend to handle new fields

---

## 🎯 Best Practices

### Code Organization
- **Backend**: Separate concerns (routes, services, models)
- **Frontend**: Component-based architecture
- **Naming**: Use descriptive names
- **Comments**: Explain complex logic

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/my-new-feature

# Make changes
git add .
git commit -m "feat: add new feature"

# Push to remote
git push origin feature/my-new-feature

# Create Pull Request
```

### Testing
- Write tests for new features
- Run tests before committing
- Test both happy path and error cases
- Test in different browsers

---

## 📚 Additional Resources

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- MongoDB: https://www.mongodb.com/docs/
- TA-Lib: https://ta-lib.org/

### Learning Resources
- Python Async: https://realpython.com/async-io-python/
- React Hooks: https://react.dev/reference/react
- MongoDB Queries: https://www.mongodb.com/docs/manual/tutorial/query-documents/

### Community
- VS Code: https://code.visualstudio.com/docs
- FastAPI Discord: https://discord.gg/fastapi
- React Community: https://react.dev/community

---

## ✅ Setup Checklist

- [ ] Install Python 3.9+
- [ ] Install Node.js 16+
- [ ] Install MongoDB
- [ ] Install VS Code
- [ ] Install VS Code extensions
- [ ] Clone/copy project
- [ ] Install backend dependencies
- [ ] Install frontend dependencies
- [ ] Configure .env files
- [ ] Start MongoDB
- [ ] Start backend (port 8001)
- [ ] Start frontend (port 3000)
- [ ] Open http://localhost:3000
- [ ] Test signal generation
- [ ] Configure Pocket Option credentials

---

## 🎉 You're Ready!

Your local development environment is set up. Happy coding! 🚀

For questions or issues, check:
- Backend logs in terminal
- Frontend console (F12 in browser)
- MongoDB logs
- This documentation
