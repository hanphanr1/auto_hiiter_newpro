# -*- coding: utf-8 -*-
"""/addproxy, /removeproxy, /proxy commands."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from filters import IsAdminOrAllowed
from aiogram.enums import ParseMode

from proxy_manager import (
    get_user_proxies, add_user_proxy, remove_user_proxy,
    check_proxy_alive, check_proxies_batch,
)
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


@router.message(Command("addproxy"), IsAdminOrAllowed())
async def cmd_addproxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id

    if len(args) < 2:
        proxies = get_user_proxies(uid)
        lst = "\n".join(f"  ├ <code>{p}</code>" for p in proxies[:10]) or "  └ Empty"
        await msg.answer(
            f"{_HEADER}\n"
            f"  🔌 <b>{t(uid, 'proxy_title')}</b>\n"
            f"{SEP}\n\n"
            f"📋 <b>{t(uid, 'proxy_your_proxies')}</b> ({len(proxies)}):\n{lst}\n\n"
            f"🔹 <code>/addproxy host:port:user:pass</code>\n"
            f"🔹 <code>/removeproxy all</code>\n"
            f"🔹 <code>/proxy check</code>"
            f"{_FOOTER}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    lines = [l.strip() for l in args[1].strip().split("\n") if l.strip()]
    if not lines:
        await msg.answer(
            f"{SEP}\n{t(uid, 'proxy_no_valid')}\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    status_msg = await msg.answer(t(uid, "proxy_checking", count=len(lines)))
    results = await check_proxies_batch(lines)
    alive = [r for r in results if r["status"] == "alive"]
    for r in alive:
        add_user_proxy(uid, r["proxy"])

    out = (
        f"{_HEADER}\n"
        f"  🔌 <b>{t(uid, 'proxy_add_title')}</b>\n"
        f"{SEP}\n\n"
        f"✅ {t(uid, 'proxy_alive')}: <b>{len(alive)}</b>/{len(lines)}\n"
        f"❌ {t(uid, 'proxy_dead')}: <b>{len(lines) - len(alive)}</b>/{len(lines)}\n"
    )
    if alive:
        out += f"\n🟢 {t(uid, 'proxy_added')}:\n"
        for r in alive[:5]:
            out += f"  ├ <code>{r['proxy']}</code> ({r['response_time']})\n"
        if len(alive) > 5:
            out += f"  └ ...+{len(alive) - 5} more\n"
    out += _FOOTER
    await status_msg.edit_text(out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@router.message(Command("removeproxy"), IsAdminOrAllowed())
async def cmd_removeproxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id

    if len(args) < 2:
        await msg.answer(
            f"{_HEADER}\n"
            f"  🔌 <b>{t(uid, 'proxy_rm_title')}</b>\n"
            f"{SEP}\n\n"
            f"🔹 <code>/removeproxy host:port:user:pass</code>\n"
            f"🔹 <code>/removeproxy all</code>"
            f"{_FOOTER}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    target = args[1].strip()
    if target.lower() == "all":
        count = len(get_user_proxies(uid))
        remove_user_proxy(uid, "all")
        await msg.answer(
            f"{SEP}\n{t(uid, 'proxy_removed_all', count=count)}\n{SEP}",
            parse_mode=ParseMode.HTML,
        )
    else:
        ok = remove_user_proxy(uid, target)
        if ok:
            await msg.answer(
                f"{SEP}\n{t(uid, 'proxy_removed', proxy=target)}\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.answer(
                f"{SEP}\n{t(uid, 'proxy_not_found')}\n{SEP}",
                parse_mode=ParseMode.HTML,
            )


@router.message(Command("proxy"), IsAdminOrAllowed())
async def cmd_proxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id
    proxies = get_user_proxies(uid)

    if len(args) >= 2 and args[1].strip().lower() == "check":
        if not proxies:
            await msg.answer(
                f"{SEP}\n{t(uid, 'proxy_empty')}\n{SEP}",
                parse_mode=ParseMode.HTML,
            )
            return
        status_msg = await msg.answer(t(uid, "proxy_checking", count=len(proxies)))
        results = await check_proxies_batch(proxies)
        alive = [r for r in results if r["status"] == "alive"]
        dead = [r for r in results if r["status"] == "dead"]
        out = (
            f"{_HEADER}\n"
            f"  🔌 <b>{t(uid, 'proxy_check_title')}</b>\n"
            f"{SEP}\n\n"
            f"✅ {t(uid, 'proxy_alive')}: <b>{len(alive)}</b>  "
            f"❌ {t(uid, 'proxy_dead')}: <b>{len(dead)}</b>\n"
        )
        if alive:
            out += "\n🟢 Online:\n"
            for r in alive[:5]:
                out += f"  ├ <code>{r['proxy']}</code> — {r['response_time']} — {r.get('country', '')}\n"
        if dead:
            out += "\n🔴 Offline:\n"
            for r in dead[:3]:
                out += f"  ├ <code>{r['proxy']}</code> — {r.get('error', '')}\n"
        out += _FOOTER
        await status_msg.edit_text(out, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    else:
        lst = "\n".join(f"  ├ <code>{p}</code>" for p in proxies[:10]) or "  └ Empty"
        await msg.answer(
            f"{_HEADER}\n"
            f"  🔌 <b>{t(uid, 'proxy_title')}</b>\n"
            f"{SEP}\n\n"
            f"📋 <b>{t(uid, 'proxy_your_proxies')}</b> ({len(proxies)}):\n{lst}\n\n"
            f"<code>/proxy check</code> — {t(uid, 'proxy_check_all')}"
            f"{_FOOTER}",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
