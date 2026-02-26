#!/usr/bin/env python3
"""
FAST RESPONSE: Create doc immediately, respond with docUrl, process in background.

PROBLEM: GAS UrlFetchApp has ~6min timeout. Processing 3 competitors takes ~12min.
The Respond node fires AFTER everything is done — GAS never gets the response.

SOLUTION:
1. Create Google Doc immediately (parallel with competitor processing)
2. Respond with docUrl within ~2 seconds
3. Competitor loop + formatting continues in background
4. Set custom property "seo_audit_status=complete" at the very end
5. Frontend polls for status via GAS → Drive API

FLOW:
  Parse Input → Create Google Doc (temp title) → Respond (immediate: docUrl, docId)
             → Get Next Competitor → [loop] → Prepare Document
               → Rename Doc → Write Content → Format → Tables → Move to Folder → Set Doc Complete
"""

import json
import subprocess
import sys
import uuid

N8N_URL = "https://n8n.rnd.webpromo.tools"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2Zjc3NjZjMS04ZTZkLTQ3OGYtYTY2Ny05MzYxOWJhMzVkYmUiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzcxODY0MDI1fQ.pDWUjuqs6RF51PEKQtTHOUFJPvOF4YLFFsBWaCoL5I8"
WORKFLOW_ID = "BAekxapYobfgHYTt"

# ═══════════════════════════════════════════════════════
# STEP 1: Fetch live workflow
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("STEP 1: Fetching live workflow...")
result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
wf = json.loads(result.stdout)
print(f"  Nodes: {len(wf['nodes'])}, Active: {wf['active']}")

# Backup
with open("/home/user/n8n_seo_audit/workflow_backup_fast_response.json", 'w') as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════
# STEP 2: Modify nodes
# ═══════════════════════════════════════════════════════
print("\nSTEP 2: Modifying nodes...")

nodes_by_name = {n['name']: n for n in wf['nodes']}

# ─── Create Google Doc: use temp title (runs before Prepare Document) ───
cg = nodes_by_name['Create Google Doc']
cg['parameters']['jsonBody'] = '={ "title": "SEO Аудит │ {{ $now.toFormat(\'yyyy-MM-dd\') }}" }'
cg['position'] = [-720, 120]  # Move up, parallel with loop
print("  Modified: Create Google Doc (temp title, moved to parallel branch)")

# ─── Respond: early response with processing status ───
resp = nodes_by_name['Respond']
resp['parameters']['responseBody'] = (
    '={\n'
    '  "status": "processing",\n'
    '  "docUrl": "https://docs.google.com/document/d/{{ $(\'Create Google Doc\').first().json.documentId }}/edit",\n'
    '  "docId": "{{ $(\'Create Google Doc\').first().json.documentId }}",\n'
    '  "competitorsCount": {{ $(\'Parse Input\').first().json.totalCompetitors || 1 }}\n'
    '}'
)
resp['position'] = [-520, 120]  # Right after Create Google Doc
print("  Modified: Respond (early response, status=processing)")

# ─── Write Document Content: use $('Create Google Doc') reference instead of $json ───
wdc = nodes_by_name['Write Document Content']
wdc['parameters']['url'] = "=https://docs.googleapis.com/v1/documents/{{ $('Create Google Doc').first().json.documentId }}:batchUpdate"
print("  Modified: Write Document Content (use $('Create Google Doc') ref)")

# ─── Move to Folder: keep as-is, it already uses $('Create Google Doc') and $('Prepare Document') refs ───
print("  Unchanged: Move to Folder (already uses $() refs)")

