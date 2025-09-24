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
import json

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

# Import JWT authentication module
from jwt_auth import jwt_auth, create_initial_tokens

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ServiceNow connection instance
snow_connection = None

def get_snow_connection():
    """Get or create ServiceNow connection using JWT authentication"""
    global snow_connection
    if snow_connection is None:
        # Load configuration from environment variables
        instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        
        # Check for JWT token first, fallback to username/password for initial setup
        # access_token = os.getenv('SERVICENOW_JWT_TOKEN')
        #
        if access_token:
            # Use JWT token authentication
            try:
                # Validate token and extract user info
                token_payload = jwt_auth.validate_token(access_token)
                username = token_payload.get('sub')
                
                logger.info(f"Using JWT authentication for user: {username}")
                
                # Create ServiceNow connection with JWT token
                # Note: This assumes the ObservabilityServiceNow class supports JWT tokens
                # You may need to modify the API class or use token-based authentication
                snow_connection = ObservabilityServiceNow(
                    username=username,
                    password=None,  # Not needed with JWT
                    client_id=os.getenv('JWT_CLIENT_ID'),
                    client_secret=os.getenv('JWT_CLIENT_SECRET'),
                    servicenow_api_url=instance_url,
                    # Pass JWT token if supported
                )
                
            except Exception as e:
                logger.error(f"JWT token validation failed: {e}")
                logger.info("Falling back to username/password authentication")
                access_token = None
        
        if not access_token:
            # Fallback to username/password authentication
            username = os.getenv('SERVICENOW_USERNAME')  
            password = os.getenv('SERVICENOW_PASSWORD')
            
            if not all([instance_url, username, password]):
                raise ValueError(
                    "Missing ServiceNow credentials. Please set either SERVICENOW_JWT_TOKEN or "
                    "SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, and SERVICENOW_PASSWORD environment variables."
                )
            
            logger.info(f"Using username/password authentication for user: {username}")
            
            # Create ServiceNow connection using traditional auth
            snow_connection = ObservabilityServiceNow(
                username=username,
                password=password,
                client_id='e78a061f7cd346388b10be87a08a5a86',
                client_secret='7nsw$|SMZx',
                servicenow_api_url=instance_url
            )
    
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
def generate_jwt_token(
    username: str,
    password: str,
    instance_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate JWT tokens for ServiceNow authentication.
    
    This tool creates access and refresh tokens that can be used instead of username/password.
    Store the tokens securely and use them in environment variables for subsequent connections.
    
    Args:
        username: ServiceNow username
        password: ServiceNow password (used only for initial token generation)
        instance_url: ServiceNow instance URL (optional, will use env var if not provided)
        
    Returns:
        Dictionary containing JWT tokens and metadata
    """
    try:
        # Use provided instance URL or fall back to environment variable
        snow_instance = instance_url or os.getenv('SERVICENOW_INSTANCE_URL')
        
        if not snow_instance:
            raise ValueError("ServiceNow instance URL is required")
        
        # Create initial tokens
        tokens = create_initial_tokens(
            username=username,
            password=password,  # In production, validate this against ServiceNow first
            instance_url=snow_instance,
            client_id='e78a061f7cd346388b10be87a08a5a86'
        )
        
        result = {
            "success": True,
            "message": "JWT tokens generated successfully",
            "tokens": tokens,
            "usage_instructions": {
                "access_token": "Set as SERVICENOW_JWT_TOKEN environment variable",
                "refresh_token": "Store securely for token renewal",
                "expires_in_hours": jwt_auth.token_expiry_hours,
                "refresh_expires_in_days": jwt_auth.refresh_token_expiry_days
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Generated JWT tokens for user: {username}")
        return result
        
    except Exception as e:
        logger.error(f"Error generating JWT token: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validate a JWT token and return its information.
    
    Args:
        token: JWT token string to validate
        
    Returns:
        Dictionary containing token validation results and information
    """
    try:
        # Validate token
        payload = jwt_auth.validate_token(token)
        
        # Get detailed token information
        token_info = jwt_auth.get_token_info(token)
        
        result = {
            "success": True,
            "message": "JWT token is valid",
            "token_info": token_info,
            "payload": {
                "username": payload.get('sub'),
                "instance_url": payload.get('snow_instance'),
                "token_type": payload.get('type'),
                "issuer": payload.get('iss'),
                "audience": payload.get('aud')
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Validated JWT token for user: {payload.get('sub')}")
        return result
        
    except Exception as e:
        logger.error(f"Error validating JWT token: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def refresh_jwt_token(refresh_token: str) -> Dict[str, Any]:
    """
    Refresh JWT tokens using a valid refresh token.
    
    Args:
        refresh_token: Valid refresh token string
        
    Returns:
        Dictionary containing new access and refresh tokens
    """
    try:
        # Refresh tokens
        new_tokens = jwt_auth.refresh_token(refresh_token)
        
        result = {
            "success": True,
            "message": "JWT tokens refreshed successfully",
            "tokens": new_tokens,
            "usage_instructions": {
                "access_token": "Update SERVICENOW_JWT_TOKEN environment variable",
                "refresh_token": "Store the new refresh token securely",
                "expires_in_hours": jwt_auth.token_expiry_hours
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("JWT tokens refreshed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error refreshing JWT token: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@mcp.tool()
def get_jwt_token_info(token: str) -> Dict[str, Any]:
    """
    Get information about a JWT token without validation.
    
    This tool provides token details even for expired tokens.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary containing token information
    """
    try:
        token_info = jwt_auth.get_token_info(token)
        
        result = {
            "success": True,
            "token_info": token_info,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Retrieved JWT token info for user: {token_info.get('username')}")
        return result
        
    except Exception as e:
        logger.error(f"Error getting JWT token info: {str(e)}")
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
    mcp.run()

