# ServiceNow MCP Server Setup Instructions

## Fixed Issues ✅

Your Claude connection issue has been resolved! Here's what was fixed:

### ⚡ **LATEST FIX**: TaskGroup Error (Line 314)
- ✅ **FIXED**: Replaced FastMCP with standard MCP server implementation
- ✅ **FIXED**: Eliminated async TaskGroup compatibility issues
- ✅ **RESULT**: Server now runs without unhandled TaskGroup errors

### 1. **Missing Server Code** 
- ✅ Created complete MCP server (`server.py`) with proper ServiceNow integration
- ✅ Fixed all syntax errors and function calls
- ✅ Added proper error handling and logging

### 2. **Import and Function Call Errors**
- ✅ Fixed incorrect ServiceNow API imports 
- ✅ Corrected function signatures and parameters
- ✅ Resolved recursive function call in `test_connection()`
- ✅ Fixed missing `await` on `server.run()`

### 3. **Environment Variable Issues**
- ✅ Updated to correct `SERVICENOW_*` variable names
- ✅ Fixed configuration files to match

## Quick Setup Steps

### 1. Set Your ServiceNow Credentials

Create a `.env` file:
```bash
cd /Users/vayyagari/PycharmProjects/snow_mcp_server_gd
cat > .env << 'EOF'
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your_username_here
SERVICENOW_PASSWORD=your_password_here
LOG_LEVEL=INFO
EOF
```

### 2. Install Missing Dependency
```bash
source .venv/bin/activate
pip install python-dotenv
```

### 3. Configure Claude Desktop

Update `~/Library/Application Support/Claude/claude_desktop_config.json`:
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

### 4. Test the Server
```bash
cd /Users/vayyagari/PycharmProjects/snow_mcp_server_gd
source .venv/bin/activate
# Set test credentials to verify server starts
export SERVICENOW_INSTANCE_URL="https://test.service-now.com"
export SERVICENOW_USERNAME="test"
export SERVICENOW_PASSWORD="test"
python server.py
```

### 5. Restart Claude Desktop
After updating the configuration, restart Claude Desktop completely.

## Available Tools After Connection

1. **`get_servicenow_incidents`** - Query incidents by state, priority, assignment group
2. **`search_knowledge_base`** - Search knowledge articles 
3. **`get_knowledge_article`** - Get specific KB article by ID
4. **`test_connection`** - Test ServiceNow connectivity

## Troubleshooting

If you still get errors:

1. **Check Claude Desktop logs** (usually in Console app on macOS)
2. **Verify Python path** - make sure it points to your virtual environment
3. **Test server manually** with your real ServiceNow credentials
4. **Ensure ServiceNow instance is accessible** and credentials are correct

The server should now connect successfully to Claude! 🎉
