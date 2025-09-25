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

# Apply comprehensive urllib3 monkey patch before importing ServiceNow API tools
try:
    import urllib3_monkey_patch_comprehensive
    logging.info("Applied comprehensive urllib3 monkey patch for all ServiceNow API modules")
except ImportError as e:
    logging.warning(f"Could not apply comprehensive urllib3 monkey patch: {e}")

# Import ServiceNow API tools
try:
    from gd_servicenow_api.observability_snow_jwt import ObservabilityServiceNow as ObservabilityServiceNowJWT
    logging.info("Successfully imported ObservabilityServiceNowJWT from observability_snow_jwt")
except ImportError as e:
    logging.warning(f"Failed to import JWT version, falling back to regular version: {e}")
    try:
        from gd_servicenow_api.observability_snow import ObservabilityServiceNow as ObservabilityServiceNowJWT
        logging.info("Successfully imported ObservabilityServiceNow as fallback")
    except ImportError as e2:
        logging.error(f"Failed to import any ServiceNow API tools: {e2}")
        raise

# Note: Using only ObservabilityServiceNowJWT, no httpx fallback

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
    """Get or create ServiceNow connection using patched ObservabilityServiceNow"""
    global snow_connection
    if snow_connection is None:
        # Load credentials from environment variables
        instance_url = os.getenv('SERVICENOW_INSTANCE_URL')
        username = os.getenv('SERVICENOW_USERNAME')
        password = os.getenv('SERVICENOW_PASSWORD')
        client_id = os.getenv('JWT_CLIENT_ID')
        client_secret = os.getenv('JWT_CLIENT_SECRET')
        
        if not all([instance_url, username, password]):
            raise ValueError(
                "Missing ServiceNow credentials. Please set SERVICENOW_INSTANCE_URL, "
                "SERVICENOW_USERNAME, and SERVICENOW_PASSWORD environment variables."
            )
        
        # Try the working wrapper first (most reliable)
        # if ObservabilityServiceNowWrapper:
        #     try:
        #         snow_connection = ObservabilityServiceNow(
        #             username=username,
        #             password=password,
        #             client_id=client_id,
        #             client_secret=client_secret,
        #             servicenow_api_url=instance_url
        #         )
        #         logger.info("Successfully created ServiceNow connection with working wrapper")
        #     except Exception as e:
        #         logger.warning(f"Working wrapper failed: {e}")
        #         snow_connection = None
        
        # Use ObservabilityServiceNowJWT (no httpx fallback)
        if snow_connection is None:
            try:
                snow_connection = ObservabilityServiceNowJWT(
                    username=username,
                    password=password,
                    client_id=client_id,
                    client_secret=client_secret,
                    servicenow_api_url=instance_url
                )
                logger.info("Successfully created ServiceNow connection with ObservabilityServiceNowJWT")
            except Exception as e:
                logger.error(f"ObservabilityServiceNowJWT failed: {e}")
                raise ValueError(f"Failed to create ServiceNow connection: {e}")
    
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
    Search ServiceNow knowledge base articles using list_articles method.
    
    Args:
        search_term: Search term for knowledge articles
        category: Knowledge category
        limit: Maximum number of articles to return
        
    Returns:
        Dictionary containing knowledge articles and metadata
    """
    try:
        connection = get_snow_connection()
        
        # Create a simple params object for the list_articles API call
        class SimpleParams:
            def __init__(self, **kwargs):
                # Set default values for all expected attributes
                self.limit = kwargs.get('limit', 10)
                self.offset = kwargs.get('offset', 0)
                self.query = kwargs.get('query', '')
                self.category = kwargs.get('category', '')
                self.knowledge_base = kwargs.get('knowledge_base', '')
                self.workflow_state = kwargs.get('workflow_state', '')
                self.state = kwargs.get('state', '')
                # Set any additional attributes
                for key, value in kwargs.items():
                    if not hasattr(self, key):
                        setattr(self, key, value)
        
        params_dict = {
            "limit": limit,
            "offset": 0,
            "query": search_term,
            "category": category
        }
                    
        params_obj = SimpleParams(**params_dict)
        logger.info(f"Calling list_articles with params: {params_dict}")
        articles_response = connection.list_articles(params_obj)
        logger.info(f"list_articles returned: {articles_response}")
        
        if not articles_response.get("success", False):
            raise Exception(articles_response.get("message", "Failed to search knowledge base"))
            
        # Handle different response formats from list_articles
        logger.info(f"Full articles_response: {articles_response}")
        
        if "articles" in articles_response:
            articles = articles_response.get("articles", [])
            logger.info(f"Found {len(articles)} articles in 'articles' field")
        elif "result" in articles_response:
            articles = articles_response.get("result", [])
            logger.info(f"Found {len(articles)} articles in 'result' field")
        else:
            articles = []
            logger.warning("No articles found in response - checking response keys")
            logger.info(f"Response keys: {list(articles_response.keys())}")
            
            # Check if the response itself is a list of articles
            if isinstance(articles_response, list):
                articles = articles_response
                logger.info(f"Response is a list with {len(articles)} articles")
            else:
                # Check if there are any other keys that might contain articles
                for key, value in articles_response.items():
                    if isinstance(value, list) and len(value) > 0:
                        logger.info(f"Found potential articles in key '{key}' with {len(value)} items")
                        if isinstance(value[0], dict):
                            articles = value
                            logger.info(f"Using articles from key '{key}'")
                            break
        
        # Sanitize HTML content in articles to prevent JSON parsing issues
        sanitized_articles = []
        logger.info(f"Processing {len(articles)} articles for HTML sanitization")
        
        for i, article in enumerate(articles):
            if isinstance(article, dict):
                sanitized_article = article.copy()
                
                # Sanitize HTML content in text field
                if 'text' in sanitized_article and isinstance(sanitized_article['text'], dict):
                    text_content = sanitized_article['text'].get('value', '')
                    if text_content:
                        logger.info(f"Article {i+1}: Found text content with {len(text_content)} characters")
                        
                        # Remove HTML tags and clean up the content
                        import re
                        import html
                        
                        # First, decode HTML entities
                        clean_text = html.unescape(text_content)
                        
                        # Remove HTML tags
                        clean_text = re.sub(r'<[^>]+>', '', clean_text)
                        
                        # Remove extra whitespace and newlines
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        
                        # Remove any remaining control characters that could break JSON
                        clean_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_text)
                        
                        # Limit length to prevent huge responses
                        if len(clean_text) > 1000:
                            clean_text = clean_text[:1000] + "..."
                        
                        sanitized_article['text']['value'] = clean_text
                        sanitized_article['text']['display_value'] = clean_text
                        
                        logger.info(f"Article {i+1}: Sanitized text content to {len(clean_text)} characters")
                    else:
                        logger.info(f"Article {i+1}: Text field is empty")
                
                # Also sanitize other text fields that might contain HTML
                for field_name in ['short_description', 'meta_description', 'description']:
                    if field_name in sanitized_article and isinstance(sanitized_article[field_name], dict):
                        field_content = sanitized_article[field_name].get('value', '')
                        if field_content:
                            import re
                            import html
                            
                            # Clean the field content
                            clean_field = html.unescape(field_content)
                            clean_field = re.sub(r'<[^>]+>', '', clean_field)
                            clean_field = re.sub(r'\s+', ' ', clean_field).strip()
                            clean_field = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_field)
                            
                            if len(clean_field) > 500:
                                clean_field = clean_field[:500] + "..."
                            
                            sanitized_article[field_name]['value'] = clean_field
                            sanitized_article[field_name]['display_value'] = clean_field
                            
                            logger.info(f"Article {i+1}: Sanitized {field_name} field")
                
                sanitized_articles.append(sanitized_article)
            else:
                sanitized_articles.append(article)
        
        logger.info(f"Sanitized {len(sanitized_articles)} articles")
        
        result = {
            "success": True,
            "count": len(sanitized_articles),
            "articles": sanitized_articles,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Final result: {len(sanitized_articles)} articles returned to client")
        logger.info(f"Retrieved {len(articles)} knowledge articles from ServiceNow using list_articles")
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
        
        # Use get_article method directly with article ID as string parameter
        articles_response = connection.get_article(article_id)
        
        if not articles_response.get("success", False):
            raise Exception(articles_response.get("message", "Failed to retrieve knowledge article"))
            
        # The get_article method returns the article data in the "article" key
        article_data = articles_response.get("article", {})
        
        if not article_data:
            raise Exception(f"Knowledge article {article_id} not found")
        
        result = {
            "success": True,
            "article": article_data,
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
    # Use stdio for Claude Desktop compatibility
    import asyncio
    asyncio.run(mcp.run_stdio_async())
