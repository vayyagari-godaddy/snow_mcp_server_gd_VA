#!/usr/bin/env python3
"""
ServiceNow MCP Server

A Model Context Protocol (MCP) server that provides tools for interacting with ServiceNow.
This server enables Claude to query incidents, knowledge base articles, and other ServiceNow data.
"""

import os
import logging
import asyncio
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, continue with system env vars
    pass

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolRequest,
    CallToolResult,
)
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

# Initialize MCP server
server = Server("servicenow-mcp-server")

@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools"""
    return [
        Tool(
            name="get_servicenow_incidents",
            description="Retrieve ServiceNow incidents based on search criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Incident state (e.g., 'New', 'In Progress', 'Resolved')"},
                    "priority": {"type": "string", "description": "Incident priority (1-5)"},
                    "assignment_group": {"type": "string", "description": "Assignment group name"},
                    "caller_id": {"type": "string", "description": "Caller ID or email"},
                    "limit": {"type": "integer", "description": "Maximum number of incidents to return", "default": 20}
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="search_knowledge_base",
            description="Search ServiceNow knowledge base articles",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "Search term for knowledge articles"},
                    "category": {"type": "string", "description": "Knowledge category"},
                    "limit": {"type": "integer", "description": "Maximum number of articles to return", "default": 10}
                },
                "additionalProperties": False
            }
        ),
        Tool(
            name="get_knowledge_article",
            description="Get a specific ServiceNow knowledge base article by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "article_id": {"type": "string", "description": "Knowledge base article ID or number"}
                },
                "required": ["article_id"],
                "additionalProperties": False
            }
        ),
        Tool(
            name="test_connection",
            description="Test the ServiceNow connection",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls"""
    try:
        if name == "get_servicenow_incidents":
            return await handle_get_incidents(arguments)
        elif name == "search_knowledge_base":
            return await handle_search_knowledge_base(arguments)
        elif name == "get_knowledge_article":
            return await handle_get_knowledge_article(arguments)
        elif name == "test_connection":
            return await handle_test_connection(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")]
            )
    except Exception as e:
        logger.error(f"Tool call error for {name}: {str(e)}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")]
        )

async def handle_get_incidents(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle get_servicenow_incidents tool call"""
    try:
        connection = get_snow_connection()
        
        # Build query parameters for incident table
        query_parts = []
        if arguments.get("state"):
            query_parts.append(f"state={arguments['state']}")
        if arguments.get("priority"):
            query_parts.append(f"priority={arguments['priority']}")
        if arguments.get("assignment_group"):
            query_parts.append(f"assignment_group.name={arguments['assignment_group']}")
        if arguments.get("caller_id"):
            query_parts.append(f"caller_id.email={arguments['caller_id']}")
        
        extra_params = "&".join(query_parts) if query_parts else None
        limit = arguments.get("limit", 20)
        
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
        
        return CallToolResult(
            content=[TextContent(type="text", text=f"Retrieved {len(incidents)} ServiceNow incidents:\n\n{incidents}")]
        )
        
    except Exception as e:
        logger.error(f"Error retrieving incidents: {str(e)}")
        error_result = {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
        
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error retrieving incidents: {str(e)}")]
        )

async def handle_search_knowledge_base(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle search_knowledge_base tool call"""
    try:
        connection = get_snow_connection()
        
        # Create a simple params object for the API call
        class SimpleParams:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)
        
        params_dict = {
            "limit": arguments.get("limit", 10),
            "offset": 0,
            "query": arguments.get("search_term"),
            "category": arguments.get("category")
        }
                    
        params_obj = SimpleParams(**params_dict)
        articles_response = connection.list_articles(params_obj)
        
        if not articles_response.get("success", False):
            raise Exception(articles_response.get("message", "Failed to search knowledge base"))
            
        articles = articles_response.get("articles", [])
        
        logger.info(f"Retrieved {len(articles)} knowledge articles from ServiceNow")
        
        return CallToolResult(
            content=[TextContent(type="text", text=f"Found {len(articles)} knowledge articles:\n\n{articles}")]
        )
        
    except Exception as e:
        logger.error(f"Error searching knowledge base: {str(e)}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error searching knowledge base: {str(e)}")]
        )

async def handle_get_knowledge_article(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle get_knowledge_article tool call"""
    try:
        connection = get_snow_connection()
        article_id = arguments.get("article_id")
        
        if not article_id:
            raise Exception("article_id is required")
        
        # Get specific knowledge article
        article_response = connection.get_article(article_id)
        
        if not article_response.get("success", False):
            raise Exception(article_response.get("message", "Failed to retrieve knowledge article"))
            
        article = article_response.get("article", {})
        
        logger.info(f"Retrieved knowledge article {article_id} from ServiceNow")
        
        return CallToolResult(
            content=[TextContent(type="text", text=f"Knowledge Article {article_id}:\n\n{article}")]
        )
        
    except Exception as e:
        logger.error(f"Error retrieving knowledge article: {str(e)}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error retrieving knowledge article: {str(e)}")]
        )

async def handle_test_connection(arguments: Dict[str, Any]) -> CallToolResult:
    """Handle test_connection tool call"""
    try:
        connection = get_snow_connection()
        
        # Test connection with a simple query to incidents table
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
        
        return CallToolResult(
            content=[TextContent(type="text", text=f"ServiceNow connection test successful!\n\nConnection Details:\n{result['connection_details']}")]
        )
        
    except Exception as e:
        logger.error(f"ServiceNow connection test failed: {str(e)}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"ServiceNow connection test failed: {str(e)}")]
        )

async def main():
    """Main server entry point"""
    logger.info("Starting ServiceNow MCP Server...")
    
    # Test connection on startup (optional)
    try:
        result = await handle_test_connection({})
        if "successful" in str(result).lower():
            logger.info("ServiceNow connection verified")
        else:
            logger.warning("ServiceNow connection test returned unexpected result")
    except Exception as e:
        logger.warning(f"ServiceNow connection test failed on startup: {e}")
        logger.warning("Server will continue, but ServiceNow operations may fail")
    
    # Run the server
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream=read_stream,
                write_stream=write_stream,
                initialization_options={}
            )
    except* Exception as eg:
        # Handle ExceptionGroup from TaskGroup
        for exc in eg.exceptions:
            logger.error(f"Server exception: {exc}")
        raise

if __name__ == "__main__":
    # Run the server
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise
