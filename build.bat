@echo off
setlocal

REM Exit on error
set "error_occurred="
trap 'set error_occurred=true; (>&2 echo Error occurred in script at line %LINENO%); exit /b 1' ERR

REM Navigate to the frontend directory
echo "Navigating to the frontend directory..."
cd frontend || (echo "Failed to navigate to frontend directory" & exit /b 1)

REM Install frontend dependencies
echo "Installing frontend dependencies..."
call npm install || (echo "npm install failed" & exit /b 1)

REM Build the frontend
echo "Building frontend..."
call npm run build || (echo "npm run build failed" & exit /b 1)

REM Navigate back to the root directory
echo "Navigating back to the root directory..."
cd .. || (echo "Failed to navigate back to root directory" & exit /b 1)

REM Build the Python package
echo "Building Python package..."
python -m build || (echo "Python build failed" & exit /b 1)

endlocal
