@echo off
REM Build script for AgentM Docker container (Windows)
REM This script provides better error reporting and build progress visibility

echo ===============================================
echo Building AgentM Docker Container
echo ===============================================
echo.

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: docker-compose not found. Please install Docker Compose.
    exit /b 1
)

echo Starting Docker build...
echo This may take several minutes on first build.
echo.

REM Build with progress output
docker-compose build --progress=plain

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===============================================
    echo Build completed successfully!
    echo ===============================================
    echo.
    echo To start the container, run:
    echo   docker-compose up -d
    echo.
    echo To view logs:
    echo   docker-compose logs -f
    echo.
) else (
    echo.
    echo ===============================================
    echo Build failed! Check the error messages above.
    echo ===============================================
    echo.
    echo Common issues:
    echo   1. Segmentation fault - Try increasing Docker memory limit
    echo   2. Network issues - Check your internet connection
    echo   3. Disk space - Ensure you have enough free space
    echo.
    exit /b %ERRORLEVEL%
)
