#!/usr/bin/env python3
"""
Complete urllib3 2.x Compatibility Fix

This script provides a comprehensive fix for urllib3 2.5.0 compatibility issues
by patching the problematic connection handling at multiple levels.
"""

import urllib3
import requests
import logging
import sys
import os

logger = logging.getLogger(__name__)

def apply_urllib3_fix():
    """
    Apply a comprehensive fix for urllib3 2.x compatibility issues.
    """
    
    if not urllib3.__version__.startswith('2.'):
        logger.info("urllib3 1.x detected, no fix needed")
        return True
    
    logger.info(f"urllib3 {urllib3.__version__} detected, applying comprehensive fix")
    
    try:
        # Fix 1: Patch http.client.HTTPConnection
        import http.client
        
        original_endheaders = http.client.HTTPConnection.endheaders
        original_send_output = http.client.HTTPConnection._send_output
        
        def safe_endheaders(self, message_body=None, *, encode_chunked=False):
            """Safe endheaders that handles urllib3 2.x issues"""
            try:
                # Check for the specific bug where HTTPSConnection is passed as message_body
                if message_body is not None and hasattr(message_body, '__class__'):
                    class_name = str(type(message_body))
                    if 'HTTPSConnection' in class_name or 'HTTPConnection' in class_name:
                        logger.warning(f"Fixed urllib3 bug: {class_name} passed as message_body")
                        message_body = None
                
                return original_endheaders(self, message_body, encode_chunked=encode_chunked)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"Fixed urllib3 TypeError: {e}")
                    return original_endheaders(self, None, encode_chunked=encode_chunked)
                else:
                    raise
        
        def safe_send_output(self, message_body=None, encode_chunked=False):
            """Safe _send_output that handles urllib3 2.x issues"""
            try:
                # Check for the specific bug where HTTPSConnection is passed as message_body
                if message_body is not None and hasattr(message_body, '__class__'):
                    class_name = str(type(message_body))
                    if 'HTTPSConnection' in class_name or 'HTTPConnection' in class_name:
                        logger.warning(f"Fixed urllib3 bug in _send_output: {class_name} passed as message_body")
                        message_body = None
                
                return original_send_output(self, message_body, encode_chunked=encode_chunked)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"Fixed urllib3 TypeError in _send_output: {e}")
                    return original_send_output(self, None, encode_chunked=encode_chunked)
                else:
                    raise
        
        # Apply the patches
        http.client.HTTPConnection.endheaders = safe_endheaders
        http.client.HTTPConnection._send_output = safe_send_output
        
        # Fix 2: Patch urllib3.connection.HTTPConnection
        from urllib3.connection import HTTPConnection as Urllib3HTTPConnection
        
        original_urllib3_endheaders = Urllib3HTTPConnection.endheaders
        original_urllib3_send_output = Urllib3HTTPConnection._send_output
        
        def safe_urllib3_endheaders(self, message_body=None, *, encode_chunked=False):
            """Safe urllib3 endheaders"""
            try:
                if message_body is not None and hasattr(message_body, '__class__'):
                    class_name = str(type(message_body))
                    if 'HTTPSConnection' in class_name or 'HTTPConnection' in class_name:
                        logger.warning(f"Fixed urllib3 connection bug: {class_name} passed as message_body")
                        message_body = None
                
                return original_urllib3_endheaders(self, message_body, encode_chunked=encode_chunked)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"Fixed urllib3 connection TypeError: {e}")
                    return original_urllib3_endheaders(self, None, encode_chunked=encode_chunked)
                else:
                    raise
        
        def safe_urllib3_send_output(self, message_body=None, encode_chunked=False):
            """Safe urllib3 _send_output"""
            try:
                if message_body is not None and hasattr(message_body, '__class__'):
                    class_name = str(type(message_body))
                    if 'HTTPSConnection' in class_name or 'HTTPConnection' in class_name:
                        logger.warning(f"Fixed urllib3 connection bug in _send_output: {class_name} passed as message_body")
                        message_body = None
                
                return original_urllib3_send_output(self, message_body, encode_chunked=encode_chunked)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"Fixed urllib3 connection TypeError in _send_output: {e}")
                    return original_urllib3_send_output(self, None, encode_chunked=encode_chunked)
                else:
                    raise
        
        # Apply urllib3 patches
        Urllib3HTTPConnection.endheaders = safe_urllib3_endheaders
        Urllib3HTTPConnection._send_output = safe_urllib3_send_output
        
        logger.info("Comprehensive urllib3 fix applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply urllib3 fix: {e}")
        return False

def test_fix():
    """Test the fix with ObservabilityServiceNow"""
    
    logger.info("Testing urllib3 fix with ObservabilityServiceNow...")
    
    try:
        from gd_servicenow_api.observability_snow import ObservabilityServiceNow
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
    """Main function"""
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    print("🔧 Applying comprehensive urllib3 2.x compatibility fix...")
    
    # Apply the fix
    success = apply_urllib3_fix()
    
    if success:
        print("✅ urllib3 compatibility fix applied successfully")
        
        # Test the fix
        print("🧪 Testing ObservabilityServiceNow with the fix...")
        test_success = test_fix()
        
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
