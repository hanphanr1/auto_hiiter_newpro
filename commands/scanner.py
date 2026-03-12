# -*- coding: utf-8 -*-
"""Telegram Channel Scanner - integrated into bot."""
import asyncio
import re
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.enums import ParseMode

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberInvalidError,
    ApiIdInvalidError,
)

from config import ADMIN_ID
from i18n import get_lang, t, BRAND, BY, SEP, PROOF_LINK
import logging
import json
import os

logger = logging.getLogger(__name__)

# Debug log
logger.info("=== SCANNER MODULE LOADING ===")

router = Router()

# Add a simple test handler
@router.message(Command("scan_test"))
async def cmd_scan_test(msg: Message):
    logger.info(f"scan_test called by {msg.from_user.id}")
    await msg.answer(f"Scanner hoạt động! ADMIN_ID: {ADMIN_ID}, Your ID: {msg.from_user.id}")

# Scanner config path
SCANNER_DIR = os.path.join(os.path.dirname(__file__), "..", "scraper")
SCANNER_CONFIG = os.path.join(SCANNER_DIR, "config.json")
SCANNER_SESSION = os.path.join(SCANNER_DIR, "scanner_bot_session.session")

# Ensure scraper directory exists
os.makedirs(SCANNER_DIR, exist_ok=True)

# Default regex patterns
DEFAULT_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "url": r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*",
}

# User state storage for multi-step scan
user_states = {}


