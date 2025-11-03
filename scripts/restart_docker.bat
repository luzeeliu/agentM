@echo off
REM Quick restart script - use when you've changed code but not dependencies

echo ==========================================
echo Restarting Docker Container
echo ==========================================
echo.

echo [1/2] Restarting container...
docker-compose restart

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to restart container!
    exit /b 1
)

echo.
echo Waiting for container to be ready...
timeout /t 3 /nobreak > nul

echo.
echo [2/2] Checking if it's running...
docker-compose ps

echo.
echo ==========================================
echo [SUCCESS] Container restarted!
echo ==========================================
echo.
echo View logs: docker-compose logs -f agentm
echo.
