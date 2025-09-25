#!/usr/bin/python
# coding: utf-8
"""
Patched version of ObservabilityServiceNow to fix urllib3 compatibility issues.
This version uses httpx instead of requests to avoid the urllib3 TypeError.
"""

import os
import httpx
import logging
from datetime import datetime
from urllib.parse import quote_plus
import json
from base64 import b64encode
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import the original class to inherit from it
try:
    from gd_servicenow_api.observability_snow import ObservabilityServiceNow as OriginalObservabilityServiceNow
    from gd_servicenow_api.exceptions import (AuthError, UnauthorizedError, ParameterError, MissingParameterError, DataProcessorAlreadyExists)
except ImportError as e:
    logger.error(f"Failed to import original ObservabilityServiceNow: {e}")
    raise

class ObservabilityServiceNowPatched(OriginalObservabilityServiceNow):
    """
    Patched version of ObservabilityServiceNow that uses httpx instead of requests
    to avoid urllib3 compatibility issues.
    """
    
    def __init__(self, username=None, password=None, client_id=None, client_secret=None, servicenow_api_url=None):
        """
        Initialize the patched ServiceNow client with httpx instead of requests.
        """
        self.url = servicenow_api_url
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers_api = None
        
        # Use httpx instead of requests to avoid urllib3 issues
        self._session = httpx.Client()
        
        # Perform authentication
        self._authenticate()
        
        logger.info(f"ObservabilityServiceNowPatched initialized for {self.url}")
    
    def _authenticate(self):
        """Perform OAuth authentication using httpx."""
        try:
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

            response = self._session.post(
                f'{self.url}/oauth_token.do', 
                headers=headers_auth, 
                data=auth_params
            )

            if response.status_code == 403:
                raise UnauthorizedError
            elif response.status_code == 401:
                raise AuthError
            elif response.status_code == 404:
                raise ParameterError

            response.raise_for_status()
            token_data = response.json()
            
            self.headers_api = {
                'accept': 'application/json',
                'Authorization': 'Bearer ' + token_data['access_token'],
            }
            
            logger.info("Successfully authenticated with ServiceNow using httpx")
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
    
    def get_table(self, table: str, rows: int = 1, **kwargs) -> tuple[Dict[str, Any], Dict[str, Any], int]:
        """
        Get data from a ServiceNow table using httpx.
        """
        try:
            url = f"{self.url}/api/now/table/{table}"
            params = {"sysparm_limit": rows}
            params.update(kwargs)
            
            response = self._session.get(url, headers=self.headers_api, params=params)
            response.raise_for_status()
            
            return response.json(), dict(response.headers), response.status_code
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching table {table}: {e.response.status_code} - {e.response.text}")
            return {"error": e.response.text}, {}, e.response.status_code
        except httpx.RequestError as e:
            logger.error(f"Request error fetching table {table}: {e}")
            return {"error": str(e)}, {}, 500
        except Exception as e:
            logger.error(f"Unexpected error fetching table {table}: {e}")
            return {"error": str(e)}, {}, 500
    
    def post_table(self, table: str, data: Dict[str, Any], **kwargs) -> tuple[Dict[str, Any], Dict[str, Any], int]:
        """
        Post data to a ServiceNow table using httpx.
        """
        try:
            url = f"{self.url}/api/now/table/{table}"
            
            response = self._session.post(url, headers=self.headers_api, json=data, **kwargs)
            response.raise_for_status()
            
            return response.json(), dict(response.headers), response.status_code
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error posting to table {table}: {e.response.status_code} - {e.response.text}")
            return {"error": e.response.text}, {}, e.response.status_code
        except httpx.RequestError as e:
            logger.error(f"Request error posting to table {table}: {e}")
            return {"error": str(e)}, {}, 500
        except Exception as e:
            logger.error(f"Unexpected error posting to table {table}: {e}")
            return {"error": str(e)}, {}, 500
    
    def put_table(self, table: str, sys_id: str, data: Dict[str, Any], **kwargs) -> tuple[Dict[str, Any], Dict[str, Any], int]:
        """
        Update data in a ServiceNow table using httpx.
        """
        try:
            url = f"{self.url}/api/now/table/{table}/{sys_id}"
            
            response = self._session.put(url, headers=self.headers_api, json=data, **kwargs)
            response.raise_for_status()
            
            return response.json(), dict(response.headers), response.status_code
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error updating table {table}: {e.response.status_code} - {e.response.text}")
            return {"error": e.response.text}, {}, e.response.status_code
        except httpx.RequestError as e:
            logger.error(f"Request error updating table {table}: {e}")
            return {"error": str(e)}, {}, 500
        except Exception as e:
            logger.error(f"Unexpected error updating table {table}: {e}")
            return {"error": str(e)}, {}, 500
    
    def delete_table(self, table: str, sys_id: str, **kwargs) -> tuple[Dict[str, Any], Dict[str, Any], int]:
        """
        Delete data from a ServiceNow table using httpx.
        """
        try:
            url = f"{self.url}/api/now/table/{table}/{sys_id}"
            
            response = self._session.delete(url, headers=self.headers_api, **kwargs)
            response.raise_for_status()
            
            return response.json(), dict(response.headers), response.status_code
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting from table {table}: {e.response.status_code} - {e.response.text}")
            return {"error": e.response.text}, {}, e.response.status_code
        except httpx.RequestError as e:
            logger.error(f"Request error deleting from table {table}: {e}")
            return {"error": str(e)}, {}, 500
        except Exception as e:
            logger.error(f"Unexpected error deleting from table {table}: {e}")
            return {"error": str(e)}, {}, 500
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the ServiceNow connection.
        """
        try:
            response_data, headers, status_code = self.get_table(
                table="incident",
                rows=1
            )

            if status_code == 200:
                return {
                    "success": True,
                    "message": "ServiceNow connection is working with patched httpx client",
                    "connection_details": {
                        "instance_url": self.url,
                        "username": self.username,
                        "method": "httpx_patched"
                    }
                }
            else:
                error_message = "Unauthorized"
                if isinstance(response_data, dict) and 'error' in response_data:
                    if isinstance(response_data['error'], dict) and 'message' in response_data['error']:
                        error_message = response_data['error']['message']
                    else:
                        error_message = str(response_data['error'])

                return {
                    "success": False,
                    "error": f"Authentication failed - check username/password or instance URL",
                    "status_code": status_code,
                    "details": f"ServiceNow returned {status_code}: {error_message}"
                }
        except Exception as e:
            logger.error(f"ServiceNow connection test failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def __del__(self):
        """Clean up httpx client on destruction."""
        if hasattr(self, '_session') and self._session:
            try:
                self._session.close()
            except:
                pass

# Create an alias for easier import
ObservabilityServiceNow = ObservabilityServiceNowPatched