def load_scanner_config() -> Optional[dict]:
    """Load API credentials from scanner config."""
    if os.path.exists(SCANNER_CONFIG):
        try:
            with open(SCANNER_CONFIG, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load scanner config: {e}")
    return None


def save_scanner_config(api_id: int, api_hash: str, phone: str) -> None:
    """Save API credentials to scanner config."""
    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
    }
    try:
        os.makedirs(os.path.dirname(SCANNER_CONFIG), exist_ok=True)
        with open(SCANNER_CONFIG, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save scanner config: {e}")


async def get_scanner_client():
    """Get or create Telegram client for scanning."""
    config = load_scanner_config()
    if not config:
        return None, None, "Chưa cấu hình API. Admin cần /scan_setup trước."

    client = TelegramClient(SCANNER_SESSION, config["api_id"], config["api_hash"])
    return client, config["phone"], None


async def resolve_channel(client: TelegramClient, channel_input: str):
    """Resolve channel from input."""
    try:
        # Handle numeric IDs
        if channel_input.lstrip("-").isdigit():
            channel_id = int(channel_input)
            return await client.get_entity(channel_id)

        # Handle t.me links
        if "t.me/" in channel_input:
            channel_input = channel_input.split("t.me/")[-1]
            if channel_input.startswith("joinchat/"):
                channel_input = channel_input.replace("joinchat/", "+")

        # Remove @ prefix
        if channel_input.startswith("@"):
            channel_input = channel_input[1:]

        return await client.get_entity(channel_input)
    except Exception as e:
        logger.error(f"Failed to resolve channel: {e}")
        return None


async def scan_channel(client: TelegramClient, entity, limit: int, pattern: str):
    """Scan messages from channel and extract pattern."""
    matches = set()
    scanned = 0
    regex = re.compile(pattern)

    async for message in client.iter_messages(entity, limit=None):
        scanned += 1

        if not message.message:
            continue

        found = regex.findall(message.message)
        if found:
            matches.update(found)

        if len(matches) >= limit:
            break

    return list(matches), scanned


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID


@router.message(Command("scan"))
async def cmd_scan(msg: Message):
    """Start scanner - show menu."""
    uid = msg.from_user.id

    if not is_admin(uid):
        await msg.answer("Chỉ admin mới được dùng tính năng này.")
        return

    config = load_scanner_config()
    if not config:
        await msg.answer(
            f"{SEP}\n"
            "⚠️ <b>Chưa cấu hình Scanner API</b>\n\n"
            f"Dùng /scan_setup để cấu hình API Telegram\n"
            "(api_id, api_hash, phone)"
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    # Show scan menu
    await msg.answer(
        f"{SEP}\n"
        "📡 <b>Telegram Channel Scanner</b>\n\n"
        "Nhập channel để scan:\n"
        "- Username: @channelname\n"
        "- Link: t.me/joinchat/...\n"
        "- ID: -100xxxxxxxxx\n\n"
        "Hoặc gõ /scan_dialogs để chọn từ danh sách\n\n"
        f"Gõ /cancel để hủy"
        f"\n{SEP}",
        parse_mode=ParseMode.HTML,
    )

    # Set user state waiting for channel
    user_states[uid] = {"step": "channel", "action": "scan"}


@router.message(Command("scan_setup"))
async def cmd_scan_setup(msg: Message):
    """Setup scanner API credentials."""
    uid = msg.from_user.id
    logger.info(f"scan_setup called by {uid}, ADMIN_ID={ADMIN_ID}, is_admin={is_admin(uid)}")

    if not is_admin(uid):
        await msg.answer(f"Chỉ admin mới được dùng. Your ID: {uid}, ADMIN_ID: {ADMIN_ID}")
        return

    await msg.answer(
        f"{SEP}\n"
        "⚙️ <b>Scanner Setup</b>\n\n"
        "Nhập api_id (lấy từ my.telegram.org):"
        f"\n{SEP}",
        parse_mode=ParseMode.HTML,
    )

    user_states[uid] = {"step": "api_id", "action": "setup"}
    logger.info(f"User {uid} state set to scan_setup")


@router.message(Command("scan_session"))
async def cmd_scan_session(msg: Message):
    """Create new session for scanner."""
    uid = msg.from_user.id

    if not is_admin(uid):
        await msg.answer("Chỉ admin mới được dùng tính năng này.")
        return

    config = load_scanner_config()
    if not config:
        await msg.answer(
            f"{SEP}\n"
            "⚠️ Chưa cấu hình API. Dùng /scan_setup trước."
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.answer(
        f"{SEP}\n"
        "📱 <b>Tạo Session Mới</b>\n\n"
        f"Phone: <code>{config.get('phone', 'N/A')}</code>\n\n"
        "Đang kết nối Telegram..."
        f"\n{SEP}",
        parse_mode=ParseMode.HTML,
    )

    client = None
    try:
        client = TelegramClient(SCANNER_SESSION, config["api_id"], config["api_hash"])
        await client.connect()

        if await client.is_user_authorized():
            await msg.answer(
                f"{SEP}\n"
                "✅ <b>Đã đăng nhập</b>\n\n"
                "Session còn hiệu lực."
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.answer(
                f"{SEP}\n"
                "📱 <b>Đăng nhập mới</b>\n\n"
                "Gửi code request..."
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
            await client.send_code_request(config["phone"])

            await msg.answer(
                f"{SEP}\n"
                "🔢 <b>Nhập code</b>\n\n"
                "Nhập mã xác thực từ Telegram:"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
            user_states[uid] = {"step": "auth_code", "action": "login", "client": client}

    except Exception as e:
        logger.error(f"Session error: {e}")
        await msg.answer(
            f"{SEP}\n"
            f"❌ Lỗi: {str(e)}"
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
    finally:
        if client:
            await client.disconnect()


@router.message(Command("scan_dialogs"))
async def cmd_scan_dialogs(msg: Message):
    """List available dialogs/channels."""
    uid = msg.from_user.id

    if not is_admin(uid):
        await msg.answer("Chỉ admin mới được dùng tính năng này.")
        return

    client, phone, error = await get_scanner_client()
    if error:
        await msg.answer(f"{SEP}\n{error}\n{SEP}", parse_mode=ParseMode.HTML)
        return

    try:
        await client.connect()

        if not await client.is_user_authorized():
            await msg.answer(
                f"{SEP}\n"
                "⚠️ Chưa đăng nhập. Dùng /scan_session để đăng nhập."
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
            return

        await msg.answer(
            f"{SEP}\n"
            "📋 <b>Đang lấy danh sách...</b>"
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )

        dialogs = await client.get_dialogs(limit=50)

        # Filter channels/groups
        channels = []
        for dialog in dialogs:
            entity = dialog.entity
            if hasattr(entity, "broadcast") and entity.broadcast:
                channels.append((entity, entity.title, "Channel"))
            elif hasattr(entity, "megagroup") and entity.megagroup:
                channels.append((entity, entity.title, "Supergroup"))

        if not channels:
            await msg.answer(
                f"{SEP}\n"
                "Không tìm thấy channel nào."
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
            return

        # Build list
        text = f"{SEP}\n"
        text += "📋 <b>Danh sách Channels:</b>\n\n"

        for i, (entity, title, gtype) in enumerate(channels[:20], 1):
            text += f"{i}. {title} ({gtype})\n"

        text += f"\nDùng /scan_chọn <số> để chọn channel"
        text += f"\n{SEP}"

        # Save to state for selection
        user_states[uid] = {"step": "select_dialog", "action": "select", "dialogs": channels[:20]}

        await msg.answer(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"List dialogs error: {e}")
        await msg.answer(
            f"{SEP}\n"
            f"❌ Lỗi: {str(e)}"
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
    finally:
        if client:
            await client.disconnect()


@router.message(Command("scan_chọn"))
async def cmd_scan_chon(msg: Message):
    """Select channel from list."""
    uid = msg.from_user.id

    if not is_admin(uid):
        await msg.answer("Chỉ admin mới được dùng tính năng này.")
        return

    state = user_states.get(uid, {})

    if state.get("step") != "select_dialog" or state.get("action") != "select":
        await msg.answer(
            f"{SEP}\n"
            "Dùng /scan_dialogs trước để xem danh sách."
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        choice = int(msg.text.replace("/scan_chọn", "").strip())
        if choice < 1 or choice > len(state["dialogs"]):
            await msg.answer(f"Số không hợp lệ (1-{len(state['dialogs'])})")
            return

        entity, title, gtype = state["dialogs"][choice - 1]

        # Now ask for limit
        user_states[uid] = {
            "step": "limit",
            "action": "scan",
            "entity": entity,
            "title": title,
        }

        await msg.answer(
            f"{SEP}\n"
            f"✅ <b>Channel:</b> {title}\n\n"
            "Nhập số lượng kết quả muốn lấy:"
            f"\n{SEP}",
            parse_mode=ParseMode.HTML,
        )

    except ValueError:
        await msg.answer("Nhập số hợp lệ.")


@router.message(Command("cancel"))
async def cmd_cancel(msg: Message):
    """Cancel current operation."""
    uid = msg.from_user.id
    if uid in user_states:
        del user_states[uid]
    await msg.answer(
        f"{SEP}\n"
        "❌ <b>Đã hủy</b>"
        f"\n{SEP}",
        parse_mode=ParseMode.HTML,
    )


@router.message()
async def handle_scan_input(msg: Message):
    """Handle text input for scan workflow."""
    uid = msg.from_user.id
    text = (msg.text or "").strip()

    if not text or not msg.text:
        return

    state = user_states.get(uid, {})
    logger.info(f"handle_scan_input called by {uid}, state={state}, text={text[:50]}")

    # === SETUP FLOW ===
    if state.get("action") == "setup":
        if state.get("step") == "api_id":
            try:
                api_id = int(text)
                user_states[uid]["api_id"] = api_id
                user_states[uid]["step"] = "api_hash"
                await msg.answer(
                    f"{SEP}\n"
                    "Nhập api_hash:"
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )
            except ValueError:
                await msg.answer("Api_id phải là số. Thử lại:")

        elif state.get("step") == "api_hash":
            api_hash = text
            user_states[uid]["api_hash"] = api_hash
            user_states[uid]["step"] = "phone"
            await msg.answer(
                f"{SEP}\n"
                "Nhập số điện thoại (có mã quốc gia, vd +84...):"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )

        elif state.get("step") == "phone":
            phone = text
            config = load_scanner_config() or {}
            save_scanner_config(
                user_states[uid].get("api_id"),
                user_states[uid].get("api_hash"),
                phone,
            )
            del user_states[uid]

            await msg.answer(
                f"{SEP}\n"
                "✅ <b>Đã lưu cấu hình!</b>\n\n"
                f"Phone: <code>{phone}</code>\n\n"
                "Tiếp theo dùng /scan_session để đăng nhập Telegram."
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )

    # === LOGIN FLOW ===
    elif state.get("action") == "login" and state.get("step") == "auth_code":
        client = state.get("client")
        if not client:
            await msg.answer("Lỗi client. Dùng /scan_session lại.")
            return

        try:
            await client.sign_in(config.get("phone"), text)
            await msg.answer(
                f"{SEP}\n"
                "✅ <b>Đăng nhập thành công!</b>\n\n"
                "Giờ có thể dùng /scan để quét channel."
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
        except SessionPasswordNeededError:
            user_states[uid]["step"] = "2fa"
            await msg.answer(
                f"{SEP}\n"
                "🔐 <b>2FA Password:</b>\n\n"
                "Nhập mật khẩu 2FA:"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            await msg.answer(
                f"{SEP}\n"
                f"❌ Lỗi đăng nhập: {str(e)}"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
        finally:
            await client.disconnect()

        if uid in user_states:
            del user_states[uid]

    elif state.get("action") == "login" and state.get("step") == "2fa":
        client = state.get("client")
        if client:
            try:
                await client.sign_in(password=text)
                await msg.answer(
                    f"{SEP}\n"
                    "✅ <b>Đăng nhập 2FA thành công!</b>"
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                await msg.answer(
                    f"{SEP}\n"
                    f"❌ Lỗi: {str(e)}"
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )
            finally:
                await client.disconnect()
        if uid in user_states:
            del user_states[uid]

    # === SCAN FLOW ===
    elif state.get("action") == "scan":
        if state.get("step") == "channel":
            # User entered channel input
            client, phone, error = await get_scanner_client()
            if error:
                await msg.answer(f"{SEP}\n{error}\n{SEP}", parse_mode=ParseMode.HTML)
                return

            await msg.answer(
                f"{SEP}\n"
                "🔄 <b>Đang kết nối...</b>"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )

            try:
                await client.connect()

                if not await client.is_user_authorized():
                    await msg.answer(
                        f"{SEP}\n"
                        "⚠️ Chưa đăng nhập. Dùng /scan_session."
                        f"\n{SEP}",
                        parse_mode=ParseMode.HTML,
                    )
                    return

                entity = await resolve_channel(client, text)

                if not entity:
                    await msg.answer(
                        f"{SEP}\n"
                        "❌ Không tìm thấy channel. Thử link khác hoặc dùng /scan_dialogs."
                        f"\n{SEP}",
                        parse_mode=ParseMode.HTML,
                    )
                    return

                user_states[uid] = {
                    "step": "limit",
                    "action": "scan",
                    "entity": entity,
                    "title": getattr(entity, "title", "Unknown"),
                    "client": client,
                }

                await msg.answer(
                    f"{SEP}\n"
                    f"✅ <b>Channel:</b> {getattr(entity, 'title', 'Unknown')}\n\n"
                    "Nhập số lượng kết quả:"
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )

            except Exception as e:
                logger.error(f"Scan error: {e}")
                await msg.answer(
                    f"{SEP}\n"
                    f"❌ Lỗi: {str(e)}"
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )

        elif state.get("step") == "limit":
            try:
                limit = int(text)
                if limit < 1:
                    limit = 10
            except ValueError:
                limit = 10

            entity = state.get("entity")
            title = state.get("title", "Unknown")
            client = state.get("client")

            if not client or not entity:
                await msg.answer(
                    f"{SEP}\n"
                    "Lỗi state. Dùng /scan lại."
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Ask for regex pattern
            user_states[uid] = {
                "step": "pattern",
                "action": "scan",
                "entity": entity,
                "title": title,
                "client": client,
                "limit": limit,
            }

            await msg.answer(
                f"{SEP}\n"
                f"✅ <b>Channel:</b> {title}\n"
                f"Limit: {limit}\n\n"
                "✏️ <b>Nhập chuỗi regex cần scan:</b>\n"
                "(ví dụ: email, url, hoặc regex tùy chỉnh)"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )

        elif state.get("step") == "pattern":
            # User entered regex pattern
            pattern = text.strip()
            pattern_name = "Kết quả"

            entity = state.get("entity")
            title = state.get("title", "Unknown")
            client = state.get("client")
            limit = state.get("limit", 10)

            await msg.answer(
                f"{SEP}\n"
                f"🔍 <b>Đang scan {pattern_name}...</b>\n"
                f"Channel: {title}\n"
                f"Limit: {limit}"
                f"\n{SEP}",
                parse_mode=ParseMode.HTML,
            )

            try:
                results, scanned = await scan_channel(client, entity, limit, pattern)

                if not results:
                    await msg.answer(
                        f"{SEP}\n"
                        f"✅ <b>Scan hoàn tất</b>\n\n"
                        f"Đã quét {scanned} tin nhắn\n"
                        f"Không tìm thấy {pattern_name} nào."
                        f"\n{SEP}",
                        parse_mode=ParseMode.HTML,
                    )
                elif len(results) <= 10:
                    # Send directly in chat
                    result_list = "\n".join(f"<code>{r}</code>" for r in results)
                    await msg.answer(
                        f"{SEP}\n"
                        f"✅ <b>Scan hoàn tất</b>\n\n"
                        f"Đã quét {scanned} tin nhắn\n"
                        f"Tìm thấy {len(results)} {pattern_name}:\n\n"
                        f"{result_list}"
                        f"\n{SEP}",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    # Send as file
                    out = "\n".join(results)
                    name = f"{title}_{pattern_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

                    await msg.answer_document(
                        BufferedInputFile(out.encode("utf-8"), filename=name),
                        caption=(
                            f"{SEP}\n"
                            f"✅ <b>Scan hoàn tất</b>\n\n"
                            f"Đã quét {scanned} tin nhắn\n"
                            f"Tìm thấy {len(results)} {pattern_name}"
                            f"\n{SEP}"
                        ),
                        parse_mode=ParseMode.HTML,
                    )

            except Exception as e:
                logger.error(f"Scan results error: {e}")
                await msg.answer(
                    f"{SEP}\n"
                    f"❌ Lỗi scan: {str(e)}"
                    f"\n{SEP}",
                    parse_mode=ParseMode.HTML,
                )
            finally:
                if client:
                    await client.disconnect()

            if uid in user_states:
                del user_states[uid]
