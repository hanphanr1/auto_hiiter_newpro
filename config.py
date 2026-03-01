import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
# Optional: restrict to group or owner (set to 0 to allow all)
ALLOWED_GROUP_ID = int(os.environ.get("ALLOWED_GROUP_ID", "0"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
