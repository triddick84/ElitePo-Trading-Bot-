@echo off
REM Quick start script for development (Windows)

echo ======================================
echo Starting Pocket Option Signal Bot
echo ======================================
echo.

REM Check if MongoDB is running
tasklist /FI "IMAGENAME eq mongod.exe" 2>NUL | find /I /N "mongod.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo Starting MongoDB...
    start "MongoDB" mongod --dbpath .\data\db
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] MongoDB already running
)

REM Start Backend
echo Starting Backend...
start "Backend" cmd /k "cd backend && venv\Scripts\activate && python -m uvicorn server:app --reload --host 0.0.0.0 --port 8001"

timeout /t 3 /nobreak >nul
echo [OK] Backend started on http://localhost:8001

REM Start Frontend  
echo Starting Frontend...
start "Frontend" cmd /k "cd frontend && yarn start"

echo.
echo ========================================
echo All services started!
echo ========================================
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8001
echo API Docs: http://localhost:8001/docs
echo.
echo Close the terminal windows to stop services
echo.
pause
