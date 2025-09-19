#!/usr/bin/env python3
"""
ServiceNow MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with ServiceNow.
This server enables Claude to query incidents, knowledge base articles, and other ServiceNow data.
"""

import os
import logging
from typing import Any, Dict, List, Optional
import asyncio
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, continue with system env vars
    pass

from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, Field

# Import ServiceNow API tools
try:
    from gd_servicenow_api.observability_snow import ObservabilityServiceNow
except ImportError as e:
    logging.error(f"Failed to import ServiceNow API tools: {e}")
    raise

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
server = FastMCP("ServiceNow MCP Server")

# Pydantic models for request validation
class IncidentQuery(BaseModel):
    """Model for incident query parameters"""
    state: Optional[str] = Field(None, description="Incident state (e.g., 'New', 'In Progress', 'Resolved')")
    priority: Optional[str] = Field(None, description="Incident priority (1-5)")
    assignment_group: Optional[str] = Field(None, description="Assignment group name")
    caller_id: Optional[str] = Field(None, description="Caller ID or email")
    limit: Optional[int] = Field(20, description="Maximum number of incidents to return")

class KnowledgeQuery(BaseModel):
    """Model for knowledge base query parameters"""
    search_term: Optional[str] = Field(None, description="Search term for knowledge articles")
    category: Optional[str] = Field(None, description="Knowledge category")
    limit: Optional[int] = Field(10, description="Maximum number of articles to return")

class KBArticleQuery(BaseModel):
    """Model for specific knowledge base article retrieval"""
    article_id: str = Field(..., description="Knowledge base article ID or number")

# ServiceNow connection instance
snow_connection = None

def get_snow_connection():
    """Get or create ServiceNow connection"""
    global snow_connection
    if snow_connection is None:
        # Load credentials from environment variables
        instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        username = os.getenv('SERVICENOW_USERNAME')
        password = os.getenv('SERVICENOW_PASSWORD')
        
        if not all([instance_url, username, password]):
            raise ValueError(
                "Missing ServiceNow credentials. Please set SERVICENOW_INSTANCE_URL, "
                "SERVICENOW_USERNAME, and SERVICENOW_PASSWORD environment variables."
            )
        
        # Create ServiceNow connection using ObservabilityServiceNow class
        # Note: The client_id and client_secret are hardcoded in the original package
        snow_connection = ObservabilityServiceNow(
            username=username,
            password=password,
            client_id='e78a061f7cd346388b10be87a08a5a86',
            client_secret='7nsw$|SMZx',
            servicenow_api_url=instance_url
        )
    
    return snow_connection

@server.tool()
async def get_servicenow_incidents(query: IncidentQuery) -> Dict[str, Any]:
    """
    Retrieve ServiceNow incidents based on search criteria.
    
    Args:
        query: IncidentQuery object with search parameters
        
    Returns:
        Dictionary containing incident data and metadata
    """
    try:
        connection = get_snow_connection()
        
        # Build query parameters
        params = {}
        if query.state:
            params['state'] = query.state
        if query.priority:
            params['priority'] = query.priority
        if query.assignment_group:
            params['assignment_group'] = query.assignment_group
        if query.caller_id:
            params['caller_id'] = query.caller_id
        
        # Get incidents using the ServiceNow client
        # Build query parameters for incident table
        query_parts = []
        if query.state:
            query_parts.append(f"state={query.state}")
        if query.priority:
            query_parts.append(f"priority={query.priority}")
        if query.assignment_group:
            query_parts.append(f"assignment_group.name={query.assignment_group}")
        if query.caller_id:
            query_parts.append(f"caller_id.email={query.caller_id}")
        
        extra_params = "&".join(query_parts) if query_parts else None
        
        # Get incidents from ServiceNow
        incidents_response, status_code = connection.get_table_with_offset(
            table="incident",
            rows=query.limit or 20,
            extra_params=extra_params
        )
        
        if status_code != 200:
            raise Exception(f"Failed to retrieve incidents: HTTP {status_code}")
            
        incidents = incidents_response.get("result", [])
        
        logger.info(f"Retrieved {len(incidents)} incidents from ServiceNow")
        
        return {
            "success": True,
            "count": len(incidents),
            "incidents": incidents,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving incidents: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@server.tool()
async def search_knowledge_base(query: KnowledgeQuery) -> Dict[str, Any]:
    """
    Search ServiceNow knowledge base articles.
    
    Args:
        query: KnowledgeQuery object with search parameters
        
    Returns:
        Dictionary containing knowledge articles and metadata
    """
    try:
        connection = get_snow_connection()
        
        # Build search parameters
        params = {}
        if query.search_term:
            params['search_term'] = query.search_term
        if query.category:
            params['category'] = query.category
            
        # Search knowledge base using ServiceNow client
        # Create a simple params dict for the API call
        params_dict = {
            "limit": query.limit or 10,
            "offset": 0,
            "query": query.search_term,
            "category": query.category
        }
        
        # Convert dict to object for the API call
        class SimpleParams:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
                    
        params_obj = SimpleParams(**params_dict)
        articles_response = connection.list_articles(params_obj)
        
        if not articles_response.get("success", False):
            raise Exception(articles_response.get("message", "Failed to search knowledge base"))
            
        articles = articles_response.get("articles", [])
        
        logger.info(f"Retrieved {len(articles)} knowledge articles from ServiceNow")
        
        return {
            "success": True,
            "count": len(articles),
            "articles": articles,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error searching knowledge base: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@server.tool()
async def get_knowledge_article(query: KBArticleQuery) -> Dict[str, Any]:
    """
    Get a specific ServiceNow knowledge base article by ID.
    
    Args:
        query: KBArticleQuery object with article ID
        
    Returns:
        Dictionary containing the knowledge article data
    """
    try:
        connection = get_snow_connection()
        
        # Get specific knowledge article
        article_response = connection.get_article(query.article_id)
        
        if not article_response.get("success", False):
            raise Exception(article_response.get("message", "Failed to retrieve knowledge article"))
            
        article = article_response.get("article", {})
        
        logger.info(f"Retrieved knowledge article {query.article_id} from ServiceNow")
        
        return {
            "success": True,
            "article": article,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving knowledge article: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@server.tool()
async def test_connection() -> Dict[str, Any]:
    """
    Test the ServiceNow connection.
    
    Returns:
        Dictionary with connection status
    """
    try:
        connection = get_snow_connection()
        
        # Test connection with a simple query to incidents table
        test_response, status_code = connection.get_table(
            table="incident",
            rows=1
        )
        
        if status_code != 200:
            raise Exception(f"Connection test failed: HTTP {status_code}")
        
        logger.info("ServiceNow connection test successful")
        
        return {
            "success": True,
            "message": "ServiceNow connection is working",
            "connection_details": {
                "instance_url": os.getenv('SERVICENOW_INSTANCE_URL'),
                "username": os.getenv('SERVICENOW_USERNAME'),
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"ServiceNow connection test failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def main():
    """Main server entry point"""
    logger.info("Starting ServiceNow MCP Server...")
    
    # Test connection on startup
    try:
        await test_connection()
        logger.info("ServiceNow connection verified")
    except Exception as e:
        logger.warning(f"ServiceNow connection test failed on startup: {e}")
        logger.warning("Server will continue, but ServiceNow operations may fail")
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            init_options={
                "name": "servicenow-server",
                "version": "1.0.0"
            }
        )

if __name__ == "__main__":
    # Run the server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
