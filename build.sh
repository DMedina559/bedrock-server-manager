#!/bin/bash

# Exit on error
set -e

# --- Build Legacy Frontend ---
echo "--- Building Legacy Frontend ---"
cd frontend/legacy
echo "Installing legacy frontend dependencies..."
npm install
echo "Building legacy frontend..."
npm run build
cd ../..

# --- Build V2 Frontend ---
echo "--- Building V2 Frontend ---"
cd frontend/v2
echo "Installing V2 frontend dependencies..."
npm install
echo "Building V2 frontend..."
npm run build
cd ../..

# --- Build Python Package ---
echo "--- Building Python Package ---"
python -m build
