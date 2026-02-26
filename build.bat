@echo off
setlocal

REM --- Build Legacy Frontend ---
echo "--- Building Legacy Frontend ---"
echo "Navigating to the legacy frontend directory..."
cd frontend\legacy || (echo "Failed to navigate to frontend\legacy directory" & exit /b 1)

echo "Installing legacy frontend dependencies..."
call npm install || (echo "npm install failed for legacy frontend" & exit /b 1)

echo "Building legacy frontend..."
call npm run build || (echo "npm run build failed for legacy frontend" & exit /b 1)

echo "Navigating back to the root directory..."
cd ..\.. || (echo "Failed to navigate back to root directory" & exit /b 1)

REM --- Build V2 Frontend ---
echo "--- Building V2 Frontend ---"
echo "Navigating to the V2 frontend directory..."
cd frontend\v2 || (echo "Failed to navigate to frontend\v2 directory" & exit /b 1)

echo "Installing V2 frontend dependencies..."
call npm install || (echo "npm install failed for V2 frontend" & exit /b 1)

echo "Building V2 frontend..."
call npm run build || (echo "npm run build failed for V2 frontend" & exit /b 1)

echo "Navigating back to the root directory..."
cd ..\.. || (echo "Failed to navigate back to root directory" & exit /b 1)

REM --- Build Python Package ---
echo "--- Building Python Package ---"
python -m build || (echo "Python build failed" & exit /b 1)

endlocal
