# Removes all __pycache__ directories and .pyc files

echo "🧹 Cleaning Python cache files..."

# Remove __pycache__ directories
find . -name "__pycache__" -type d -print
echo "Removing __pycache__ directories..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Remove .pyc files
find . -name "*.pyc" -print
echo "Removing .pyc files..."
find . -name "*.pyc" -delete 2>/dev/null || true

# Remove .pyo files (optimized bytecode)
find . -name "*.pyo" -delete 2>/dev/null || true

echo "Python cache cleanup complete!"
echo ""
echo "Tip: Run 'source setup_dev_env.sh' to prevent future cache creation"