#!/usr/bin/env python3
"""
ServiceNow MCP Server using FastMCP

A Model Context Protocol (MCP) server that provides tools for interacting with ServiceNow.
This server enables Claude to query incidents, knowledge base articles, and other ServiceNow data.
"""

import os
import logging
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, continue with system env vars
    pass

from mcp.server.fastmcp import FastMCP

# Import ServiceNow API tools
try:
    from gd_servicenow_api.observability_snow import ObservabilityServiceNow
except ImportError as e:
    logging.error(f"Failed to import ServiceNow API tools: {e}")
    raise

# Import our custom httpx-based client as fallback
try:
    from servicenow_client_httpx import create_servicenow_client_httpx
except ImportError as e:
    logging.warning(f"Failed to import httpx-based ServiceNow client: {e}")
    create_servicenow_client_httpx = None

# Import our working wrapper
try:
    from observability_snow_wrapper import ObservabilityServiceNowWrapper
except ImportError as e:
    logging.warning(f"Failed to import ObservabilityServiceNowWrapper: {e}")
    ObservabilityServiceNowWrapper = None

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ServiceNow connection instance
snow_connection = None


def get_snow_connection():
    """Get or create ServiceNow connection"""
    global snow_connection
    # if snow_connection is None:
    #     # Load credentials from environment variables
    #     instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
    #     username = os.getenv('SERVICENOW_USERNAME')
    #     password = os.getenv('SERVICENOW_PASSWORD')
    #
    #     if not all([instance_url, username, password]):
    #         raise ValueError(
    #             "Missing ServiceNow credentials. Please set SERVICENOW_INSTANCE_URL, "
    #             "SERVICENOW_USERNAME, and SERVICENOW_PASSWORD environment variables."
    #         )
    #
    #     # Try the original client first, fallback to httpx client if it fails
    #     try:
    #         # Create ServiceNow connection using ObservabilityServiceNow class
    #         snow_connection = ObservabilityServiceNow(
    #             username=username,
    #             password=password,
    #             client_id=os.getenv('JWT_CLIENT_ID', 'default_client_id'),
    #             client_secret=os.getenv('JWT_CLIENT_SECRET', 'default_secret'),
    #             servicenow_api_url=instance_url
    #         )
    #         logger.info("Successfully created ServiceNow connection with original client")
    #     except Exception as e:
    #         logger.warning(f"Original ServiceNow client failed: {e}")
    #         logger.info("Falling back to httpx-based client")
    #
    #         # Use our custom httpx-based client as fallback
    #         if create_servicenow_client_httpx:
    #             snow_connection = create_servicenow_client_httpx()
    #             if snow_connection:
    #                 logger.info("Successfully created ServiceNow connection with httpx client")
    #             else:
    #                 raise ValueError("Failed to create httpx-based ServiceNow client")
    #         else:
    #             raise ValueError("httpx-based client not available and original client failed")
    #
    return snow_connection

# Initialize FastMCP server
mcp = FastMCP("ServiceNow MCP Server")

@mcp.tool()
def get_servicenow_incidents(
    state: Optional[str] = None,
    priority: Optional[str] = None,
    assignment_group: Optional[str] = None,
    caller_id: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Retrieve ServiceNow incidents based on search criteria.
    
    Args:
        state: Incident state (e.g., 'New', 'In Progress', 'Resolved')
        priority: Incident priority (1-5)
        assignment_group: Assignment group name
        caller_id: Caller ID or email
        limit: Maximum number of incidents to return
        
    Returns:
        Dictionary containing incident data and metadata
    """
    try:
        connection = get_snow_connection()
        
        # Build query parameters for incident table
        query_parts = []
        if state:
            query_parts.append(f"state={state}")
        if priority:
            query_parts.append(f"priority={priority}")
        if assignment_group:
            query_parts.append(f"assignment_group.name={assignment_group}")
        if caller_id:
            query_parts.append(f"caller_id.email={caller_id}")
        
        extra_params = "&".join(query_parts) if query_parts else None
        
        # Get incidents from ServiceNow
        incidents_response, status_code = connection.get_table_with_offset(
            table="incident",
            rows=limit,
            extra_params=extra_params
        )
        
        if status_code != 200:
            raise Exception(f"Failed to retrieve incidents: HTTP {status_code}")
            
        incidents = incidents_response.get("result", [])
        
        result = {
            "success": True,
            "count": len(incidents),
            "incidents": incidents,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Retrieved {len(incidents)} incidents from ServiceNow")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving incidents: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def search_knowledge_base(
    search_term: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search ServiceNow knowledge base articles.
    
    Args:
        search_term: Search term for knowledge articles
        category: Knowledge category
        limit: Maximum number of articles to return
        
    Returns:
        Dictionary containing knowledge articles and metadata
    """
    try:
        connection = get_snow_connection()
        
        # Create a simple params object for the API call
        class SimpleParams:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        params_dict = {
            "limit": limit,
            "offset": 0,
            "query": search_term,
            "category": category
        }
                    
        params_obj = SimpleParams(**params_dict)
        articles_response = connection.list_articles(params_obj)
        
        if not articles_response.get("success", False):
            raise Exception(articles_response.get("message", "Failed to search knowledge base"))
            
        articles = articles_response.get("articles", [])
        
        result = {
            "success": True,
            "count": len(articles),
            "articles": articles,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Retrieved {len(articles)} knowledge articles from ServiceNow")
        return result
        
    except Exception as e:
        logger.error(f"Error searching knowledge base: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def get_knowledge_article(article_id: str) -> Dict[str, Any]:
    """
    Get a specific ServiceNow knowledge base article by ID.
    
    Args:
        article_id: Knowledge base article ID or number
        
    Returns:
        Dictionary containing the knowledge article data
    """
    try:
        connection = get_snow_connection()
        
        # Get specific knowledge article
        article_response = connection.get_article(article_id)
        
        if not article_response.get("success", False):
            raise Exception(article_response.get("message", "Failed to retrieve knowledge article"))
            
        article = article_response.get("article", {})
        
        result = {
            "success": True,
            "article": article,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Retrieved knowledge article {article_id} from ServiceNow")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving knowledge article: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def test_connection() -> Dict[str, Any]:
    """
    Test the ServiceNow connection.
    
    Returns:
        Dictionary with connection status
    """
    try:
        connection = get_snow_connection()
        
        # Check if it's our wrapper, httpx client, or the original client
        if hasattr(connection, 'test_connection'):
            # It's our wrapper or httpx client
            result = connection.test_connection()
            result["timestamp"] = datetime.now().isoformat()
            return result
        else:
            # It's the original client - use the old method
            test_response, headers, status_code = connection.get_table(
                table="incident",
                rows=1
            )
            
            if status_code != 200:
                raise Exception(f"Connection test failed: HTTP {status_code}")
                
            result = {
                "success": True,
                "message": "ServiceNow connection is working",
                "connection_details": {
                    "instance_url": os.getenv('SERVICENOW_INSTANCE_URL'),
                    "username": os.getenv('SERVICENOW_USERNAME'),
                },
                "timestamp": datetime.now().isoformat()
            }
        
        logger.info("ServiceNow connection test successful")
        return result
        
    except Exception as e:
        logger.error(f"ServiceNow connection test failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    # Run the server
    logger.info("Starting ServiceNow MCP Server with FastMCP...")
    # # Use stdio for Claude Desktop compatibility
    import asyncio
    asyncio.run(mcp.run_stdio_async())
    # get_knowledge_article('f9b928573b3c2a94117fa51916e45a5d')
