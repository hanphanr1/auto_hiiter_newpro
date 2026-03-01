# -*- coding: utf-8 -*-
"""/addproxy, /removeproxy, /proxy commands."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from proxy_manager import (
    get_user_proxies, add_user_proxy, remove_user_proxy,
    check_proxy_alive, check_proxies_batch,
)

router = Router()

_BRAND = "TPTTH PRIVATE HITTER"
_BY = "by @idkbroo_fr"
_SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━"

@router.message(Command("addproxy"))
async def cmd_addproxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id

    if len(args) < 2:
        proxies = get_user_proxies(uid)
        lst = "\n".join(f"  ├ <code>{p}</code>" for p in proxies[:10]) or "  └ Empty"
        await msg.answer(
            f"{_SEP}\n"
            f"  <b>{_BRAND}</b> — Proxy\n"
            f"{_SEP}\n\n"
            f"🔌 <b>Your Proxies</b> ({len(proxies)}):\n{lst}\n\n"
            f"🔹 <code>/addproxy host:port:user:pass</code>\n"
            f"🔹 <code>/removeproxy all</code>\n"
            f"🔹 <code>/proxy check</code>\n\n"
            f"{_SEP}\n"
            f"  <b>{_BY}</b>\n"
            f"{_SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [l.strip() for l in args[1].strip().split("\n") if l.strip()]
    if not lines:
        await msg.answer(f"{_SEP}\n❌ Không có proxy hợp lệ.\n{_SEP}")
        return

    status_msg = await msg.answer(f"⏳ Checking {len(lines)} proxy...")
    results = await check_proxies_batch(lines)
    alive = [r for r in results if r["status"] == "alive"]
    for r in alive:
        add_user_proxy(uid, r["proxy"])

    out = (
        f"{_SEP}\n"
        f"  <b>{_BRAND}</b> — Add Proxy\n"
        f"{_SEP}\n\n"
        f"✅ Alive: <b>{len(alive)}</b>/{len(lines)}\n"
        f"❌ Dead: <b>{len(lines) - len(alive)}</b>/{len(lines)}\n"
    )
    if alive:
        out += "\n🔹 Added:\n"
        for r in alive[:5]:
            out += f"  ├ <code>{r['proxy']}</code> ({r['response_time']})\n"
        if len(alive) > 5:
            out += f"  └ ...+{len(alive) - 5} more\n"
    out += f"\n{_SEP}\n  <b>{_BY}</b>\n{_SEP}"
    await status_msg.edit_text(out, parse_mode=ParseMode.HTML)

@router.message(Command("removeproxy"))
async def cmd_removeproxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id

    if len(args) < 2:
        await msg.answer(
            f"{_SEP}\n"
            f"  <b>{_BRAND}</b> — Remove Proxy\n"
            f"{_SEP}\n\n"
            f"🔹 <code>/removeproxy host:port:user:pass</code>\n"
            f"🔹 <code>/removeproxy all</code>\n\n"
            f"{_SEP}\n  <b>{_BY}</b>\n{_SEP}",
            parse_mode=ParseMode.HTML,
        )
        return

    target = args[1].strip()
    if target.lower() == "all":
        count = len(get_user_proxies(uid))
        remove_user_proxy(uid, "all")
        await msg.answer(
            f"{_SEP}\n✅ Đã xóa tất cả <b>{count}</b> proxy.\n{_SEP}",
            parse_mode=ParseMode.HTML,
        )
    else:
        ok = remove_user_proxy(uid, target)
        if ok:
            await msg.answer(
                f"{_SEP}\n✅ Đã xóa <code>{target}</code>\n{_SEP}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.answer(f"{_SEP}\n❌ Không tìm thấy proxy.\n{_SEP}")

@router.message(Command("proxy"))
async def cmd_proxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id
    proxies = get_user_proxies(uid)

    if len(args) >= 2 and args[1].strip().lower() == "check":
        if not proxies:
            await msg.answer(
                f"{_SEP}\n❌ Chưa có proxy. Thêm bằng /addproxy\n{_SEP}"
            )
            return
        status_msg = await msg.answer(f"⏳ Checking {len(proxies)} proxy...")
        results = await check_proxies_batch(proxies)
        alive = [r for r in results if r["status"] == "alive"]
        dead = [r for r in results if r["status"] == "dead"]
        out = (
            f"{_SEP}\n"
            f"  <b>{_BRAND}</b> — Proxy Check\n"
            f"{_SEP}\n\n"
            f"✅ Alive: <b>{len(alive)}</b>  ❌ Dead: <b>{len(dead)}</b>\n"
        )
        if alive:
            out += "\n🟢 Alive:\n"
            for r in alive[:5]:
                out += f"  ├ <code>{r['proxy']}</code> — {r['response_time']} — {r.get('country','')}\n"
        if dead:
            out += "\n🔴 Dead:\n"
            for r in dead[:3]:
                out += f"  ├ <code>{r['proxy']}</code> — {r.get('error','')}\n"
        out += f"\n{_SEP}\n  <b>{_BY}</b>\n{_SEP}"
        await status_msg.edit_text(out, parse_mode=ParseMode.HTML)
    else:
        lst = "\n".join(f"  ├ <code>{p}</code>" for p in proxies[:10]) or "  └ Empty"
        await msg.answer(
            f"{_SEP}\n"
            f"  <b>{_BRAND}</b> — Proxy\n"
            f"{_SEP}\n\n"
            f"🔌 <b>Proxies</b> ({len(proxies)}):\n{lst}\n\n"
            f"<code>/proxy check</code> — check all\n\n"
            f"{_SEP}\n  <b>{_BY}</b>\n{_SEP}",
            parse_mode=ParseMode.HTML,
        )
