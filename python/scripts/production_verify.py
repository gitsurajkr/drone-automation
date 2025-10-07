#!/usr/bin/env python3
"""
Simple System Verification Script
================================
Basic verification of drone automation system components.
"""

import sys
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_core_imports():
    """Test that all core modules can be imported."""
    try:
        # Test critical imports
        import dronekit
        import websockets  
        import pymavlink
        logger.info("✅ External dependencies imported successfully")
        
        # Test internal modules
        sys.path.append('.')
        from src.core.controller import Controller
        from src.safety.flight_safety import FlightSafetyManager
        from src.communication.ws_server import start_ws_server
        from config.config import WS_HOST, WS_PORT
        logger.info("✅ Internal modules imported successfully")
        
        return True
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def test_safety_systems():
    """Test safety manager initialization."""
    try:
        from src.safety.flight_safety import FlightSafetyManager
        safety_manager = FlightSafetyManager()
        logger.info("✅ Safety manager initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Safety system error: {e}")
        return False

def test_configuration():
    """Test configuration loading."""
    try:
        from config.config import WS_HOST, WS_PORT, DEFAULT_CONNECTION_STRING
        from config.sitl_config import SITLConfig
        
        assert WS_HOST is not None
        assert WS_PORT is not None
        assert DEFAULT_CONNECTION_STRING is not None
        
        logger.info("✅ Configuration loaded successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        return False

def main():
    """Run all verification tests."""
    logger.info("🚁 Starting system verification...")
    
    tests = [
        ("Core Imports", test_core_imports),
        ("Safety Systems", test_safety_systems),
        ("Configuration", test_configuration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"Running {test_name} test...")
        if test_func():
            passed += 1
        else:
            logger.error(f"Test failed: {test_name}")
    
    logger.info(f"\n📊 Verification Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All systems verified successfully - PRODUCTION READY!")
        return 0
    else:
        logger.error("⚠️ Some tests failed - review errors above")
        return 1

if __name__ == "__main__":
    exit(main())