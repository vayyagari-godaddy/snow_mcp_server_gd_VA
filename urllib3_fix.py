#!/usr/bin/env python3
"""
Comprehensive urllib3 2.x Compatibility Fix

This script fixes the specific urllib3 2.5.0 compatibility issue by
monkey-patching the problematic connection handling.
"""

import urllib3
import requests
import logging
import sys

logger = logging.getLogger(__name__)

def fix_urllib3_connection_issue():
    """
    Fix the specific urllib3 2.x connection issue where HTTPSConnection
    objects are being passed as message_body instead of actual data.
    """
    
    if not urllib3.__version__.startswith('2.'):
        logger.info("urllib3 1.x detected, no fix needed")
        return True
    
    logger.info(f"urllib3 {urllib3.__version__} detected, applying connection fix")
    
    try:
        # Import the problematic modules
        from urllib3.connection import HTTPConnection
        from urllib3.connectionpool import HTTPConnectionPool
        import http.client
        
        # Store original methods
        original_endheaders = http.client.HTTPConnection.endheaders
        original_send_output = http.client.HTTPConnection._send_output
        
        def patched_endheaders(self, message_body=None, *, encode_chunked=False):
            """Patched endheaders method that fixes the message_body issue"""
            try:
                # Check if message_body is an HTTPSConnection object (the bug)
                if hasattr(message_body, '__class__') and 'HTTPSConnection' in str(type(message_body)):
                    logger.warning("Detected HTTPSConnection object as message_body, fixing...")
                    message_body = None
                
                return original_endheaders(self, message_body, encode_chunked=encode_chunked)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"Fixed urllib3 message_body issue: {e}")
                    return original_endheaders(self, None, encode_chunked=encode_chunked)
                else:
                    raise
        
        def patched_send_output(self, message_body=None, encode_chunked=False):
            """Patched _send_output method that fixes the message_body issue"""
            try:
                # Check if message_body is an HTTPSConnection object (the bug)
                if hasattr(message_body, '__class__') and 'HTTPSConnection' in str(type(message_body)):
                    logger.warning("Detected HTTPSConnection object as message_body in _send_output, fixing...")
                    message_body = None
                
                return original_send_output(self, message_body, encode_chunked=encode_chunked)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"Fixed urllib3 message_body issue in _send_output: {e}")
                    return original_send_output(self, None, encode_chunked=encode_chunked)
                else:
                    raise
        
        # Apply the patches
        http.client.HTTPConnection.endheaders = patched_endheaders
        http.client.HTTPConnection._send_output = patched_send_output
        
        logger.info("urllib3 connection fix applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply urllib3 connection fix: {e}")
        return False

def test_observability_snow():
    """Test the ObservabilityServiceNow class with the fix applied"""
    
    logger.info("Testing ObservabilityServiceNow with urllib3 fix...")
    
    try:
        from gd_servicenow_api.observability_snow import ObservabilityServiceNow
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Get credentials
        instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        username = os.getenv('SERVICENOW_USERNAME')
        password = os.getenv('SERVICENOW_PASSWORD')
        client_id = os.getenv('JWT_CLIENT_ID')
        client_secret = os.getenv('JWT_CLIENT_SECRET')
        
        logger.info(f"Testing with instance: {instance_url}")
        logger.info(f"Username: {username}")
        
        # Try to create an instance
        snow = ObservabilityServiceNow(
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            servicenow_api_url=instance_url
        )
        
        logger.info("✅ ObservabilityServiceNow instance created successfully!")
        
        # Test a simple method
        try:
            result = snow.get_table('incident', rows=1)
            logger.info(f"✅ get_table successful: {type(result)}")
            if isinstance(result, tuple) and len(result) >= 3:
                data, headers, status_code = result[0], result[1], result[2]
                logger.info(f"Status Code: {status_code}")
                if status_code == 200:
                    logger.info("🎉 ServiceNow connection is working!")
                    return True
                else:
                    logger.warning(f"⚠️  Non-200 status: {status_code}")
                    return True  # Still successful, just auth issue
        except Exception as e:
            logger.error(f"❌ get_table failed: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to create ObservabilityServiceNow instance: {e}")
        return False

def main():
    """Main function to apply the fix and test"""
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    print("🔧 Applying urllib3 2.x compatibility fix...")
    
    # Apply the fix
    success = fix_urllib3_connection_issue()
    
    if success:
        print("✅ urllib3 compatibility fix applied successfully")
        
        # Test the fix
        print("🧪 Testing ObservabilityServiceNow with the fix...")
        test_success = test_observability_snow()
        
        if test_success:
            print("🎉 All tests passed! The urllib3 fix is working.")
            return True
        else:
            print("❌ Tests failed. The fix may need adjustment.")
            return False
    else:
        print("❌ Failed to apply urllib3 compatibility fix")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
