# -*- coding: utf-8 -*-
# ============================================================
#   RAW MEHEDI — GUEST GEN (REGION-WISE SAVE + UID/PASS ONLY)
#   Save: accounts-BD.json, accounts-IND.json, accounts-SG.json ...
# ============================================================
import sys, os, json, time, uuid, random, asyncio, socket
import ssl, hmac, hashlib, string, traceback
from datetime import datetime
from typing import Dict, List, Optional

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

import httpx
import aiohttp
from google_play_scraper import app as play_scraper
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from protobuf_decoder.protobuf_decoder import Parser

# ==================== CONFIG ====================
DEVICES_FILE = "devices.json"

GEN_NICKNAME_PREFIX = "MEHEDI"
GEN_PASSWORD_LEN    = 14
GEN_DELAY_BETWEEN   = 8.0
REGISTER_MAX_RETRY  = 5
GRANT_MAX_RETRY     = 3
GEN_COUNT_DEFAULT   = 4
GEN_REGION_DEFAULT  = "BD"

AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])
KEYSTREAM = bytes([0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30,0x31,0x37,0x30,0x30,0x30,0x30,0x30,0x32,0x30])
HEX_KEY = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"
API_KEY = HEX_KEY.encode()

REGION_LANG = {"ME":"ar","IND":"hi","ID":"id","VN":"vi","TH":"th","BD":"bn",
               "PK":"ur","TW":"zh","RU":"ru","SAC":"es","BR":"pt","NA":"pt",
               "SG":"pt","US":"pt"}

# ==================== REGION MENU ====================
REGIONS = [
    ("BD",  "Bangladesh"),
    ("IND", "India"),
    ("SG",  "Singapore"),
    ("TH",  "Thailand"),
    ("PH",  "Philippines"),
    ("VN",  "Vietnam"),
    ("MY",  "Malaysia"),
    ("ID",  "Indonesia"),
    ("HK",  "Hong Kong"),
    ("TW",  "Taiwan"),
    ("BR",  "Brazil"),
    ("US",  "United States"),
    ("ME",  "Middle East"),
    ("PK",  "Pakistan"),
    ("RU",  "Russia"),
]

# ==================== COLORFUL PRINT ====================
class C:
    RESET='\033[0m'; BOLD='\033[1m'
    RED='\033[91m'; GREEN='\033[92m'; YELLOW='\033[93m'
    BLUE='\033[94m'; PURPLE='\033[95m'; CYAN='\033[96m'
    WHITE='\033[97m'; GRAY='\033[90m'

def _ts(): return datetime.now().strftime("%H:%M:%S")
def banner():
    print(f"{C.PURPLE}{C.BOLD}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  🌈  RAW MEHEDI — GUEST GEN (UID/PASS ONLY)                  ║")
    print("║     Save: accounts-BD.json, accounts-IND.json ...            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{C.RESET}")

def print_success(m): print(f"{C.GRAY}[{_ts()}]{C.RESET} {C.GREEN}✅ {m}{C.RESET}")
def print_error(m):   print(f"{C.GRAY}[{_ts()}]{C.RESET} {C.RED}❌ {m}{C.RESET}")
def print_warning(m): print(f"{C.GRAY}[{_ts()}]{C.RESET} {C.YELLOW}⚠️  {m}{C.RESET}")
def print_info(m):    print(f"{C.GRAY}[{_ts()}]{C.RESET} {C.CYAN}ℹ️  {m}{C.RESET}")
def print_step(m):    print(f"{C.GRAY}[{_ts()}]{C.RESET} {C.BLUE}▶  {m}{C.RESET}")
def print_gen(m):     print(f"{C.GRAY}[{_ts()}]{C.RESET} {C.PURPLE}🎯 {m}{C.RESET}")
def print_sep():      print(f"{C.GRAY}{'─' * 64}{C.RESET}")

def show_region_menu():
    print_sep()
    print(f"{C.PURPLE}{C.BOLD}🌍 SELECT REGION{C.RESET}")
    print_sep()
    for i, (code, name) in enumerate(REGIONS, 1):
        marker = "⭐" if code == GEN_REGION_DEFAULT else "  "
        print(f"  {marker} {C.CYAN}[{i:2d}]{C.RESET} {C.BOLD}{code:4s}{C.RESET} → {name}")
    print_sep()

