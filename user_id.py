# -*- coding: utf-8 -*-
"""User ID management - stores authorized users in source code."""

import os
import json
from typing import Set

# File to store authorized user IDs (in source code to persist across deploys)
USER_ID_FILE = os.path.join(os.path.dirname(__file__), "allowed_users.json")

# Default allowed users (will be loaded from file if exists)
_allowed_users: Set[int] = set()


def load_users() -> Set[int]:
    """Load allowed users from file."""
    global _allowed_users
    if os.path.exists(USER_ID_FILE):
        try:
            with open(USER_ID_FILE, "r") as f:
                data = json.load(f)
                _allowed_users = set(data.get("users", []))
        except (json.JSONDecodeError, IOError):
            _allowed_users = set()
    return _allowed_users


def save_users() -> None:
    """Save allowed users to file."""
    with open(USER_ID_FILE, "w") as f:
        json.dump({"users": list(_allowed_users)}, f, indent=2)


def get_allowed_users() -> Set[int]:
    """Get all allowed user IDs."""
    if not _allowed_users:
        load_users()
    return _allowed_users


def is_user_allowed(user_id: int) -> bool:
    """Check if user is allowed to use the bot."""
    return user_id in get_allowed_users()


def add_user(user_id: int) -> bool:
    """Add a user to allowed list. Returns True if added, False if already exists."""
    users = get_allowed_users()
    if user_id not in users:
        users.add(user_id)
        save_users()
        return True
    return False


def remove_user(user_id: int) -> bool:
    """Remove a user from allowed list. Returns True if removed, False if not found."""
    users = get_allowed_users()
    if user_id in users:
        users.discard(user_id)
        save_users()
        return True
    return False
