#!/usr/bin/env python3
"""
Generate the staging workflow "WS - DB (STAGING)" from the production
workflow "WS - DB (PROD)".

Changes applied:
1. All SQL table references ws_* -> ws_*_stg (for sync nodes)
2. START_main trigger: daily 02:01 -> every 2 hours
3. Batch trigger: adds sync_status check to skip when cycle is complete
4. Need Reset? TRUE path: adds migration + snapshot + fix encoding + telegram
5. After Load trigger: removed (snapshot runs after migration)
6. Orphan nodes removed
"""

import json
import copy
import uuid
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "WS - DB (PROD) (1).json")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "WS - DB (STAGING).json")

# Credential IDs (from production workflow)
POSTGRES_CRED = {
    "postgres": {
        "id": "Vew3cjknhnKa16N5",
        "name": "Supabase - Postgres account"
    }
}
TELEGRAM_CRED = {
    "telegramApi": {
        "id": "mHbM43fsaWN90avF",
        "name": "I.Redin - ws tg log"
    }
}
TELEGRAM_CHAT_ID = "-1003503638426"


def gen_id():
    return str(uuid.uuid4())


def replace_table_names_in_sql(sql):
    """Replace production table names with staging equivalents in SQL."""
    # Order matters: longer names first to avoid partial replacements
    replacements = [
        ("ws_departments_id_seq", "ws_departments_stg_id_seq"),
        ("ws_time_logs", "ws_time_logs_stg"),
        ("ws_sync_state", "ws_sync_state_stg"),
        ("ws_departments", "ws_departments_stg"),
        ("ws_projects", "ws_projects_stg"),
        ("ws_tasks", "ws_tasks_stg"),
        ("ws_users", "ws_users_stg"),
    ]
    for old, new in replacements:
        sql = sql.replace(old, new)
    return sql


def get_node_by_name(nodes, name):
    """Find a node by its name."""
    for node in nodes:
        if node.get("name") == name:
            return node
    return None


def remove_nodes_by_names(nodes, names_to_remove):
    """Remove nodes from the list by name."""
    return [n for n in nodes if n.get("name") not in names_to_remove]


def remove_connections_for_nodes(connections, names_to_remove):
    """Remove connections from/to removed nodes."""
    # Remove source connections
    for name in names_to_remove:
        connections.pop(name, None)
    # Remove target connections pointing to removed nodes
    for source_name in list(connections.keys()):
        for output_type in connections[source_name]:
            for output_list in connections[source_name][output_type]:
                connections[source_name][output_type] = [
                    [conn for conn in out if conn.get("node") not in names_to_remove]
                    for out in connections[source_name][output_type]
                ]


# ============================================================
# New nodes to add
# ============================================================

def make_check_sync_status_node():
    """Node: Check if sync cycle is already complete (skip if so)."""
    return {
        "parameters": {
            "operation": "executeQuery",
            "query": (
                "SELECT COALESCE(\n"
                "  (SELECT value FROM ws_sync_state_stg WHERE key = 'sync_status'),\n"
                "  'idle'\n"
                ") as sync_status;"
            ),
            "options": {}
        },
        "id": gen_id(),
        "name": "Check Sync Status",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [-752, 944],
        "retryOnFail": True,
        "maxTries": 3,
        "credentials": POSTGRES_CRED
    }


