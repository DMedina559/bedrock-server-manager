#!/bin/bash

# Exit on error
set -e

# Navigate to the frontend directory
cd frontend

# Install frontend dependencies
echo "Installing frontend dependencies..."
npm install

# Build the frontend
echo "Building frontend..."
npm run build

# Navigate back to the root directory
cd ..

# Build the Python package
echo "Building Python package..."
python -m build
