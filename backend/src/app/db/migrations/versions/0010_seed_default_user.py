"""Seed default admin user.

Revision ID: 0010_seed_default_user
Revises: 0009_job_glossary_user_id
Creates an admin user from env vars (ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_FULL_NAME).
Idempotent: only inserts if the email does not already exist.
Password is hashed at migration time — hash is never stored in the file.
"""
from __future__ import annotations

import os
from typing import Union

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "0010_seed_default_user"
down_revision: Union[str, None] = "0009_job_glossary_user_id"
branch_labels = None
depends_on = None


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def upgrade() -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin123@gmail.com")
    password = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    full_name = os.environ.get("ADMIN_FULL_NAME", "Admin User")
    hashed = _hash_password(password)

    op.execute(
        f"""
        INSERT INTO users (id, email, hashed_password, full_name, is_active, is_superuser, email_verified, created_at)
        VALUES (
            '00000000-0000-0000-0000-000000000001',
            '{email}',
            '{hashed}',
            '{full_name}',
            true,
            true,
            true,
            now()
        )
        ON CONFLICT (email) DO NOTHING
        """
    )


def downgrade() -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin123@gmail.com")
    op.execute(f"DELETE FROM users WHERE email = '{email}'")