def make_is_sync_complete_node():
    """IF node: check if sync_status == 'complete'."""
    return {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "loose"
                },
                "conditions": [
                    {
                        "id": "check-sync-complete",
                        "leftValue": "={{ $json.sync_status }}",
                        "rightValue": "complete",
                        "operator": {
                            "type": "string",
                            "operation": "equals"
                        }
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": gen_id(),
        "name": "Is Sync Complete?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [-592, 944]
    }


def make_skip_batch_node():
    """NoOp node for when sync is already complete."""
    return {
        "parameters": {},
        "id": gen_id(),
        "name": "Skip Batch",
        "type": "n8n-nodes-base.noOp",
        "typeVersion": 1,
        "position": [-432, 848]
    }


def make_migrate_to_production_node():
    """Postgres node: execute atomic migration from staging to production."""
    return {
        "parameters": {
            "operation": "executeQuery",
            "query": "SELECT * FROM migrate_staging_to_production();",
            "options": {}
        },
        "id": gen_id(),
        "name": "Migrate to Production",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [928, 624],
        "retryOnFail": True,
        "maxTries": 3,
        "credentials": POSTGRES_CRED
    }


def make_snapshot_after_migration_node():
    """Postgres node: snapshot overdue tasks (runs on PRODUCTION tables)."""
    return {
        "parameters": {
            "operation": "executeQuery",
            "query": (
                "INSERT INTO task_status_history (log_date, task_id, user_id, status_on_date)\n"
                "SELECT \n"
                "    CURRENT_DATE,\n"
                "    t.id,\n"
                "    t.user_to_id,\n"
                "    'overdue'\n"
                "FROM ws_tasks t\n"
                "WHERE \n"
                "    t.status = 'active'\n"
                "    AND t.date_end IS NOT NULL\n"
                "    AND t.date_end::date < CURRENT_DATE\n"
                "ON CONFLICT (log_date, task_id) \n"
                "DO UPDATE SET \n"
                "    user_id = EXCLUDED.user_id,\n"
                "    status_on_date = EXCLUDED.status_on_date;"
            ),
            "options": {}
        },
        "id": gen_id(),
        "name": "Snapshot After Migration",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [1168, 624],
        "credentials": POSTGRES_CRED
    }


def make_fix_encoding_after_migration_node():
    """Postgres node: fix encoding errors on PRODUCTION tables after migration."""
    return {
        "parameters": {
            "operation": "executeQuery",
            "query": (
                "WITH updated AS (\n"
                "  UPDATE ws_tasks\n"
                "  SET \n"
                "      name = regexp_replace(name, '[\\u4E00-\\u9FFF\\u3400-\\u4DBF]+', '[ENCODING ERROR]', 'g'),\n"
                "      text = regexp_replace(text, '[\\u4E00-\\u9FFF\\u3400-\\u4DBF]+', '[ENCODING ERROR]', 'g')\n"
                "  WHERE \n"
                "      name ~ '[\\u4E00-\\u9FFF\\u3400-\\u4DBF]'\n"
                "      OR text ~ '[\\u4E00-\\u9FFF\\u3400-\\u4DBF]'\n"
                "  RETURNING id\n"
                ")\n"
                "SELECT \n"
                "  COUNT(*) as fixed_count,\n"
                "  CASE \n"
                "    WHEN COUNT(*) > 0 THEN 'Fixed ' || COUNT(*) || ' tasks with encoding errors'\n"
                "    ELSE 'No encoding errors found'\n"
                "  END as message\n"
                "FROM updated;"
            ),
            "options": {}
        },
        "id": gen_id(),
        "name": "Fix Encoding After Migration",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [1408, 624],
        "credentials": POSTGRES_CRED
    }


def make_set_sync_complete_node():
    """Postgres node: mark staging sync as complete."""
    return {
        "parameters": {
            "operation": "executeQuery",
            "query": (
                "INSERT INTO ws_sync_state_stg (key, value, updated_at)\n"
                "VALUES ('sync_status', 'complete', NOW())\n"
                "ON CONFLICT (key) DO UPDATE SET value = 'complete', updated_at = NOW();"
            ),
            "options": {}
        },
        "id": gen_id(),
        "name": "Set Sync Complete",
        "type": "n8n-nodes-base.postgres",
        "typeVersion": 2.6,
        "position": [1648, 624],
        "credentials": POSTGRES_CRED
    }


def make_telegram_migration_node():
    """Telegram node: send migration completion notification."""
    return {
        "parameters": {
            "chatId": TELEGRAM_CHAT_ID,
            "text": (
                "={{ \"\\u2705 Migration Complete!\\n\\n\""
                " + \"\\ud83d\\udcca Departments: \" + $('Migrate to Production').first().json.migrated_departments + \"\\n\""
                " + \"\\ud83d\\udc65 Users: \" + $('Migrate to Production').first().json.migrated_users + \"\\n\""
                " + \"\\ud83d\\udcc1 Projects: \" + $('Migrate to Production').first().json.migrated_projects + \"\\n\""
                " + \"\\u2611\\ufe0f Tasks: \" + $('Migrate to Production').first().json.migrated_tasks + \"\\n\""
                " + \"\\u23f1 Time logs: \" + $('Migrate to Production').first().json.migrated_time_logs + \"\\n\""
                " + \"\\n\" + $('Fix Encoding After Migration').first().json.message"
                " + \"\\n\\ud83d\\udcc5 \" + $now.format('DD.MM.YYYY HH:mm:ss') }}"
            ),
            "additionalFields": {}
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [1888, 624],
        "id": gen_id(),
        "name": "Telegram Migration",
        "webhookId": gen_id(),
        "credentials": TELEGRAM_CRED
    }


def make_cleanup_staging_sql():
    """Return the cleanup SQL for staging tables."""
    return (
        "-- Disable FK checks\n"
        "SET session_replication_role = 'replica';\n\n"
        "-- Clean staging tables\n"
        "TRUNCATE TABLE ws_time_logs_stg CASCADE;\n"
        "TRUNCATE TABLE ws_tasks_stg CASCADE;\n"
        "TRUNCATE TABLE ws_projects_stg CASCADE;\n"
        "TRUNCATE TABLE ws_users_stg CASCADE;\n"
        "TRUNCATE TABLE ws_departments_stg CASCADE;\n"
        "TRUNCATE TABLE ws_sync_state_stg CASCADE;\n\n"
        "-- Re-enable FK checks\n"
        "SET session_replication_role = 'origin';\n\n"
        "-- Reset departments sequence\n"
        "ALTER SEQUENCE ws_departments_stg_id_seq RESTART WITH 1;\n\n"
        "-- Initialize sync state\n"
        "INSERT INTO ws_sync_state_stg (key, value, updated_at)\n"
        "VALUES ('batch_offset', '0', NOW()), ('sync_status', 'syncing', NOW())\n"
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();"
    )


# ============================================================
# Main transformation
# ============================================================

def main():
    # Read production workflow
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        prod = json.load(f)

    staging = copy.deepcopy(prod)
    staging["name"] = "WS - DB (STAGING)"
    # Remove ID so n8n creates a new workflow
    staging.pop("id", None)
    staging["versionId"] = gen_id()

    # ----------------------------------------------------------
    # Step 1: Replace table names in all SQL-containing nodes
    # ----------------------------------------------------------
    # Nodes whose SQL should reference PRODUCTION (not staging):
    production_only_nodes = {
        "Snapshot Overdue Tasks", "Snapshot Overdue Tasks1",
        "Fix Encoding Errors", "Fix Encoding Errors1",
        "Check Snapshot Today",
    }

    for node in staging["nodes"]:
        node_name = node.get("name", "")
        params = node.get("parameters", {})

        # Skip nodes that should keep production table references
        if node_name in production_only_nodes:
            continue

        # Replace table names in SQL query parameters
        if "query" in params:
            params["query"] = replace_table_names_in_sql(params["query"])

    # ----------------------------------------------------------
    # Step 2: Modify triggers
    # ----------------------------------------------------------

    # START_main: change from daily 02:01 to every 2 hours
    start_main = get_node_by_name(staging["nodes"], "START_main")
    if start_main:
        start_main["name"] = "START_staging"
        start_main["parameters"]["rule"]["interval"] = [
            {
                "field": "cronExpression",
                "expression": "0 */2 * * *"
            }
        ]

    # Main trigger stays at 6 minutes - we'll insert sync check nodes
    main_trigger = get_node_by_name(staging["nodes"], "Main")
    if main_trigger:
        main_trigger["name"] = "Batch"

    # ----------------------------------------------------------
    # Step 3: Remove orphan nodes and After Load trigger chain
    # ----------------------------------------------------------
    orphan_nodes = [
        # After Load trigger chain (snapshot now runs after migration)
        "After Load", "Snapshot Overdue Tasks", "Fix Encoding Errors1",
        "Send a text message2",
        # Old orphan nodes from previous workflow version
        "Get Valid Users", "Get Batch Offset1", "Get Projects (API)",
        "Prepare Batch1",
        # Sticky notes for removed sections
        "Sticky Note3",
    ]
    staging["nodes"] = remove_nodes_by_names(staging["nodes"], orphan_nodes)
    remove_connections_for_nodes(staging["connections"], orphan_nodes)

    # Also remove Snapshot Overdue Tasks1 and Fix Encoding Errors
    # (they'll be replaced by post-migration nodes)
    old_post_sync_nodes = [
        "Snapshot Overdue Tasks1", "Fix Encoding Errors",
        "Check Snapshot Today", "Already Done?",
    ]
    staging["nodes"] = remove_nodes_by_names(staging["nodes"], old_post_sync_nodes)
    remove_connections_for_nodes(staging["connections"], old_post_sync_nodes)

    # ----------------------------------------------------------
    # Step 4: Update Cleanup SQL
    # ----------------------------------------------------------
    cleanup_node = get_node_by_name(staging["nodes"], "Cleanup All Tables")
    if cleanup_node:
        cleanup_node["parameters"]["query"] = make_cleanup_staging_sql()

    # ----------------------------------------------------------
    # Step 5: Add new nodes
    # ----------------------------------------------------------
    new_nodes = [
        make_check_sync_status_node(),
        make_is_sync_complete_node(),
        make_skip_batch_node(),
        make_migrate_to_production_node(),
        make_snapshot_after_migration_node(),
        make_fix_encoding_after_migration_node(),
        make_set_sync_complete_node(),
        make_telegram_migration_node(),
    ]
    staging["nodes"].extend(new_nodes)

    # ----------------------------------------------------------
    # Step 6: Update connections
    # ----------------------------------------------------------
    conns = staging["connections"]

    # --- Batch trigger chain with sync check ---
    # Batch -> Check Sync Status -> Is Sync Complete?
    #   TRUE -> Skip Batch
    #   FALSE -> Get Valid Users4 -> ...
    conns["Batch"] = {
        "main": [[{"node": "Check Sync Status", "type": "main", "index": 0}]]
    }
    conns["Check Sync Status"] = {
        "main": [[{"node": "Is Sync Complete?", "type": "main", "index": 0}]]
    }
    conns["Is Sync Complete?"] = {
        "main": [
            [{"node": "Skip Batch", "type": "main", "index": 0}],       # TRUE: complete
            [{"node": "Get Valid Users4", "type": "main", "index": 0}],  # FALSE: continue
        ]
    }
    conns["Skip Batch"] = {"main": [[]]}

    # Remove old "Main" connection (renamed to "Batch" above)
    conns.pop("Main", None)

    # --- START_staging connection ---
    conns["START_staging"] = {
        "main": [[{"node": "Cleanup All Tables", "type": "main", "index": 0}]]
    }
    conns.pop("START_main", None)

    # --- Need Reset? TRUE path: migration instead of snapshot check ---
    conns["Need Reset?"] = {
        "main": [
            [{"node": "Migrate to Production", "type": "main", "index": 0}],  # TRUE: reset needed
            [{"node": "Cycle Complete", "type": "main", "index": 0}],          # FALSE: no reset
        ]
    }

    # Migration chain
    conns["Migrate to Production"] = {
        "main": [[{"node": "Snapshot After Migration", "type": "main", "index": 0}]]
    }
    conns["Snapshot After Migration"] = {
        "main": [[{"node": "Fix Encoding After Migration", "type": "main", "index": 0}]]
    }
    conns["Fix Encoding After Migration"] = {
        "main": [[{"node": "Set Sync Complete", "type": "main", "index": 0}]]
    }
    conns["Set Sync Complete"] = {
        "main": [[{"node": "Telegram Migration", "type": "main", "index": 0}]]
    }
    conns["Telegram Migration"] = {
        "main": [[{"node": "Cycle Complete", "type": "main", "index": 0}]]
    }

    # Remove old connections for removed nodes
    for old_name in ["Check Snapshot Today", "Already Done?",
                     "Snapshot Overdue Tasks1", "Fix Encoding Errors"]:
        conns.pop(old_name, None)

    # ----------------------------------------------------------
    # Step 7: Add sticky notes for documentation
    # ----------------------------------------------------------
    staging["nodes"].append({
        "parameters": {
            "content": (
                "## WS - DB (STAGING)\n\n"
                "**Shadow sync workflow**\n\n"
                "**START_staging** (every 2h):\n"
                "Clean staging tables -> Load users -> Init offset\n\n"
                "**Batch** (every 6 min):\n"
                "Check sync status -> Process batch -> Update offset\n\n"
                "**Migration** (after all batches done):\n"
                "Atomic migrate staging->prod -> Snapshot -> Fix encoding -> Telegram"
            ),
            "height": 480,
            "width": 420,
            "color": 5
        },
        "type": "n8n-nodes-base.stickyNote",
        "position": [-1904, 144],
        "typeVersion": 1,
        "id": gen_id(),
        "name": "Sticky Note Staging Info"
    })

    # ----------------------------------------------------------
    # Step 8: Clean up
    # ----------------------------------------------------------
    # Remove any connections referencing nodes that no longer exist
    existing_node_names = {n["name"] for n in staging["nodes"]}
    for source in list(conns.keys()):
        if source not in existing_node_names:
            del conns[source]
            continue
        for output_type in conns[source]:
            conns[source][output_type] = [
                [c for c in output if c.get("node") in existing_node_names]
                for output in conns[source][output_type]
            ]

    # ----------------------------------------------------------
    # Save
    # ----------------------------------------------------------
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(staging, f, indent=2, ensure_ascii=False)

    print(f"Staging workflow saved to: {OUTPUT_FILE}")

    # Print summary
    print(f"\nNodes: {len(staging['nodes'])}")
    print(f"Connections: {len(staging['connections'])}")
    print("\nNew nodes added:")
    for n in new_nodes:
        print(f"  - {n['name']} ({n['type']})")
    print("\nNodes removed:")
    for n in orphan_nodes + old_post_sync_nodes:
        print(f"  - {n}")
    print("\nTrigger changes:")
    print("  - START_main (02:01 daily) -> START_staging (every 2 hours)")
    print("  - Main (6 min) -> Batch (6 min) + sync status check")
    print("  - After Load (04:00) -> REMOVED (snapshot runs after migration)")


if __name__ == "__main__":
    main()