def choose_region_interactive() -> str:
    show_region_menu()
    try:
        inp = input(f"{C.CYAN}Enter number (1-{len(REGIONS)}) or region code [{GEN_REGION_DEFAULT}]: {C.RESET}").strip().upper()
    except Exception:
        inp = ""
    if not inp: return GEN_REGION_DEFAULT
    if inp.isdigit():
        idx = int(inp) - 1
        if 0 <= idx < len(REGIONS): return REGIONS[idx][0]
        print_warning(f"invalid number, using {GEN_REGION_DEFAULT}")
        return GEN_REGION_DEFAULT
    codes = [r[0] for r in REGIONS]
    if inp in codes: return inp
    print_warning(f"unknown region {inp}, using {GEN_REGION_DEFAULT}")
    return GEN_REGION_DEFAULT

# ==================== PASSWORD / NICKNAME ====================
def gen_password() -> str:
    return ''.join(random.choices(string.ascii_uppercase, k=GEN_PASSWORD_LEN))

def gen_nickname() -> str:
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{GEN_NICKNAME_PREFIX}•{suffix}"

# ==================== GGRE ====================
GGRE_RAW = bytes.fromhex(
    "47475245010101006d020000b260ee08e1f86b4c57f9c70f86bba26ed5d1436bcf52e142db3249d905eded757764991ca31a8373cdd26eab91b80f3f1f6f262f4f10b895d7b6937ddba30a27197453890e9da49373f736c679b8254e2f8e1623e91084a5fdd5374fe478ff99e010834553fddeb0bec4018d142e49df9bb236675b67e852f92a43586f7a7d4d0d7a197a1d4da32714dab4d069ad53214e2c33b3877420a12459738c4c619cbd815fa878bbd104776bb3e1ac7818d5397b04a666ac57f682763ff2df31bc2f846ddc7904f3dce1bda0c4b01f9698e9166f98c84f92640abe3f6317834a42e5c12573b46842c1a6ea8fe6ca9c006dca48a2087e1f983dfb5692771e4a0b15b337ad669b1d08b40862b176bace5331b49a767375b1a8469012aa70a67b55fe71b72478201d0b3ac7269c064c960361e92ee7ba8a42cc6b582bf9b965fb388fa9172ad44c4b073ac23c02080a6bcd106b691ffdf4c7cf71e42f2063fcf196e9bddc5e85be1fe5048eb1b31b460efbb46d76195eef9904c4cba326f2e17ff51fec17dd965aa06dadd4ab07d6966e4a7c38e8afd66dfde56c872bb87516a8f7313c797e4d80e5ad4a5f7afad95c1e0449254adae052e71a3fb98399f93ab30848e0d23252dd45e6fd41bc5fa7303dfb846a8fd713a0032a0b0ae96dfba1bbe41d20abd8099e2cb7fccc329d25bd153029139ef05d090a5093ea557693c0a8d491395b8a23ca844b3887dd5dfc29ac06f4b9be87883a793211b973465e2644c4f5de02b8ab01571401203fc2740423826858cc6da0194c195d27aac4ec4b9d23d506c1501d06440aca3fc180926d75d4a004d3dff21eb4ea1e8c86e6c9627248eff953e1d192d5c8efc006a7e512388ef2ebdb72ee3ad42d719f28e8f994e12ebf4c79f2ffe3abd7408ccd2236a7b89b2606247a732c10c4"
)

# ==================== ENCODERS ====================
def encode_varint(n: int) -> bytes:
    out = bytearray()
    if n < 0: n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F; n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)

def _pb_varint(fn, val): return encode_varint((fn<<3)|0) + encode_varint(val)
def _pb_length(fn, val):
    enc = val.encode('utf-8') if isinstance(val,str) else val
    return encode_varint((fn<<3)|2) + encode_varint(len(enc)) + enc

