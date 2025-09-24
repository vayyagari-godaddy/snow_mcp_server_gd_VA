#!/usr/bin/env python3
"""
Dependency Installation Script for ServiceNow MCP Server with JWT Authentication

This script handles installation of all required packages, working around
corporate repository limitations by installing packages from appropriate sources.
"""

import subprocess
import sys
import importlib
import os

def run_pip_install(packages, index_url=None, no_deps=False):
    """Run pip install with the given parameters"""
    cmd = [sys.executable, "-m", "pip", "install"]
    
    if index_url:
        cmd.extend(["--index-url", index_url])
    
    if no_deps:
        cmd.append("--no-deps")
    
    cmd.extend(packages)
    
    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode == 0:
            print("✅ Success!")
            return True
        else:
            print(f"❌ Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def check_package(package_name, display_name=None):
    """Check if a package can be imported"""
    if not display_name:
        display_name = package_name
    
    try:
        importlib.import_module(package_name)
        print(f"✅ {display_name} is available")
        return True
    except ImportError:
        print(f"❌ {display_name} is NOT available")
        return False

def main():
    print("🔧 Installing ServiceNow MCP Server Dependencies with JWT Authentication")
    print("=" * 80)
    
    # Public PyPI packages (not available in corporate repo)
    print("\n📦 Installing packages from public PyPI...")
    public_packages = [
        ["fastapi>=0.68.0"],
        ["PyJWT>=2.0.0", "cryptography>=3.0.0"],
        ["aiohttp>=3.7.0"],
        ["asyncio-throttle>=1.0.0"],
        ["python-dotenv>=0.19.0"],
        ["sse-starlette>=1.0.0"],
        ["boto3>=1.26.7"],  # Required by gd-servicenow-api
        ["requests>=2.25.0"]  # Common dependency
    ]
    
    for package_list in public_packages:
        print(f"\nInstalling: {', '.join(package_list)}")
        success = run_pip_install(package_list, index_url="https://pypi.org/simple/")
        if not success:
            print(f"⚠️  Warning: Failed to install {', '.join(package_list)}")
    
    # Corporate repository packages (likely available internally)
    print("\n🏢 Installing packages from corporate repository...")
    corporate_packages = [
        ["mcp>=1.0.0"],
        ["pydantic>=2.0.0"],
        ["uvicorn>=0.20.0"]
    ]
    
    for package_list in corporate_packages:
        print(f"\nInstalling: {', '.join(package_list)}")
        success = run_pip_install(package_list)  # Use default corporate repo
        if not success:
            print(f"⚠️  Warning: Failed to install {', '.join(package_list)}")
    
    # Special handling for gd-servicenow-api
    print("\n🔧 Installing gd-servicenow-api...")
    print("Installing gd-servicenow-api==0.2.0 from corporate repository...")
    success = run_pip_install(["gd-servicenow-api==0.2.0"])
    if not success:
        print("⚠️  gd-servicenow-api installation failed from corporate repo")
        print("Trying to install without dependencies...")
        success = run_pip_install(["gd-servicenow-api==0.2.0"], no_deps=True)
        if not success:
            print("❌ Critical: gd-servicenow-api installation failed completely")
    
    # Verification
    print("\n🔍 Verifying installations...")
    print("=" * 80)
    
    core_packages = [
        ("mcp", "MCP Framework"),
        ("pydantic", "Pydantic"),
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("jwt", "PyJWT"),
        ("cryptography", "Cryptography"),
        ("aiohttp", "aioHTTP"),
        ("dotenv", "python-dotenv"),
        ("gd_servicenow_api", "GD ServiceNow API")
    ]
    
    all_good = True
    for package, display_name in core_packages:
        if not check_package(package, display_name):
            all_good = False
    
    print("\n" + "=" * 80)
    if all_good:
        print("🎉 SUCCESS! All required packages are installed and importable.")
        print("\n📋 Next Steps:")
        print("1. Copy env_template.txt to .env and configure your credentials")
        print("2. Test the server: python3 server_fastmcp.py")
        print("3. Use the new JWT authentication tools!")
    else:
        print("⚠️  PARTIAL SUCCESS: Some packages are missing.")
        print("\n🔧 Manual Installation Required:")
        print("For any missing packages, try:")
        print("  python3 -m pip install --index-url https://pypi.org/simple/ <package_name>")
    
    print("\n🔐 JWT Authentication Features Added:")
    print("- generate_jwt_token() - Create JWT tokens")
    print("- validate_jwt_token() - Validate tokens")
    print("- refresh_jwt_token() - Refresh expired tokens")
    print("- get_jwt_token_info() - Get token information")

if __name__ == "__main__":
    main()
