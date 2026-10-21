#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
#   FF GUILD JOINER — (Using External JWT API + IND Server)
# ============================================================

import sys, os, json, time, base64
import urllib3
from typing import Dict, Optional, Tuple, Any

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== OPTIONAL MODULES ====================
try:
    import jwt as pyjwt
    _JWT_AVAILABLE = True
except Exception:
    _JWT_AVAILABLE = False

try:
    import reqClan_pb2
    _REQ_CLAN_PB = True
except Exception:
    _REQ_CLAN_PB = False

# ==================== HARDCODED IND CONFIG ====================
OB = "OB55"
IND_SERVER_URL = "https://client.ind.freefiremobile.com"

AES_KEY = bytes([89,103,38,116,99,37,68,69,117,104,54,37,90,99,94,56])
AES_IV  = bytes([54,111,121,90,68,114,50,50,69,51,121,99,104,106,77,37])

JWT_API_URL = "https://ff-jwt-gen-api.lovable.app/api/public/token"
ACCOUNTS_FILE = "accounts-IND.json"

# ==================== CRYPTO ====================
def encrypt_payload(data: bytes) -> bytes:
    return AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(data, AES.block_size))

def decode_jwt(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract Account ID and Nickname from JWT"""
    if not token: return None, None
    try:
        if _JWT_AVAILABLE:
            payload = pyjwt.decode(token, options={"verify_signature": False})
        else:
            parts = token.split(".")
            if len(parts) < 2: return None, None
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
        return str(payload.get("account_id") or ""), str(payload.get("nickname") or "")
    except Exception:
        return None, None

# ==================== PROTOBUF ====================
def _varint(n: int) -> bytes:
    out = bytearray()
    if n < 0: n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def pb_encode(field_num: int, value) -> bytes:
    if isinstance(value, int):
        return _varint((field_num << 3) | 0) + _varint(value)
    if isinstance(value, (str, bytes)):
        ev = value.encode() if isinstance(value, str) else value
        return _varint((field_num << 3) | 2) + _varint(len(ev)) + ev
    return b""

def build_clan_join_payload(clan_id: int) -> bytes:
    if _REQ_CLAN_PB:
        try:
            msg = reqClan_pb2.MyMessage()
            msg.field_1 = int(clan_id)
            return msg.SerializeToString()
        except Exception: pass
    return pb_encode(1, int(clan_id))

# ==================== JWT FETCH & JOIN ====================
def get_jwt_from_api(uid: str, password: str) -> Tuple[Optional[str], Optional[str]]:
    """Fetch JWT from the API"""
    url = f"{JWT_API_URL}?uid={uid}&password={password}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            token = data.get("token") or data.get("jwt") or data.get("access_token")
            if not token and isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 100 and v.count('.') == 2:
                        token = v
                        break
            if token:
                return token, None
            return None, f"Token not in response: {data}"
        else:
            return None, f"HTTP {r.status_code} - {r.text[:100]}"
    except Exception as e:
        return None, str(e)

def request_clan(jwt_token: str, clan_id: int) -> Tuple[int, str]:
    """Send Guild Join request to IND Server"""
    url = f"{IND_SERVER_URL.rstrip('/')}/RequestJoinClan"
    payload = encrypt_payload(build_clan_join_payload(clan_id))
    hdrs = {
        "Authorization": f"Bearer {jwt_token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": OB,
        "Content-Type": "application/octet-stream",
        "User-Agent": "UnityPlayer/2018.4.12f1",
    }
    try:
        r = requests.post(url, headers=hdrs, data=payload, verify=False, timeout=15)
        return r.status_code, r.text
    except Exception as e:
        return 0, str(e)

# ==================== MAIN SCRIPT ====================
if __name__ == "__main__":
    print("=" * 50)
    print("FF GUILD JOINER (JWT API + IND SERVER)")
    print("=" * 50)
    
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[-] Error: {ACCOUNTS_FILE} not found in the current directory.")
        sys.exit(1)
        
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accounts = json.load(f)
    except Exception as e:
        print(f"[-] Error reading {ACCOUNTS_FILE}: {e}")
        sys.exit(1)

    if not isinstance(accounts, list) or not accounts:
        print("[-] Error: accounts file is empty or invalid format.")
        sys.exit(1)

    clan_id_input = input("Enter Guild (Clan) ID to join: ").strip()
    if not clan_id_input.isdigit():
        print("[-] Error: Clan ID must be numeric.")
        sys.exit(1)
    
    clan_id = int(clan_id_input)
    print(f"\n[*] Loaded {len(accounts)} accounts.")
    print(f"[*] Target Guild ID: {clan_id}")
    print("-" * 50)

    success_count = 0
    fail_count = 0

    for idx, acc in enumerate(accounts):
        uid = str(acc.get("uid", "")).strip()
        password = str(acc.get("password", "")).strip()
        
        if not uid or not password:
            print(f"[{idx+1}/{len(accounts)}] [-] Skipped (Missing UID or Pass)")
            fail_count += 1
            continue

        print(f"[{idx+1}/{len(accounts)}] UID: {uid} ... ", end="", flush=True)
        
        jwt_token, err = get_jwt_from_api(uid, password)
        if not jwt_token:
            print(f"[-] JWT API Failed: {err}")
            fail_count += 1
            time.sleep(1)
            continue
            
        acc_id, nickname = decode_jwt(jwt_token)
        nickname = nickname or "Unknown"
            
        code, text = request_clan(jwt_token, clan_id)
        if code == 200:
            print(f"[+] SUCCESS! Joined. (Nick: {nickname})")
            success_count += 1
        else:
            if "already" in text.lower() or "success" in text.lower():
                print(f"[+] SUCCESS! (HTTP {code})")
                success_count += 1
            else:
                print(f"[-] Join Failed. HTTP {code} | {text[:50]}")
                fail_count += 1
                
        time.sleep(2)

    print("-" * 50)
    print(f"[*] Process Complete: {success_count} Success, {fail_count} Failed.")