#!/bin/bash
# Quick start script for the Incident AI Agent

set -e

echo "🔍 AI Incident Investigation Agent - Quick Start"
echo "================================================"

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "Python version: $python_version"

# Check for .env
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "📝 Please edit .env and add your GEMINI_API_KEY"
    echo "   Get a free key at: https://aistudio.google.com/app/apikey"
    echo ""
fi

# Source .env
set -a && source .env && set +a

if [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
    echo "❌ GEMINI_API_KEY not set in .env"
    echo "   Get your free key at: https://aistudio.google.com/app/apikey"
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -r backend/requirements.txt -q

# Seed data
echo ""
echo "🌱 Seeding demo data..."
cd backend && python utils/data_generator.py && cd ..

# Run Streamlit
echo ""
echo "🚀 Starting Streamlit app..."
echo "   Open http://localhost:8501 in your browser"
echo ""
cd backend
streamlit run ../frontend/streamlit_app.py --server.port=8501
