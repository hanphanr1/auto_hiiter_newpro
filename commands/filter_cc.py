# -*- coding: utf-8 -*-
"""CC filter: document (.txt) → reply with filtered .txt; text → reply with CC lines."""
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode

from cc_filter import extract_cc_lines
from i18n import get_lang, t, BRAND, BY, SEP, PROOF_LINK

router = Router()

_HEADER = (
    f"╔{'═' * 28}╗\n"
    f"    ⚡ <b>{BRAND}</b> ⚡\n"
    f"╚{'═' * 28}╝"
)

_FOOTER = (
    f"\n📢 <a href=\"{PROOF_LINK}\">Proof</a> | ⚡ <b>{BY}</b>\n"
    f"{SEP}"
)


@router.message(F.document, F.document.file_name.endswith(".txt"))
async def on_document_txt(msg: Message):
    uid = msg.from_user.id
    doc = msg.document
    try:
        file = await msg.bot.get_file(doc.file_id)
        data = await msg.bot.download_file(file.file_path)
        text = data.read().decode("utf-8", errors="replace")
    except Exception as e:
        await msg.answer(
            f"{SEP}\n{t(uid, 'filter_error', error=str(e))}\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = extract_cc_lines(text)
    if not lines:
        await msg.answer(
            f"{SEP}\n{t(uid, 'filter_no_cc')}\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    out = "\n".join(lines)
    name = (doc.file_name or "filtered").rsplit(".", 1)[0] + "_filtered.txt"
    await msg.answer_document(
        BufferedInputFile(out.encode("utf-8"), filename=name),
        caption=(
            f"{_HEADER}\n"
            f"  🔎 <b>{t(uid, 'filter_title')}</b>\n"
            f"{SEP}\n\n"
            f"{t(uid, 'filter_result', count=len(lines), file=doc.file_name)}"
            f"{_FOOTER}"
        ),
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text)
async def on_text(msg: Message):
    text = (msg.text or "").strip()
    if not text or text.startswith("/"):
        return
    uid = msg.from_user.id
    lines = extract_cc_lines(text)
    if not lines:
        return

    if len(lines) <= 10:
        header = (
            f"{_HEADER}\n"
            f"  🔎 <b>{t(uid, 'filter_title')}</b>\n"
            f"{SEP}\n\n"
        )
        body = "\n".join(f"<code>{l}</code>" for l in lines)
        footer = (
            f"\n\n{t(uid, 'filter_text_result', count=len(lines))}"
            f"{_FOOTER}"
        )
        await msg.answer(header + body + footer, parse_mode=ParseMode.HTML)
    else:
        out = "\n".join(lines)
        name = "filtered_cc.txt"
        await msg.answer_document(
            BufferedInputFile(out.encode("utf-8"), filename=name),
            caption=(
                f"{_HEADER}\n"
                f"  🔎 <b>{t(uid, 'filter_title')}</b>\n"
                f"{SEP}\n\n"
                f"{t(uid, 'filter_text_result', count=len(lines))}"
                f"{_FOOTER}"
            ),
            parse_mode=ParseMode.HTML,
        )