def create_proto(fields) -> bytes:
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(field, str): field = int(field)
        if isinstance(value, dict):
            packet.extend(_pb_length(field, bytes(create_proto(value))))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    packet.extend(_pb_length(field, bytes(create_proto(item))))
                elif isinstance(item, str):
                    packet.extend(_pb_length(field, item))
                elif isinstance(item, (bytes, bytearray)):
                    packet.extend(_pb_length(field, bytes(item)))
                elif isinstance(item, bool):
                    packet.extend(_pb_varint(field, 1 if item else 0))
                elif isinstance(item, int):
                    packet.extend(_pb_varint(field, item))
        elif isinstance(value, bool):
            packet.extend(_pb_varint(field, 1 if value else 0))
        elif isinstance(value, int):
            packet.extend(_pb_varint(field, value))
        elif isinstance(value, str):
            packet.extend(_pb_length(field, value))
        elif isinstance(value, (bytes, bytearray)):
            packet.extend(_pb_length(field, bytes(value)))
    return bytes(packet)

def encrypt_aes(hex_data: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return cipher.encrypt(pad(bytes.fromhex(hex_data), AES.block_size)).hex()

def _encode_proto_std(fields):
    out = b""
    for f in sorted(fields.keys()):
        v = fields[f]
        if isinstance(v, bool):
            out += encode_varint((f << 3) | 0) + encode_varint(int(v))
        elif isinstance(v, int):
            out += encode_varint((f << 3) | 0) + encode_varint(v)
        elif isinstance(v, (str, bytes)):
            if isinstance(v, str): v = v.encode()
            out += encode_varint((f << 3) | 2) + encode_varint(len(v)) + v
    return out

# ==================== DECODERS ====================
def decode_varint(data, offset):
    result = 0; shift = 0
    while offset < len(data):
        byte = data[offset]
        result |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80): return result, offset
        shift += 7
    return None, offset

def decode_protobuf_2(data):
    result = {}; offset = 0
    while offset < len(data):
        header, offset = decode_varint(data, offset)
        if header is None: break
        fn = header >> 3; wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None: result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None: break
            value = data[offset:offset+length]; offset += length
            try:
                s = value.decode('utf-8')
                result[fn] = s if s else value.hex()
            except UnicodeDecodeError:
                nested = decode_protobuf_2(value)
                result[fn] = nested if nested else value.hex()
        elif wt == 1: offset += 8
        elif wt == 3: offset += 4
        else: break
    return result

def extract_raw_fields(data: bytes) -> dict:
    result = {}; offset = 0
    while offset < len(data):
        header, offset = decode_varint(data, offset)
        if header is None: break
        fn = header >> 3; wt = header & 0x7
        if wt == 0:
            v, offset = decode_varint(data, offset)
            if v is not None: result[fn] = v
        elif wt == 2:
            length, offset = decode_varint(data, offset)
            if length is None: break
            if offset + length > len(data): break
            result[fn] = bytes(data[offset:offset+length]); offset += length
        elif wt == 1: offset += 8
        elif wt == 3: offset += 4
        else: break
    return result

def _parse_results_sync(results):
    out = {}
    for r in results:
        fd = {"wire_type": r.wire_type}
        if r.wire_type == "varint": fd["data"] = r.data
        elif r.wire_type in ("string","bytes"): fd["data"] = r.data
        elif r.wire_type == "length_delimited":
            if hasattr(r.data, "results"): fd["data"] = _parse_results_sync(r.data.results)
            elif isinstance(r.data, list): fd["data"] = _parse_results_sync(r.data)
            else: fd["data"] = str(r.data)
        out[str(r.field)] = fd
    return out

def decode_protobuf_dict(data: bytes) -> dict:
    try:
        parsed = Parser().parse(data)
        return _parse_results_sync(parsed)
    except Exception:
        return {}

def _extract_key_iv(res_json):
    if "__RAW_HEX__" in res_json and "__OFFSET__" in res_json:
        try:
            raw = bytes.fromhex(res_json["__RAW_HEX__"])
            off = int(res_json["__OFFSET__"])
            rf = extract_raw_fields(raw[off:])
            for kf, vf in [(22,23),(24,25),(6,7)]:
                k = rf.get(kf); v = rf.get(vf)
                if isinstance(k,(bytes,bytearray)) and len(k)==16 and \
                   isinstance(v,(bytes,bytearray)) and len(v)==16:
                    return bytes(k), bytes(v)
        except Exception: pass
    found = {}
    for k, v in res_json.items():
        if str(k).startswith("__"): continue
        if not isinstance(v, dict): continue
        data = v.get("data")
        if data is None: continue
        raw = None
        if isinstance(data, (bytes,bytearray)) and len(data)==16: raw = bytes(data)
        elif isinstance(data, str) and len(data)==32:
            try:
                c = bytes.fromhex(data)
                if len(c)==16: raw = c
            except Exception: pass
        if raw and len(raw)==16:
            try: found[int(k)] = raw
            except Exception: pass
    if len(found) < 2: return None, None
    for kf, vf in [(22,23),(24,25),(6,7)]:
        if kf in found and vf in found: return found[kf], found[vf]
    sk = sorted(found.keys())
    return found[sk[0]], found[sk[1]]

