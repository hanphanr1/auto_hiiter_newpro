import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ALLOWED_GROUP_ID = int(os.environ.get("ALLOWED_GROUP_ID", "0"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "1"))

# Set PROOF_CHANNEL = "-100123456789" hoặc @username để gửi proof khi charge thành công
# Để trống nếu không muốn gửi proof
PROOF_CHANNEL = os.environ.get("PROOF_CHANNEL", "")
PROOF_LINK = os.environ.get("PROOF_LINK", "https://t.me/tptth_proof")
