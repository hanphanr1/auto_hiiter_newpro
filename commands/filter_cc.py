# -*- coding: utf-8 -*-
"""CC filter: document (.txt) → reply with filtered .txt; text → reply with CC lines."""
import io
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode

from cc_filter import extract_cc_lines

router = Router()

_BRAND = "TPTTH PRIVATE HITTER"
_BY = "by @idkbroo_fr"

@router.message(F.document, F.document.file_name.endswith(".txt"))
async def on_document_txt(msg: Message):
    doc = msg.document
    try:
        file = await msg.bot.get_file(doc.file_id)
        data = await msg.bot.download_file(file.file_path)
        text = data.read().decode("utf-8", errors="replace")
    except Exception as e:
        await msg.answer(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>Error</b>\nKhông đọc được file: {e}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
        )
        return
    lines = extract_cc_lines(text)
    if not lines:
        await msg.answer(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ Không tìm thấy CC nào trong file.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        )
        return
    out = "\n".join(lines)
    name = (doc.file_name or "filtered").rsplit(".", 1)[0] + "_filtered.txt"
    await msg.answer_document(
        BufferedInputFile(out.encode("utf-8"), filename=name),
        caption=(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <b>{_BRAND}</b> — CC Filter\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Lọc ra <b>{len(lines)}</b> CC từ <code>{doc.file_name}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <b>{_BY}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        parse_mode=ParseMode.HTML,
    )

@router.message(F.text)
async def on_text(msg: Message):
    text = (msg.text or "").strip()
    if not text or text.startswith("/"):
        return
    lines = extract_cc_lines(text)
    if not lines:
        return
    if len(lines) <= 10:
        header = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <b>{_BRAND}</b> — CC Filter\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        body = "\n".join(f"<code>{l}</code>" for l in lines)
        footer = (
            f"\n\n✅ <b>{len(lines)}</b> CC found\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  <b>{_BY}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await msg.answer(header + body + footer, parse_mode=ParseMode.HTML)
    else:
        out = "\n".join(lines)
        name = "filtered_cc.txt"
        await msg.answer_document(
            BufferedInputFile(out.encode("utf-8"), filename=name),
            caption=(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  <b>{_BRAND}</b> — CC Filter\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ Lọc ra <b>{len(lines)}</b> CC\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  <b>{_BY}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            parse_mode=ParseMode.HTML,
        )
