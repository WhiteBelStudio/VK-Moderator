CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('moderator', 'admin')),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moderation_restrictions (
    user_id INTEGER PRIMARY KEY,
    restriction_type TEXT NOT NULL CHECK (restriction_type IN ('mute')),
    expires_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moderation_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_moderation_actions_target
    ON moderation_actions(target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_moderation_actions_actor
    ON moderation_actions(actor_id, created_at DESC);
