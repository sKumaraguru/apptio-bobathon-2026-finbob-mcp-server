#!/usr/bin/env python3
"""
Test script to verify SharePoint integration with cwshareddriveutils.
"""

import sys
from pathlib import Path

# Add parent directory to Python path so 'backend' package can be imported
parent_dir = str(Path(__file__).parent.parent.resolve())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

print("=" * 80)
print("TESTING SHAREPOINT INTEGRATION")
print("=" * 80)

# Test 1: Import all required modules
print("\n1. Testing imports...")
try:
    from cwshareddriveutils.sharepoint.sharepoint import SharePointClientProvider, SharePointExcelManager
    from cwshareddriveutils.sharepoint.clients import MicrosoftSharepointAuth, SharePointNetworkClient
    from cwshareddriveutils.sharepoint.models import AzureAppCredentials
    print("   ✓ cwshareddriveutils imports successful")
except ImportError as e:
    print(f"   ✗ Failed to import cwshareddriveutils: {e}")
    sys.exit(1)

try:
    from backend.src.sharepoint.client import SharePointClient
    from backend.src.sharepoint.discovery import FileDiscoveryService
    from backend.src.sharepoint.cache import CacheManager
    from backend.src.models.internal import SharePointSiteConfig
    print("   ✓ Local module imports successful")
except ImportError as e:
    print(f"   ✗ Failed to import local modules: {e}")
    sys.exit(1)

# Test 2: Create credentials object
print("\n2. Testing AzureAppCredentials creation...")
try:
    credentials = AzureAppCredentials(
        client_id="test-client-id",
        client_secret="test-client-secret",
        tenant_id="test-tenant-id"
    )
    print(f"   ✓ Credentials created: tenant_id={credentials.tenant_id}")
except Exception as e:
    print(f"   ✗ Failed to create credentials: {e}")
    sys.exit(1)

# Test 3: Skip auth creation with test credentials (requires real Azure AD)
print("\n3. Testing MicrosoftSharepointAuth creation...")
print("   ⊘ Skipped - requires valid Azure AD credentials")
print("   ✓ Auth class is available and importable")

# Test 4: Create network client
print("\n4. Testing SharePointNetworkClient creation...")
try:
    network_client = SharePointNetworkClient()
    print(f"   ✓ Network client created: {type(network_client).__name__}")
except Exception as e:
    print(f"   ✗ Failed to create network client: {e}")
    sys.exit(1)

# Test 5: Skip provider creation (requires auth)
print("\n5. Testing SharePointClientProvider creation...")
print("   ⊘ Skipped - requires valid auth object")
print("   ✓ Provider class is available and importable")

# Test 6: Skip client retrieval (requires provider)
print("\n6. Testing client retrieval from provider...")
print("   ⊘ Skipped - requires valid provider")
print("   ✓ SharePointExcelManager class is available and importable")

# Test 7: Test SharePointClient wrapper structure (without actual connection)
print("\n7. Testing SharePointClient wrapper structure...")
print("   ⊘ Skipped full initialization - requires valid Azure credentials")
try:
    # Just verify the class can be imported and has the right structure
    from inspect import signature
    
    # Check __init__ signature
    init_sig = signature(SharePointClient.__init__)
    params = list(init_sig.parameters.keys())
    assert 'tenant_id' in params, "Missing tenant_id parameter"
    assert 'client_id' in params, "Missing client_id parameter"
    assert 'client_secret' in params, "Missing client_secret parameter"
    assert 'site_configs' in params, "Missing site_configs parameter"
    print(f"   ✓ SharePointClient.__init__ has correct parameters")
    
    # Check methods exist
    assert hasattr(SharePointClient, 'list_files'), "Missing list_files method"
    assert hasattr(SharePointClient, 'download_file'), "Missing download_file method"
    assert hasattr(SharePointClient, 'get_file_info'), "Missing get_file_info method"
    assert hasattr(SharePointClient, 'search_files'), "Missing search_files method"
    print("   ✓ All SharePointClient methods present")
    
except Exception as e:
    print(f"   ✗ Structure verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 8: Test FileDiscoveryService structure
print("\n8. Testing FileDiscoveryService structure...")
try:
    # Check FileDiscoveryService methods
    assert hasattr(FileDiscoveryService, 'discover_assessment_reports'), "Missing discover_assessment_reports"
    assert hasattr(FileDiscoveryService, 'find_master_report'), "Missing find_master_report"
    assert hasattr(FileDiscoveryService, 'find_report_by_id'), "Missing find_report_by_id"
    assert hasattr(FileDiscoveryService, 'find_report_by_file_id'), "Missing find_report_by_file_id"
    print("   ✓ All FileDiscoveryService methods present")
except AssertionError as e:
    print(f"   ✗ Method verification failed: {e}")
    sys.exit(1)

# Test 9: Verify integration points
print("\n9. Verifying integration points...")
try:
    # Verify that our wrapper uses the correct cwshareddriveutils classes
    import inspect
    source = inspect.getsource(SharePointClient.__init__)
    
    assert 'AzureAppCredentials' in source, "Should use AzureAppCredentials"
    assert 'MicrosoftSharepointAuth' in source, "Should use MicrosoftSharepointAuth"
    assert 'SharePointNetworkClient' in source, "Should use SharePointNetworkClient"
    assert 'SharePointClientProvider' in source, "Should use SharePointClientProvider"
    print("   ✓ SharePointClient uses correct cwshareddriveutils classes")
    
except Exception as e:
    print(f"   ✗ Integration verification failed: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("ALL TESTS PASSED ✓")
print("=" * 80)
print("\nNotes:")
print("- These tests verify the integration structure only")
print("- Actual SharePoint operations require valid Azure credentials")
print("- To test real operations, configure credentials in .env file")
print("=" * 80)

# Made with Bob
