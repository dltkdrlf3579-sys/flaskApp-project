@echo off
echo ========================================
echo Flask Portal Development Mode
echo ========================================
echo.

REM Set environment variables for development
set USE_MOCK=true
set FLASK_ENV=development
set FLASK_DEBUG=1

echo [1] Syncing mock data to database...
python test_mock_sync.py
echo.

echo [2] Starting Flask application...
echo.
echo Application will be available at:
echo   - http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python app.py