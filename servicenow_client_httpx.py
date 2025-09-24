#!/usr/bin/env python3
"""
ServiceNow client using httpx to avoid urllib3 compatibility issues.
"""

import os
import json
import base64
import httpx
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ServiceNowClientHttpx:
    """ServiceNow client using httpx instead of requests."""
    
    def __init__(self, instance_url: str, username: str, password: str):
        self.instance_url = instance_url.rstrip('/')
        self.username = username
        self.password = password
        
    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the ServiceNow connection."""
        try:
            headers = self._get_headers()
            url = f"{self.instance_url}/api/now/table/incident"
            params = {'sysparm_limit': 1}
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "ServiceNow connection is working",
                        "status_code": response.status_code,
                        "instance_url": self.instance_url,
                        "username": self.username
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "error": "Authentication failed - check username/password or instance URL",
                        "status_code": response.status_code,
                        "details": "ServiceNow returned 401 Unauthorized"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            logger.error(f"ServiceNow connection test failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_incidents(self, state: Optional[str] = None, priority: Optional[str] = None, 
                     assignment_group: Optional[str] = None, caller_id: Optional[str] = None, 
                     limit: int = 20) -> Dict[str, Any]:
        """Get ServiceNow incidents."""
        try:
            headers = self._get_headers()
            url = f"{self.instance_url}/api/now/table/incident"
            params = {'sysparm_limit': limit}
            
            # Add filters if provided
            if state:
                params['sysparm_query'] = f"state={state}"
            if priority:
                query = params.get('sysparm_query', '')
                if query:
                    query += f"^priority={priority}"
                else:
                    query = f"priority={priority}"
                params['sysparm_query'] = query
            if assignment_group:
                query = params.get('sysparm_query', '')
                if query:
                    query += f"^assignment_group={assignment_group}"
                else:
                    query = f"assignment_group={assignment_group}"
                params['sysparm_query'] = query
            if caller_id:
                query = params.get('sysparm_query', '')
                if query:
                    query += f"^caller_id={caller_id}"
                else:
                    query = f"caller_id={caller_id}"
                params['sysparm_query'] = query
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": data.get('result', []),
                        "count": len(data.get('result', [])),
                        "total": data.get('result', [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get incidents: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def search_knowledge_base(self, search_term: Optional[str] = None, 
                            category: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Search ServiceNow knowledge base."""
        try:
            headers = self._get_headers()
            url = f"{self.instance_url}/api/now/table/kb_knowledge"
            params = {'sysparm_limit': limit}
            
            # Add search filters
            if search_term:
                params['sysparm_query'] = f"short_descriptionLIKE{search_term}"
            if category:
                query = params.get('sysparm_query', '')
                if query:
                    query += f"^category={category}"
                else:
                    query = f"category={category}"
                params['sysparm_query'] = query
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": data.get('result', []),
                        "count": len(data.get('result', [])),
                        "total": data.get('result', [])
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            logger.error(f"Failed to search knowledge base: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_knowledge_article(self, article_id: str) -> Dict[str, Any]:
        """Get a specific knowledge base article."""
        try:
            headers = self._get_headers()
            url = f"{self.instance_url}/api/now/table/kb_knowledge/{article_id}"
            
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "data": data.get('result', {}),
                        "article": data.get('result', {})
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                        "status_code": response.status_code
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get knowledge article: {e}")
            return {
                "success": False,
                "error": str(e)
            }

def create_servicenow_client_httpx() -> Optional[ServiceNowClientHttpx]:
    """Create a ServiceNow client using httpx and environment variables."""
    try:
        instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        username = os.getenv('SERVICENOW_USERNAME')
        password = os.getenv('SERVICENOW_PASSWORD')
        
        if not all([instance_url, username, password]):
            logger.error("Missing required ServiceNow environment variables")
            return None
            
        return ServiceNowClientHttpx(instance_url, username, password)
        
    except Exception as e:
        logger.error(f"Failed to create ServiceNow client: {e}")
        return None
