#!/usr/bin/env python3
"""
ObservabilityServiceNow Wrapper

This wrapper provides a working alternative to the problematic ObservabilityServiceNow
class by using httpx instead of requests/urllib3.
"""

import os
import httpx
import json
import logging
from typing import Any, Dict, Tuple, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class ObservabilityServiceNowWrapper:
    """
    A working wrapper for ObservabilityServiceNow that uses httpx instead of requests.
    This bypasses the urllib3 2.x compatibility issues.
    """
    
    def __init__(self, username=None, password=None, client_id=None, client_secret=None, servicenow_api_url=None):
        """Initialize the wrapper with ServiceNow credentials"""
        
        # Load environment variables
        load_dotenv()
        
        # Use provided parameters or fall back to environment variables
        self.username = username or os.getenv('SERVICENOW_USERNAME')
        self.password = password or os.getenv('SERVICENOW_PASSWORD')
        self.client_id = client_id or os.getenv('JWT_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('JWT_CLIENT_SECRET')
        self.url = servicenow_api_url or os.getenv('SERVICENOW_INSTANCE_URL')
        
        # Validate required parameters
        if not all([self.username, self.password, self.url]):
            raise ValueError(
                "Missing required parameters. Please provide username, password, and servicenow_api_url "
                "or set SERVICENOW_USERNAME, SERVICENOW_PASSWORD, and SERVICENOW_INSTANCE_URL environment variables."
            )
        
        # Create httpx client
        self.client = httpx.Client(
            base_url=self.url,
            auth=(self.username, self.password),
            timeout=30.0
        )
        
        # Set up headers
        self.headers_api = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        logger.info(f"ObservabilityServiceNowWrapper initialized for {self.url}")
    
    def get_table(self, table: str, rows: int = 1) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
        """
        Get data from a ServiceNow table.
        
        Args:
            table: The table name (e.g., 'incident', 'change_request')
            rows: Number of rows to retrieve
            
        Returns:
            Tuple of (data, headers, status_code)
        """
        try:
            url = f"/api/now/table/{table}"
            params = {"sysparm_limit": rows}
            
            response = self.client.get(url, headers=self.headers_api, params=params)
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
    
    def create_incident(self, incident_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Create a new incident in ServiceNow.
        
        Args:
            incident_data: Dictionary containing incident data
            
        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            url = "/api/now/table/incident"
            
            response = self.client.post(
                url, 
                headers=self.headers_api, 
                json=incident_data
            )
            response.raise_for_status()
            
            return response.json(), response.status_code
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating incident: {e.response.status_code} - {e.response.text}")
            return {"error": e.response.text}, e.response.status_code
        except httpx.RequestError as e:
            logger.error(f"Request error creating incident: {e}")
            return {"error": str(e)}, 500
        except Exception as e:
            logger.error(f"Unexpected error creating incident: {e}")
            return {"error": str(e)}, 500
    
    def create_change_request(self, change_data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        """
        Create a new change request in ServiceNow.
        
        Args:
            change_data: Dictionary containing change request data
            
        Returns:
            Tuple of (response_data, status_code)
        """
        try:
            url = "/api/now/table/change_request"
            
            response = self.client.post(
                url, 
                headers=self.headers_api, 
                json=change_data
            )
            response.raise_for_status()
            
            return response.json(), response.status_code
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating change request: {e.response.status_code} - {e.response.text}")
            return {"error": e.response.text}, e.response.status_code
        except httpx.RequestError as e:
            logger.error(f"Request error creating change request: {e}")
            return {"error": str(e)}, 500
        except Exception as e:
            logger.error(f"Unexpected error creating change request: {e}")
            return {"error": str(e)}, 500
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the ServiceNow connection.
        
        Returns:
            Dictionary containing connection test results
        """
        try:
            # Test connection with a simple query to incidents table
            response_data, headers, status_code = self.get_table(
                table="incident",
                rows=1
            )
            
            if status_code == 200:
                return {
                    "success": True,
                    "message": "ServiceNow connection is working with httpx wrapper",
                    "connection_details": {
                        "instance_url": self.url,
                        "username": self.username,
                        "method": "httpx"
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
    
    def close(self):
        """Close the httpx client"""
        if hasattr(self, 'client'):
            self.client.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

def create_observability_snow_wrapper():
    """
    Create an ObservabilityServiceNowWrapper instance.
    
    Returns:
        ObservabilityServiceNowWrapper instance or None if creation fails
    """
    try:
        return ObservabilityServiceNowWrapper()
    except Exception as e:
        logger.error(f"Failed to create ObservabilityServiceNowWrapper: {e}")
        return None

def test_wrapper():
    """Test the wrapper"""
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    print("🧪 Testing ObservabilityServiceNowWrapper...")
    
    try:
        wrapper = create_observability_snow_wrapper()
        
        if wrapper is None:
            print("❌ Failed to create wrapper")
            return False
        
        print("✅ Wrapper created successfully")
        
        # Test connection
        result = wrapper.test_connection()
        
        if result.get("success"):
            print("🎉 Connection test successful!")
            print(f"Message: {result.get('message')}")
            return True
        else:
            print(f"❌ Connection test failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        if 'wrapper' in locals():
            wrapper.close()

if __name__ == "__main__":
    test_wrapper()