# ─── Add Rename Doc node ───
rename_doc = {
    "parameters": {
        "method": "PATCH",
        "url": "=https://www.googleapis.com/drive/v3/files/{{ $('Create Google Doc').first().json.documentId }}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleDriveOAuth2Api",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={ \"name\": {{ JSON.stringify($json.docTitle) }} }",
        "options": {}
    },
    "id": str(uuid.uuid4()),
    "name": "Rename Doc",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.3,
    "position": [1360, 576],
    "credentials": {
        "googleDriveOAuth2Api": {
            "id": "Nl36H51nJBoCaf67",
            "name": "Google Drive for n8n"
        }
    }
}
wf['nodes'].append(rename_doc)
print(f"  Added: Rename Doc (id={rename_doc['id'][:8]}...)")

# ─── Add Set Doc Complete node ───
set_complete = {
    "parameters": {
        "method": "PATCH",
        "url": "=https://www.googleapis.com/drive/v3/files/{{ $('Create Google Doc').first().json.documentId }}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "googleDriveOAuth2Api",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={ "properties": { "seo_audit_status": "complete" } }',
        "options": {}
    },
    "id": str(uuid.uuid4()),
    "name": "Set Doc Complete",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.3,
    "position": [4336, 304],
    "credentials": {
        "googleDriveOAuth2Api": {
            "id": "Nl36H51nJBoCaf67",
            "name": "Google Drive for n8n"
        }
    }
}
wf['nodes'].append(set_complete)
print(f"  Added: Set Doc Complete (id={set_complete['id'][:8]}...)")

# ═══════════════════════════════════════════════════════
# STEP 3: Rebuild ALL connections
# ═══════════════════════════════════════════════════════
print("\nSTEP 3: Building connections...")

connections = {
    # ─── Entry: webhook → parse ───
    "Webhook": {"main": [[
        {"node": "Parse Input", "type": "main", "index": 0}
    ]]},

    # ─── Parse Input: TWO parallel branches ───
    "Parse Input": {"main": [[
        {"node": "Create Google Doc", "type": "main", "index": 0},    # Branch 1: create doc immediately
        {"node": "Get Next Competitor", "type": "main", "index": 0},  # Branch 2: process competitors
    ]]},

    # ─── Branch 1: immediate response ───
    "Create Google Doc": {"main": [[
        {"node": "Respond", "type": "main", "index": 0},
    ]]},
    # Respond: terminal (no outgoing)

    # ─── Branch 2: competitor loop ───
    "Get Next Competitor": {"main": [[
        {"node": "Set Variables", "type": "main", "index": 0}
    ]]},
    "Set Variables": {"main": [[
        {"node": "Get Spreadsheet Info", "type": "main", "index": 0}
    ]]},
    "Get Spreadsheet Info": {"main": [[
        {"node": "Extract Domain & Folder", "type": "main", "index": 0}
    ]]},
    "Extract Domain & Folder": {"main": [[
        {"node": "Read All Sheets", "type": "main", "index": 0}
    ]]},
    "Read All Sheets": {"main": [[
        {"node": "Prepare Data", "type": "main", "index": 0}
    ]]},
    "Prepare Data": {"main": [[
        {"node": "Agent 1 - Organic Traffic", "type": "main", "index": 0},
        {"node": "Agent 2 - Link Profile", "type": "main", "index": 0},
        {"node": "Agent 3 - Top Pages Links", "type": "main", "index": 0},
        {"node": "Agent 4 - Behavioral", "type": "main", "index": 0},
        {"node": "Agent 5 - Keywords", "type": "main", "index": 0},
        {"node": "Agent 6 - Traffic Pages", "type": "main", "index": 0},
    ]]},
    "Agent 1 - Organic Traffic": {"main": [[{"node": "Merge Results", "type": "main", "index": 0}]]},
    "Agent 2 - Link Profile": {"main": [[{"node": "Merge Results", "type": "main", "index": 1}]]},
    "Agent 3 - Top Pages Links": {"main": [[{"node": "Merge Results", "type": "main", "index": 2}]]},
    "Agent 4 - Behavioral": {"main": [[{"node": "Merge Results", "type": "main", "index": 3}]]},
    "Agent 5 - Keywords": {"main": [[{"node": "Merge Results", "type": "main", "index": 4}]]},
    "Agent 6 - Traffic Pages": {"main": [[{"node": "Merge Results", "type": "main", "index": 5}]]},
    "Merge Results": {"main": [[{"node": "Collect Sections", "type": "main", "index": 0}]]},
    "Collect Sections": {"main": [[{"node": "Final Summary Agent", "type": "main", "index": 0}]]},
    "Final Summary Agent": {"main": [[{"node": "Accumulate Result", "type": "main", "index": 0}]]},
    "Accumulate Result": {"main": [[{"node": "Is Complete?", "type": "main", "index": 0}]]},
    "Is Complete?": {"main": [
        [{"node": "Prepare Document", "type": "main", "index": 0}],      # true
        [{"node": "Get Next Competitor", "type": "main", "index": 0}],   # false (loop)
    ]},

    # ─── Document pipeline (after all competitors processed) ───
    "Prepare Document": {"main": [[
        {"node": "Rename Doc", "type": "main", "index": 0}
    ]]},
    "Rename Doc": {"main": [[
        {"node": "Write Document Content", "type": "main", "index": 0}
    ]]},
    "Write Document Content": {"main": [[
        {"node": "Build Format Requests", "type": "main", "index": 0}
    ]]},
    "Build Format Requests": {"main": [[
        {"node": "Apply Formatting", "type": "main", "index": 0}
    ]]},
    "Apply Formatting": {"main": [[
        {"node": "Read Document", "type": "main", "index": 0}
    ]]},
    "Read Document": {"main": [[
        {"node": "Build Table Requests", "type": "main", "index": 0}
    ]]},
    "Build Table Requests": {"main": [[
        {"node": "Has Tables?", "type": "main", "index": 0}
    ]]},
    "Has Tables?": {"main": [
        [{"node": "Execute Table Requests", "type": "main", "index": 0}],   # true
        [{"node": "Merge Table Branch", "type": "main", "index": 1}],       # false
    ]},
    "Execute Table Requests": {"main": [[{"node": "Read Document Final", "type": "main", "index": 0}]]},
    "Read Document Final": {"main": [[{"node": "Build Cell Text", "type": "main", "index": 0}]]},
    "Build Cell Text": {"main": [[{"node": "Execute Cell Text", "type": "main", "index": 0}]]},
    "Execute Cell Text": {"main": [[{"node": "Read Doc For Styling", "type": "main", "index": 0}]]},
    "Read Doc For Styling": {"main": [[{"node": "Build Table Style", "type": "main", "index": 0}]]},
    "Build Table Style": {"main": [[{"node": "Apply Table Style", "type": "main", "index": 0}]]},
    "Apply Table Style": {"main": [[{"node": "Merge Table Branch", "type": "main", "index": 0}]]},
    "Merge Table Branch": {"main": [[{"node": "Move to Folder", "type": "main", "index": 0}]]},
    "Move to Folder": {"main": [[{"node": "Set Doc Complete", "type": "main", "index": 0}]]},
    # Set Doc Complete: terminal
}

# ─── Verify ───
node_names = {n['name'] for n in wf['nodes']}
errors = []
for src, outputs in connections.items():
    if src not in node_names:
        errors.append(f"Source '{src}' not found")
    for out_list in outputs.get('main', []):
        for conn in out_list:
            if conn['node'] not in node_names:
                errors.append(f"Target '{conn['node']}' (from '{src}') not found")
if errors:
    for e in errors:
        print(f"  ERROR: {e}")
    sys.exit(1)
print(f"  All connections verified ({len(connections)} sources)")

# ═══════════════════════════════════════════════════════
# STEP 4: Deploy
# ═══════════════════════════════════════════════════════
print("\nSTEP 4: Deploying...")

payload = {
    "name": wf['name'],
    "nodes": wf['nodes'],
    "connections": connections,
    "settings": {"executionOrder": "v1"}
}

payload_json = json.dumps(payload, ensure_ascii=False)
with open("/home/user/n8n_seo_audit/workflow_fast_response.json", 'w') as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)

