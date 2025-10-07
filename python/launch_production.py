#!/usr/bin/env python3
"""
Production Deployment Script
===========================
Launch the drone automation system in production mode.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/drone_system_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('production_launcher')

async def main():
    """Production entry point."""
    try:
        logger.info("🚁 Starting Drone Automation System - PRODUCTION MODE")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        # Import and start the WebSocket server
        from src.communication.ws_server import start_ws_server
        from config.config import WS_HOST, WS_PORT
        
        logger.info(f"Starting WebSocket server on {WS_HOST}:{WS_PORT}")
        logger.info("System ready for drone connections...")
        logger.info("Press Ctrl+C to shutdown gracefully")
        
        # Start the server
        await start_ws_server()
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
    except Exception as e:
        logger.error(f"💥 System error: {e}")
        raise
    finally:
        logger.info("🔒 System shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        sys.exit(1)