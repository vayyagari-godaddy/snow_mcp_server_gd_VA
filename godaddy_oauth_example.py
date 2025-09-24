import requests
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import secrets

# OAuth Configuration
token_url = "https://api.dev-godaddy.com/v2/oauth2/token"
client_id = "6a4e6d3a-4129-408c-ae58-d8afdc977ae0"
client_secret = "m5vEBhHEBFXkPDlJCkssj9caP64eY4LR"
redirect_uri = "http://localhost:8080"  # Note: http, not https for localhost

# Global variables to store the result
code = None
state = secrets.token_urlsafe(16)  # Generate random state for security


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global code
        self.close_connection = True
        
        # Send response to browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Authorization received! You can close this window.</h1></body></html>')
        
        # Parse the callback URL
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        
        # Validate state parameter
        if 'state' not in query or query['state'][0] != state:
            print("ERROR: State parameter missing or invalid")
            return
            
        # Extract authorization code
        if 'code' in query:
            code = query['code'][0]
            print(f"✅ Received Auth Code: {code}")
        else:
            print("ERROR: No authorization code received")
    
    def log_message(self, format, *args):
        # Suppress HTTP server logs
        pass


def get_authorization_code():
    """Get authorization code from GoDaddy OAuth"""
    global code
    
    # Build authorization URL with state parameter
    auth_params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'openid',
        'response_type': 'code',
        'state': state
    }
    auth_url = f"https://api.dev-godaddy.com/v2/oauth2/authorize?{urllib.parse.urlencode(auth_params)}"
    
    print(f"🔗 Opening authorization URL: {auth_url}")
    print("👤 Please log in and authorize the application...")
    
    # Open browser and start local server
    webbrowser.open(auth_url)
    
    server = HTTPServer(('localhost', 8080), RequestHandler)
    print(f"🖥️  Local server listening on http://localhost:8080")
    
    # Wait for the callback
    server.handle_request()
    server.server_close()
    
    return code


def exchange_code_for_token(auth_code):
    """Exchange authorization code for access token"""
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "redirect_uri": redirect_uri,
    }
    
    print("🔄 Exchanging code for access token...")
    token_response = requests.post(token_url, data=token_payload)
    
    if token_response.status_code == 200:
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        print(f"✅ Access Token received: {access_token[:20]}...")
        return token_data
    else:
        print(f"❌ Error getting access token: {token_response.text}")
        return None


if __name__ == "__main__":
    print("🚀 Starting GoDaddy OAuth Flow...")
    
    # Step 1: Get authorization code
    auth_code = get_authorization_code()
    
    if auth_code:
        # Step 2: Exchange code for token
        token_data = exchange_code_for_token(auth_code)
        
        if token_data:
            print("🎉 OAuth flow completed successfully!")
            print(f"Access Token: {token_data.get('access_token')}")
            print(f"Token Type: {token_data.get('token_type')}")
            print(f"Expires In: {token_data.get('expires_in')} seconds")
        else:
            print("❌ Failed to get access token")
    else:
        print("❌ Failed to get authorization code")