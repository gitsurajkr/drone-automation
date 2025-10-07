# Separate SITL configuration module
from typing import List, Optional
import re

class SITLConfig:
    """Configuration and validation for SITL (Software In The Loop) connections only."""
    
    # Strict SITL patterns - only localhost/127.0.0.1 connections
    SITL_PATTERNS = [
        "tcp:127.0.0.1:",
        "tcp:localhost:",
        "udp:127.0.0.1:",
        "udp:localhost:",
        "127.0.0.1:14550",
        "127.0.0.1:5760",
        "localhost:14550", 
        "localhost:5760"
    ]
    
    # Hardware connection indicators (NEVER apply SITL config to these)
    HARDWARE_INDICATORS = [
        "/dev/tty",      # Linux serial ports
        "COM",           # Windows serial ports  
        ".serial",       # Serial connection files
        "hardware",      # Explicit hardware indicator
        "/dev/serial",   # Serial device path
        "ttyUSB",        # USB serial adapters
        "ttyACM",        # Arduino/PX4 connections
    ]
    
    @classmethod
    def is_sitl_connection(cls, connection_string: str) -> bool:
        """Verify if connection string is definitely a SITL connection."""
        if not connection_string:
            return False
            
        # First check if it's definitely hardware - if so, never SITL
        if cls._is_hardware_connection(connection_string):
            return False
            
        # Then check if it matches strict SITL patterns
        connection_lower = connection_string.lower()
        return any(pattern.lower() in connection_lower for pattern in cls.SITL_PATTERNS)
    
    @classmethod
    def _is_hardware_connection(cls, connection_string: str) -> bool:
        """Detect hardware connections that should NEVER have SITL config applied."""
        connection_lower = connection_string.lower()
        return any(indicator.lower() in connection_lower for indicator in cls.HARDWARE_INDICATORS)
    
    @classmethod
    def validate_sitl_safety(cls, connection_string: str) -> tuple[bool, str]:
        """
        Validate that SITL configuration is safe to apply.
        Returns: (is_safe, reason)
        """
        if cls._is_hardware_connection(connection_string):
            return False, f"Hardware connection detected: {connection_string}. SITL config not allowed."
            
        if not cls.is_sitl_connection(connection_string):
            return False, f"Connection pattern not recognized as SITL: {connection_string}"
            
        # Additional safety checks
        if "192.168." in connection_string or "10." in connection_string:
            return False, "Network IP detected - possible hardware drone connection"
            
        return True, "SITL connection validated as safe"

    @classmethod  
    def get_sitl_parameters(cls) -> dict:
        """Get safe SITL-only parameters."""
        return {
            'ARMING_CHECK': 0,          # Disable arming checks for SITL
            'FS_GCS_ENABLE': 0,         # Disable GCS failsafe for SITL
            'FS_EKF_ACTION': 0,         # Disable EKF failsafe for SITL  
            'SYSID_SW_MREV': 120,       # Mark as SITL version
        }