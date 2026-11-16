PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE organizations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(email) > 0 AND email = trim(email)),
    display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE organization_memberships (
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ('admin', 'member')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, user_id)
);

CREATE INDEX organization_memberships_user_idx ON organization_memberships(user_id);

COMMIT;
