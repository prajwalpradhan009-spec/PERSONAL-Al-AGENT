"""
Discord Integration (REST API)
Communicates with Discord using a bot token. Message sending / sensitive reads
require explicit confirmation at the agent layer.

Requires: `discord_bot_token` in config.json credentials block.

Capabilities: list_channels, get_channel_info, read_messages, send_message,
search_messages.
"""

import requests
from typing import Dict, Any, List, Optional

from app.integrations.credentials import get_setting, is_configured, missing_for

API = "https://discord.com/api/v10"


def _headers() -> Dict[str, str]:
    return {"Authorization": f"Bot {get_setting('discord_bot_token')}"}


def _require() -> Dict[str, Any]:
    if not is_configured("discord_bot_token"):
        _, hint = missing_for("discord_bot_token")
        return {"success": False, "error": "Discord integration requires a bot token.", "hint": hint}
    return {"success": True}


def _dc(method: str, path: str, **kwargs) -> Dict[str, Any]:
    try:
        resp = requests.request(method, API + path, headers=_headers(), timeout=15, **kwargs)
        if resp.status_code in (200, 201, 204):
            data = resp.json() if resp.content else {}
            return {"success": True, "status_code": resp.status_code, "data": data}
        return {"success": False, "status_code": resp.status_code, "error": resp.text[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_bot_info() -> Dict[str, Any]:
    res = _dc("GET", "/users/@me")
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "username": d.get("username"), "id": d.get("id"),
            "output": f"Bot '{d.get('username')}' is online."}


def get_guilds(limit: int = 20) -> Dict[str, Any]:
    res = _dc("GET", "/users/@me/guilds", params={"limit": limit})
    if not res.get("success"):
        return res
    guilds = [{"id": g.get("id"), "name": g.get("name")} for g in res["data"]]
    return {"success": True, "guilds": guilds, "count": len(guilds), "output": f"Bot is in {len(guilds)} server(s)."}


def _resolve_channel_id(channel: str, guild_id: str = None) -> Optional[str]:
    """Resolves a channel name or id to a channel id."""
    if channel.isdigit():
        return channel
    params = {}
    if guild_id:
        params["guild_id"] = guild_id
    res = _dc("GET", "/users/@me/guilds" if not guild_id else f"/guilds/{guild_id}/channels", params=params) if not guild_id else _dc("GET", f"/guilds/{guild_id}/channels")
    if not res.get("success"):
        return None
    channel_name = channel.strip().lower().lstrip("#")
    for ch in res["data"]:
        if ch.get("name", "").lower() == channel_name or ch.get("id") == channel:
            return ch.get("id")
    return None


def list_channels(guild_id: str = None) -> Dict[str, Any]:
    """Lists text channels the bot can see (optionally scoped to a guild)."""
    if guild_id:
        res = _dc("GET", f"/guilds/{guild_id}/channels")
    else:
        res = _dc("GET", "/users/@me/guilds")
        if not res.get("success"):
            return res
        all_channels = []
        for g in res["data"][:5]:
            ch_res = _dc("GET", f"/guilds/{g['id']}/channels")
            if ch_res.get("success"):
                all_channels.extend({"id": c.get("id"), "name": c.get("name"), "type": c.get("type"), "guild": g["name"]}
                                    for c in ch_res["data"] if c.get("type") in (0, 5))
        return {"success": True, "channels": all_channels, "count": len(all_channels),
                "output": f"Found {len(all_channels)} channel(s) across guilds."}
    if not res.get("success"):
        return res
    channels = [{"id": c.get("id"), "name": c.get("name"), "type": c.get("type")} for c in res["data"] if c.get("type") in (0, 5)]
    return {"success": True, "channels": channels, "count": len(channels), "output": f"Found {len(channels)} channel(s)."}


def get_channel_info(channel: str, guild_id: str = None) -> Dict[str, Any]:
    cid = _resolve_channel_id(channel, guild_id)
    if not cid:
        return {"success": False, "error": f"Channel '{channel}' not found."}
    res = _dc("GET", f"/channels/{cid}")
    if not res.get("success"):
        return res
    d = res["data"]
    return {"success": True, "id": d.get("id"), "name": d.get("name"), "type": d.get("type"),
            "topic": d.get("topic"), "nsfw": d.get("nsfw"), "output": f"Channel #{d.get('name')} ({d.get('id')})."}


def read_messages(channel: str, guild_id: str = None, limit: int = 10) -> Dict[str, Any]:
    """Reads recent messages from a channel (text channels the bot has access to)."""
    cid = _resolve_channel_id(channel, guild_id)
    if not cid:
        return {"success": False, "error": f"Channel '{channel}' not found or bot lacks access."}
    res = _dc("GET", f"/channels/{cid}/messages", params={"limit": limit})
    if not res.get("success"):
        return res
    messages = [{"id": m.get("id"), "author": m.get("author", {}).get("username"), "content": m.get("content"), "timestamp": m.get("timestamp")}
                for m in res["data"]]
    return {"success": True, "channel": channel, "messages": messages, "count": len(messages),
            "output": f"Read {len(messages)} message(s) from #{channel}."}


def search_messages(query: str, guild_id: str = None, limit: int = 10) -> Dict[str, Any]:
    """Searches messages across the channels the bot can see for a keyword."""
    matches = []
    guilds = [guild_id] if guild_id else [g["id"] for g in get_guilds().get("guilds", [])]
    for gid in guilds:
        channels = list_channels(gid)
        if not channels.get("success"):
            continue
        for ch in channels["channels"]:
            res = _dc("GET", f"/channels/{ch['id']}/messages", params={"limit": 25})
            if not res.get("success"):
                continue
            for m in res["data"]:
                if query.lower() in (m.get("content") or "").lower():
                    matches.append({"guild": gid, "channel": ch["name"], "author": m.get("author", {}).get("username"),
                                    "content": m.get("content"), "timestamp": m.get("timestamp")})
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        if len(matches) >= limit:
            break
    return {"success": True, "query": query, "matches": matches, "count": len(matches),
            "output": f"Found {len(matches)} message(s) matching '{query}'."}


def send_message(channel: str, content: str, guild_id: str = None, confirm: bool = False) -> Dict[str, Any]:
    """Sends a text message. Requires confirm=True (outbound, sensitive)."""
    if not confirm:
        return {"success": False, "error": "Refusing to send a Discord message without confirmation. Retry with confirm=True."}
    req = _require()
    if not req.get("success"):
        return req
    cid = _resolve_channel_id(channel, guild_id)
    if not cid:
        return {"success": False, "error": f"Channel '{channel}' not found or bot lacks access."}
    res = _dc("POST", f"/channels/{cid}/messages", json={"content": content})
    if not res.get("success"):
        return res
    return {"success": True, "channel": channel, "content": content,
            "output": f"Message sent to #{channel}."}