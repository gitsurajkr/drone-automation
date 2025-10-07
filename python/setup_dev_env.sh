#!/bin/bash
# Drone Automation Development Environment Setup
# Run: source setup_dev_env.sh

echo "🚁 Setting up drone automation development environment..."

# Prevent Python from creating __pycache__ directories
export PYTHONDONTWRITEBYTECODE=1
echo "✅ Disabled Python bytecode generation"

# Activate virtual environment
if [ -f "ardupilot/bin/activate" ]; then
    source ardupilot/bin/activate
    echo "✅ Activated virtual environment"
else
    echo "⚠️  Virtual environment not found at ardupilot/bin/activate"
fi

# Set Python path for imports
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
echo "✅ Set Python path to current directory"

# Clean any existing cache
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "✅ Cleaned existing Python cache files"

echo ""
echo "🎉 Development environment ready!"
echo "📝 Note: __pycache__ directories will not be created"
echo "🚀 Run 'python launch_production.py' to start the system"
echo ""