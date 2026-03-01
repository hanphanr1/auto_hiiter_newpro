import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_GROUP_ID = int(os.environ.get("ALLOWED_GROUP_ID", "0"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
PROOF_CHANNEL = os.environ.get("PROOF_CHANNEL", "@private_hiiter")
