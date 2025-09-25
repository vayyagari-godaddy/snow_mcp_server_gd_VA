#!/usr/bin/env python3
"""
Monkey patch for urllib3 compatibility issue in ObservabilityServiceNow JWT version.
This patch is applied at runtime to fix the urllib3 TypeError in observability_snow_jwt.py.
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
        logger.info("HttpxRequestsAdapter initialized for JWT version")
    
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

def apply_urllib3_monkey_patch_jwt():
    """
    Apply monkey patch to fix urllib3 compatibility issue in JWT version.
    This replaces the requests session in ObservabilityServiceNow JWT with httpx.
    """
    try:
        # Import the original JWT class
        from gd_servicenow_api.observability_snow_jwt import ObservabilityServiceNow
        
        # Store the original methods
        original_init = ObservabilityServiceNow.__init__
        original_auth = ObservabilityServiceNow.auth
        original_get_token = ObservabilityServiceNow._get_token
        
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
            
            # Set up JWT-specific attributes
            self.username = os.getenv('SERVICENOW_USERNAME')
            self.password = os.getenv('SERVICENOW_PASSWORD')
            self.client_id = os.getenv('JWT_CLIENT_ID')
            self.client_secret = os.getenv('JWT_CLIENT_SECRET')
            self.server, self.port = 'localhost', 8080
            self._redirect_uri = f'http://{self.server}:{self.port}'
            self._last_request_time = 0
            self.auth_url = os.getenv('JWT_AUTH_URL')
            self.token_url = os.getenv('JWT_TOKEN_URL')
            
            # Initialize other attributes
            self.known_assignment_groups = dict()
            self.known_ci_cmdb = dict()
            self.known_ci_cmdb_status = dict()
            
            # Perform authentication using the patched session
            self.auth()
            
            logger.info(f"ObservabilityServiceNow JWT initialized with httpx patch for {self.url}")
        
        def patched_auth(self):
            """Patched auth method that uses httpx for token requests."""
            import webbrowser
            import urllib.parse
            import binascii
            from http.server import HTTPServer, BaseHTTPRequestHandler
            
            # Generate state
            state = binascii.hexlify(os.urandom(20)).decode('utf-8')
            
            params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self._redirect_uri,
                'state': state
            }
            
            # Use httpx for the initial request
            try:
                response = self._session.get(self.auth_url, params=params)
                webbrowser.open(response.url)
            except Exception as e:
                logger.warning(f"httpx auth request failed, falling back to requests: {e}")
                # Fallback to original requests method
                request = requests.Request('GET', self.auth_url, params).prepare()
                request.prepare_url(self.auth_url, params)
                webbrowser.open(request.url)
            
            # Start the local server to receive the callback
            server = HTTPServer((self.server, self.port), RequestHandler)
            server.handle_request()
            
            # Get the authorization code from the global variable
            global code
            payload = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self._redirect_uri
            }
            self._get_token(payload)
        
        def patched_get_token(self, payload):
            """Patched _get_token method that uses httpx."""
            from gd_servicenow_api.exceptions import (AuthError, UnauthorizedError, ParameterError)
            import json
            
            try:
                r = self._session.post(self.token_url, data=payload)
            except Exception as e:
                logger.warning(f"httpx token request failed, falling back to requests: {e}")
                r = requests.post(self.token_url, data=payload)
            
            if r.status_code == 403:
                raise UnauthorizedError
            elif r.status_code == 401:
                raise AuthError
            elif r.status_code == 404:
                raise ParameterError

            data = json.loads(r.text)
            self.id_token = data['id_token']
            self.token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.headers_api = {
                'accept': 'application/json',
                'Authorization': 'Bearer ' + self.id_token,
            }
            
            logger.info("Successfully obtained JWT tokens using httpx patch")
        
        # Apply the patches
        ObservabilityServiceNow.__init__ = patched_init
        ObservabilityServiceNow.auth = patched_auth
        ObservabilityServiceNow._get_token = patched_get_token
        
        logger.info("✅ urllib3 monkey patch applied successfully to JWT version")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to apply urllib3 monkey patch to JWT version: {e}")
        return False

def revert_urllib3_monkey_patch_jwt():
    """
    Revert the monkey patch (this would require restarting the Python process).
    """
    logger.warning("Monkey patch reversion requires restarting the Python process")
    return False

# Auto-apply the patch when this module is imported
if __name__ == "__main__":
    success = apply_urllib3_monkey_patch_jwt()
    if success:
        print("✅ urllib3 monkey patch applied successfully to JWT version")
    else:
        print("❌ Failed to apply urllib3 monkey patch to JWT version")
        sys.exit(1)
else:
    # Auto-apply when imported
    apply_urllib3_monkey_patch_jwt()
