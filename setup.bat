@echo off
REM Local Development Setup Script for Windows

echo ======================================
echo Pocket Option Signal Bot - Local Setup
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3 not found. Please install Python 3.9+
    exit /b 1
)
echo [OK] Python 3 found

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 16+
    exit /b 1
)
echo [OK] Node.js found

REM Check if MongoDB is installed
mongod --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] MongoDB not found. Please install MongoDB Community Edition
) else (
    echo [OK] MongoDB found
)

echo.
echo Installing Backend Dependencies...
cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Failed to install backend dependencies
    exit /b 1
)
echo [OK] Backend dependencies installed

REM Setup .env file
if not exist ".env" (
    echo Creating backend .env file from template...
    copy .env.example .env
    echo [WARNING] Please edit backend\.env with your configuration
)

cd ..

echo.
echo Installing Frontend Dependencies...
cd frontend

REM Check if yarn is installed
yarn --version >nul 2>&1
if errorlevel 1 (
    npm install
) else (
    yarn install
)

if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies
    exit /b 1
)
echo [OK] Frontend dependencies installed

REM Setup .env file
if not exist ".env" (
    echo Creating frontend .env file from template...
    copy .env.example .env
)

cd ..

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next Steps:
echo    1. Edit backend\.env with your configuration
echo    2. Start MongoDB: mongod --dbpath C:\data\db
echo    3. Start Backend: cd backend ^&^& venv\Scripts\activate ^&^& python -m uvicorn server:app --reload --port 8001
echo    4. Start Frontend: cd frontend ^&^& yarn start
echo    5. Open http://localhost:3000 in your browser
echo.
echo Or use VS Code:
echo    - Open this folder in VS Code
echo    - Press F5 to start debugging
echo    - Select 'Full Stack (Backend + Frontend)'
echo.
pause