# ==================== HTTP CLIENT ====================
client = httpx.AsyncClient(verify=False, timeout=10.0,
    limits=httpx.Limits(max_connections=300, max_keepalive_connections=150))

# ==================== VERSION ====================
def get_app_version():
    try: return play_scraper('com.dts.freefireth').get('version')
    except Exception: return "1.132.9"

async def version_config(region="BD"):
    app_version = get_app_version()
    lang = REGION_LANG.get(region.upper(), "en")
    url = (f"https://version.ggwhitehawk.com/live/ver.php?version={app_version}"
           f"&lang={lang}&device=android&channel=android&appstore=googleplay"
           f"&region={region.upper()}&whitelist_version=1.3.0&whitelist_sp_version=1.0.0")
    try:
        r = await client.get(url)
        j = r.json()
        server_url = j.get("server_url")
        remote_version = j.get("remote_version")
        latest_release_version = j.get("latest_release_version")
        gops = [u.strip() for u in j.get("gop_url","").split(";") if u.strip()]
        gop_1 = gops[0] if gops else "https://ffmconnect.ppmainecoonghj.com"
        if not server_url: return None
        return latest_release_version, remote_version, server_url, gop_1, app_version
    except Exception as e:
        print_error(f"[VERCONFIG] {e}")
        return None

# ==================== REGISTER / GRANT ====================
def generate_signature(payload_str):
    return hmac.new(API_KEY, payload_str.encode(), hashlib.sha256).hexdigest()

