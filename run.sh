#!/usr/bin/env bash
# run.sh — Clean start script for Sahayak AI on macOS / Linux

set -e

echo "============================================="
echo "   Starting Sahayak AI Support Assistant"
echo "============================================="

# 1. Navigate to script directory
cd "$(dirname "$0")"

# 2. Clear old Streamlit and Python caches
echo "🧹 Cleaning temporary files and Streamlit cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
rm -rf ~/.streamlit/cache 2>/dev/null || true

# 3. Clean temporary audio files if any exist
find . -maxdepth 2 -type f \( -name "*.tmp" -o -name "*.wav" -o -name "*.mp3" \) -mtime +7 -delete 2>/dev/null || true

# 4. Activate virtual environment if present
if [ -d ".venv" ]; then
    echo "🐍 Activating .venv virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "🐍 Activating venv virtual environment..."
    source venv/bin/activate
fi

# 5. Start Streamlit app with recommended production flags
echo "🚀 Starting Streamlit application on port 8501..."
exec streamlit run app.py --server.headless=true --server.port=8501

