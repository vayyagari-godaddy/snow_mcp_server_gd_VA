# ServiceNow MCP Server

A Model Context Protocol (MCP) server that enables Claude to interact with ServiceNow instances. This server provides tools for querying incidents, searching knowledge base articles, and retrieving specific ServiceNow data.

## Features

- 🎫 **Incident Management**: Query and retrieve ServiceNow incidents with various filters
- 📚 **Knowledge Base**: Search and retrieve knowledge base articles  
- 🔍 **Specific Article Lookup**: Get detailed information for specific KB articles
- 🔧 **Connection Testing**: Verify ServiceNow connectivity
- 📊 **Comprehensive Logging**: Detailed logging for troubleshooting

## Prerequisites

- Python 3.8 or higher
- ServiceNow instance with API access
- Claude Desktop application

## Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd /Users/vayyagari/PycharmProjects/snow_mcp_server_gd
   ```

2. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### 1. ServiceNow Credentials

Create a `.env` file in the project root with your ServiceNow credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit with your actual credentials
nano .env
```

Add your ServiceNow credentials to the `.env` file:
```env
SNOW_INSTANCE_URL=https://your-instance.service-now.com
SNOW_USERNAME=your_username_here
SNOW_PASSWORD=your_password_here
LOG_LEVEL=INFO
```

### 2. Claude Desktop Configuration

#### Option 1: Environment Variables in Claude Config
Update your Claude Desktop configuration file with the server details and credentials:

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)

```json
{
  "mcpServers": {
    "servicenow": {
      "command": "python",
      "args": ["/Users/vayyagari/PycharmProjects/snow_mcp_server_gd/server.py"],
      "env": {
        "SNOW_INSTANCE_URL": "https://your-instance.service-now.com",
        "SNOW_USERNAME": "your_username_here", 
        "SNOW_PASSWORD": "your_password_here"
      }
    }
  }
}
```

#### Option 2: Using .env file (Recommended)
Install `python-dotenv` and modify the server to load from `.env`:

```json
{
  "mcpServers": {
    "servicenow": {
      "command": "/Users/vayyagari/PycharmProjects/snow_mcp_server_gd/.venv/bin/python",
      "args": ["/Users/vayyagari/PycharmProjects/snow_mcp_server_gd/server.py"],
      "cwd": "/Users/vayyagari/PycharmProjects/snow_mcp_server_gd"
    }
  }
}
```

## Usage

### Starting the Server

The server will start automatically when Claude Desktop connects to it. You can also test it manually:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the server
python server.py
```

### Available Tools

#### 1. Get ServiceNow Incidents
```python
# Example usage in Claude:
get_servicenow_incidents({
  "state": "New", 
  "priority": "1",
  "limit": 10
})
```

#### 2. Search Knowledge Base
```python
# Example usage in Claude:
search_knowledge_base({
  "search_term": "password reset",
  "limit": 5
})
```

#### 3. Get Specific Knowledge Article
```python
# Example usage in Claude:
get_knowledge_article({
  "article_id": "KB0010001"
})
```

#### 4. Test Connection
```python
# Example usage in Claude:
test_connection()
```

## Troubleshooting

### Common Issues

1. **"Claude is not connecting"**
   - Verify Claude Desktop configuration file path and syntax
   - Check that Python path in config matches your virtual environment
   - Ensure all credentials are correctly set

2. **ServiceNow Authentication Errors**
   - Verify your ServiceNow credentials in `.env` file
   - Check that your ServiceNow user has API access permissions
   - Confirm the instance URL format (should include https://)

3. **Module Import Errors**
   - Ensure virtual environment is activated
   - Install all requirements: `pip install -r requirements.txt`
   - Check that `gd-servicenow-api` is properly installed

4. **Permission Denied Errors**
   - Ensure the server.py file is executable
   - Check file permissions: `chmod +x server.py`

### Debug Mode

Enable debug logging by setting in your `.env` file:
```env
LOG_LEVEL=DEBUG
```

### Testing the Server

Test the server connection manually:
```bash
# Activate environment
source .venv/bin/activate

# Test the server
python -c "import asyncio; from server import test_connection; print(asyncio.run(test_connection()))"
```

## Development

### Project Structure
```
snow_mcp_server_gd/
├── .venv/                 # Virtual environment
├── server.py             # Main MCP server
├── requirements.txt      # Python dependencies
├── claude_desktop_config.json  # Claude configuration example
├── .env.example         # Environment variables template
└── README.md           # This file
```

### Adding New Tools

To add new ServiceNow tools:

1. Define a new Pydantic model for request validation
2. Create a new `@server.tool()` decorated function
3. Import and use appropriate ServiceNow API functions
4. Handle errors and return structured responses

## Security Notes

- Never commit `.env` files with real credentials to version control
- Use environment variables or secure credential management
- Ensure ServiceNow user has minimal required permissions
- Consider using OAuth or certificate-based authentication for production

## Support

- Check ServiceNow API documentation for field names and query options
- Review MCP protocol documentation at https://modelcontextprotocol.io/
- Enable debug logging for detailed error information

## License

This project is licensed under the MIT License.
