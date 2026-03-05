import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_GROUP_ID = int(os.environ.get("ALLOWED_GROUP_ID", "0"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1"))
PROOF_CHANNEL = os.environ.get("PROOF_CHANNEL", "@private_hiiter")
PROOF_LINK = "https://t.me/tptth_proof"
