"""SQLite bot operation table migrations."""

from __future__ import annotations

def _auto_migrate_bot_sqlite(conn) -> None:
    """Backfill bot runtime columns for existing local SQLite databases."""

    knowledge_cols = [row[1] for row in conn.execute("PRAGMA table_info(bot_knowledge_files)").fetchall()]
    if knowledge_cols:
        for column_name, ddl in {
            "review_status": "VARCHAR(20) NOT NULL DEFAULT 'approved'",
            "visibility_scope": "VARCHAR(40) NOT NULL DEFAULT 'all_bots'",
            "owner_profile_key": "VARCHAR(80)",
            "tags": "JSON NOT NULL DEFAULT '[]'",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "expires_at": "DATETIME",
        }.items():
            if column_name not in knowledge_cols:
                conn.execute(f"ALTER TABLE bot_knowledge_files ADD COLUMN {column_name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_files_review_status ON bot_knowledge_files (review_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_files_visibility_scope ON bot_knowledge_files (visibility_scope)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_files_owner_profile_key ON bot_knowledge_files (owner_profile_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_files_expires_at ON bot_knowledge_files (expires_at)")

    test_cols = [row[1] for row in conn.execute("PRAGMA table_info(bot_test_cases)").fetchall()]
    if test_cols:
        for column_name, ddl in {
            "conversation_turns": "JSON NOT NULL DEFAULT '[]'",
            "required_evidence": "BOOLEAN NOT NULL DEFAULT 1",
            "priority": "VARCHAR(20) NOT NULL DEFAULT 'P1'",
            "last_result": "JSON",
            "last_run_at": "DATETIME",
        }.items():
            if column_name not in test_cols:
                conn.execute(f"ALTER TABLE bot_test_cases ADD COLUMN {column_name} {ddl}")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_test_cases_priority ON bot_test_cases (priority)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_channel_adapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adapter_key VARCHAR(80) NOT NULL UNIQUE,
            channel_type VARCHAR(40) NOT NULL,
            name VARCHAR(120) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'enabled',
            event_mode VARCHAR(40) NOT NULL DEFAULT 'webhook',
            auth_scheme VARCHAR(40) NOT NULL DEFAULT 'signed_webhook',
            signing_required BOOLEAN NOT NULL DEFAULT 1,
            rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
            retry_policy JSON NOT NULL DEFAULT '{}',
            capabilities JSON NOT NULL DEFAULT '[]',
            config JSON,
            last_error_message TEXT,
            last_checked_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_channel_adapters_channel_type ON bot_channel_adapters (channel_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_channel_adapters_status ON bot_channel_adapters (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_channel_adapters_created_at ON bot_channel_adapters (created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_channel_adapters_type_status ON bot_channel_adapters (channel_type, status)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_inbound_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id VARCHAR(100) NOT NULL UNIQUE,
            dedup_key VARCHAR(160) NOT NULL UNIQUE,
            channel_key VARCHAR(100) NOT NULL,
            channel_type VARCHAR(40) NOT NULL,
            sender_id VARCHAR(120),
            sender_name VARCHAR(120),
            content TEXT NOT NULL,
            status VARCHAR(30) NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            raw_payload JSON,
            result_payload JSON,
            received_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_channel_key ON bot_inbound_events (channel_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_channel_type ON bot_inbound_events (channel_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_sender_id ON bot_inbound_events (sender_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_status ON bot_inbound_events (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_received_at ON bot_inbound_events (received_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_channel_received ON bot_inbound_events (channel_key, received_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbound_events_status_received ON bot_inbound_events (status, received_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_inbox_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbox_id VARCHAR(80) NOT NULL UNIQUE,
            conversation_id VARCHAR(80) NOT NULL,
            channel_key VARCHAR(100) NOT NULL,
            channel_name VARCHAR(120),
            profile_key VARCHAR(80) NOT NULL,
            title VARCHAR(200) NOT NULL,
            sender_name VARCHAR(120),
            owner_name VARCHAR(120),
            status VARCHAR(30) NOT NULL DEFAULT 'open',
            priority VARCHAR(20) NOT NULL DEFAULT 'P2',
            tags JSON NOT NULL DEFAULT '[]',
            last_message_at DATETIME,
            handoff_required BOOLEAN NOT NULL DEFAULT 0,
            handoff_reason TEXT,
            resolution_summary TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_conversation_id ON bot_inbox_items (conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_channel_key ON bot_inbox_items (channel_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_profile_key ON bot_inbox_items (profile_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_status ON bot_inbox_items (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_priority ON bot_inbox_items (priority)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_last_message_at ON bot_inbox_items (last_message_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_created_at ON bot_inbox_items (created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_status_priority ON bot_inbox_items (status, priority)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_inbox_items_channel_status ON bot_inbox_items (channel_key, status)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            handoff_id VARCHAR(80) NOT NULL UNIQUE,
            inbox_id VARCHAR(80) NOT NULL,
            conversation_id VARCHAR(80) NOT NULL,
            assignee_name VARCHAR(120) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'open',
            reason TEXT,
            requested_by_name VARCHAR(120),
            resolved_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_handoffs_inbox_id ON bot_handoffs (inbox_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_handoffs_conversation_id ON bot_handoffs (conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_handoffs_status ON bot_handoffs (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_handoffs_created_at ON bot_handoffs (created_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_task_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id VARCHAR(80) NOT NULL UNIQUE,
            task_id VARCHAR(80) NOT NULL,
            profile_key VARCHAR(80) NOT NULL,
            trigger_type VARCHAR(30) NOT NULL DEFAULT 'manual',
            status VARCHAR(30) NOT NULL,
            result_payload JSON,
            error_message TEXT,
            started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at DATETIME,
            duration_ms INTEGER
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_task_runs_task_id ON bot_task_runs (task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_task_runs_profile_key ON bot_task_runs (profile_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_task_runs_status ON bot_task_runs (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_task_runs_started_at ON bot_task_runs (started_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_task_runs_task_started ON bot_task_runs (task_id, started_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_task_runs_status_started ON bot_task_runs (status, started_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_release_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_id VARCHAR(80) NOT NULL UNIQUE,
            profile_key VARCHAR(80) NOT NULL,
            version INTEGER NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'draft',
            environment_key VARCHAR(40) NOT NULL DEFAULT 'prod',
            payload JSON NOT NULL DEFAULT '{}',
            test_summary JSON,
            created_by_name VARCHAR(120),
            published_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_release_versions_profile_key ON bot_release_versions (profile_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_release_versions_status ON bot_release_versions (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_release_versions_environment_key ON bot_release_versions (environment_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_release_versions_created_at ON bot_release_versions (created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_release_versions_profile_version ON bot_release_versions (profile_key, version)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_release_versions_env_status ON bot_release_versions (environment_key, status)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_id VARCHAR(80) NOT NULL UNIQUE,
            conversation_id VARCHAR(80),
            message_id INTEGER,
            profile_key VARCHAR(80),
            rating VARCHAR(30) NOT NULL,
            reason VARCHAR(120),
            comment TEXT,
            status VARCHAR(30) NOT NULL DEFAULT 'open',
            created_by_name VARCHAR(120),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_feedback_conversation_id ON bot_feedback (conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_feedback_message_id ON bot_feedback (message_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_feedback_profile_key ON bot_feedback (profile_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_feedback_rating ON bot_feedback (rating)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_feedback_status ON bot_feedback (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_feedback_created_at ON bot_feedback (created_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_knowledge_sync_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id VARCHAR(80) NOT NULL UNIQUE,
            name VARCHAR(160) NOT NULL,
            source_type VARCHAR(50) NOT NULL,
            category VARCHAR(50) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'enabled',
            schedule_type VARCHAR(30) NOT NULL DEFAULT 'manual',
            source_config JSON NOT NULL DEFAULT '{}',
            last_run_at DATETIME,
            result_payload JSON,
            created_by_name VARCHAR(120),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_sync_jobs_source_type ON bot_knowledge_sync_jobs (source_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_sync_jobs_category ON bot_knowledge_sync_jobs (category)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_sync_jobs_status ON bot_knowledge_sync_jobs (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_knowledge_sync_jobs_created_at ON bot_knowledge_sync_jobs (created_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_key VARCHAR(40) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'enabled',
            is_default BOOLEAN NOT NULL DEFAULT 0,
            config JSON NOT NULL DEFAULT '{}',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_environments_status ON bot_environments (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_environments_created_at ON bot_environments (created_at)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_compliance_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_key VARCHAR(80) NOT NULL UNIQUE,
            name VARCHAR(120) NOT NULL,
            policy_type VARCHAR(50) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'enabled',
            action VARCHAR(40) NOT NULL DEFAULT 'warn',
            rules JSON NOT NULL DEFAULT '{}',
            created_by_name VARCHAR(120),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_compliance_policies_policy_type ON bot_compliance_policies (policy_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_compliance_policies_status ON bot_compliance_policies (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_bot_compliance_policies_created_at ON bot_compliance_policies (created_at)")

