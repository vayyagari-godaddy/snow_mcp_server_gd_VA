#!/usr/bin/env python3
"""
Monkey patch for urllib3 compatibility issue in ObservabilityServiceNow.
This patch is applied at runtime to fix the urllib3 TypeError.
"""

import os
import sys
import logging
import httpx
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class HttpxRequestsAdapter:
    """
    Adapter that makes httpx work like requests to avoid urllib3 compatibility issues.
    """
    
    def __init__(self):
        self.client = httpx.Client()
        logger.info("HttpxRequestsAdapter initialized")
    
    def post(self, url: str, headers: Optional[Dict[str, str]] = None, 
             data: Optional[Dict[str, Any]] = None, **kwargs) -> 'HttpxResponse':
        """Convert requests-style post to httpx."""
        try:
            # Convert data dict to form data if needed
            if data and isinstance(data, dict):
                # httpx expects form data as dict, requests also accepts dict
                response = self.client.post(url, headers=headers, data=data, **kwargs)
            else:
                response = self.client.post(url, headers=headers, data=data, **kwargs)
            
            return HttpxResponse(response)
        except Exception as e:
            logger.warning(f"httpx post failed, falling back to requests: {e}")
            # Fallback to original requests
            return requests.post(url, headers=headers, data=data, **kwargs)
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, 
            params: Optional[Dict[str, Any]] = None, **kwargs) -> 'HttpxResponse':
        """Convert requests-style get to httpx."""
        try:
            response = self.client.get(url, headers=headers, params=params, **kwargs)
            return HttpxResponse(response)
        except Exception as e:
            logger.warning(f"httpx get failed, falling back to requests: {e}")
            # Fallback to original requests
            return requests.get(url, headers=headers, params=params, **kwargs)
    
    def put(self, url: str, headers: Optional[Dict[str, str]] = None, 
            json: Optional[Dict[str, Any]] = None, **kwargs) -> 'HttpxResponse':
        """Convert requests-style put to httpx."""
        try:
            response = self.client.put(url, headers=headers, json=json, **kwargs)
            return HttpxResponse(response)
        except Exception as e:
            logger.warning(f"httpx put failed, falling back to requests: {e}")
            # Fallback to original requests
            return requests.put(url, headers=headers, json=json, **kwargs)
    
    def delete(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> 'HttpxResponse':
        """Convert requests-style delete to httpx."""
        try:
            response = self.client.delete(url, headers=headers, **kwargs)
            return HttpxResponse(response)
        except Exception as e:
            logger.warning(f"httpx delete failed, falling back to requests: {e}")
            # Fallback to original requests
            return requests.delete(url, headers=headers, **kwargs)
    
    def close(self):
        """Close the httpx client."""
        if hasattr(self.client, 'close'):
            self.client.close()

class HttpxResponse:
    """
    Wrapper to make httpx response look like requests response.
    """
    
    def __init__(self, httpx_response):
        self._response = httpx_response
        self.status_code = httpx_response.status_code
        self.headers = httpx_response.headers
        self.text = httpx_response.text
        self.url = str(httpx_response.url)
    
    def json(self):
        """Return JSON data."""
        return self._response.json()
    
    def raise_for_status(self):
        """Raise exception for bad status codes."""
        self._response.raise_for_status()
    
    @property
    def content(self):
        """Return response content as bytes."""
        return self._response.content

def apply_urllib3_monkey_patch():
    """
    Apply monkey patch to fix urllib3 compatibility issue.
    This replaces the requests session in ObservabilityServiceNow with httpx.
    """
    try:
        # Import the original class
        from gd_servicenow_api.observability_snow import ObservabilityServiceNow
        
        # Store the original __init__ method
        original_init = ObservabilityServiceNow.__init__
        
        def patched_init(self, username=None, password=None, client_id=None, 
                        client_secret=None, servicenow_api_url=None):
            """Patched __init__ method that uses httpx instead of requests."""
            self.url = servicenow_api_url
            self.username = username
            self.password = password
            self.client_id = client_id
            self.client_secret = client_secret
            self.headers_api = None
            
            # Use our httpx adapter instead of requests
            self._session = HttpxRequestsAdapter()
            
            # Perform authentication using the patched session
            self._authenticate()
            
            logger.info(f"ObservabilityServiceNow initialized with httpx patch for {self.url}")
        
        def _authenticate(self):
            """Patched authentication method."""
            from base64 import b64encode
            from gd_servicenow_api.exceptions import (AuthError, UnauthorizedError, ParameterError)
            
            user_pass = f'{self.client_id}:{self.client_secret}'.encode()
            user_pass_encoded = b64encode(user_pass).decode()
            headers_auth = {
                'Authorization': 'Basic ' + str(user_pass_encoded),
            }

            auth_params = {
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }

            response = self._session.post(f'{self.url}/oauth_token.do', headers=headers_auth, data=auth_params)

            if response.status_code == 403:
                raise UnauthorizedError
            elif response.status_code == 401:
                raise AuthError
            elif response.status_code == 404:
                raise ParameterError

            self.headers_api = {
                'accept': 'application/json',
                'Authorization': 'Bearer ' + response.json()['access_token'],
            }
            
            logger.info("Successfully authenticated with ServiceNow using httpx patch")
        
        # Apply the patches
        ObservabilityServiceNow.__init__ = patched_init
        ObservabilityServiceNow._authenticate = _authenticate
        
        logger.info("✅ urllib3 monkey patch applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to apply urllib3 monkey patch: {e}")
        return False

def revert_urllib3_monkey_patch():
    """
    Revert the monkey patch (this would require restarting the Python process).
    """
    logger.warning("Monkey patch reversion requires restarting the Python process")
    return False

# Auto-apply the patch when this module is imported
if __name__ == "__main__":
    success = apply_urllib3_monkey_patch()
    if success:
        print("✅ urllib3 monkey patch applied successfully")
    else:
        print("❌ Failed to apply urllib3 monkey patch")
        sys.exit(1)
else:
    # Auto-apply when imported
    apply_urllib3_monkey_patch()
