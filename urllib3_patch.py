#!/usr/bin/env python3
"""
urllib3 Compatibility Patch for ObservabilityServiceNow

This patch fixes the urllib3 2.5.0 compatibility issue by monkey-patching
the problematic methods in the requests library.
"""

import urllib3
import requests
import logging

logger = logging.getLogger(__name__)

def patch_urllib3_compatibility():
    """
    Patch urllib3 compatibility issues with requests library.
    
    The issue is that urllib3 2.x changed how it handles HTTPSConnection objects
    in the message_body parameter, causing TypeError when requests tries to
    send HTTP requests.
    """
    
    # Check if we're using urllib3 2.x
    if not urllib3.__version__.startswith('2.'):
        logger.info("urllib3 1.x detected, no patch needed")
        return True
    
    logger.info(f"urllib3 {urllib3.__version__} detected, applying compatibility patch")
    
    try:
        # Import the problematic modules
        from urllib3.connectionpool import HTTPConnectionPool
        from urllib3.connection import HTTPConnection
        from urllib3.util.retry import Retry
        from urllib3.poolmanager import PoolManager
        
        # Store original methods
        original_urlopen = HTTPConnectionPool.urlopen
        original_make_request = HTTPConnectionPool._make_request
        
        def patched_urlopen(self, method, url, *args, **kwargs):
            """Patched urlopen method that handles urllib3 2.x compatibility"""
            try:
                return original_urlopen(self, method, url, *args, **kwargs)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"urllib3 compatibility issue detected: {e}")
                    # Try to fix the request by ensuring proper data encoding
                    if 'body' in kwargs and kwargs['body'] is not None:
                        if hasattr(kwargs['body'], 'encode'):
                            kwargs['body'] = kwargs['body'].encode('utf-8')
                        elif not isinstance(kwargs['body'], (bytes, bytearray)):
                            kwargs['body'] = str(kwargs['body']).encode('utf-8')
                    return original_urlopen(self, method, url, *args, **kwargs)
                else:
                    raise
        
        def patched_make_request(self, conn, method, url, *args, **kwargs):
            """Patched _make_request method that handles urllib3 2.x compatibility"""
            try:
                return original_make_request(self, conn, method, url, *args, **kwargs)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"urllib3 compatibility issue in _make_request: {e}")
                    # Try to fix the request by ensuring proper data encoding
                    if 'body' in kwargs and kwargs['body'] is not None:
                        if hasattr(kwargs['body'], 'encode'):
                            kwargs['body'] = kwargs['body'].encode('utf-8')
                        elif not isinstance(kwargs['body'], (bytes, bytearray)):
                            kwargs['body'] = str(kwargs['body']).encode('utf-8')
                    return original_make_request(self, conn, method, url, *args, **kwargs)
                else:
                    raise
        
        # Apply the patches
        HTTPConnectionPool.urlopen = patched_urlopen
        HTTPConnectionPool._make_request = patched_make_request
        
        logger.info("urllib3 compatibility patch applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply urllib3 compatibility patch: {e}")
        return False

def patch_requests_session():
    """
    Patch requests.Session to handle urllib3 2.x compatibility issues.
    """
    
    if not urllib3.__version__.startswith('2.'):
        return True
    
    try:
        from requests.adapters import HTTPAdapter
        from requests.sessions import Session
        
        # Store original send method
        original_send = HTTPAdapter.send
        
        def patched_send(self, request, **kwargs):
            """Patched send method that handles urllib3 2.x compatibility"""
            try:
                return original_send(self, request, **kwargs)
            except TypeError as e:
                if "message_body should be a bytes-like object" in str(e):
                    logger.warning(f"urllib3 compatibility issue in requests: {e}")
                    # Try to fix the request body
                    if hasattr(request, 'body') and request.body is not None:
                        if hasattr(request.body, 'encode'):
                            request.body = request.body.encode('utf-8')
                        elif not isinstance(request.body, (bytes, bytearray)):
                            request.body = str(request.body).encode('utf-8')
                    return original_send(self, request, **kwargs)
                else:
                    raise
        
        # Apply the patch
        HTTPAdapter.send = patched_send
        
        logger.info("requests compatibility patch applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply requests compatibility patch: {e}")
        return False

def apply_all_patches():
    """Apply all urllib3 compatibility patches"""
    logger.info("Applying urllib3 compatibility patches...")
    
    success1 = patch_urllib3_compatibility()
    success2 = patch_requests_session()
    
    if success1 and success2:
        logger.info("All urllib3 compatibility patches applied successfully")
        return True
    else:
        logger.error("Some urllib3 compatibility patches failed")
        return False

if __name__ == "__main__":
    # Test the patches
    logging.basicConfig(level=logging.INFO)
    success = apply_all_patches()
    
    if success:
        print("✅ urllib3 compatibility patches applied successfully")
        
        # Test with a simple request
        try:
            import requests
            response = requests.get("https://httpbin.org/get", timeout=5)
            print(f"✅ Test request successful: {response.status_code}")
        except Exception as e:
            print(f"❌ Test request failed: {e}")
    else:
        print("❌ urllib3 compatibility patches failed")
