#!/usr/bin/env python3
"""
Final urllib3 compatibility patch for ObservabilityServiceNow.
This patch modifies the original class to use httpx instead of requests.
"""

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def apply_urllib3_patch():
    """
    Apply a patch to the original ObservabilityServiceNow class to fix urllib3 compatibility.
    """
    try:
        # Find the observability_snow.py file
        import gd_servicenow_api
        package_path = Path(gd_servicenow_api.__file__).parent
        observability_snow_path = package_path / "observability_snow.py"
        
        if not observability_snow_path.exists():
            logger.error(f"Could not find observability_snow.py at {observability_snow_path}")
            return False
        
        # Read the original file
        with open(observability_snow_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Check if already patched
        if "httpx" in original_content and "urllib3_patch_applied" in original_content:
            logger.info("ObservabilityServiceNow is already patched")
            return True
        
        # Create the patch
        patch_content = '''
# urllib3_patch_applied - httpx compatibility patch
import httpx
import requests
from urllib3.exceptions import InsecureRequestWarning

# Suppress urllib3 warnings
urllib3.disable_warnings(InsecureRequestWarning)

# Patch the requests session to use httpx
class HttpxAdapter:
    """Adapter to make httpx work like requests for ObservabilityServiceNow."""
    
    def __init__(self):
        self.client = httpx.Client()
    
    def post(self, url, headers=None, data=None, **kwargs):
        """Convert requests-style post to httpx."""
        try:
            response = self.client.post(url, headers=headers, data=data, **kwargs)
            # Convert httpx response to requests-like response
            return HttpxResponse(response)
        except Exception as e:
            # Fallback to original requests if httpx fails
            return requests.post(url, headers=headers, data=data, **kwargs)
    
    def get(self, url, headers=None, params=None, **kwargs):
        """Convert requests-style get to httpx."""
        try:
            response = self.client.get(url, headers=headers, params=params, **kwargs)
            return HttpxResponse(response)
        except Exception as e:
            # Fallback to original requests if httpx fails
            return requests.get(url, headers=headers, params=params, **kwargs)
    
    def put(self, url, headers=None, json=None, **kwargs):
        """Convert requests-style put to httpx."""
        try:
            response = self.client.put(url, headers=headers, json=json, **kwargs)
            return HttpxResponse(response)
        except Exception as e:
            # Fallback to original requests if httpx fails
            return requests.put(url, headers=headers, json=json, **kwargs)
    
    def delete(self, url, headers=None, **kwargs):
        """Convert requests-style delete to httpx."""
        try:
            response = self.client.delete(url, headers=headers, **kwargs)
            return HttpxResponse(response)
        except Exception as e:
            # Fallback to original requests if httpx fails
            return requests.delete(url, headers=headers, **kwargs)

class HttpxResponse:
    """Wrapper to make httpx response look like requests response."""
    
    def __init__(self, httpx_response):
        self._response = httpx_response
        self.status_code = httpx_response.status_code
        self.headers = httpx_response.headers
        self.text = httpx_response.text
    
    def json(self):
        """Return JSON data."""
        return self._response.json()
    
    def raise_for_status(self):
        """Raise exception for bad status codes."""
        self._response.raise_for_status()

# Apply the patch to the ObservabilityServiceNow class
def patch_observability_snow():
    """Apply the httpx patch to ObservabilityServiceNow."""
    # This will be called after the class is defined
    pass
'''
        
        # Find the insertion point (after imports, before class definition)
        lines = original_content.split('\n')
        insert_index = 0
        
        # Find the last import statement
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')) and not line.strip().startswith('#'):
                insert_index = i + 1
        
        # Insert the patch
        lines.insert(insert_index, patch_content)
        
        # Modify the __init__ method to use the patched session
        patched_content = '\n'.join(lines)
        
        # Replace the session initialization
        patched_content = patched_content.replace(
            'self._session = requests',
            'self._session = HttpxAdapter()'
        )
        
        # Write the patched file
        with open(observability_snow_path, 'w', encoding='utf-8') as f:
            f.write(patched_content)
        
        logger.info(f"Successfully applied urllib3 patch to {observability_snow_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply urllib3 patch: {e}")
        return False

def revert_urllib3_patch():
    """
    Revert the urllib3 patch by restoring the original file.
    """
    try:
        import gd_servicenow_api
        package_path = Path(gd_servicenow_api.__file__).parent
        observability_snow_path = package_path / "observability_snow.py"
        
        if not observability_snow_path.exists():
            logger.error(f"Could not find observability_snow.py at {observability_snow_path}")
            return False
        
        # Read the patched file
        with open(observability_snow_path, 'r', encoding='utf-8') as f:
            patched_content = f.read()
        
        # Check if it's patched
        if "urllib3_patch_applied" not in patched_content:
            logger.info("ObservabilityServiceNow is not patched")
            return True
        
        # Remove the patch content
        lines = patched_content.split('\n')
        filtered_lines = []
        skip_lines = False
        
        for line in lines:
            if line.strip() == "# urllib3_patch_applied - httpx compatibility patch":
                skip_lines = True
                continue
            elif skip_lines and line.strip() == "def patch_observability_snow():":
                # Skip until we find the end of the patch
                continue
            elif skip_lines and line.strip() == 'self._session = HttpxAdapter()':
                # Replace with original
                filtered_lines.append('        self._session = requests')
                skip_lines = False
                continue
            elif skip_lines and line.strip().startswith('def patch_observability_snow'):
                # Skip the patch function
                continue
            elif skip_lines and line.strip() == 'def revert_urllib3_patch():':
                # End of patch
                skip_lines = False
                continue
            elif not skip_lines:
                filtered_lines.append(line)
        
        # Write the reverted file
        with open(observability_snow_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(filtered_lines))
        
        logger.info(f"Successfully reverted urllib3 patch from {observability_snow_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to revert urllib3 patch: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply or revert urllib3 patch for ObservabilityServiceNow")
    parser.add_argument("action", choices=["apply", "revert"], help="Action to perform")
    
    args = parser.parse_args()
    
    if args.action == "apply":
        success = apply_urllib3_patch()
        if success:
            print("✅ urllib3 patch applied successfully")
        else:
            print("❌ Failed to apply urllib3 patch")
            sys.exit(1)
    elif args.action == "revert":
        success = revert_urllib3_patch()
        if success:
            print("✅ urllib3 patch reverted successfully")
        else:
            print("❌ Failed to revert urllib3 patch")
            sys.exit(1)
