#!/usr/bin/env python3
"""Deploy updated workflow to n8n instance, preserving real credentials."""

import json
import subprocess
import sys
import uuid

N8N_URL = "https://n8n.rnd.webpromo.tools"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8"
WORKFLOW_ID = "BAekxapYobfgHYTt"

# ─── Step 1: Get the current live workflow ───
print("Step 1: Fetching current workflow from n8n...")
result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
live_wf = json.loads(result.stdout)
print(f"  Got workflow: {live_wf['name']} ({len(live_wf['nodes'])} nodes)")

# ─── Step 2: Load our local modified workflow ───
print("Step 2: Loading local modified workflow...")
with open('/home/user/n8n_seo_audit/SEO_Audit_AI_Report.json') as f:
    local_wf = json.load(f)
print(f"  Local workflow: {len(local_wf['nodes'])} nodes")

# ─── Step 3: Map local node IDs to live node IDs ───
# Build mapping: local_node_name → live_node (with real IDs and credentials)
live_nodes_by_name = {}
for node in live_wf['nodes']:
    live_nodes_by_name[node['name']] = node

# Credential mapping from the live workflow
CRED_GOOGLE_DOCS = {"googleDocsOAuth2Api": {"id": "hb1wRTQP0sY6dAnx", "name": "Google Docs"}}
CRED_GOOGLE_DRIVE = {"googleDriveOAuth2Api": {"id": "Nl36H51nJBoCaf67", "name": "Google Drive for n8n"}}
CRED_GOOGLE_SHEETS = {"googleSheetsOAuth2Api": {"id": "hMp9ISVYVcdpImYl", "name": "Google Sheets account"}}
CRED_OPENAI = {"openAiApi": {"id": "b1hLC5E1Ad7p27A9", "name": "OpenAI"}}

# ─── Step 4: Build updated nodes list ───
print("Step 3: Building updated workflow...")

updated_nodes = []
local_to_live_id = {}  # Map local IDs to the IDs we'll use in the output

for local_node in local_wf['nodes']:
    name = local_node['name']

    if name in live_nodes_by_name:
        # Existing node — preserve live ID and credentials, update parameters
        live_node = live_nodes_by_name[name]
        updated_node = dict(live_node)

        # Update parameters from local (these contain our changes)
        updated_node['parameters'] = local_node['parameters']

        # Preserve position from local if significantly different
        updated_node['position'] = local_node['position']

        local_to_live_id[local_node['id']] = live_node['id']
        updated_nodes.append(updated_node)

    else:
        # New node — generate UUID, assign correct credentials
        new_id = str(uuid.uuid4())
        local_to_live_id[local_node['id']] = new_id

        new_node = dict(local_node)
        new_node['id'] = new_id

        # Assign correct credentials based on node type/usage
        if 'googleDocsOAuth2Api' in (local_node.get('credentials') or {}):
            new_node['credentials'] = CRED_GOOGLE_DOCS
        elif 'googleDriveOAuth2Api' in (local_node.get('credentials') or {}):
            new_node['credentials'] = CRED_GOOGLE_DRIVE
        elif 'googleSheetsOAuth2Api' in (local_node.get('credentials') or {}):
            new_node['credentials'] = CRED_GOOGLE_SHEETS
        elif 'openAiApi' in (local_node.get('credentials') or {}):
            new_node['credentials'] = CRED_OPENAI

        updated_nodes.append(new_node)
        print(f"  NEW node: {name} ({new_id[:8]}...)")

# ─── Step 5: Build connections using node names (same as local) ───
# The connections in our local file use node NAMES, which match the live workflow
updated_connections = local_wf['connections']

# ─── Step 6: Prepare the PUT payload ───
payload = {
    "name": live_wf['name'],
    "nodes": updated_nodes,
    "connections": updated_connections,
    "settings": {"executionOrder": "v1"}
}

# ─── Step 7: PUT the updated workflow ───
print(f"Step 4: Uploading to n8n ({len(updated_nodes)} nodes)...")

payload_json = json.dumps(payload, ensure_ascii=False)

result = subprocess.run(
    ["curl", "-s", "-X", "PUT",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}",
     "-H", "Content-Type: application/json",
     "-d", payload_json],
    capture_output=True, text=True
)

try:
    response = json.loads(result.stdout)
    if 'id' in response:
        print(f"  SUCCESS: Workflow updated (versionId: {response.get('versionId', 'N/A')[:16]}...)")
        print(f"  Nodes: {len(response.get('nodes', []))}")
    else:
        print(f"  ERROR: {result.stdout[:500]}")
        sys.exit(1)
except json.JSONDecodeError:
    print(f"  ERROR: Invalid response: {result.stdout[:500]}")
    sys.exit(1)

# ─── Step 8: Activate the workflow ───
print("Step 5: Activating workflow...")
result = subprocess.run(
    ["curl", "-s", "-X", "POST",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}/activate",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)

try:
    response = json.loads(result.stdout)
    print(f"  Active: {response.get('active', 'unknown')}")
    print(f"\nDone! Workflow deployed and activated.")
    print(f"URL: {N8N_URL}/workflow/{WORKFLOW_ID}")
except json.JSONDecodeError:
    print(f"  Warning: Could not parse activation response: {result.stdout[:200]}")
