# -*- coding: utf-8 -*-
"""
Guild Glory - Professional Web Dashboard & Real-Time Automation Server
Embedded Async Web Server (aiohttp)
Optimized for ultra-smooth operation, zero memory leaks, and dynamic multi-account control.
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Any, Optional
from aiohttp import web

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")

EXP_TABLE: Dict[int, int] = {
    1: 0, 2: 48, 3: 202, 4: 544, 5: 1012, 6: 1844, 7: 2792, 8: 3800,
    9: 4870, 10: 6004, 11: 7192, 12: 8448, 13: 9760, 14: 11140, 15: 12566,
    16: 14060, 17: 15610, 18: 17224, 19: 18902, 20: 20632, 21: 22424, 22: 24278,
    23: 26192, 24: 28166, 25: 30200, 26: 32294, 27: 34448, 28: 37804, 29: 41274,
    30: 44870, 31: 48582, 32: 53394, 33: 58566, 34: 64096, 35: 69994, 36: 76460,
    37: 83506, 38: 91128, 39: 99322, 40: 108092, 41: 120144, 42: 133266, 43: 147472,
    44: 162760, 45: 179126, 46: 196572, 47: 215368, 48: 235516, 49: 257010, 50: 279860,
    51: 304056, 52: 348318, 53: 394982, 54: 444044, 55: 495508, 56: 549364, 57: 633756,
    58: 721744, 59: 813336, 60: 908522, 61: 1041438, 62: 1180352, 63: 1325266,
    64: 1476184, 65: 1634300, 66: 1840946, 67: 2056594, 68: 2281242, 69: 2514880,
    70: 2757530, 71: 3059506, 72: 3372284, 73: 3699456, 74: 4041030, 75: 4397002,
    76: 4829104, 77: 5282204, 78: 5756304, 79: 6251408, 80: 6776502, 81: 7381324,
    82: 8043154, 83: 8752982, 84: 9510808, 85: 10316338, 86: 11277190, 87: 12291748,
    88: 13360304, 89: 14482858, 90: 15659418, 91: 17026708, 92: 18453950, 93: 19941280,
    94: 21488570, 95: 23095858, 96: 24763138, 97: 26490428, 98: 28378704, 99: 30124996,
    100: 32032884
}

def calculate_level_progress(level: int, current_exp: int) -> Dict[str, Any]:
    level = max(1, level)
    next_level = min(100, level + 1)
    base_exp = EXP_TABLE.get(level, 0)
    target_exp = EXP_TABLE.get(next_level, base_exp + 50000)
    
    needed_for_level = max(1, target_exp - base_exp)
    earned_in_level = max(0, current_exp - base_exp)
    remaining_exp = max(0, target_exp - current_exp)
    progress_pct = min(100.0, max(0.0, (earned_in_level / needed_for_level) * 100.0))

    return {
        "next_level": next_level,
        "base_exp": base_exp,
        "target_exp": target_exp,
        "needed_for_level": needed_for_level,
        "earned_in_level": earned_in_level,
        "remaining_exp": remaining_exp,
        "progress_pct": round(progress_pct, 1)
    }

class BotState:
    def __init__(self):
        self.accounts: Dict[str, Dict[str, Any]] = {}
        self.logs: List[Dict[str, Any]] = []
        self.max_logs = 300
        self.total_matches = 0
        self.total_matches_started = 0
        self.total_gained_exp = 0
        self.start_time = time.time()
        self.account_workers: Dict[str, asyncio.Task] = {}
        self.account_token_map: Dict[str, str] = {}
        self.auth_to_game_id: Dict[str, str] = {}
        self.game_to_auth_id: Dict[str, str] = {}
        self.paused_accounts: set = set()
        self.refresh_callbacks: Dict[str, Any] = {}
        self.account_credentials: Dict[str, Dict[str, Any]] = {}
        self.active_writers: Dict[str, set] = {}

    def register_writer(self, uid: str, writer):
        uid_str = str(uid)
        if uid_str not in self.active_writers:
            self.active_writers[uid_str] = set()
        self.active_writers[uid_str].add(writer)

    def unregister_writer(self, uid: str, writer):
        uid_str = str(uid)
        if uid_str in self.active_writers:
            self.active_writers[uid_str].discard(writer)
            if not self.active_writers[uid_str]:
                self.active_writers.pop(uid_str, None)

    def close_writers_for_account(self, uid: str):
        uid_str = str(uid)
        candidates = {uid_str}
        if uid_str in self.auth_to_game_id: candidates.add(str(self.auth_to_game_id[uid_str]))
        if uid_str in self.game_to_auth_id: candidates.add(str(self.game_to_auth_id[uid_str]))
        if uid_str in self.account_token_map:
            mapped = self.account_token_map[uid_str]
            candidates.add(str(mapped))
            candidates.add(str(mapped)[:16])

        for c in list(candidates):
            writers = list(self.active_writers.get(c, []))
            for w in writers:
                try:
                    if hasattr(w, "close"):
                        if hasattr(w, "is_closing"):
                            if not w.is_closing(): w.close()
                        else: w.close()
                except Exception: pass
            self.active_writers.pop(c, None)

    def log(self, message: str, level: str = "info", uid: Optional[str] = None):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "message": message,
            "uid": str(uid) if uid else None
        }
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def register_account(self, uid: str, nickname: str, region: str, level: int, exp: int,
                         likes: int = 0, token: Optional[str] = None, auth_uid: Optional[str] = None):
        uid_str = str(uid)
        auth_uid_str = str(auth_uid) if auth_uid else self.game_to_auth_id.get(uid_str, "")
        if auth_uid_str:
            self.auth_to_game_id[auth_uid_str] = uid_str
            self.game_to_auth_id[uid_str] = auth_uid_str
            self.account_token_map[auth_uid_str] = uid_str
            self.account_token_map[uid_str] = auth_uid_str
        if token:
            self.account_token_map[uid_str] = token
            self.account_token_map[token[:16]] = uid_str
            if auth_uid_str: self.account_token_map[auth_uid_str] = token

        prog = calculate_level_progress(level or 1, exp)
        lvl_val = level or 1

        if uid_str not in self.accounts:
            self.accounts[uid_str] = {
                "uid": uid_str,
                "auth_uid": auth_uid_str or "",
                "nickname": nickname or f"Player_{uid_str[:6]}",
                "region": region or "IND",
                "level": lvl_val,
                "next_level": prog["next_level"],
                "initial_exp": exp,
                "current_exp": exp,
                "gained_exp": 0,
                "remaining_exp": prog["remaining_exp"],
                "target_exp": prog["target_exp"],
                "needed_for_level": prog["needed_for_level"],
                "earned_in_level": prog["earned_in_level"],
                "progress_pct": prog["progress_pct"],
                "likes": likes or 0,
                "status": "PAUSED" if self.is_paused(uid_str) else "ONLINE",
                "matches_played": 0,
                "active_matches": 0,
                "last_match_time": None,
                "token": token or "",
                "start_time": time.time(),
                "is_paused": self.is_paused(uid_str),
                "paused_at": time.time() if self.is_paused(uid_str) else None,
                "total_pause_duration": 0.0,
                "last_updated": time.strftime("%H:%M:%S")
            }
        else:
            acc = self.accounts[uid_str]
            if auth_uid_str: acc["auth_uid"] = auth_uid_str
            if nickname: acc["nickname"] = nickname
            if region: acc["region"] = region
            if level: acc["level"] = level
            if token: acc["token"] = token
            acc["current_exp"] = exp
            acc["gained_exp"] = max(0, exp - acc["initial_exp"])
            acc["next_level"] = prog["next_level"]
            acc["remaining_exp"] = prog["remaining_exp"]
            acc["target_exp"] = prog["target_exp"]
            acc["needed_for_level"] = prog["needed_for_level"]
            acc["earned_in_level"] = prog["earned_in_level"]
            acc["progress_pct"] = prog["progress_pct"]
            acc["likes"] = likes
            if not acc.get("is_paused"): acc["status"] = "ONLINE"
            acc["last_updated"] = time.strftime("%H:%M:%S")
        self.recalc_totals()

    def get_account_uptime(self, uid_str: str) -> int:
        acc = self.accounts.get(uid_str)
        if not acc:
            mapped = self.game_to_auth_id.get(uid_str) or self.auth_to_game_id.get(uid_str)
            if mapped and mapped in self.accounts: acc = self.accounts[mapped]
        if not acc: return 0
        start_t = acc.get("start_time", time.time())
        total_pause = acc.get("total_pause_duration", 0.0)
        if acc.get("is_paused") and acc.get("paused_at"):
            return max(0, int(acc["paused_at"] - start_t - total_pause))
        return max(0, int(time.time() - start_t - total_pause))

    def is_paused(self, uid: str) -> bool:
        uid_str = str(uid)
        if uid_str in self.paused_accounts: return True
        game_id = self.auth_to_game_id.get(uid_str)
        if game_id and game_id in self.paused_accounts: return True
        auth_uid = self.game_to_auth_id.get(uid_str)
        if auth_uid and auth_uid in self.paused_accounts: return True
        acc = self.accounts.get(uid_str) or (self.accounts.get(game_id) if game_id else None)
        return bool(acc and acc.get("is_paused"))

    def toggle_pause(self, uid: str) -> bool:
        uid_str = str(uid)
        candidates = {uid_str}
        if uid_str in self.auth_to_game_id: candidates.add(self.auth_to_game_id[uid_str])
        if uid_str in self.game_to_auth_id: candidates.add(self.game_to_auth_id[uid_str])

        target_acc = None
        target_key = uid_str
        for c in candidates:
            if c in self.accounts:
                target_acc = self.accounts[c]
                target_key = c
                break

        is_now_paused = not self.is_paused(uid_str)
        if is_now_paused:
            for c in candidates:
                self.paused_accounts.add(c)
                self.close_writers_for_account(c)
            if target_acc:
                target_acc["is_paused"] = True
                target_acc["paused_at"] = time.time()
                target_acc["status"] = "PAUSED"
            nick = target_acc.get("nickname", target_key) if target_acc else target_key
            self.log(f"⏸ UID {target_key} ({nick}) Matchmaking PAUSED.", "warning", target_key)
            if "on_pause_toggle" in self.refresh_callbacks:
                try: asyncio.create_task(self.refresh_callbacks["on_pause_toggle"](target_key, True))
                except Exception: pass
        else:
            for c in candidates: self.paused_accounts.discard(c)
            if target_acc:
                target_acc["is_paused"] = False
                if target_acc.get("paused_at"):
                    pause_dur = time.time() - target_acc["paused_at"]
                    target_acc["total_pause_duration"] = target_acc.get("total_pause_duration", 0.0) + pause_dur
                    target_acc["paused_at"] = None
                target_acc["status"] = "ONLINE"
            nick = target_acc.get("nickname", target_key) if target_acc else target_key
            self.log(f"▶ UID {target_key} ({nick}) Matchmaking RESUMED.", "success", target_key)
            if "on_pause_toggle" in self.refresh_callbacks:
                try: asyncio.create_task(self.refresh_callbacks["on_pause_toggle"](target_key, False))
                except Exception: pass

        return is_now_paused

    def toggle_pause_all(self) -> bool:
        any_active = any(not self.is_paused(k) for k in self.accounts.keys())
        for k in list(self.accounts.keys()):
            current_paused = self.is_paused(k)
            if any_active and not current_paused:
                self.toggle_pause(k)
            elif not any_active and current_paused:
                self.toggle_pause(k)
        return any_active

    def update_exp(self, uid: str, current_exp: int, level: Optional[int] = None):
        uid_str = str(uid)
        if uid_str in self.accounts:
            acc = self.accounts[uid_str]
            old_exp = acc["current_exp"]
            old_level = acc.get("level", 1)
            acc["current_exp"] = current_exp
            if level is not None and level > 0: acc["level"] = level
            acc["gained_exp"] = max(0, current_exp - acc["initial_exp"])

            prog = calculate_level_progress(acc["level"], current_exp)
            acc["next_level"] = prog["next_level"]
            acc["remaining_exp"] = prog["remaining_exp"]
            acc["target_exp"] = prog["target_exp"]
            acc["needed_for_level"] = prog["needed_for_level"]
            acc["earned_in_level"] = prog["earned_in_level"]
            acc["progress_pct"] = prog["progress_pct"]
            acc["last_updated"] = time.strftime("%H:%M:%S")

            if old_level < acc["level"]:
                self.log(f"🎉 LEVEL UP! UID {uid_str} ({acc['nickname']}) reached Level {acc['level']}!", "success", uid_str)

            diff = current_exp - old_exp
            if diff > 0:
                self.log(f"★ UID {uid_str} ({acc['nickname']}) gained +{diff:,} EXP | Level {acc['level']} ({prog['progress_pct']}%)", "success", uid_str)
            self.recalc_totals()

    def update_status(self, uid: str, status: str, active_matches: Optional[int] = None):
        uid_str = str(uid)
        if uid_str in self.accounts:
            self.accounts[uid_str]["status"] = status
            if active_matches is not None:
                self.accounts[uid_str]["active_matches"] = active_matches
            self.accounts[uid_str]["last_updated"] = time.strftime("%H:%M:%S")

    def increment_match_started(self):
        self.total_matches_started += 1

    def increment_match(self, uid: str):
        uid_str = str(uid)
        self.total_matches += 1
        if uid_str in self.accounts:
            self.accounts[uid_str]["matches_played"] += 1
            self.accounts[uid_str]["last_match_time"] = time.strftime("%H:%M:%S")
            self.accounts[uid_str]["last_updated"] = time.strftime("%H:%M:%S")
            self.log(f"⚔ Match #{self.accounts[uid_str]['matches_played']} finished for {self.accounts[uid_str]['nickname']} ({uid_str})", "info", uid_str)

    def recalc_totals(self):
        self.total_gained_exp = sum(acc.get("gained_exp", 0) for acc in self.accounts.values())

bot_state = BotState()

FALLBACK_INDEX_HTML = """<!DOCTYPE html>
<html>
<head><title>Guild Glory Dashboard</title></head>
<body style="background:#07090e;color:#fff;font-family:sans-serif;text-align:center;padding:50px;">
<h1>GUILD GLORY MASTER BOT</h1>
<p>templates/index.html is loading...</p>
</body>
</html>"""


# ==================== HTTP HANDLERS ====================

async def handle_index(request: web.Request) -> web.Response:
    content = FALLBACK_INDEX_HTML
    if os.path.exists(TEMPLATE_PATH):
        try:
            with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception: pass
    return web.Response(text=content, content_type="text/html", charset="utf-8")


async def handle_get_stats(request: web.Request) -> web.Response:
    accounts_data = list(bot_state.accounts.values())
    accounts_data.sort(key=lambda x: x.get("gained_exp", 0), reverse=True)
    uptime_sec = max(1, int(time.time() - bot_state.start_time))
    total_gained = bot_state.total_gained_exp
    exp_per_hour = int((total_gained / uptime_sec) * 3600)
    total_active_matches = sum(acc.get("active_matches", 0) for acc in accounts_data)

    for acc in accounts_data:
        uid_k = str(acc.get("uid", ""))
        acc["uptime_seconds"] = bot_state.get_account_uptime(uid_k)
        acc["is_paused"] = bot_state.is_paused(uid_k)

    return web.json_response({
        "total_accounts": len(bot_state.accounts),
        "total_matches": bot_state.total_matches,
        "total_matches_started": bot_state.total_matches_started,
        "total_active_matches": total_active_matches,
        "total_gained_exp": total_gained,
        "exp_per_hour": exp_per_hour,
        "accounts": accounts_data,
        "logs": bot_state.logs[-100:],
        "uptime": uptime_sec
    })


async def handle_get_logs(request: web.Request) -> web.Response:
    lines = []
    for l in bot_state.logs[-100:]:
        lines.append(f"<span class='log-time'>[{l['time']}]</span> <span class='log-{l.get('level', 'info')}'>{l['message']}</span>")
    return web.json_response({"logs": lines})


async def handle_get_guildinfo(request: web.Request) -> web.Response:
    guild_id = request.query.get("guild_id", "").strip()
    region = request.query.get("region", "IND").upper()

    if not guild_id or guild_id in ("Not Set", "---"):
        return web.json_response({
            "clan_basic_info": {
                "clan_id": "Not Set",
                "clan_name": "No Clan Set",
                "clan_level": "-",
                "Total guild xp": 0,
                "old_xp": 0,
                "gained_exp": 0,
                "region": region
            }
        })

    base_xp = 1850000
    live_gained = bot_state.total_gained_exp
    current_xp = base_xp + live_gained

    return web.json_response({
        "clan_basic_info": {
            "clan_id": str(guild_id),
            "clan_name": f"GUILD • {guild_id[-5:]}",
            "clan_level": "6",
            "Total guild xp": current_xp,
            "old_xp": base_xp,
            "gained_exp": live_gained,
            "region": region
        }
    })


async def handle_add_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        accounts_file = "accounts-IND.json"
        if not os.path.exists(accounts_file): accounts_file = "accounts.json"

        existing = []
        if os.path.exists(accounts_file):
            try:
                with open(accounts_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception: existing = []

        if "uid" in data and "password" in data:
            uid = str(data["uid"]).strip()
            pwd = str(data["password"]).strip()
            if not uid or not pwd:
                return web.json_response({"status": "error", "error": "UID and Password are required"})

            if uid in bot_state.account_workers:
                try: bot_state.account_workers[uid].cancel()
                except Exception: pass
                bot_state.account_workers.pop(uid, None)

            existing = [acc for acc in existing if str(acc.get("uid", "")) != uid]
            existing.append({"uid": uid, "password": pwd})
            identifier = uid
        elif "token" in data:
            token = str(data["token"]).strip()
            if not token:
                return web.json_response({"status": "error", "error": "Token is required"})
            tok_key = token[:16]
            for k in list(bot_state.account_workers.keys()):
                if k == tok_key or k.startswith(tok_key[:10]) or tok_key.startswith(k[:10]):
                    try: bot_state.account_workers[k].cancel()
                    except Exception: pass
                    bot_state.account_workers.pop(k, None)
            existing = [acc for acc in existing if acc.get("token", "") != token]
            existing.append({"token": token})
            identifier = f"Token_{token[:8]}..."
        else:
            return web.json_response({"status": "error", "error": "Invalid payload"})

        with open(accounts_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

        bot_state.log(f"New account added: {identifier}", "success")
        if "on_account_added" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_account_added"](data))

        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_delete_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        req_uid = str(data.get("uid", "")).strip()
        req_auth_uid = str(data.get("auth_uid", "")).strip()
        if not req_uid and not req_auth_uid:
            return web.json_response({"status": "error", "error": "UID is required"})

        candidate_ids = set()
        if req_uid: candidate_ids.add(req_uid)
        if req_auth_uid: candidate_ids.add(req_auth_uid)

        for cid in list(candidate_ids):
            if cid in bot_state.game_to_auth_id: candidate_ids.add(str(bot_state.game_to_auth_id[cid]))
            if cid in bot_state.auth_to_game_id: candidate_ids.add(str(bot_state.auth_to_game_id[cid]))

        for fn in ["accounts-IND.json", "accounts-BD.json", "accounts-SG.json", "accounts.json"]:
            if os.path.exists(fn):
                try:
                    with open(fn, "r", encoding="utf-8") as f: arr = json.load(f)
                    new_arr = [a for a in arr if str(a.get("uid", "")).strip() not in candidate_ids]
                    with open(fn, "w", encoding="utf-8") as f: json.dump(new_arr, f, indent=2)
                except Exception: pass

        for cid in candidate_ids:
            bot_state.accounts.pop(cid, None)
            bot_state.account_credentials.pop(cid, None)
            bot_state.auth_to_game_id.pop(cid, None)
            bot_state.game_to_auth_id.pop(cid, None)
            bot_state.account_token_map.pop(cid, None)

        cancelled_keys = []
        for k, worker in list(bot_state.account_workers.items()):
            if str(k) in candidate_ids:
                try: worker.cancel()
                except Exception: pass
                cancelled_keys.append(k)

        for k in cancelled_keys: bot_state.account_workers.pop(k, None)
        for cid in candidate_ids: bot_state.close_writers_for_account(cid)

        target_repr = req_uid or req_auth_uid
        bot_state.log(f"Account {target_repr} deleted.", "warning", target_repr)
        bot_state.recalc_totals()
        return web.json_response({"status": "ok", "deleted": list(candidate_ids)})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


# ⭐ NEW: ক্লিয়ার অল অপশন (Clear All Guests & Wipe token_cache.json)
async def handle_clear_all_guests(request: web.Request) -> web.Response:
    try:
        # ১. সব অ্যাকাউন্ট ওয়ার্কার টাস্ক বাতিল করা
        for k, worker in list(bot_state.account_workers.items()):
            try: worker.cancel()
            except Exception: pass
        bot_state.account_workers.clear()

        # ২. সকেট কানেকশন ক্লোজ করা
        for uid in list(bot_state.active_writers.keys()):
            bot_state.close_writers_for_account(uid)
        bot_state.active_writers.clear()

        # ৩. ইন-মেমোরি স্টেট ক্লিয়ার করা
        bot_state.accounts.clear()
        bot_state.account_credentials.clear()
        bot_state.auth_to_game_id.clear()
        bot_state.game_to_auth_id.clear()
        bot_state.account_token_map.clear()
        bot_state.paused_accounts.clear()
        bot_state.total_matches = 0
        bot_state.total_matches_started = 0
        bot_state.total_gained_exp = 0

        # ৪. token_cache.json সম্পূর্ণ ডিলিট করা
        token_cache_file = "token_cache.json"
        if os.path.exists(token_cache_file):
            try: os.remove(token_cache_file)
            except Exception:
                with open(token_cache_file, "w", encoding="utf-8") as f: f.write("{}")

        # ৫. সব অ্যাকাউন্ট ফাইল খালি করা (accounts-*.json)
        for fn in ["accounts-IND.json", "accounts-BD.json", "accounts-SG.json", "accounts.json"]:
            if os.path.exists(fn):
                try:
                    with open(fn, "w", encoding="utf-8") as f:
                        json.dump([], f, indent=2)
                except Exception: pass

        bot_state.log("🧹 All guest accounts and token_cache.json wiped clean! Ready to generate fresh accounts.", "success")
        return web.json_response({"status": "ok", "message": "All guest accounts and token cache cleared successfully."})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_refresh_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if "on_refresh_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_refresh_account"](uid))
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_restart_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if "on_restart_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_restart_account"](uid))
        elif "on_refresh_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_refresh_account"](uid))
        return web.json_response({"status": "ok"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_clear_logs(request: web.Request) -> web.Response:
    bot_state.logs.clear()
    return web.json_response({"status": "ok"})


async def handle_toggle_pause(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if not uid: return web.json_response({"status": "error", "error": "UID is required"})
        is_paused = bot_state.toggle_pause(uid)
        return web.json_response({"status": "ok", "is_paused": is_paused})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_toggle_pause_all(request: web.Request) -> web.Response:
    try:
        paused_state = bot_state.toggle_pause_all()
        return web.json_response({"status": "ok", "all_paused": paused_state})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_play_account(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        uid = str(data.get("uid", "")).strip()
        if not uid: return web.json_response({"status": "error", "error": "UID is required"})

        if bot_state.is_paused(uid): bot_state.toggle_pause(uid)
        bot_state.update_status(uid, "SEARCHING_MATCH")
        bot_state.log(f"▶ Manual PLAY triggered for UID {uid}...", "success", uid)

        if "on_restart_account" in bot_state.refresh_callbacks:
            asyncio.create_task(bot_state.refresh_callbacks["on_restart_account"](uid))

        return web.json_response({"status": "ok", "message": f"Play triggered for {uid}"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_play_all(request: web.Request) -> web.Response:
    try:
        for uid in list(bot_state.accounts.keys()):
            if bot_state.is_paused(uid): bot_state.toggle_pause(uid)
            bot_state.update_status(uid, "SEARCHING_MATCH")
            if "on_restart_account" in bot_state.refresh_callbacks:
                asyncio.create_task(bot_state.refresh_callbacks["on_restart_account"](uid))

        bot_state.log("🚀 PLAY ALL triggered! All accounts active.", "success")
        return web.json_response({"status": "ok", "message": "Play all triggered"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_start_generator(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        region = str(data.get("region", "IND")).upper()
        count = int(data.get("count", 4))
        count = max(1, min(count, 50))

        async def run_gen_task():
            bot_state.log(f"🚀 Generator Started: Region={region}, Count={count}", "info")
            try:
                import gen
                created = await gen.create_accounts(region, count)
                bot_state.log(f"✅ Created {len(created)} fresh account(s)! Auto-starting workers...", "success")

                # ⭐ নতুন তৈরি অ্যাকাউন্ট স্বয়ংক্রিয়ভাবে বটের সাথে কানেক্ট করা
                if "on_account_added" in bot_state.refresh_callbacks:
                    for acc in created:
                        asyncio.create_task(bot_state.refresh_callbacks["on_account_added"](acc))
            except Exception as e:
                bot_state.log(f"❌ Generator Error: {e}", "error")

        asyncio.create_task(run_gen_task())
        return web.json_response({"status": "ok", "message": f"Generating {count} accounts in {region}"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


async def handle_start_clan_join(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        clan_id_raw = str(data.get("clan_id", "")).strip()
        region = str(data.get("region", "IND")).upper()

        if not clan_id_raw.isdigit():
            return web.json_response({"status": "error", "error": "Clan ID must be numeric."})

        clan_id = int(clan_id_raw)

        async def run_clan_task():
            candidate_files = [f"accounts-{region}.json", "accounts-IND.json", "accounts.json"]
            target_file = None
            for cf in candidate_files:
                if os.path.exists(cf):
                    target_file = cf
                    break

            if not target_file:
                bot_state.log(f"❌ No accounts file found for {region}!", "error")
                return

            try:
                with open(target_file, "r", encoding="utf-8") as f: accounts = json.load(f)
            except Exception as e:
                bot_state.log(f"❌ Failed to read {target_file}: {e}", "error")
                return

            bot_state.log(f"🛡️ Bulk Clan Joiner Started: Guild ID={clan_id} | Accounts={len(accounts)}", "info")

            import clan_join
            success_c = 0
            fail_c = 0

            for idx, acc in enumerate(accounts):
                uid = str(acc.get("uid", "")).strip()
                pwd = str(acc.get("password", "")).strip()
                if not uid or not pwd:
                    fail_c += 1
                    continue

                jwt_token, err = clan_join.get_jwt_from_api(uid, pwd)
                if not jwt_token:
                    bot_state.log(f"[-] [{idx+1}/{len(accounts)}] UID {uid} JWT Error: {err}", "warning", uid)
                    fail_c += 1
                    await asyncio.sleep(1.0)
                    continue

                code, text = clan_join.request_clan(jwt_token, clan_id)
                if code == 200:
                    bot_state.log(f"✅ [{idx+1}/{len(accounts)}] UID {uid} Joined Guild {clan_id}!", "success", uid)
                    success_c += 1
                else:
                    if "already" in text.lower() or "success" in text.lower():
                        bot_state.log(f"✅ [{idx+1}/{len(accounts)}] UID {uid} already in Guild!", "success", uid)
                        success_c += 1
                    else:
                        bot_state.log(f"⚠️ [{idx+1}/{len(accounts)}] UID {uid} Join Failed ({code})", "warning", uid)
                        fail_c += 1
                await asyncio.sleep(2.0)

            bot_state.log(f"🎉 Clan Join Process Finished: {success_c} Success, {fail_c} Failed.", "success")

        asyncio.create_task(run_clan_task())
        return web.json_response({"status": "ok", "message": "Clan joiner started"})
    except Exception as e:
        return web.json_response({"status": "error", "error": str(e)})


# ==================== SERVER BOOTSTRAP ====================

async def start_web_dashboard(host: str = "0.0.0.0", port: int = 30058):
    app = web.Application()

    app.router.add_get("/", handle_index)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_get("/api/logs", handle_get_logs)
    app.router.add_get("/api/guildinfo", handle_get_guildinfo)
    app.router.add_post("/api/account/add", handle_add_account)
    app.router.add_post("/api/account/delete", handle_delete_account)
    app.router.add_post("/api/account/clear_all", handle_clear_all_guests)
    app.router.add_post("/api/accounts/delete_all", handle_clear_all_guests)
    app.router.add_post("/api/account/refresh", handle_refresh_account)
    app.router.add_post("/api/account/restart", handle_restart_account)
    app.router.add_post("/api/account/pause", handle_toggle_pause)
    app.router.add_post("/api/account/pause_all", handle_toggle_pause_all)
    app.router.add_post("/api/account/play", handle_play_account)
    app.router.add_post("/api/account/play_all", handle_play_all)
    app.router.add_post("/api/logs/clear", handle_clear_logs)
    app.router.add_post("/api/generator/start", handle_start_generator)
    app.router.add_post("/api/clan/join", handle_start_clan_join)
    app.router.add_post("/api/clanjoin", handle_start_clan_join)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner
