# -*- coding: utf-8 -*-
"""/addproxy, /removeproxy, /proxy commands (from autohitter)."""
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from proxy_manager import (
    get_user_proxies, add_user_proxy, remove_user_proxy,
    check_proxy_alive, check_proxies_batch,
)

router = Router()

@router.message(Command("addproxy"))
async def cmd_addproxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id

    if len(args) < 2:
        proxies = get_user_proxies(uid)
        lst = "\n".join(f"  • <code>{p}</code>" for p in proxies[:10]) or "  Chưa có proxy"
        await msg.answer(
            f"<b>Proxy Manager</b>\n\n"
            f"Proxies của bạn ({len(proxies)}):\n{lst}\n\n"
            "<b>Thêm:</b> <code>/addproxy host:port:user:pass</code>\n"
            "<b>Xóa:</b> <code>/removeproxy proxy</code> hoặc <code>/removeproxy all</code>\n"
            "<b>Check:</b> <code>/proxy check</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [l.strip() for l in args[1].strip().split("\n") if l.strip()]
    if not lines:
        await msg.answer("Không có proxy hợp lệ.")
        return

    status_msg = await msg.answer(f"Checking {len(lines)} proxy...")
    results = await check_proxies_batch(lines)
    alive = [r for r in results if r["status"] == "alive"]
    for r in alive:
        add_user_proxy(uid, r["proxy"])

    out = (
        f"<b>Kết quả</b>\n"
        f"Alive: {len(alive)}/{len(lines)}\n"
        f"Dead: {len(lines) - len(alive)}/{len(lines)}\n"
    )
    if alive:
        out += "\nĐã thêm:\n"
        for r in alive[:5]:
            out += f"  • <code>{r['proxy']}</code> ({r['response_time']})\n"
        if len(alive) > 5:
            out += f"  • ...và {len(alive) - 5} proxy khác\n"
    await status_msg.edit_text(out, parse_mode=ParseMode.HTML)

@router.message(Command("removeproxy"))
async def cmd_removeproxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id

    if len(args) < 2:
        await msg.answer(
            "<b>Xóa proxy</b>\n"
            "<code>/removeproxy proxy</code> hoặc <code>/removeproxy all</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    target = args[1].strip()
    if target.lower() == "all":
        count = len(get_user_proxies(uid))
        remove_user_proxy(uid, "all")
        await msg.answer(f"Đã xóa tất cả {count} proxy.")
    else:
        ok = remove_user_proxy(uid, target)
        if ok:
            await msg.answer(f"Đã xóa <code>{target}</code>", parse_mode=ParseMode.HTML)
        else:
            await msg.answer("Không tìm thấy proxy.")

@router.message(Command("proxy"))
async def cmd_proxy(msg: Message):
    args = (msg.text or "").split(maxsplit=1)
    uid = msg.from_user.id
    proxies = get_user_proxies(uid)

    if len(args) >= 2 and args[1].strip().lower() == "check":
        if not proxies:
            await msg.answer("Chưa có proxy. Thêm bằng /addproxy")
            return
        status_msg = await msg.answer(f"Checking {len(proxies)} proxy...")
        results = await check_proxies_batch(proxies)
        alive = [r for r in results if r["status"] == "alive"]
        dead = [r for r in results if r["status"] == "dead"]
        out = f"<b>Proxy Check</b>\nAlive: {len(alive)} | Dead: {len(dead)}\n"
        if alive:
            out += "\nAlive:\n"
            for r in alive[:5]:
                out += f"  • <code>{r['proxy']}</code> – {r['response_time']} – {r.get('country','')}\n"
        if dead:
            out += "\nDead:\n"
            for r in dead[:3]:
                out += f"  • <code>{r['proxy']}</code> – {r.get('error','')}\n"
        await status_msg.edit_text(out, parse_mode=ParseMode.HTML)
    else:
        lst = "\n".join(f"  • <code>{p}</code>" for p in proxies[:10]) or "  Chưa có proxy"
        await msg.answer(
            f"<b>Proxies ({len(proxies)})</b>\n{lst}\n\n"
            "<code>/proxy check</code> – check tất cả",
            parse_mode=ParseMode.HTML,
        )
