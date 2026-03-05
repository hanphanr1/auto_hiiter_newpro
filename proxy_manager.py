# -*- coding: utf-8 -*-
"""Per-user proxy manager (from autohitter). JSON storage, rotate, check alive."""
import os
import json
import time
import random
import asyncio
import aiohttp

PROXY_FILE = "proxies.json"

def _load() -> dict:
    if os.path.exists(PROXY_FILE):
        try:
            with open(PROXY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save(data: dict):
    with open(PROXY_FILE, "w") as f:
        json.dump(data, f, indent=2)

def parse_proxy_url(proxy_str: str) -> str | None:
    proxy_str = proxy_str.strip()
    if not proxy_str:
        return None
    try:
        if "@" in proxy_str:
            auth, host_part = proxy_str.rsplit("@", 1)
            user, pw = auth.split(":", 1) if ":" in auth else (auth, "")
            host, port = host_part.rsplit(":", 1) if ":" in host_part else (host_part, "80")
            return f"http://{user}:{pw}@{host}:{port}"
        parts = proxy_str.split(":")
        if len(parts) == 4:
            return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
        if len(parts) == 2:
            return f"http://{parts[0]}:{parts[1]}"
    except Exception:
        pass
    return None

def get_user_proxies(user_id: int) -> list[str]:
    data = _load()
    val = data.get(str(user_id), [])
    if isinstance(val, str):
        return [val] if val else []
    return val if isinstance(val, list) else []

def add_user_proxy(user_id: int, proxy: str):
    data = _load()
    key = str(user_id)
    if key not in data:
        data[key] = []
    elif isinstance(data[key], str):
        data[key] = [data[key]] if data[key] else []
    if proxy not in data[key]:
        data[key].append(proxy)
    _save(data)

def remove_user_proxy(user_id: int, proxy: str | None = None) -> bool:
    data = _load()
    key = str(user_id)
    if key not in data:
        return False
    if proxy is None or proxy.lower() == "all":
        del data[key]
    elif isinstance(data[key], list):
        data[key] = [p for p in data[key] if p != proxy]
        if not data[key]:
            del data[key]
    _save(data)
    return True

def get_random_proxy(user_id: int) -> str | None:
    proxies = get_user_proxies(user_id)
    return random.choice(proxies) if proxies else None

def get_random_proxy_url(user_id: int) -> str | None:
    raw = get_random_proxy(user_id)
    return parse_proxy_url(raw) if raw else None

async def check_proxy_alive(proxy_str: str, timeout: int = 10) -> dict:
    result = {
        "proxy": proxy_str,
        "status": "dead",
        "response_time": None,
        "external_ip": None,
        "country": None,
        "error": None,
    }
    proxy_url = parse_proxy_url(proxy_str)
    if not proxy_url:
        result["error"] = "Invalid format"
        return result
    try:
        start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://ip-api.com/json",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                elapsed = round((time.perf_counter() - start) * 1000)
                if resp.status == 200:
                    data = await resp.json()
                    result["status"] = "alive"
                    result["response_time"] = f"{elapsed}ms"
                    result["external_ip"] = data.get("query")
                    result["country"] = data.get("country")
    except asyncio.TimeoutError:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)[:30]
    return result

async def check_proxies_batch(proxies: list[str], max_concurrent: int = 10) -> list[dict]:
    sem = asyncio.Semaphore(max_concurrent)
    async def _check(p):
        async with sem:
            return await check_proxy_alive(p)
    return await asyncio.gather(*[_check(p) for p in proxies])