async def register_account(password, gop_url, app_version, max_retries=REGISTER_MAX_RETRY):
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    rp = {"app_id":100067,"client_type":2,"password":password,"source":2}
    payload = json.dumps(rp, separators=(',',':'))
    sig = generate_signature(payload)
    headers = {
        "User-Agent": f"GarenaMSDK/4.0.44(SM-E135F ;Android 14;en;GB;app {app_version} 2019118525;)",
        "Authorization": f"Signature {sig}",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8"}

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession(connector=connector) as s:
                async with s.post(f"{gop_url}/api/v2/oauth/guest:register",
                                  headers=headers, data=payload,
                                  timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    txt = await resp.text()
                    data = json.loads(txt)
                    if data.get("code") == 0:
                        return data["data"]["uid"]

                    code = data.get("code")
                    if code == 1006:
                        wait = attempt * 3.0
                        print_warning(f"[REGISTER] 1006 (rate-limit) → retry {attempt}/{max_retries} in {wait}s")
                        await asyncio.sleep(wait)
                        continue

                    print_error(f"[REGISTER] code={code} msg={data.get('msg')}")
                    return None
        except Exception as e:
            print_error(f"[REGISTER] attempt {attempt}: {e}")
            await asyncio.sleep(attempt * 1.5)
    print_error(f"[REGISTER] all {max_retries} retries failed")
    return None

async def grant_token(uid, password, gop_url, app_version, max_retries=GRANT_MAX_RETRY):
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    gp = {"client_id":100067,"client_secret":HEX_KEY,"client_type":2,
          "device_id":f"02-{uuid.uuid4()}","password":password,
          "response_type":"token","uid":int(uid)}
    payload = json.dumps(gp, separators=(',',':'))
    sig = generate_signature(payload)
    headers = {
        "User-Agent": f"GarenaMSDK/4.0.44(SM-E135F ;Android 14;en;GB;app {app_version} 2019118525;)",
        "Authorization": f"Signature {sig}",
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8"}

    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession(connector=connector) as s:
                async with s.post(f"{gop_url}/api/v2/oauth/guest/token:grant",
                                  headers=headers, data=payload,
                                  timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    txt = await resp.text()
                    data = json.loads(txt)
                    if data.get("code") == 0:
                        return data["data"]
                    code = data.get("code")
                    if code in (1006, 1007, 1008):
                        wait = attempt * 2.0
                        print_warning(f"[GRANT] {code} → retry {attempt}/{max_retries} in {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    print_error(f"[GRANT] code={code}")
                    return None
        except Exception as e:
            print_error(f"[GRANT] attempt {attempt}: {e}")
            await asyncio.sleep(attempt * 1.0)
    return None

# ==================== PAYLOAD ====================
async def get_payload(access_token, open_id, platform, version, lang_code="en"):
    device_id = f"Google|{uuid.uuid4()}"
    major_login = {
        "3": str(datetime.now())[:-7], "4": "free fire", "5": 1,
        "7": f"{version}",
        "8": "Android OS 14 / API-34 (UP1A.231005.007/E135FXXSEEZE2)",
        "9": "Handheld", "11": "CarrierDataNetwork",
        "12": 1672, "13": 750, "14": "338",
        "15": "ARMv7 VFPv3 NEON | 2002 | 8",
        "16": 3702, "17": "Mali-G52",
        "18": "OpenGL ES 3.2 v1.r38p1-01bet0-mbs2v41_0.6d20ec041e51b2f2d25dfc265586ebe8",
        "19": device_id, "20": "104.28.197.151", "21": lang_code,
        "22": f"{open_id}", "23": f"{platform}", "24": "Handheld",
        "25": "samsung SM-E135F", "26": "BD",
        "29": f"{access_token}", "30": 1, "42": "Cellular",
        "57": "7428b253defc164018c604a1ebbfebdf",
        "60": 52037, "61": 5355, "62": 3723, "63": 3,
        "64": 5483, "65": 52037, "66": 5483, "67": 52037,
        "73": 2,
        "74": "/data/app/~~yACsV8QOk9OexgajWQP30A==/com.dts.freefireth-Bi_wPVrrhYM2nYncc29q7Q==/lib/arm",
        "76": 1,
        "77": "b8e0cd5e295eee42f5860d3c86e483dd|/data/app/~~yACsV8QOk9OexgajWQP30A==/com.dts.freefireth-Bi_wPVrrhYM2nYncc29q7Q==/base.apk",
        "78": 3, "79": 1, "81": "32", "83": "2019121229",
        "86": "OpenGLES2", "87": 8191, "88": int(platform),
        "92": 16091, "93": "android",
        "94": "KqsHT3Yeqo3RLRl8efNiL3aL/1SHwlSrtK0DwNAqdkNBQz70TeVy+icaIwuR3UK4b65Uf3IG5xBFEv0uu+jQZI+rOYCmNCsXjJT4QcZaYgoaaUGG",
        "95": 111107,
        "96": "{\"cur_rate\":null,\"support_etc2\":false}",
        "97": 1, "98": 1,
        "99": f"{platform}", "100": f"{platform}",
        "102": "4503454457550c0766",
        "104": 53792, "105": 1,
        "106": "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/|https://core-bs.ggpolarbear.com/live/ABHotUpdates/|6b2078db9d22dd98f8e9386a39af8462",
        "107": "c8e41b7a93f02d56e1a94c7b8203f5d1",
    }
    get_login_data = dict(major_login)
    get_login_data["90"] = "Khulna"
    get_login_data["91"] = "D"
    get_login_data["99"] = "0"
    get_login_data["103"] = 1
    proto1 = create_proto(major_login).hex()
    proto2 = create_proto(get_login_data).hex()
    return bytes.fromhex(encrypt_aes(proto1)), bytes.fromhex(encrypt_aes(proto2))

# ==================== MAJOR LOGIN ====================
async def major_login(payload, login_url, release_version):
    url = f"{login_url.rstrip('/')}/MajorLogin"
    req_headers = {
        "Accept": "*/*", "Authorization": "Bearer ",
        "Content-Type": "application/x-www-form-urlencoded",
        "ReleaseVersion": f"{release_version}",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
        "X-Unity-Version": "2018.4.12f1",
    }
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(url, headers=req_headers, data=payload, ssl=ssl_context) as response:
                rc = await response.read()
                if response.status != 200: return None
                if len(rc) < 200: return None
                best = None; best_score = -1; best_off = 0
                for offset in [64, 0, 48, 32, 80, 16, 128, 8, 96, 60, 56, 40, 24, 20, 12, 4]:
                    if offset >= len(rc): continue
                    cb = rc[offset:]
                    cand = None
                    try: cand = decode_protobuf_dict(cb)
                    except Exception: cand = None
                    if not cand:
                        try:
                            c2 = decode_protobuf_2(cb)
                            if c2: cand = {str(k): {"data": v} for k, v in c2.items()}
                        except Exception: cand = None
                    if not cand: continue
                    keys = set(cand.keys())
                    has_jwt = ("8" in keys) or (8 in keys)
                    has_url = ("10" in keys) or (10 in keys)
                    score = len(cand) + (100 if has_jwt else 0) + (50 if has_url else 0)
                    if score > best_score:
                        best = cand; best_score = score; best_off = offset
                    if has_jwt and has_url: break
                if not best: return None
                if ("8" not in best) and (8 not in best): return None
                best["__RAW_HEX__"] = rc.hex()
                best["__OFFSET__"] = best_off
                return best
    except Exception as e:
        print_error(f"[MAJOR-LOGIN] {e}")
        return None

# ==================== MAJOR REGISTER ====================
async def major_register(release_v, access_token, open_id, name, game_version,
                          login_url, lang_code="en"):
    field14 = bytes(ord(c) ^ KEYSTREAM[i % 32] for i, c in enumerate(open_id))
    fields = {
        1: name, 2: access_token, 3: open_id,
        5: 102000007, 6: 4, 7: 1, 13: 1,
        14: field14, 15: lang_code, 16: 2,
        20: game_version, 21: 1, 22: GGRE_RAW,
    }
    proto = _encode_proto_std(fields)
    payload = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(proto, 16))
    url = f"{login_url.rstrip('/')}/MajorRegister"
    hdrs = {
        "Accept": "*/*", "Authorization": "Bearer ",
        "Content-Type": "application/x-www-form-urlencoded",
        "ReleaseVersion": f"{release_v}",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
        "X-Unity-Version": "2018.4.12f1",
    }
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.post(url, headers=hdrs, data=payload, ssl=ssl_ctx) as resp:
                content = await resp.read()
                if resp.status != 200 or not content: return None
                for off in [0, 64, 48, 32, 16]:
                    if off >= len(content): continue
                    try:
                        r = decode_protobuf_2(content[off:])
                        if r and 3 in r:
                            return {str(k): {"data": v} for k, v in r.items()}
                    except Exception: pass
                return None
    except Exception as e:
        print_error(f"[MAJOR-REG] {e}")
        return None

# ==================== CHOOSE REGION ====================
async def choose_region(region, jwt_token, login_url, release_version):
    region_code = region.upper()
    url = f"{login_url.rstrip('/')}/ChooseRegion"
    proto = create_proto({1: region_code})
    payload = bytes.fromhex(encrypt_aes(proto.hex()))
    hdrs = {
        "Accept-Encoding": "gzip",
        "Authorization": f"Bearer {jwt_token}",
        "Connection": "Keep-Alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "ReleaseVersion": f"{release_version}",
        "User-Agent": "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
        "X-GA": "v1 1", "X-GA-SV": str(int(time.time())),
        "X-Unity-Version": "2018.4.12f1",
    }
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as s:
            async with s.post(url, data=payload, headers=hdrs, ssl=ssl_ctx) as r:
                print_info(f"[CHOOSE-REGION] {region} → HTTP {r.status}")
                return r.status
    except Exception as e:
        print_error(f"[CHOOSE-REGION] {e}")
        return None

# ==================== GET LOGIN DATA ====================
async def get_login_data(payload, jwt_token, server_url, release_version):
    url = f"{server_url.rstrip('/')}/GetLoginData"
    hdrs = {"Accept":"*/*","Authorization":f"Bearer {jwt_token}",
        "Content-Type":"application/x-www-form-urlencoded",
        "ReleaseVersion":f"{release_version}",
        "User-Agent":"UnityPlayer/2018.4.12f1","X-GA":"v1 1",
        "X-GA-SV":str(int(time.time())),"X-Unity-Version":"2018.4.12f1"}
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False; ssl_ctx.verify_mode = ssl.CERT_NONE
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as s:
            async with s.post(url, headers=hdrs, data=payload, ssl=ssl_ctx) as r:
                if r.status != 200: return None
                content = await r.read()
                for off in [0,64,48,32,80,16,128,8,96]:
                    if off >= len(content): continue
                    try:
                        c = decode_protobuf_dict(content[off:])
                        if c and len(c) >= 3: return c
                    except Exception: pass
                for off in [0,64,48,32,80]:
                    if off >= len(content): continue
                    c = decode_protobuf_2(content[off:])
                    if c and len(c) >= 3:
                        return {str(k):{"data":v} for k,v in c.items()}
        return None
    except Exception: return None

# ==================== CREATE ONE ====================
async def create_one_account(region: str, index: int, total: int):
    print_sep()
    print_gen(f"🤖 CREATING BOT {index}/{total} | region={region}")
    print_sep()

    password = gen_password()
    nickname = gen_nickname()
    print_info(f"  [{index}] nickname: {nickname}")
    print_info(f"  [{index}] password: {password}")

    vc = await version_config(region)
    if not vc:
        print_error(f"  [{index}] version config failed")
        return None
    release_v, remote_v, login_url, gop_1, app_version = vc
    if not login_url.endswith("/"): login_url += "/"
    lang = REGION_LANG.get(region.upper(), "en")
    game_version = remote_v or app_version

    uid = await register_account(password, gop_1, app_version)
    if not uid:
        print_error(f"  [{index}] register failed")
        return None
    print_success(f"  [{index}] UID = {uid}")

    tok = await grant_token(uid, password, gop_1, app_version)
    if not tok:
        print_error(f"  [{index}] grant failed")
        return None
    open_id = tok["open_id"]
    access_token = tok["access_token"]
    platform = tok.get("platform", 4)

    major_payload, login_payload = await get_payload(
        access_token, open_id, platform, game_version, lang)
    if not major_payload or not login_payload:
        print_error(f"  [{index}] payload build failed")
        return None

    mr = await major_register(release_v, access_token, open_id, nickname,
                               game_version, login_url, lang)
    if not mr:
        print_error(f"  [{index}] MajorRegister failed")
        return None

    await asyncio.sleep(1.0)

    res_json = None
    for attempt in range(3):
        mp, lp = await get_payload(access_token, open_id, platform, game_version, lang)
        res_json = await major_login(mp, login_url, release_v)
        if res_json and (("8" in res_json) or (8 in res_json)):
            major_payload = mp; login_payload = lp
            break
        res_json = None
        await asyncio.sleep(1.0)

    if not res_json:
        print_error(f"  [{index}] MajorLogin #1 failed")
        return None

    def _gd(k):
        v = res_json.get(str(k))
        if isinstance(v, dict) and "data" in v: return v["data"]
        if k in res_json and not isinstance(res_json[k], dict): return res_json[k]
        if isinstance(v, dict): return v.get("data")
        return None

    jwt_token      = _gd(8)
    server_url_raw = _gd(10)
    server_time    = _gd(21)
    acc_id_raw     = _gd(1)

    if not jwt_token:
        print_error(f"  [{index}] no JWT")
        return None

    if not server_url_raw:
        cr_status = await choose_region(region, jwt_token, login_url, release_v)
        if cr_status != 200:
            print_error(f"  [{index}] ChooseRegion failed ({cr_status})")
            return None
        await asyncio.sleep(1.0)

        res_json2 = None
        for attempt in range(3):
            mp2, lp2 = await get_payload(access_token, open_id, platform, game_version, lang)
            print_step(f"  [{index}] MajorLogin #2 attempt {attempt+1}/3...")
            res_json2 = await major_login(mp2, login_url, release_v)
            if res_json2 and (("10" in res_json2) or (10 in res_json2)):
                res_json = res_json2
                login_payload = lp2
                break
            res_json2 = None
            await asyncio.sleep(1.0)

        if not res_json2:
            print_error(f"  [{index}] MajorLogin #2 failed")
            return None

        res_json = res_json2

        def _gd2(k):
            v = res_json.get(str(k))
            if isinstance(v, dict) and "data" in v: return v["data"]
            if k in res_json and not isinstance(res_json[k], dict): return res_json[k]
            if isinstance(v, dict): return v.get("data")
            return None

        jwt_token      = _gd2(8)
        server_url_raw = _gd2(10)
        server_time    = _gd2(21)
        acc_id_raw     = _gd2(1)

        if not server_url_raw:
            print_error(f"  [{index}] server_url missing")
            return None

    aes_ak, iv_i = _extract_key_iv(res_json)
    if not aes_ak or not iv_i:
        print_error(f"  [{index}] AES key/IV extract failed")
        return None

    ld = await get_login_data(login_payload, jwt_token, server_url_raw, release_v)
    level = 1
    if ld:
        def _gf(f, d=None):
            v = ld.get(str(f), {}).get("data")
            return v if v is not None else d
        level = int(_gf(6, 1) or 1)
        nickname = _gf(4, nickname) or nickname

    ad = {
        "uid": str(uid),
        "password": str(password)
    }
    
    print_success(f"  [{index}] ✅ Created | UID {acc_id_raw} | Lvl {level} | Nick: {nickname}")
    return ad

# ==================== REGION-WISE SAVE ====================
def get_region_file(region: str) -> str:
    return f"accounts-{region.upper()}.json"

def load_region_accounts(region: str) -> list:
    fp = get_region_file(region)
    if not os.path.exists(fp): return []
    try:
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f) or []
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_region_accounts(region: str, accounts: list):
    fp = get_region_file(region)
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
        print_success(f"📦 {len(accounts)} account(s) → {fp}")
        return True
    except Exception as e:
        print_error(f"save {fp} failed: {e}")
        return False

# ==================== CREATE MULTIPLE ====================
async def create_accounts(region: str, count: int = GEN_COUNT_DEFAULT):
    print_sep()
    print_gen(f"START | region={region} count={count}")
    print_gen(f"Save target: {get_region_file(region)}")
    print_sep()

    existing = load_region_accounts(region)
    existing_game_uids = {str(a.get("uid")) for a in existing if isinstance(a, dict) and a.get("uid")}
    print_info(f"Existing in {get_region_file(region)}: {len(existing)} account(s)")

    created = []
    for i in range(1, count + 1):
        try:
            ad = await create_one_account(region, i, count)
            if ad:
                if str(ad.get("uid")) in existing_game_uids:
                    print_warning(f"  duplicate UID {ad['uid']}, skipping save")
                else:
                    created.append(ad)
                    existing_game_uids.add(str(ad["uid"]))
                    existing_plus = existing + created
                    save_region_accounts(region, existing_plus)
            else:
                print_warning(f"bot {i} failed")
        except Exception as e:
            print_error(f"bot {i} exception: {e}")
            traceback.print_exc()

        if i < count:
            print_info(f"waiting {GEN_DELAY_BETWEEN}s before next bot...")
            await asyncio.sleep(GEN_DELAY_BETWEEN)

    if not created:
        print_error("No new accounts created.")
        return []

    print_sep()
    print_gen(f"🎉 COMPLETE — {len(created)} NEW account(s) created")
    print_gen(f"📦 File: {get_region_file(region)}")
    print_sep()
    return created

# ==================== MAIN ====================
async def main():
    banner()
    print_info(f"Nickname Prefix: {GEN_NICKNAME_PREFIX}")
    print_info(f"Password       : RANDOM 14 uppercase")
    print_info(f"Delay          : {GEN_DELAY_BETWEEN}s between bots")
    print_info(f"Save           : accounts-<REGION>.json (UID & PASS ONLY)")
    print_sep()

    region = choose_region_interactive()

    try:
        c = input(f"{C.CYAN}🔢 Count (1-50) [{GEN_COUNT_DEFAULT}]: {C.RESET}").strip()
        count = int(c) if c else GEN_COUNT_DEFAULT
    except Exception:
        count = GEN_COUNT_DEFAULT
    count = max(1, min(50, count))

    print_sep()
    print_gen(f"region={region} count={count}")
    print_gen(f"file={get_region_file(region)}")
    print_sep()

    await create_accounts(region, count)

    try: await client.aclose()
    except Exception: pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("stopped")