result = subprocess.run(
    ["curl", "-s", "-X", "PUT",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}",
     "-H", "Content-Type: application/json",
     "-d", payload_json],
    capture_output=True, text=True
)

response = json.loads(result.stdout)
if 'id' in response:
    print(f"  SUCCESS: {len(response.get('nodes', []))} nodes")
else:
    print(f"  ERROR: {result.stdout[:500]}")
    sys.exit(1)

# Activate
result = subprocess.run(
    ["curl", "-s", "-X", "POST",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}/activate",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
print(f"  Active: {json.loads(result.stdout).get('active')}")

# ═══════════════════════════════════════════════════════
# STEP 5: Verify
# ═══════════════════════════════════════════════════════
print("\nSTEP 5: Verifying...")
result = subprocess.run(
    ["curl", "-s", "-X", "GET",
     f"{N8N_URL}/api/v1/workflows/{WORKFLOW_ID}",
     "-H", f"X-N8N-API-KEY: {API_KEY}"],
    capture_output=True, text=True
)
vwf = json.loads(result.stdout)

checks = [
    ("Parse Input", "Create Google Doc"),
    ("Parse Input", "Get Next Competitor"),
    ("Create Google Doc", "Respond"),
    ("Prepare Document", "Rename Doc"),
    ("Rename Doc", "Write Document Content"),
    ("Move to Folder", "Set Doc Complete"),
]
vc = vwf['connections']
for src, tgt in checks:
    found = False
    if src in vc:
        for ol in vc[src].get('main', []):
            for c in ol:
                if c['node'] == tgt:
                    found = True
    print(f"  {src} → {tgt}: {'OK' if found else 'MISSING!'}")

# Check Create Google Doc uses temp title
for n in vwf['nodes']:
    if n['name'] == 'Create Google Doc':
        ok = 'yyyy-MM-dd' in n['parameters'].get('jsonBody', '')
        print(f"  Create Google Doc temp title: {'OK' if ok else 'FAIL'}")
    if n['name'] == 'Respond':
        ok = 'processing' in n['parameters'].get('responseBody', '')
        print(f"  Respond status=processing: {'OK' if ok else 'FAIL'}")
    if n['name'] == 'Write Document Content':
        ok = "Create Google Doc" in n['parameters'].get('url', '')
        print(f"  Write Doc uses $('Create Google Doc'): {'OK' if ok else 'FAIL'}")

new_nodes = {'Rename Doc', 'Set Doc Complete'}
found_new = {n['name'] for n in vwf['nodes']} & new_nodes
print(f"  New nodes present: {found_new == new_nodes}")

print(f"\nDone! Respond now fires immediately after doc creation.")
print(f"URL: {N8N_URL}/workflow/{WORKFLOW_ID}")
