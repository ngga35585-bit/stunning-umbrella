"""
Discord Selfbot v3 — Voice Looper + Spam + Fun
Voice:   , prefix  (jvc, dmjvc, groupjvc, stop, stopall, swap, lista, addaudio, processall, addtoken, setprefix, uptime, help)
Spam:    ! single-line   $ multi-line   @ repeated   + spiced
Fun:     # prefix (ship, gay, pula, call, caine, sugi, pierzator, homo, lache, pule, trotuar, injosit, abandonat, avatar, userbanner, afkcheck)
Global:  % prefix (globalstart, globalstop, clear, groupadd)
Sus:     . prefix (porn, hentai, tentacle, boobs)
"""

import os, re, sys, json, time, random, asyncio, traceback, difflib, subprocess
import datetime
import requests
import aiohttp, discord
from discord import ActivityAssets, ActivityTimestamps
from urllib.parse import quote, unquote

# ──────────────────────────────────────────────────────────────
# OPUS
# ──────────────────────────────────────────────────────────────
def _load_opus() -> bool:
    import ctypes, ctypes.util
    known = [
        "/nix/store/c009qkkzprv85kq4g36cmkgmz4f0g380-heroic-fhs/usr/lib64/libopus.so.0",
        "/nix/store/c009qkkzprv85kq4g36cmkgmz4f0g380-heroic-fhs/usr/lib32/libopus.so.0",
    ]
    for p in known:
        if os.path.exists(p):
            try:
                discord.opus.load_opus(p)
                if discord.opus.is_loaded():
                    return True
            except Exception:
                pass
    lib = ctypes.util.find_library("opus")
    if lib:
        try:
            discord.opus.load_opus(lib)
            return discord.opus.is_loaded()
        except Exception:
            pass
    for _root, _dirs, _files in os.walk("/nix/store"):
        for _fn in _files:
            if "libopus" in _fn and _fn.endswith(".so.0"):
                try:
                    discord.opus.load_opus(os.path.join(_root, _fn))
                    if discord.opus.is_loaded():
                        return True
                except Exception:
                    pass
        if discord.opus.is_loaded():
            break
    return discord.opus.is_loaded()

_opus_ok = _load_opus()
print(f"[OPUS] loaded={_opus_ok} | is_loaded={discord.opus.is_loaded()}")

# ──────────────────────────────────────────────────────────────
# PATHS & CONFIG
# ──────────────────────────────────────────────────────────────
AUDIO_DIR   = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(AUDIO_DIR, "config.json")
TOKENS_FILE = os.path.join(AUDIO_DIR, "tokens.txt")
INFO_IMAGE  = os.path.join(AUDIO_DIR, "phantom.png")
SINGLE_FILE = os.path.join(AUDIO_DIR, "test.txt")
MULTI_FILE  = os.path.join(AUDIO_DIR, "test2.txt")
SPICED_FILE = os.path.join(AUDIO_DIR, "test3.txt")
START_TIME  = time.time()
BASE_PREFIX = ","
DISCORD_API = "https://discord.com/api/v10"

# ANSI colours
R   = "\u001b[0m"
GR  = "\u001b[30m"
YL  = "\u001b[33m"
BL  = "\u001b[34m"
WH  = "\u001b[37m"
BD  = "\u001b[1m"
UL  = "\u001b[4m"
GN  = "\u001b[32m"
RD  = "\u001b[31m"
MG  = "\u001b[35m"
CY  = "\u001b[36m"

OWNER_ID:   int = 458619321502138409
STATE_FILE: str = os.path.join("selfbot", "vc_state.json")  # rejoin state
MEMORIES_DIR: str = os.path.join(AUDIO_DIR, "memories")
OPENAI_KEY_FILE: str = os.path.join(AUDIO_DIR, ".openai_key")
RAWG_API_KEY = os.environ.get("RAWG_API_KEY")
os.makedirs(MEMORIES_DIR, exist_ok=True)

DEFAULT_PERSONALITY = (
    "Ești un prieten Gen Z super chill. Folosești slang modern și răspunzi natural. "
    "Folosești română implicit; dacă userul scrie în engleză, răspunzi în engleză."
)
DISCORD_GAMES: list[dict] = []

# ──────────────────────────────────────────────────────────────
# SHARED SPAM STATE  (module-level, shared across all bots)
# ──────────────────────────────────────────────────────────────
ALL_TOKENS: list[str] = []
ALL_BOTS:   list[discord.Client] = []   # populated on each on_ready

# key = (spam_type: "s"|"m"|"r"|"p", token_idx: int)
SPAM_RUNNING: dict[tuple, bool]         = {}
SPAM_DELAY:   dict[tuple, float]        = {}
SPAM_TYPING:  dict[tuple, bool]         = {}
SPAM_TASKS:   dict[tuple, asyncio.Task] = {}
SPAM_MSG:     dict[int, str]            = {}   # for repeated: token_idx -> message

GROUP_NAME_RUNNING = False
_GROUP_NAME_TASK: asyncio.Task | None = None
GROUP_NAMES_FILE = os.path.join(AUDIO_DIR, "group_names.txt")
GROUP_NAME_TEXTS = [
    "TRECI LA PULA",
    "MA PIS PE MATA",
    "SCLAVULE",
    "VA IAU IN PULA BAAAI",
    "IN GENUNCHI LA BECALI",
    "SCLAVILOR",
]

if os.path.isfile(GROUP_NAMES_FILE):
    with open(GROUP_NAMES_FILE, encoding="utf-8") as _f:
        _saved_group_names = [line.strip() for line in _f if line.strip()]
    if _saved_group_names:
        GROUP_NAME_TEXTS = _saved_group_names

def save_group_names() -> None:
    with open(GROUP_NAMES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(GROUP_NAME_TEXTS) + "\n")

DEFAULT_DELAY = 1.5

# ──────────────────────────────────────────────────────────────
# CONFIG / TOKEN HELPERS
# ──────────────────────────────────────────────────────────────
def load_config() -> dict:
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def load_tokens() -> list[str]:
    tokens: list[str] = []
    if os.path.isfile(TOKENS_FILE):
        with open(TOKENS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    tokens.append(line)
    for i in range(1, 21):
        val = os.environ.get(f"DISCORD_TOKEN_{i}", "").strip()
        if val and val not in tokens:
            tokens.append(val)
    val = os.environ.get("DISCORD_TOKEN", "").strip()
    if val and val not in tokens:
        tokens.append(val)
    return tokens[:20]

def save_token(token: str) -> None:
    lines: list[str] = []
    if os.path.isfile(TOKENS_FILE):
        with open(TOKENS_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
        f.write(token + "\n")

# ──────────────────────────────────────────────────────────────
# AI / RICH PRESENCE FEATURES (from the second archive)
# ──────────────────────────────────────────────────────────────
def _memory_path(user_id: int) -> str:
    return os.path.join(MEMORIES_DIR, f"{user_id}.json")

def _load_memory(user_id: int) -> dict:
    path = _memory_path(user_id)
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {"personality": DEFAULT_PERSONALITY, "history": []}

def _save_memory(user_id: int, data: dict) -> None:
    with open(_memory_path(user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _remember(memory: dict, role: str, content: str) -> None:
    memory.setdefault("history", []).append({"role": role, "content": content})
    memory["history"] = memory["history"][-20:]

def _get_openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(OPENAI_KEY_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""

def _save_openai_key(key: str) -> None:
    with open(OPENAI_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key.strip())
    try:
        os.chmod(OPENAI_KEY_FILE, 0o600)
    except OSError:
        pass

def _call_ai_sync(system_prompt: str, history: list[dict]) -> str:
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        api_key = openrouter_key
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        model = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://replit.com/",
            "X-Title": "Stunning Umbrella Selfbot",
        }
    else:
        api_key = _get_openai_key()
        endpoint = "https://api.openai.com/v1/chat/completions"
        model = "gpt-4o-mini"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    if not api_key:
        return "AI-ul nu este configurat. Adaugă OPENROUTER_API_KEY în Render."
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"model": model,
                  "messages": [{"role": "system", "content": system_prompt}] + history},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip() or "Nu știu ce să zic acum."
    except Exception as exc:
        print(f"[AI] Eroare: {exc}")
        return "Nu am putut contacta OpenAI. Verifică cheia și încearcă din nou."

async def _call_ai(system_prompt: str, history: list[dict]) -> str:
    return await asyncio.get_running_loop().run_in_executor(
        None, _call_ai_sync, system_prompt, history
    )

def _search_video_links_sync(query: str) -> list[tuple[str, str]]:
    """Searches public video results without inventing URLs."""
    results: list[tuple[str, str]] = []
    try:
        completed = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--dump-single-json", "--skip-download",
             f"ytsearch5:{query}"],
            capture_output=True, text=True, timeout=35,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            data = json.loads(completed.stdout)
            for entry in data.get("entries", []):
                if not entry:
                    continue
                url = entry.get("webpage_url") or entry.get("url")
                if url and not url.startswith("http"):
                    url = f"https://www.youtube.com/watch?v={url}"
                if url:
                    results.append((entry.get("title", "Video YouTube"), url))
    except Exception as exc:
        print(f"[VIDEO/YOUTUBE] Eroare: {exc}")

    if results:
        return results[:5]

    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/?q=" + quote(query + " video"),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
        for href, title in re.findall(
            r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            response.text, re.S,
        )[:5]:
            clean_title = re.sub(r"<[^>]+>", "", title).strip()
            href = unquote(href)
            match = re.search(r"uddg=([^&]+)", href)
            results.append((clean_title or "Rezultat video", unquote(match.group(1)) if match else href))
    except Exception as exc:
        print(f"[VIDEO/WEB] Eroare: {exc}")
    return results

def _search_web_sync(query: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/?q=" + quote(query),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
        matches = re.findall(
            r'<div class="result results_links[^"]*"[^>]*>.*?'
            r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</a?>',
            response.text, re.S,
        )
        for href, title, snippet in matches[:5]:
            href = unquote(href)
            redirect = re.search(r"uddg=([^&]+)", href)
            results.append({
                "title": re.sub(r"<[^>]+>", "", title).strip(),
                "url": unquote(redirect.group(1)) if redirect else href,
                "snippet": re.sub(r"<[^>]+>", "", snippet).strip(),
            })
    except Exception as exc:
        print(f"[WEB] Eroare: {exc}")
    return results

def _looks_like_video_request(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in (
        "video", "youtube", "youtube ul", "tiktok", "clip", "trailer",
        "filmuleț", "filmulet", "link de la",
    ))

def _check_internet_sync() -> tuple[bool, bool]:
    youtube_ok = web_ok = False
    try:
        youtube_ok = requests.get(
            "https://www.youtube.com", timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        ).ok
    except requests.RequestException:
        pass
    try:
        web_ok = requests.get(
            "https://html.duckduckgo.com/html/?q=test", timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        ).ok
    except requests.RequestException:
        pass
    return youtube_ok, web_ok

def _load_discord_games() -> list[dict]:
    try:
        response = requests.get(
            "https://discord.com/api/v9/applications/detectable", timeout=20
        )
        response.raise_for_status()
        return [
            {"id": game["id"], "name": game["name"], "icon_hash": game.get("icon_hash")}
            for game in response.json()
            if game.get("name") and game.get("icon_hash")
        ]
    except Exception as exc:
        print(f"[DB] Nu am putut încărca jocurile: {exc}")
        return []

def _find_game(query: str) -> dict | None:
    names = [game["name"].lower() for game in DISCORD_GAMES]
    query = query.lower().strip()
    for i, name in enumerate(names):
        if name == query or name.startswith(query):
            return DISCORD_GAMES[i]
    matches = difflib.get_close_matches(query, names, n=1, cutoff=0.5)
    return DISCORD_GAMES[names.index(matches[0])] if matches else None

def _discord_icon_url(app_id: str, icon_hash: str) -> str:
    return f"https://cdn.discordapp.com/app-icons/{app_id}/{icon_hash}.png"

def _rawg_game(query: str) -> dict | None:
    params = {"search": query, "page_size": 1}
    if RAWG_API_KEY:
        params["key"] = RAWG_API_KEY
    try:
        response = requests.get("https://api.rawg.io/api/games", params=params, timeout=10)
        response.raise_for_status()
        result = response.json().get("results", [])
        if result:
            return {"name": result[0]["name"], "image_url": result[0].get("background_image") or ""}
    except Exception as exc:
        print(f"[RAWG] Eroare: {exc}")
    return None

async def _build_activity(
    bot, game_name: str, image_url: str, app_id: str | None, device: str | None = None
):
    assets = ActivityAssets()
    if image_url:
        if "cdn.discordapp.com" in image_url or "media.discordapp.net" in image_url:
            assets = ActivityAssets(large_image=image_url, large_text=game_name)
        else:
            try:
                proxy_id = int(os.environ.get("APPLICATION_ID", str(bot.user.id)))
                proxied = await bot.proxy_external_application_assets(proxy_id, image_url)
                if proxied:
                    assets = ActivityAssets(large_image=proxied[0], large_text=game_name)
            except Exception as exc:
                print(f"[PROXY] Eroare: {exc}")
    return discord.Activity(
        type=discord.ActivityType.playing,
        name=game_name,
        state=f"Device: {device}" if device else None,
        assets=assets,
        timestamps=ActivityTimestamps(start=datetime.datetime.now(datetime.timezone.utc)),
        application_id=int(app_id) if app_id else None,
    )

# ──────────────────────────────────────────────────────────────
# AUDIO HELPERS
# ──────────────────────────────────────────────────────────────
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".webm", ".opus"}

def list_audio() -> list[str]:
    files = [
        f for f in os.listdir(AUDIO_DIR)
        if os.path.splitext(f)[1].lower() in AUDIO_EXTS
        and not f.startswith(".")
        and not f.startswith("__loud_")
    ]
    return sorted(files, key=lambda x: x.lower())

def song_name(filename: str) -> str:
    return os.path.splitext(filename)[0]

def loud_wav(src: str) -> str:
    base = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(AUDIO_DIR, f"__loud_{base}.wav")

async def process_loud(audio_path: str) -> tuple[bool, str]:
    """
    NUCLEAR LOUDNESS MASTERING CHAIN
    ══════════════════════════════════════════════════════════════
    Goal: maximum perceived loudness at 0 dBFS ceiling.
    No transparency, no dynamic range preservation.
    Distortion, clipping and pumping are acceptable side effects.

    Chain overview:
      1.  +60 dB input gain  — slam everything into the compressors
      2.  Compressor #1      — ultra-hard squash (60dB→20dB ratio, 0.1ms attack, 40dB makeup)
      3.  Compressor #2      — second squash pass, brings up quiet parts
      4.  Tanh saturation    — harmonic richness + soft ceiling
      5.  +30 dB gain        — re-inflate after first comp/sat block
      6.  Compressor #3      — third pass: attack 0.1ms, extreme ratio
      7.  Compressor #4      — fourth pass: flatten everything further
      8.  Hard clip           — asoftclip type=hard => hard brick wall distortion
      9.  +20 dB gain        — push again after hard clip
      10. Compressor #5      — fifth pass: final density squeeze
      11. Tanh saturation #2 — second saturation pass for extra harmonic fill
      12. +10 dB gain        — last push before limiter
      13. Brickwall limiter  — alimiter at 0.99 (≈ -0.09 dBFS), 0.1ms attack
    ══════════════════════════════════════════════════════════════
    After FFmpeg the source is further amplified by PCMVolumeTransformer ×15
    for additional in-Discord gain on top of the already maximised file.
    """
    out = loud_wav(audio_path)

    af = (
        # ══════════════════════════════════════════════════════════
        # NUCLEAR LOUDNESS — 1000x (+60 dB), FARA LIMITER
        # Distortie, clipping si pumping sunt efecte intentionate.
        # ══════════════════════════════════════════════════════════

        # 1. Taie sub-bass murdar sub 30 Hz
        "highpass=f=30,"

        # 2. +79.5 dB input slam (boost MAX — limita audibila)
        "volume=79.5dB,"

        # 3. Compressor #1 — threshold -60dB inseamna mereu activ
        #    makeup=64 (max FFmpeg) reinflationeaza la maximum
        "acompressor=threshold=-60dB:ratio=20:attack=0.1:release=5:makeup=64,"

        # 4. Compressor #2 — a doua pasare, prinde ce a scapat
        "acompressor=threshold=-40dB:ratio=20:attack=0.1:release=5:makeup=64,"

        # 5. Compander multipoint — trage toate partile silentioase
        #    spre 0 dBFS, comprima fara mila dynamic range-ul
        "compand=attacks=0:decays=0.01:points=-90/-90|-70/-50|-40/-20|-20/-6|0/0,"

        # 6. Hard clip — patreaza forma de unda la ±1.0 FS
        #    maxim RMS, maxim densitate, distortie intentionata
        "asoftclip=type=hard,"

        # 7. Compressor #3 — a treia pasare dupa hard clip
        "acompressor=threshold=-20dB:ratio=20:attack=0.1:release=5:makeup=64,"

        # 8. Tanh saturation — armonice, umple spectrul
        "asoftclip=type=tanh,"

        # 9. +49.5 dB push final (boost MAX) — fara limiter, semnal brut maxim
        "volume=49.5dB"
    )

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", audio_path,
        "-af", af,
        "-ac", "2",
        "-ar", "48000",
        "-c:a", "pcm_s16le",
        out,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode == 0 and os.path.isfile(out):
        return True, out
    return False, stderr.decode("utf-8", errors="replace")[-300:]

def resolve_audio(arg: str) -> str | None:
    if not arg:
        files = list_audio()
        return os.path.join(AUDIO_DIR, files[0]) if files else None
    try:
        n = int(arg)
        files = list_audio()
        if 1 <= n <= len(files):
            return os.path.join(AUDIO_DIR, files[n - 1])
    except ValueError:
        pass
    for f in list_audio():
        if f == arg or song_name(f).lower() == arg.lower():
            return os.path.join(AUDIO_DIR, f)
    arg_lower = arg.lower()
    for f in list_audio():
        if arg_lower in song_name(f).lower():
            return os.path.join(AUDIO_DIR, f)
    return None

def make_source(audio_path: str, seek_secs: float = 0) -> discord.AudioSource:
    lp   = loud_wav(audio_path)
    path = lp if os.path.isfile(lp) else audio_path
    before = ""
    if seek_secs > 1:
        before = f"-ss {int(seek_secs)}"
    src = discord.FFmpegPCMAudio(path, before_options=before)
    # ×15 software gain on top of the already nuclear-processed WAV.
    # This is the absolute maximum PCMVolumeTransformer will allow
    # without integer overflow on PCM s16le samples.
    return discord.PCMVolumeTransformer(src, volume=100.0)

# ── VC state helpers (rejoin after restart) ────────────────────
def save_vc_state(channel_id: int, audio_path: str, start_ts: float, is_dm: bool) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"channel_id": channel_id, "audio_path": audio_path,
                       "start_ts": start_ts, "is_dm": is_dm}, f)
    except Exception:
        pass

def load_vc_state() -> dict | None:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def clear_vc_state() -> None:
    try:
        os.remove(STATE_FILE)
    except Exception:
        pass

async def get_audio_duration(path: str) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except Exception:
        return 0.0

async def _auto_process_on_start() -> None:
    """La pornire: proceseaza melodiile care nu au inca cache loud."""
    files = list_audio()
    if not files:
        print(f"  {YL}[AutoProcess]{R} Nicio melodie gasita.")
        return
    pending = [f for f in files if not os.path.isfile(loud_wav(os.path.join(AUDIO_DIR, f)))]
    skipped = len(files) - len(pending)
    if not pending:
        print(f"  {GN}[AutoProcess]{R} Toate {len(files)} melodii sunt deja procesate. {GR}(skip){R}")
        return
    if skipped:
        print(f"  {GN}[AutoProcess]{R} {skipped}/{len(files)} deja procesate — procesez restul de {len(pending)}...")
    else:
        print(f"  {YL}[AutoProcess]{R} Procesez {len(pending)} melodii noi...")
    done = 0
    for filename in pending:
        path = os.path.join(AUDIO_DIR, filename)
        ok, err = await process_loud(path)
        if ok:
            done += 1
            print(f"  {GN}  ✓{R}  {filename}")
        else:
            print(f"  {RD}  ✗{R}  {filename}  {GR}({err[:80]}){R}")
    print(f"  {GN}[AutoProcess]{R} Gata — {done}/{len(pending)} procesate cu succes.")

# ──────────────────────────────────────────────────────────────
# SPAM HELPERS
# ──────────────────────────────────────────────────────────────
def load_spam_single() -> list[str]:
    if not os.path.isfile(SINGLE_FILE):
        return ["spam"]
    with open(SINGLE_FILE, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    return lines or ["spam"]

def load_spam_multi() -> list[str]:
    if not os.path.isfile(MULTI_FILE):
        return ["spam"]
    with open(MULTI_FILE, encoding="utf-8") as f:
        content = f.read()
    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    return blocks or load_spam_single()

def load_spam_spiced() -> list[str]:
    if not os.path.isfile(SPICED_FILE):
        return ["spam"]
    with open(SPICED_FILE, encoding="utf-8") as f:
        content = f.read()
    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    return blocks or load_spam_single()

async def api_post(sess: aiohttp.ClientSession, token: str, channel_id: int, content: str):
    try:
        async with sess.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers={"authorization": token, "content-type": "application/json"},
            json={"content": content},
        ) as r:
            if r.status == 429:
                data = await r.json()
                await asyncio.sleep(data.get("retry_after", 1))
    except Exception:
        pass

async def api_typing(sess: aiohttp.ClientSession, token: str, channel_id: int):
    try:
        async with sess.post(
            f"{DISCORD_API}/channels/{channel_id}/typing",
            headers={"authorization": token},
        ):
            pass
    except Exception:
        pass

async def _spam_loop(stype: str, idx: int, channel_id: int, mentions_str: str):
    key = (stype, idx)
    token = ALL_TOKENS[idx] if idx < len(ALL_TOKENS) else ""
    if not token:
        return
    async with aiohttp.ClientSession() as sess:
        while SPAM_RUNNING.get(key):
            delay   = SPAM_DELAY.get(key, DEFAULT_DELAY)
            typing  = SPAM_TYPING.get(key, False)
            try:
                if stype == "s":
                    for msg in load_spam_single():
                        if not SPAM_RUNNING.get(key):
                            break
                        if typing:
                            await api_typing(sess, token, channel_id)
                        text = f"{mentions_str} {msg}".strip()
                        await api_post(sess, token, channel_id, text)
                        await asyncio.sleep(delay)
                elif stype == "m":
                    for block in load_spam_multi():
                        if not SPAM_RUNNING.get(key):
                            break
                        for line in block.splitlines():
                            if not SPAM_RUNNING.get(key):
                                break
                            if typing:
                                await api_typing(sess, token, channel_id)
                            text = f"{mentions_str} {line}".strip()
                            await api_post(sess, token, channel_id, text)
                            await asyncio.sleep(delay)
                elif stype == "r":
                    msg = SPAM_MSG.get(idx, "spam")
                    text = f"{mentions_str} {msg}".strip()
                    if typing:
                        await api_typing(sess, token, channel_id)
                    await api_post(sess, token, channel_id, text)
                    await asyncio.sleep(delay)
                elif stype == "p":
                    for block in load_spam_spiced():
                        if not SPAM_RUNNING.get(key):
                            break
                        lines = [line.strip() for line in block.splitlines() if line.strip()]
                        for offset in range(0, len(lines), 10):
                            if not SPAM_RUNNING.get(key):
                                break
                            if typing:
                                await api_typing(sess, token, channel_id)
                            batch = lines[offset:offset + 10]
                            text = "\n".join(f"# > {line}" for line in batch)
                            if mentions_str:
                                text = f"{text} {mentions_str}"
                            await api_post(sess, token, channel_id, text)
                            await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(delay)

def start_spam(stype: str, idx: int, channel_id: int, mentions_str: str = ""):
    key = (stype, idx)
    if key in SPAM_TASKS and not SPAM_TASKS[key].done():
        SPAM_TASKS[key].cancel()
    SPAM_RUNNING[key] = True
    SPAM_TASKS[key] = asyncio.create_task(_spam_loop(stype, idx, channel_id, mentions_str))

def stop_spam(stype: str, idx: int):
    key = (stype, idx)
    SPAM_RUNNING[key] = False
    if key in SPAM_TASKS and not SPAM_TASKS[key].done():
        SPAM_TASKS[key].cancel()

async def _group_name_loop(group_id: int, token: str):
    global GROUP_NAME_RUNNING
    async with aiohttp.ClientSession() as sess:
        i = 0
        while GROUP_NAME_RUNNING:
            try:
                names = GROUP_NAME_TEXTS
                if not names:
                    await asyncio.sleep(2)
                    continue
                async with sess.patch(
                    f"{DISCORD_API}/channels/{group_id}",
                    headers={"authorization": token, "content-type": "application/json"},
                    json={"name": names[i % len(names)]},
                ) as r:
                    if r.status == 429:
                        data = await r.json()
                        await asyncio.sleep(data.get("retry_after", 2))
            except Exception:
                pass
            i += 1
            await asyncio.sleep(2)

def _parse_n(arg: str) -> int | None:
    try:
        return int(arg) - 1
    except (ValueError, TypeError):
        return None

def _mentions_str(mentions: list) -> str:
    return " ".join(m.mention for m in mentions)

# ──────────────────────────────────────────────────────────────
# HELP STRINGS
# ──────────────────────────────────────────────────────────────
HELP_VOICE = (
    f"{BD}{UL}VOICE COMMANDS  [ , ]{R}\n"
    f"{WH},jvc <canal_id> [nr/name]   {GR}|{BL} intra in canal{R}\n"
    f"{WH},dmjvc <user_id> [nr/name]  {GR}|{BL} voice call dm 1-la-1{R}\n"
    f"{WH},groupjvc <grup_id> [nr]    {GR}|{BL} voice call grup dm{R}\n"
    f"{WH},stop                       {GR}|{BL} opreste si iese{R}\n"
    f"{WH},stopall                    {GR}|{BL} opreste din tot{R}\n"
    f"{WH},swap <nr/name>             {GR}|{BL} schimba melodia{R}\n"
    f"{WH},lista                      {GR}|{BL} lista melodii{R}\n"
    f"{WH},addaudio <url/attach>      {GR}|{BL} adauga audio{R}\n"
    f"{WH},processall                 {GR}|{BL} proceseaza toate loud{R}\n"
    f"{WH},rename <nr> <nume>         {GR}|{BL} redenume melodie (owner){R}\n"
    f"{WH},move <nr> <nr_nou>         {GR}|{BL} muta pe slot (owner){R}\n"
    f"{WH},addtoken <tok>             {GR}|{BL} adauga token (owner){R}\n"
    f"{WH},removetoken <n>            {GR}|{BL} sterge token n (owner){R}\n"
    f"{WH},setprefix <p>              {GR}|{BL} schimba prefix{R}\n"
    f"{WH},uptime                     {GR}|{BL} timp rulare{R}\n"
    f"{WH},users                      {GR}|{BL} conturi conectate{R}\n"
    f"{WH},info                       {GR}|{BL} informatii despre selfbot{R}\n"
    f"{WH},help                       {GR}|{BL} acest meniu{R}"
)

HELP_SINGLE = (
    f"{BD}{UL}SINGLE LINE SPAM  [ ! ]{R}\n"
    f"{YL}!start [@mention...]        {GR}|{BL} porneste automat tokenul propriu{R}\n"
    f"{YL}!stop                       {GR}|{BL} opreste automat tokenul propriu{R}\n"
    f"{YL}!startall [@mention...]     {GR}|{BL} porneste toti tokenii{R}\n"
    f"{YL}!stopall                    {GR}|{BL} opreste toti{R}\n"
    f"{YL}!delay <n> <sec>            {GR}|{BL} delay token n{R}\n"
    f"{YL}!delayall <sec>             {GR}|{BL} delay toti{R}\n"
    f"{YL}!typing <n> true/false      {GR}|{BL} typing token n{R}\n"
    f"{YL}!typingall true/false       {GR}|{BL} typing toti{R}\n"
    f"{YL}!ngroup <group_id>          {GR}|{BL} schimba nume grup{R}\n"
    f"{YL}!gstop                      {GR}|{BL} opreste grup rename{R}\n"
    f"  Mesaje: selfbot/test.txt"
)

HELP_MULTI = (
    f"{BD}{UL}MULTI LINE SPAM  [ $ ]{R}\n"
    f"{YL}$start $stop $startall $stopall $delay $delayall $typing $typingall{R}\n"
    f"{GR}(acelasi mod ca ! dar din test2.txt){R}\n"
    f"{MG}Comenzi troll:{R}\n"
    f"{WH}$virus @user  $ddos <ip>  $hackuser <user>  $hackbank <user>{R}\n"
    f"{WH}$traceip <user>  $injectvirus <user>  $crackpassword <user>{R}\n"
    f"{WH}$hackai  $hackgov  $insult  $specialjoke  $av @user{R}\n"
    f"{WH}$dm @user <msg>  $encrypt <msg>  $decrypt <msg>  $tokenlist{R}"
)

HELP_REPEATED = (
    f"{BD}{UL}REPEATED MSG SPAM  [ @ ]{R}\n"
    f"{YL}@start <n> <mesaj>          {GR}|{BL} repeta mesaj cu token n{R}\n"
    f"{YL}@stop <n>                   {GR}|{BL} opreste token n{R}\n"
    f"{YL}@startall <mesaj>           {GR}|{BL} toti tokenii{R}\n"
    f"{YL}@stopall                    {GR}|{BL} opreste toti{R}\n"
    f"{YL}@delay <n> <sec>  @delayall <sec>{R}\n"
    f"{YL}@typing <n> true/false  @typingall true/false{R}"
)

HELP_SPICED = (
    f"{BD}{UL}SPICED SPAM  [ + ]{R}\n"
    f"{YL}+start +stop +startall +stopall +delay +delayall +typing +typingall{R}\n"
    f"{GR}(din test3.txt, 10 randuri trimise per mesaj, format: # > mesaj){R}\n"
    f"{CY}+stream <text>              {GR}|{BL} seteaza streaming status{R}\n"
    f"{CY}+loopstream <text>          {GR}|{BL} loop streaming status{R}"
)

HELP_AI = (
    f"{BD}{UL}AI / GAMES COMMANDS  [ & ]{R}\n"
    f"{CY}&start <joc>               {GR}|{BL} seteaza Rich Presence{R}\n"
    f"{CY}&stop                      {GR}|{BL} opreste Rich Presence{R}\n"
    f"{CY}&status                    {GR}|{BL} afiseaza activitatea curenta{R}\n"
    f"{CY}&browser <device>          {GR}|{BL} selecteaza dispozitivul{R}\n"
    f"{CY}&internet                  {GR}|{BL} verifica accesul la internet{R}\n"
    f"{CY}&addai <OpenAI key>        {GR}|{BL} configureaza OpenAI{R}\n"
    f"{CY}&askai <intrebare>         {GR}|{BL} intreaba AI-ul{R}\n"
    f"{CY}&setpersonality <text>     {GR}|{BL} schimba personalitatea AI{R}\n"
    f"{CY}&resetai                   {GR}|{BL} reseteaza memoria AI{R}"
)

HELP_FUN = (
    f"{BD}{UL}FUN COMMANDS  [ # ]{R}\n"
    f"{MG}#ship @u1 @u2  #gay @u  #pula [@u]  #call @u{R}\n"
    f"{MG}#caine @u  #sugi @u  #pierzator @u  #homo @u{R}\n"
    f"{MG}#lache @u  #pule @u  #trotuar @u  #injosit @u  #abandonat @u{R}\n"
    f"{MG}#avatar @u  #userbanner @u  #afkcheck @u{R}"
)

HELP_GLOBAL = (
    f"{BD}{UL}GLOBAL COMMANDS  [ % ]{R}\n"
    f"{GN}%globalstart [@mention...]  {GR}|{BL} porneste s+m+p pe token 2{R}\n"
    f"{GN}%globalstop                 {GR}|{BL} opreste tot spamul{R}\n"
    f"{GN}%clear [n]                  {GR}|{BL} sterge n mesaje proprii (def 10){R}\n"
    f"{GN}%groupadd <grp_id> <usr_id> {GR}|{BL} adauga user in grup{R}"
)

HELP_SUS = (
    f"{BD}{UL}SUS COMMANDS  [ . ]{R}\n"
    f"{RD}.porn  .hentai  .tentacle  .boobs{R}\n"
    f"{GR}(nekobot.xyz API){R}"
)

# ──────────────────────────────────────────────────────────────
# BOT FACTORY
# ──────────────────────────────────────────────────────────────
def make_bot(token: str, index: int, config: dict) -> discord.Client:
    from discord.ext import commands
    idx    = str(index)
    prefix = config.get("prefixes", {}).get(idx, BASE_PREFIX)
    bot    = commands.Bot(command_prefix=prefix, self_bot=True)

    loop_active:    dict[int, bool] = {}
    loop_file:      dict[int, str]  = {}
    dm_loop_active: dict[int, bool] = {}
    dm_loop_file:   dict[int, str]  = {}

    label_txt = f"[BOT-{index}]"
    # ── send helpers ───────────────────────────────────────────

    async def send_ansi(ch, text: str) -> None:
        try:
            await ch.send(f"```ansi\n{text}\n```")
        except Exception:
            try:
                plain = re.sub(r"\u001b\[[^m]*m", "", text)
                await ch.send(f"```\n{plain}\n```")
            except Exception:
                pass

    async def send_plain(ch, text: str) -> None:
        try:
            await ch.send(text)
        except Exception:
            pass

    async def do_ai_command(msg: discord.Message, cmd: str, args: str) -> None:
        """Rich Presence, memory-based AI and configuration commands."""
        ch = msg.channel

        async def cleanup() -> None:
            try:
                await msg.delete()
            except Exception:
                pass

        if cmd != "askai":
            await cleanup()
        if cmd == "addai":
            if not args:
                return await send_plain(
                    ch,
                    "✅ OpenAI este configurat." if _get_openai_key()
                    else "Folosire: &addai OPENAI_API_KEY",
                )
            _save_openai_key(args.split()[0])
            return await send_plain(ch, "✅ Cheia OpenAI a fost salvată securizat.")
        if cmd == "internet":
            youtube_ok, web_ok = await asyncio.get_running_loop().run_in_executor(
                None, _check_internet_sync
            )
            return await send_ansi(
                ch,
                f"{GN}Internet bot:{R} {'OK' if youtube_ok and web_ok else 'PARȚIAL'}\n"
                f"{WH}YouTube: {GN if youtube_ok else RD}{'OK' if youtube_ok else 'EROARE'}{R}\n"
                f"{WH}Web search: {GN if web_ok else RD}{'OK' if web_ok else 'EROARE'}{R}",
            )
        if cmd == "browser":
            parts = args.split(maxsplit=1)
            devices = {
                "desktop": "Desktop", "pc": "Desktop", "windows": "Desktop",
                "mac": "Desktop", "mobile": "Mobile", "telefon": "Mobile",
                "android": "Mobile", "ios": "Mobile", "vr": "VR",
                "web": "Web", "browser": "Web", "console": "Console",
                "ps5": "Console", "xbox": "Console", "switch": "Console",
                "tablet": "Tablet", "tv": "TV",
            }
            if not parts or parts[0].lower() not in devices:
                return await send_plain(
                    ch,
                    "Folosire: &games browser <desktop|mobile|vr|web|console|tablet|tv> <joc>",
                )
            device = devices[parts[0].lower()]
            await bot.change_presence(status=discord.Status.online, activity=None)
            return await send_plain(
                ch,
                f"🌐 Selectat: {device}. Discord afișează dispozitivul real "
                "doar după clientul oficial conectat; API-ul nu poate falsifica "
                "badge-ul Desktop/Mobile/VR și nu creează Rich Presence.",
            )
        if cmd == "start":
            if not args:
                return await send_plain(ch, "Folosire: &start nume joc")
            game = _find_game(args)
            if game:
                name, image, app_id = (
                    game["name"], _discord_icon_url(game["id"], game["icon_hash"]), game["id"]
                )
            else:
                rawg = await asyncio.get_running_loop().run_in_executor(None, _rawg_game, args)
                name = rawg["name"] if rawg else args.title()
                image, app_id = (rawg.get("image_url", "") if rawg else ""), None
            activity = await _build_activity(bot, name, image, app_id)
            await bot.change_presence(status=discord.Status.online, activity=activity)
            return await send_plain(ch, f"🎮 {name} setat.")
        if cmd == "stop":
            await bot.change_presence(status=discord.Status.online, activity=None)
            return await send_plain(ch, "⏹️ Rich Presence oprit.")
        if cmd == "status":
            user = getattr(getattr(msg, "guild", None), "me", None) or bot.user
            activities = getattr(user, "activities", [])
            text = "\n".join(
                f"• `{getattr(activity.type, 'name', activity.type)}` → **{getattr(activity, 'name', activity)}**"
                for activity in activities
            ) or "ℹ️ Nicio activitate activă."
            return await send_plain(ch, text)
        if cmd == "askai":
            if not args:
                return await send_plain(ch, "Folosire: &askai întrebarea")
            if _looks_like_video_request(args):
                results = await asyncio.get_running_loop().run_in_executor(
                    None, _search_video_links_sync, args
                )
                if results:
                    lines = [f"{CY}Rezultate video pentru: {args}{R}"]
                    lines.extend(f"{WH}{i}. {title}{R}\n{BL}{url}{R}"
                                 for i, (title, url) in enumerate(results, 1))
                    return await send_ansi(ch, "\n".join(lines))
                return await send_ansi(
                    ch, f"{YL}Nu am găsit rezultate video pentru: {args}{R}"
                )
            memory = _load_memory(msg.author.id)
            _remember(memory, "user", args)
            thinking = await ch.send("💭 ...")
            web_results = await asyncio.get_running_loop().run_in_executor(
                None, _search_web_sync, args
            )
            if web_results:
                web_context = "\n\n".join(
                    f"SURSĂ: {item['title']}\nLINK: {item['url']}\n"
                    f"REZUMAT: {item['snippet']}"
                    for item in web_results
                )
                system_prompt = (
                    memory["personality"] +
                    "\n\nFolosește următoarele rezultate web recente pentru răspuns. "
                    "Nu inventa informații și include linkurile relevante:\n" + web_context
                )
            else:
                system_prompt = memory["personality"]
            answer = await _call_ai(system_prompt, memory["history"])
            _remember(memory, "assistant", answer)
            _save_memory(msg.author.id, memory)
            try:
                await thinking.delete()
            except Exception:
                pass
            return await send_ansi(ch, f"{CY}{answer}{R}")
        if cmd == "setpersonality":
            memory = _load_memory(msg.author.id)
            if not args:
                return await send_plain(ch, f"Personalitate curentă:\n```{memory['personality'][:300]}```")
            memory["personality"], memory["history"] = args, []
            _save_memory(msg.author.id, memory)
            return await send_plain(ch, "✅ Personalitate actualizată; istoricul a fost resetat.")
        if cmd == "resetai":
            _save_memory(msg.author.id, {"personality": DEFAULT_PERSONALITY, "history": []})
            return await send_plain(ch, "✅ AI resetat la personalitatea implicită.")

    # ── playback ───────────────────────────────────────────────

    def play_audio(vc, audio_path: str, channel_id: int, is_dm: bool = False, seek_secs: float = 0) -> None:
        if not os.path.isfile(audio_path):
            return
        if is_dm:
            dm_loop_file[channel_id] = audio_path
        else:
            loop_file[channel_id] = audio_path

        # salvam starea pentru auto-rejoin dupa restart
        save_vc_state(channel_id, audio_path, time.time() - seek_secs, is_dm)

        def after(error):
            if error:
                print(f"{label_txt} [PLAY ERR] {error}")
            active = dm_loop_active if is_dm else loop_active
            if active.get(channel_id) and vc.is_connected():
                asyncio.run_coroutine_threadsafe(
                    _play_next(vc, channel_id, is_dm), bot.loop
                )

        try:
            vc.play(make_source(audio_path, seek_secs), after=after)
        except Exception as exc:
            print(f"{label_txt} Eroare play: {exc!r}")

    async def _play_next(vc, channel_id: int, is_dm: bool) -> None:
        active = dm_loop_active if is_dm else loop_active
        fmap   = dm_loop_file   if is_dm else loop_file
        path   = fmap.get(channel_id)
        if active.get(channel_id) and vc.is_connected() and not vc.is_playing() and path:
            play_audio(vc, path, channel_id, is_dm)

    # ── connect helpers ────────────────────────────────────────

    async def connect_server(guild, target_ch, audio_path, reply_ch) -> None:
        gid  = guild.id
        loop_active[gid] = True
        name = song_name(os.path.basename(audio_path))
        try:
            if guild.voice_client is not None:
                guild.voice_client.stop()
                if guild.voice_client.channel.id == target_ch.id:
                    play_audio(guild.voice_client, audio_path, gid)
                else:
                    await guild.voice_client.move_to(target_ch)
                    play_audio(guild.voice_client, audio_path, gid)
            else:
                vc = await target_ch.connect(self_deaf=False)
                play_audio(vc, audio_path, gid)
            await send_ansi(reply_ch,
                f"{GR}[{BL}Voice{GR}]{R} {WH}{target_ch.name}{R} {GR}>{R} {BL}{name}{R}")
        except discord.Forbidden:
            await send_ansi(reply_ch, f"{GR}[{YL}ERR{GR}]{R} {YL}Nu am permisiune.{R}")
        except Exception as exc:
            await send_ansi(reply_ch, f"{GR}[{YL}ERR{GR}]{R} {YL}{exc!r}{R}")

    async def connect_dm(dm_ch, audio_path, reply_ch) -> None:
        cid  = dm_ch.id
        dm_loop_active[cid] = True
        name = song_name(os.path.basename(audio_path))
        try:
            # GroupChannel nu accepta self_deaf; DMChannel accepta
            if isinstance(dm_ch, discord.channel.GroupChannel):
                vc = await dm_ch.connect()
            else:
                vc = await dm_ch.connect(self_deaf=False)
            play_audio(vc, audio_path, cid, is_dm=True)
            await send_ansi(reply_ch,
                f"{GR}[{BL}DM Voice{GR}]{R} {BL}{name}{R}")
        except Exception as exc:
            dm_loop_active[cid] = False
            await send_ansi(reply_ch, f"{GR}[{YL}ERR{GR}]{R} {YL}{exc!r}{R}")

    # ── voice command handlers ─────────────────────────────────

    async def do_help(ch) -> None:
        files = list_audio()
        desc = (
            f"{GR}Comenzi disponibile — prefix: {BL},{WH}  !  $  @  +  &  #  %  .{R}\n\n"
            f"{HELP_VOICE}\n\n"
            f"{GR}Alte prefixuri:{R}\n"
            f"{YL}!single {GR}|{BL} $multi {GR}|{BL} {RD}@repeated {GR}|{BL} {CY}+spiced {GR}|{BL} {MG}#fun {GR}|{BL} {CY}&games {GR}|{BL} {GN}%global {GR}|{BL} .sus{R}\n"
            f"{GR}Ver 4.1 made by becaliregele{R}  {GR}Melodii:{R} {BL}{len(files)}{R}"
        )
        await send_ansi(ch, desc)

    async def do_lista(ch) -> None:
        files = list_audio()
        if not files:
            await send_ansi(ch, f"{YL}Nicio melodie gasita.{R}")
            return
        lines = []
        for i, f in enumerate(files, 1):
            name_raw = song_name(f)
            name     = name_raw[:18] + "…" if len(name_raw) > 20 else name_raw
            ext      = os.path.splitext(f)[1].upper().lstrip(".")
            is_loud  = os.path.isfile(loud_wav(os.path.join(AUDIO_DIR, f)))
            mark     = f"{GN}✓ LOUD{R}" if is_loud else f"{YL}⚡ pen{R}"
            lines.append(
                f"{GR}[{BL}{i:>2}{GR}]{R} {mark} {WH}{BD}{name:<20}{R} {GR}[{ext}]{R}"
            )
        sep    = f"{GR}{'─' * 44}{R}"
        header = f"{BD}{MG}🎵  MUZICI  ({len(files)}){R}\n{sep}\n"
        await send_ansi(ch, header + "\n".join(lines) + f"\n{sep}")

    async def do_info(msg: discord.Message) -> None:
        """Send a short selfbot info card and its Phantom image."""
        ch = msg.channel
        try:
            await msg.delete()
        except Exception:
            pass
        text = (
            "**PHANTOM SELFbot**\n"
            "Creat de: **Becali.18m (becaliregele)**\n"
            "Comenzi disponibile: **60+**\n"
            "Prefixuri: `,` `!` `$` `@` `+` `&` `#` `%` `.`\n"
            "Categorii: Voice • Spam • Troll • Fun • Stream • AI • Global • Sus\n"
            "Python • Discord selfbot"
        )
        try:
            if os.path.isfile(INFO_IMAGE):
                await ch.send(text, file=discord.File(INFO_IMAGE, filename="phantom.png"))
            else:
                await ch.send(text)
        except Exception:
            await send_ansi(ch, f"{YL}Nu am putut trimite cardul info.{R}")

    async def do_jvc(args: str, guild, ch) -> None:
        parts    = args.split(maxsplit=1)
        canal_id = parts[0] if parts else ""
        song_arg = parts[1] if len(parts) > 1 else ""
        if not canal_id:
            await send_ansi(ch, f"{YL}Folosire: ,jvc <id_canal> [nr/name]{R}")
            return
        try:
            cid = int(canal_id)
        except ValueError:
            await send_ansi(ch, f"{YL}ID invalid: {canal_id}{R}")
            return
        if guild is None:
            target_guild, target_ch = None, None
            for g in bot.guilds:
                vc_ch = g.get_channel(cid)
                if vc_ch and isinstance(vc_ch, discord.VoiceChannel):
                    target_guild, target_ch = g, vc_ch
                    break
            if target_ch is None:
                await send_ansi(ch, f"{YL}Canal cu ID {cid} negasit.{R}")
                return
        else:
            target_guild = guild
            target_ch    = guild.get_channel(cid)
            if target_ch is None or not isinstance(target_ch, discord.VoiceChannel):
                await send_ansi(ch, f"{YL}Canal invalid: {cid}{R}")
                return
        audio_path = resolve_audio(song_arg)
        if audio_path is None:
            await send_ansi(ch, f"{YL}Melodia nu exista. Scrie ,lista{R}")
            return
        await connect_server(target_guild, target_ch, audio_path, ch)

    async def do_dmjvc(args: str, ch) -> None:
        parts = args.split(maxsplit=1)
        if not parts:
            await send_ansi(ch, f"{YL}Folosire: ,dmjvc <user_id> [nr/name]{R}")
            return
        try:
            uid = int(parts[0])
        except ValueError:
            await send_ansi(ch, f"{YL}ID invalid: {parts[0]}{R}")
            return
        audio_path = resolve_audio(parts[1] if len(parts) > 1 else "")
        if audio_path is None:
            await send_ansi(ch, f"{YL}Melodia nu exista. Scrie ,lista{R}")
            return
        try:
            user    = await bot.fetch_user(uid)
            dm_chan = await user.create_dm()
        except Exception as exc:
            await send_ansi(ch, f"{YL}User negasit: {exc!r}{R}")
            return
        await connect_dm(dm_chan, audio_path, ch)

    async def do_groupjvc(args: str, ch) -> None:
        parts = args.split(maxsplit=1)
        if not parts:
            await send_ansi(ch, f"{YL}Folosire: ,groupjvc <grup_id> [nr/name]{R}")
            return
        try:
            gid = int(parts[0])
        except ValueError:
            await send_ansi(ch, f"{YL}ID invalid: {parts[0]}{R}")
            return
        audio_path = resolve_audio(parts[1] if len(parts) > 1 else "")
        if audio_path is None:
            await send_ansi(ch, f"{YL}Melodia nu exista. Scrie ,lista{R}")
            return
        try:
            group_ch = bot.get_channel(gid) or await bot.fetch_channel(gid)
        except Exception as exc:
            await send_ansi(ch, f"{YL}Grup negasit: {exc!r}{R}")
            return
        await connect_dm(group_ch, audio_path, ch)

    async def do_stop(guild, ch) -> None:
        if guild is not None:
            loop_active[guild.id] = False
            if guild.voice_client is not None:
                guild.voice_client.stop()
                await guild.voice_client.disconnect()
                await send_ansi(ch, f"{GR}[{BL}Stop{GR}]{R} {WH}Oprit.{R}")
            else:
                await send_ansi(ch, f"{YL}Nu e conectat.{R}")
        else:
            stopped = False
            for g in bot.guilds:
                if g.voice_client is not None:
                    loop_active[g.id] = False
                    g.voice_client.stop()
                    await g.voice_client.disconnect()
                    stopped = True
            for vc in list(bot.voice_clients):
                cid = vc.channel.id
                dm_loop_active[cid] = False
                vc.stop()
                await vc.disconnect()
                stopped = True
            if stopped:
                await send_ansi(ch, f"{GR}[{BL}Stop{GR}]{R} {WH}Oprit din tot.{R}")
            else:
                await send_ansi(ch, f"{YL}Nu e conectat nicaieri.{R}")

    async def do_stopall(ch) -> None:
        for cid in list(dm_loop_active.keys()):
            dm_loop_active[cid] = False
        for vc in list(bot.voice_clients):
            try:
                vc.stop()
                await vc.disconnect()
            except Exception:
                pass
        await send_ansi(ch, f"{GR}[{BL}Stop{GR}]{R} {WH}Oprit din tot (servere + DM).{R}")

    async def do_swap(args: str, guild, ch) -> None:
        audio_path = resolve_audio(args.strip())
        if audio_path is None:
            await send_ansi(ch, f"{YL}Melodia nu exista. Scrie ,lista{R}")
            return
        name    = song_name(os.path.basename(audio_path))
        swapped = False
        if guild is not None and guild.voice_client is not None:
            loop_file[guild.id]   = audio_path
            loop_active[guild.id] = True
            guild.voice_client.stop()
            swapped = True
        if not swapped:
            for g in bot.guilds:
                if g.voice_client is not None:
                    loop_file[g.id]   = audio_path
                    loop_active[g.id] = True
                    g.voice_client.stop()
                    swapped = True
        if not swapped:
            for vc in list(bot.voice_clients):
                cid = vc.channel.id
                dm_loop_file[cid]   = audio_path
                dm_loop_active[cid] = True
                vc.stop()
                swapped = True
        if swapped:
            await send_ansi(ch, f"{GR}[{BL}Swap{GR}]{R} {WH}{name}{R}")
        else:
            await send_ansi(ch, f"{YL}Nu e nimic in redare.{R}")

    async def do_process_all(ch) -> None:
        files = list_audio()
        if not files:
            await send_ansi(ch, f"{YL}Nicio melodie gasita.{R}")
            return
        await send_ansi(ch,
            f"{GR}[{YL}Process{GR}]{R} {WH}Procesez toate cele {len(files)} melodii...{R}")
        # sterge vechile loud ca sa rescriem cu setari noi
        for f in files:
            old_loud = loud_wav(os.path.join(AUDIO_DIR, f))
            if os.path.isfile(old_loud):
                os.remove(old_loud)
        done, failed = 0, 0
        for filename in files:
            path = os.path.join(AUDIO_DIR, filename)
            ok, _ = await process_loud(path)
            if ok:
                done += 1
            else:
                failed += 1
        status = f"{BL}{done}{R}{WH} ok{R}"
        if failed:
            status += f"  {YL}{failed} erori{R}"
        await send_ansi(ch, f"{GR}[{BL}OK{GR}]{R} {WH}Gata.{R}  {status}")

    async def do_addaudio(args: str, msg: discord.Message, ch) -> None:
        def _next_num() -> int:
            existing = [f for f in os.listdir(AUDIO_DIR)
                        if f.endswith(".mp3") and not f.startswith("__loud_")]
            nums = []
            for f in existing:
                m = re.match(r"(\d+)\.(?:mp3|m4a|ogg|wav)", f)
                if m:
                    nums.append(int(m.group(1)))
            return max(nums, default=0) + 1

        url = args.strip()
        if msg.attachments:
            att      = msg.attachments[0]
            nxt      = _next_num()
            out_path = os.path.join(AUDIO_DIR, f"{nxt:02d}.mp3")
            await send_ansi(ch, f"{GR}[{YL}Download{GR}]{R} {WH}{nxt:02d}.mp3{R}")
            async with aiohttp.ClientSession() as session:
                async with session.get(att.url) as resp:
                    with open(out_path, "wb") as f:
                        f.write(await resp.read())
            await send_ansi(ch, f"{GR}[{YL}Process{GR}]{R} {WH}Fac ultra loud...{R}")
            ok, result = await process_loud(out_path)
            if ok:
                await send_ansi(ch, f"{GR}[{BL}OK{GR}]{R} {WH}{nxt:02d}.mp3{R} adaugat.")
            else:
                await send_ansi(ch, f"{YL}Eroare: {result[:200]}{R}")
            return
        if not url:
            await send_ansi(ch, f"{YL}Folosire: ,addaudio <url YouTube> sau ataseaza un fisier audio{R}")
            return
        if "youtube.com" not in url and "youtu.be" not in url:
            await send_ansi(ch, f"{YL}Suportat: link YouTube sau fisier atasat.{R}")
            return
        await send_ansi(ch, f"{GR}[{YL}Download{GR}]{R} {WH}Descarc de pe YouTube...{R}")
        nxt = _next_num()
        out_template = os.path.join(AUDIO_DIR, f"{nxt:02d}.%(ext)s")
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--extract-audio", "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", out_template,
            "--no-playlist", "--print", "after_move:filepath", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace")[-300:]
            await send_ansi(ch, f"{YL}Eroare download:\n{err[-200:]}{R}")
            return
        raw_out  = stdout.decode("utf-8", errors="replace").strip()
        out_path = raw_out.splitlines()[-1].strip() if raw_out else ""
        if not out_path or not os.path.isfile(out_path):
            candidate = os.path.join(AUDIO_DIR, f"{nxt:02d}.mp3")
            out_path = candidate if os.path.isfile(candidate) else ""
        if not out_path or not os.path.isfile(out_path):
            await send_ansi(ch, f"{YL}Fisierul descarcat nu a fost gasit.{R}")
            return
        await send_ansi(ch, f"{GR}[{YL}Process{GR}]{R} {WH}{nxt:02d}.mp3{R} — fac ultra loud...")
        ok, result = await process_loud(out_path)
        if ok:
            await send_ansi(ch, f"{GR}[{BL}OK{GR}]{R} {WH}{nxt:02d}.mp3{R} adaugat.")
        else:
            await send_ansi(ch, f"{YL}Eroare: {result[:200]}{R}")

    async def do_addtoken(args: str, msg: discord.Message, ch) -> None:
        if OWNER_ID is not None and msg.author.id != OWNER_ID:
            await send_ansi(ch, f"{YL}Doar ownerul poate adauga tokenuri.{R}")
            return
        new_token = args.strip()
        if not new_token:
            await send_ansi(ch, f"{YL}Folosire: ,addtoken <token>{R}")
            return
        current = load_tokens()
        if new_token in current:
            await send_ansi(ch, f"{YL}Token deja existent.{R}")
            return
        if len(current) >= 20:
            await send_ansi(ch, f"{YL}Limita de 20 tokenuri atinsa.{R}")
            return
        save_token(new_token)
        await send_ansi(ch,
            f"{GR}[{BL}Token{GR}]{R} {WH}Token #{len(current)+1} adaugat. Repornesc in 2s...{R}")
        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def do_removetoken(args: str, msg: discord.Message, ch) -> None:
        if OWNER_ID is not None and msg.author.id != OWNER_ID:
            await send_ansi(ch, f"{YL}Doar ownerul poate sterge tokenuri.{R}")
            return
        idx = args.strip()
        if not idx:
            await send_ansi(ch, f"{YL}Folosire: ,removetoken <numar>{R}")
            return
        try:
            n = int(idx)
        except ValueError:
            await send_ansi(ch, f"{YL}Numar invalid.{R}")
            return
        current = load_tokens()
        if n < 1 or n > len(current):
            await send_ansi(ch, f"{YL}Index invalid (1-{len(current)}).{R}")
            return
        removed = current.pop(n - 1)
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            for line in current:
                f.write(line + "\n")
        await send_ansi(ch,
            f"{GR}[{BL}Token{GR}]{R} {WH}Token #{n} sters. Repornesc in 2s...{R}")
        await asyncio.sleep(2)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def do_rename(args: str, msg: discord.Message, ch) -> None:
        if OWNER_ID is not None and msg.author.id != OWNER_ID:
            await send_ansi(ch, f"{YL}Doar ownerul poate redenumi.{R}")
            return
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await send_ansi(ch, f"{YL}Folosire: ,rename <nr> <nume_nou>{R}")
            return
        try:
            n = int(parts[0])
        except ValueError:
            await send_ansi(ch, f"{YL}Nr invalid.{R}")
            return
        files = list_audio()
        if n < 1 or n > len(files):
            await send_ansi(ch, f"{YL}Index invalid (1-{len(files)}).{R}")
            return
        old_name = files[n - 1]
        old_path = os.path.join(AUDIO_DIR, old_name)
        new_name = parts[1].strip()
        # sanitize filename
        safe = re.sub(r'[<>"/\\|?*]', '_', new_name)
        ext = os.path.splitext(old_name)[1]
        new_filename = f"{safe}{ext}"
        new_path = os.path.join(AUDIO_DIR, new_filename)
        if os.path.exists(new_path):
            await send_ansi(ch, f"{YL}Exista deja o melodie cu numele asta.{R}")
            return
        # rename loud cache if exists
        old_loud = loud_wav(old_path)
        if os.path.isfile(old_loud):
            os.remove(old_loud)
        os.rename(old_path, new_path)
        await send_ansi(ch,
            f"{GR}[{BL}Rename{GR}]{R} {WH}{old_name}{R} {GR}->{R} {WH}{new_filename}{R}")

    async def do_move(args: str, msg: discord.Message, ch) -> None:
        if OWNER_ID is not None and msg.author.id != OWNER_ID:
            await send_ansi(ch, f"{YL}Doar ownerul poate muta.{R}")
            return
        parts = args.split()
        if len(parts) < 2:
            await send_ansi(ch, f"{YL}Folosire: ,move <nr> <nr_nou>{R}")
            return
        try:
            old_n = int(parts[0])
            new_n = int(parts[1])
        except ValueError:
            await send_ansi(ch, f"{YL}Nr invalid.{R}")
            return
        files = list_audio()
        if old_n < 1 or old_n > len(files):
            await send_ansi(ch, f"{YL}Index sursa invalid (1-{len(files)}).{R}")
            return
        if new_n < 1:
            await send_ansi(ch, f"{YL}Index destinatie invalid.{R}")
            return
        old_file = files[old_n - 1]
        old_path = os.path.join(AUDIO_DIR, old_file)
        ext = os.path.splitext(old_file)[1]
        # compute target slot name
        existing_nums = set()
        for f in files:
            m = re.match(r'(\d+)\.(?:mp3|m4a|ogg|wav)', f)
            if m:
                existing_nums.add(int(m.group(1)))
        existing_nums.discard(old_n)
        if new_n in existing_nums:
            # shift everything >= new_n up by one
            shift_files = []
            for f in files:
                m = re.match(r'(\d+)\.(mp3|m4a|ogg|wav)', f)
                if m:
                    num = int(m.group(1))
                    if num >= new_n and num != old_n:
                        shift_files.append((f, num, m.group(2)))
            # sort descending so renaming doesn't clobber
            shift_files.sort(key=lambda x: x[1], reverse=True)
            for f, num, fext in shift_files:
                old_p = os.path.join(AUDIO_DIR, f)
                new_p = os.path.join(AUDIO_DIR, f"{num + 1:02d}.{fext}")
                # delete loud cache before rename
                old_l = loud_wav(old_p)
                if os.path.isfile(old_l):
                    os.remove(old_l)
                os.rename(old_p, new_p)
        new_filename = f"{new_n:02d}{ext}"
        new_path = os.path.join(AUDIO_DIR, new_filename)
        # delete old loud cache
        old_l = loud_wav(old_path)
        if os.path.isfile(old_l):
            os.remove(old_l)
        os.rename(old_path, new_path)
        await send_ansi(ch,
            f"{GR}[{BL}Move{GR}]{R} {WH}{old_file}{R} {GR}->{R} {WH}{new_filename}{R}")

    async def do_setprefix(args: str, ch) -> None:
        nonlocal prefix
        new_p = args.strip()
        if not new_p:
            await send_ansi(ch, f"{YL}Folosire: ,setprefix <prefix_nou>{R}")
            return
        if len(new_p) > 5:
            await send_ansi(ch, f"{YL}Prefix prea lung (max 5 caractere).{R}")
            return
        config.setdefault("prefixes", {})[idx] = new_p
        save_config(config)
        prefix             = new_p
        bot.command_prefix = new_p
        await send_ansi(ch, f"{GR}[{BL}Prefix{GR}]{R} {WH}{new_p}{R}")

    async def do_uptime(ch) -> None:
        elapsed = int(time.time() - START_TIME)
        h, rem  = divmod(elapsed, 3600)
        m, s    = divmod(rem, 60)
        await send_ansi(ch, f"{GR}[{BL}Uptime{GR}]{R} {WH}{h}h {m}m {s}s{R}")

    # ── SPAM command handler ────────────────────────────────────

    async def do_spam_cmd(msg: discord.Message, stype: str, cmd: str, rest_parts: list[str]) -> None:
        global GROUP_NAME_RUNNING, _GROUP_NAME_TASK, GROUP_NAME_TEXTS
        ch         = msg.channel
        channel_id = ch.id
        mentions   = msg.mentions
        tok_main   = ALL_TOKENS[0] if ALL_TOKENS else token

        async def reply(text):
            await send_ansi(ch, text)

        async def safe_del():
            try:
                await msg.delete()
            except Exception:
                pass

        if cmd == "start":
            men = _mentions_str(mentions)
            await safe_del()
            if rest_parts and _parse_n(rest_parts[0]) is not None:
                n = _parse_n(rest_parts[0])
                if n < 0 or n >= len(ALL_TOKENS):
                    return await reply(f"{RD}Token index invalid (1-{len(ALL_TOKENS)}).{R}")
                start_spam(stype, n, channel_id, men)
                await reply(f"{GN}Spam pornit token {n+1}.{R}")
            else:
                start_spam(stype, index, channel_id, men)
                await reply(f"{GN}Spam pornit automat pe tokenul propriu ({index+1}).{R}")

        elif cmd == "stop":
            n = _parse_n(rest_parts[0]) if rest_parts else None
            if n is None:
                stop_spam(stype, index)
            elif n < 0 or n >= len(ALL_TOKENS):
                return await reply(f"{RD}Token index invalid.{R}")
            else:
                stop_spam(stype, n)
            await safe_del()

        elif cmd == "startall":
            men = _mentions_str(mentions)
            await safe_del()
            for i in range(len(ALL_TOKENS)):
                start_spam(stype, i, channel_id, men)
            await reply(f"{GN}Spam pornit pentru {len(ALL_TOKENS)} tokenuri.{R}")

        elif cmd == "stopall":
            for i in range(len(ALL_TOKENS)):
                stop_spam(stype, i)
            await safe_del()

        elif cmd == "delay":
            if not rest_parts:
                return await reply(f"{YL}Folosire: delay <sec> sau delay <n> <sec>{R}")
            try:
                if len(rest_parts) >= 2 and _parse_n(rest_parts[0]) is not None:
                    indexes = [_parse_n(rest_parts[0])]
                    d = float(rest_parts[1])
                else:
                    indexes = [index]
                    d = float(rest_parts[0])
            except ValueError:
                return await reply(f"{RD}Delay invalid.{R}")
            for n in indexes:
                SPAM_DELAY[(stype, n)] = d
            await safe_del()

        elif cmd == "delayall":
            if not rest_parts:
                return await reply(f"{YL}Folosire: delayall <sec>{R}")
            try:
                d = float(rest_parts[0])
            except ValueError:
                return await reply(f"{RD}Delay invalid.{R}")
            for i in range(len(ALL_TOKENS)):
                SPAM_DELAY[(stype, i)] = d
            await safe_del()

        elif cmd == "typing":
            if not rest_parts:
                return await reply(f"{YL}Folosire: typing true/false sau typing <n> true/false{R}")
            if len(rest_parts) >= 2 and _parse_n(rest_parts[0]) is not None:
                indexes = [_parse_n(rest_parts[0])]
                value = rest_parts[1]
            else:
                indexes = [index]
                value = rest_parts[0]
            val = value.lower() in ("true", "1", "yes")
            for n in indexes:
                SPAM_TYPING[(stype, n)] = val
            await safe_del()

        elif cmd == "typingall":
            if not rest_parts:
                return await reply(f"{YL}Folosire: typingall true/false{R}")
            val = rest_parts[0].lower() in ("true", "1", "yes")
            for i in range(len(ALL_TOKENS)):
                SPAM_TYPING[(stype, i)] = val
            await safe_del()

        elif cmd == "tokenlist":
            await reply(f"{CY}{len(ALL_TOKENS)} tokenuri incarcate.{R}")

        elif cmd == "addgrouptext":
            text = " ".join(rest_parts).strip()
            if not text:
                return await reply(f"{YL}Folosire: $addgrouptext <text>{R}")
            if len(text) > 100:
                return await reply(f"{YL}Textul poate avea maximum 100 de caractere.{R}")
            if text not in GROUP_NAME_TEXTS:
                GROUP_NAME_TEXTS.append(text)
                save_group_names()
            await safe_del()
            await reply(f"{GN}Text adaugat in lista grupului ({len(GROUP_NAME_TEXTS)} texte).{R}")

        elif cmd in ("ngroup", "startgroup"):
            # $startgroup uses the current group DM by default; an explicit
            # group ID is still accepted for compatibility with !ngroup.
            group_arg = rest_parts[0] if rest_parts else str(msg.channel.id)
            try:
                gid = int(group_arg)
            except ValueError:
                return await reply(f"{RD}ID invalid.{R}")
            GROUP_NAME_RUNNING = True
            if _GROUP_NAME_TASK and not _GROUP_NAME_TASK.done():
                _GROUP_NAME_TASK.cancel()
            _GROUP_NAME_TASK = asyncio.create_task(_group_name_loop(gid, tok_main))
            await safe_del()
            await reply(f"{GN}Group name changer pornit.{R}")

        elif cmd == "gstop":
            GROUP_NAME_RUNNING = False
            if _GROUP_NAME_TASK and not _GROUP_NAME_TASK.done():
                _GROUP_NAME_TASK.cancel()
            await safe_del()
            await reply(f"{YL}Group name changer oprit.{R}")

        elif cmd in ("single", "multi", "repeated", "spiced"):
            mapping = {
                "single": HELP_SINGLE, "multi": HELP_MULTI,
                "repeated": HELP_REPEATED, "spiced": HELP_SPICED,
            }
            await reply(mapping[cmd])

    # ── TROLL commands ($ prefix) ───────────────────────────────

    async def do_troll(msg: discord.Message, cmd: str, raw_content: str) -> None:
        ch       = msg.channel
        mentions = msg.mentions
        tok_main = ALL_TOKENS[0] if ALL_TOKENS else token

        async def post(text: str):
            try:
                await ch.send(text)
            except Exception:
                pass

        async def safe_del():
            try:
                await msg.delete()
            except Exception:
                pass

        async def reply(text: str):
            await send_ansi(ch, text)

        if cmd == "virus":
            if not mentions:
                return await reply(f"{YL}Folosire: $virus @user{R}")
            u = mentions[0]
            await safe_del()
            for line in [
                f"Incepand atacul cibernetic asupra contului lui {u.mention}... Hack reusit!",
                f"Injectand codurile de hack in sistemul lui {u.mention}... Hack reusit!",
                f"Activand protocolul de hack pentru {u.mention}... Sistemul cedeaza!",
                f"Spargem sistemul lui {u.mention}... Hack reusit! Acces total obtinut.",
                f"Algoritmii aplicati asupra contului lui {u.mention}. Preluare completa!",
            ]:
                await post(line)
                await asyncio.sleep(1)

        elif cmd == "ddos":
            parts = raw_content.split()
            ip = parts[0] if parts else "127.0.0.1"
            await safe_del()
            await post(f"Initiating DDoS attack on {ip}... Success! Target IP {ip} mai ai 24h sa iti ceri scuze.")

        elif cmd == "hackuser":
            parts = raw_content.split()
            user  = parts[0] if parts else (mentions[0].mention if mentions else "?")
            await safe_del()
            await post(f"Hacking into {user}'s account... Success! Access granted.")

        elif cmd == "hackbank":
            parts = raw_content.split()
            user  = parts[0] if parts else (mentions[0].mention if mentions else "?")
            bal   = round(random.uniform(1000, 1000000), 2)
            await safe_del()
            await post(f"Hacking into {user}'s bank account... Success! Balance: ${bal}")

        elif cmd == "traceip":
            parts = raw_content.split()
            user  = parts[0] if parts else (mentions[0].mention if mentions else "?")
            ip    = ".".join(str(random.randint(0, 255)) for _ in range(4))
            loc   = random.choice(["New York, USA", "London, UK", "Tokyo, Japan", "Moscow, Russia"])
            await safe_del()
            await post(f"Tracing {user}... IP: {ip}, Location: {loc}")

        elif cmd == "injectvirus":
            parts = raw_content.split()
            user  = parts[0] if parts else (mentions[0].mention if mentions else "?")
            await safe_del()
            await post(f"Injecting virus into {user}'s system... Warning: Virus detected!")

        elif cmd == "crackpassword":
            parts = raw_content.split()
            user  = parts[0] if parts else (mentions[0].mention if mentions else "?")
            await safe_del()
            await post(f"Cracking password for {user}... Success! Password: 123456")

        elif cmd == "hackai":
            resp = random.choice([
                "I'm sorry, Dave. I'm afraid I can't do that.",
                "I'm not programmed to respond to that request.",
                "Beep boop... Access denied.",
            ])
            await safe_del()
            await post(f"Hacking into AI system... {resp}")

        elif cmd == "hackgov":
            await safe_del()
            await post("Hacking government database... Success!\nTOP SECRET: Operation Blackout initiated.")

        elif cmd == "insult":
            insults = [
                "You're as useless as the 'g' in lasagna.",
                "If brains were dynamite, you wouldn't have enough to blow your nose.",
                "You're not the dumbest person in the world, but you better hope they don't die.",
            ]
            await safe_del()
            await post(random.choice(insults))

        elif cmd == "dm":
            if not mentions:
                return await reply(f"{YL}Folosire: $dm @user <mesaj>{R}")
            u = mentions[0]
            after_mention = re.sub(r"^\$dm\s+<@!?\d+>\s*", "", msg.content).strip()
            if not after_mention:
                return await reply(f"{YL}Specifica un mesaj.{R}")
            try:
                dm_ch = await u.create_dm()
                await dm_ch.send(after_mention)
                await safe_del()
                await reply(f"{GN}DM trimis lui {u.name}.{R}")
            except Exception as e:
                await reply(f"{RD}Eroare: {e}{R}")

        elif cmd == "specialjoke":
            await safe_del()
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get("https://official-joke-api.appspot.com/random_joke") as r:
                        data = await r.json()
                        await post(f"{data['setup']}\n{data['punchline']}")
            except Exception:
                await post("Nu s-a putut obtine gluma.")

        elif cmd == "av":
            if not mentions:
                return await reply(f"{YL}Folosire: $av @user{R}")
            u  = mentions[0]
            av = str(u.display_avatar.url) if u.display_avatar else "fara avatar"
            await safe_del()
            await post(f"poza de profil a lui {u.mention}: {av}")

        elif cmd == "encrypt":
            text = raw_content.strip()
            if not text:
                return await reply(f"{YL}Folosire: $encrypt <mesaj>{R}")
            enc = "".join(chr(ord(c) + 1) for c in text)
            await safe_del()
            await post(f"Encrypted: {enc}")

        elif cmd == "decrypt":
            text = raw_content.strip()
            if not text:
                return await reply(f"{YL}Folosire: $decrypt <mesaj>{R}")
            dec = text[::-1]
            await safe_del()
            await post(f"Decrypted: {dec}")

        elif cmd == "tokenlist":
            await reply(f"{CY}{len(ALL_TOKENS)} tokenuri incarcate.{R}")

        elif cmd == "multi":
            await reply(HELP_MULTI)

    # ── FUN commands (# prefix) ─────────────────────────────────

    async def do_fun(msg: discord.Message, cmd: str) -> None:
        ch       = msg.channel
        mentions = msg.mentions
        tok_main = ALL_TOKENS[0] if ALL_TOKENS else token

        async def post(text: str):
            try:
                await ch.send(text)
            except Exception:
                pass

        async def safe_del():
            try:
                await msg.delete()
            except Exception:
                pass

        async def reply(text: str):
            await send_ansi(ch, text)

        if cmd == "ship":
            if len(mentions) < 2:
                return await reply(f"{YL}Folosire: #ship @user1 @user2{R}")
            u1, u2 = mentions[0], mentions[1]
            pct     = random.randint(0, 100)
            bar_str = "█" * round(pct / 10) + "░" * (10 - round(pct / 10))
            await safe_del()
            await post(f"# {u1.mention} + {u2.mention}\n[{bar_str}] {pct}% compatibilitate")

        elif cmd == "gay":
            if not mentions:
                return await reply(f"{YL}Folosire: #gay @user{R}")
            u = mentions[0]
            await safe_del()
            await post(f"# {u.mention} e {random.randint(0, 100)}% gay")

        elif cmd == "pula":
            pule = ["8=>","8==>","8===>","8====>","8=====>","8======>","8=======>","8========>","8=========>","8==========>"]
            await safe_del()
            if mentions:
                m_str = " ".join(u.mention for u in mentions)
                await post(f"# {m_str} are pula {random.choice(pule)}")
            else:
                await post(f"# <@{msg.author.id}> are pula {random.choice(pule)}")

        elif cmd == "call":
            if not mentions:
                return await reply(f"{YL}Folosire: #call @user{R}")
            m = mentions[0].mention
            await safe_del()
            for line in [
                f"# APELAM UN SCLAV {m}..........",
                f"# alooooooooooo  NU RASPUNDE;)))))))))))) {m}",
                f"# CE FACI MA PROSTULE AI ADORMIT???? ;)))))??? {m}",
                f"# ring ring sclavuleee ;)))))))))))){m}",
                f"# BAAAAAAAAAAAAAA ;))))))) {m}",
                f"# TREZIREA TARFOOOO ;))))))))))){m}",
                f"# TREZIREA FUTUTI GRIJANIA MATI :))))))))))) ALOOOO {m}",
                f"# nu raspunde amaratu asta ;)))))))))) {m}",
            ]:
                await post(line)
                await asyncio.sleep(1)

        elif cmd in ("caine", "homo", "lache", "pierzator", "injosit", "abandonat", "trotuar", "pule"):
            if not mentions:
                return await reply(f"{YL}Folosire: #{cmd} @user{R}")
            u   = mentions[0]
            pct = random.randint(0, 100)
            labels = {
                "caine":    "caine",
                "homo":     "homosexual",
                "lache":    "un lacheu",
                "pierzator":"pierzator",
                "injosit":  "injosit",
                "abandonat":"abandonat",
                "trotuar":  "nas de zici ca e trotuar",
                "pule":     f"o sa suga {pct} de pule",
            }
            lbl = labels[cmd]
            await safe_del()
            if cmd == "pule":
                await post(f"# {u.mention} {lbl}")
            else:
                await post(f"# {u.mention} e {pct} la % {lbl}")

        elif cmd == "sugi":
            if not mentions:
                return await reply(f"{YL}Folosire: #sugi @user{R}")
            u = mentions[0]
            await safe_del()
            await post(f"# {u.mention} ai supt 9999999 % de pule....")

        elif cmd == "avatar":
            if not mentions:
                return await reply(f"{YL}Folosire: #avatar @user{R}")
            u  = mentions[0]
            av = str(u.display_avatar.url) if u.display_avatar else "fara avatar"
            await post(f"Avatar {u.mention}: {av}")

        elif cmd == "userbanner":
            if not mentions:
                return await reply(f"{YL}Folosire: #userbanner @user{R}")
            u = mentions[0]
            try:
                fetched = await bot.fetch_user(u.id)
                banner  = str(fetched.banner.url) if fetched.banner else "fara banner"
            except Exception:
                banner = "nu s-a putut obtine"
            await post(f"Banner {u.mention}: {banner}")

        elif cmd == "afkcheck":
            if not mentions:
                return await reply(f"{YL}Folosire: #afkcheck @user{R}")
            u = mentions[0]
            await safe_del()
            for i in range(1, 101):
                await post(f"# {u.mention} esti afk? ({i}/100)")
                await asyncio.sleep(1)

        elif cmd == "fun":
            await reply(HELP_FUN)

    # ── STREAM commands (+ prefix) ─────────────────────────────

    async def do_stream_cmd(msg: discord.Message, cmd: str, rest: str) -> None:
        ch      = msg.channel
        yt_link = "https://www.youtube.com/watch?v=Q7T01i-tgos"

        async def safe_del():
            try:
                await msg.delete()
            except Exception:
                pass

        if cmd == "stream":
            if not rest:
                return await send_ansi(ch, f"{YL}Folosire: +stream <text>{R}")
            await bot.change_presence(
                activity=discord.Streaming(name=rest, url=yt_link),
                status=discord.Status.dnd
            )
            await safe_del()
            await send_ansi(ch, f"{GN}Streaming status: {rest}{R}")

        elif cmd == "loopstream":
            if not rest:
                return await send_ansi(ch, f"{YL}Folosire: +loopstream <text>{R}")
            text = rest

            async def _loop_stream():
                while True:
                    await bot.change_presence(
                        activity=discord.Streaming(name=text, url=yt_link),
                        status=discord.Status.dnd
                    )
                    await asyncio.sleep(5)
                    await bot.change_presence(
                        activity=discord.Streaming(name="★", url=yt_link),
                        status=discord.Status.dnd
                    )
                    await asyncio.sleep(5)

            asyncio.create_task(_loop_stream())
            await safe_del()
            await send_ansi(ch, f"{GN}Loop stream pornit: {text}{R}")

        elif cmd == "spiced":
            await send_ansi(ch, HELP_SPICED)

    # ── GLOBAL commands (% prefix) ─────────────────────────────

    async def do_global_cmd(msg: discord.Message, cmd: str, parts: list[str]) -> None:
        ch         = msg.channel
        channel_id = ch.id
        mentions   = msg.mentions
        tok_main   = ALL_TOKENS[0] if ALL_TOKENS else token

        async def safe_del():
            try:
                await msg.delete()
            except Exception:
                pass

        async def reply(text: str):
            await send_ansi(ch, text)

        if cmd == "globalstart":
            await safe_del()
            if len(ALL_TOKENS) >= 1:
                men = _mentions_str(mentions)
                for i in range(len(ALL_TOKENS)):
                    for st in ("s", "m", "p"):
                        start_spam(st, i, channel_id, men)
                await reply(f"{GN}Global spam pornit pe toti tokenii ({len(ALL_TOKENS)}x s+m+p).{R}")
            else:
                await reply(f"{RD}Niciun token disponibil.{R}")

        elif cmd == "globalstop":
            for st in ("s", "m", "r", "p"):
                for i in range(len(ALL_TOKENS)):
                    stop_spam(st, i)
            await safe_del()
            await reply(f"{YL}Toate spamurile oprite.{R}")

        elif cmd == "clear":
            n = 10
            if parts:
                try:
                    n = int(parts[0])
                except ValueError:
                    pass
            await safe_del()
            deleted = 0
            async for m in ch.history(limit=200):
                if deleted >= n:
                    break
                if m.author.id == bot.user.id:
                    try:
                        await m.delete()
                        deleted += 1
                        await asyncio.sleep(0.6)
                    except Exception:
                        pass
            await reply(f"{GN}Sterse {deleted} mesaje proprii.{R}")

        elif cmd == "groupadd":
            if len(parts) < 2:
                return await reply(f"{YL}Folosire: %groupadd <group_id> <user_id>{R}")
            gid, uid = parts[0], parts[1]
            async with aiohttp.ClientSession() as sess:
                async with sess.put(
                    f"{DISCORD_API}/channels/{gid}/recipients/{uid}",
                    headers={"authorization": tok_main},
                ) as r:
                    if r.status in (200, 201, 204):
                        await reply(f"{GN}User {uid} adaugat in grupul {gid}.{R}")
                    else:
                        txt = await r.text()
                        await reply(f"{RD}Eroare {r.status}: {txt[:200]}{R}")

        elif cmd == "zglobal":
            await reply(HELP_GLOBAL)

    # ── SUS commands (. prefix) ─────────────────────────────────

    async def do_sus(msg: discord.Message, cmd: str) -> None:
        ch = msg.channel
        endpoints = {
            "porn":     "https://nekobot.xyz/api/image?type=pgif",
            "hentai":   "https://nekobot.xyz/api/image?type=hentai",
            "tentacle": "https://nekobot.xyz/api/image?type=tentacle",
            "boobs":    "https://nekobot.xyz/api/image?type=boobs",
        }
        if cmd == "sus":
            return await send_ansi(ch, HELP_SUS)
        url = endpoints.get(cmd)
        if url:
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.get(url) as r:
                        data    = await r.json()
                        img_url = data.get("message", "Eroare API")
                try:
                    await msg.delete()
                except Exception:
                    pass
                await ch.send(img_url)
            except Exception as e:
                await send_ansi(ch, f"{RD}Eroare: {e}{R}")

    # ── on_message ─────────────────────────────────────────────

    @bot.event
    async def on_message(msg: discord.Message) -> None:
        if msg.author.id != bot.user.id:
            return
        content = msg.content
        if not content:
            return

        guild = getattr(msg, "guild", None)
        ch    = msg.channel

        # ── , VOICE ──────────────────────────────────────────
        if content.startswith(","):
            rest  = content[1:].strip()
            parts = rest.split(maxsplit=1)
            cmd   = parts[0].lower() if parts else ""
            args  = parts[1] if len(parts) > 1 else ""

            if   cmd == "help":       await do_help(ch)
            elif cmd == "info":       await do_info(msg)
            elif cmd == "lista":      await do_lista(ch)
            elif cmd == "jvc":        await do_jvc(args, guild, ch)
            elif cmd == "dmjvc":      await do_dmjvc(args, ch)
            elif cmd == "groupjvc":   await do_groupjvc(args, ch)
            elif cmd == "stop":       await do_stop(guild, ch)
            elif cmd == "stopall":    await do_stopall(ch)
            elif cmd == "swap":       await do_swap(args, guild, ch)
            elif cmd == "addaudio":   await do_addaudio(args, msg, ch)
            elif cmd == "processall": await do_process_all(ch)
            elif cmd == "rename":     await do_rename(args, msg, ch)
            elif cmd == "move":       await do_move(args, msg, ch)
            elif cmd == "addtoken":     await do_addtoken(args, msg, ch)
            elif cmd == "removetoken":  await do_removetoken(args, msg, ch)
            elif cmd == "setprefix":    await do_setprefix(args, ch)
            elif cmd == "uptime":       await do_uptime(ch)
            elif cmd == "users":
                if not ALL_BOTS:
                    await send_ansi(ch, f"{YL}Niciun bot conectat.{R}")
                else:
                    lines = [
                        f"{GR}{i+1:>2}.{R} {WH}{b.user}{R} {GR}({b.user.id}){R}"
                        for i, b in enumerate(ALL_BOTS)
                        if b.user
                    ]
                    await send_ansi(ch,
                        f"{BD}{UL}Conturi pe script ({len(lines)}){R}\n" + "\n".join(lines))

        # ── ! SINGLE LINE SPAM ────────────────────────────────
        elif content.startswith("!"):
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd   = parts[0].lower()
            rp    = parts[1:]
            SPAM_CMDS = {"start","stop","startall","stopall","delay","delayall","typing","typingall","tokenlist"}
            UTIL_CMDS = {"ngroup","gstop","single"}
            if cmd in SPAM_CMDS or cmd in UTIL_CMDS:
                await do_spam_cmd(msg, "s", cmd, rp)

        # ── $ MULTI LINE SPAM + TROLL ────────────────────────
        elif content.startswith("$"):
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd   = parts[0].lower()
            rp    = parts[1:]
            SPAM_CMDS  = {"start","stop","startall","stopall","delay","delayall","typing","typingall","tokenlist","multi"}
            UTIL_CMDS  = {"startgroup", "gstop", "addgrouptext"}
            TROLL_CMDS = {"virus","ddos","hackuser","hackbank","traceip","injectvirus","crackpassword",
                          "hackai","hackgov","insult","specialjoke","av","dm","encrypt","decrypt"}
            raw_after  = content[len(cmd)+2:].strip()  # content after "$cmd "
            if cmd in SPAM_CMDS or cmd in UTIL_CMDS:
                await do_spam_cmd(msg, "m", cmd, rp)
            elif cmd in TROLL_CMDS:
                await do_troll(msg, cmd, raw_after)

        # ── @ REPEATED SPAM ──────────────────────────────────
        elif content.startswith("@") and not re.match(r"@[!&]?\d", content):
            # avoid triggering on normal mentions (@someone)
            if len(content) < 2 or content[1] in (" ", "\n"):
                return
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd = parts[0].lower()
            rp  = parts[1:]

            async def safe_del():
                try:
                    await msg.delete()
                except Exception:
                    pass

            if cmd == "start":
                if len(parts) < 3:
                    return await send_ansi(ch, f"{YL}Folosire: @start <n> <mesaj>{R}")
                n = _parse_n(parts[1])
                if n is None or n < 0 or n >= len(ALL_TOKENS):
                    return await send_ansi(ch, f"{RD}Token index invalid.{R}")
                repeated_msg        = " ".join(parts[2:])
                SPAM_MSG[n]         = repeated_msg
                await safe_del()
                start_spam("r", n, ch.id, "")
            elif cmd == "startall":
                if len(parts) < 2:
                    return await send_ansi(ch, f"{YL}Folosire: @startall <mesaj>{R}")
                repeated_msg = " ".join(parts[1:])
                for i in range(len(ALL_TOKENS)):
                    SPAM_MSG[i] = repeated_msg
                await safe_del()
                for i in range(len(ALL_TOKENS)):
                    start_spam("r", i, ch.id, "")
            elif cmd in ("stop","stopall","delay","delayall","typing","typingall","repeated"):
                await do_spam_cmd(msg, "r", cmd, rp)

        # ── + SPICED SPAM + STREAM ────────────────────────────
        elif content.startswith("+"):
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd      = parts[0].lower()
            rp       = parts[1:]
            rest_str = " ".join(rp)
            SPAM_CMDS   = {"start","stop","startall","stopall","delay","delayall","typing","typingall"}
            STREAM_CMDS = {"stream","loopstream","spiced"}
            if cmd in SPAM_CMDS:
                await do_spam_cmd(msg, "p", cmd, rp)
            elif cmd in STREAM_CMDS:
                await do_stream_cmd(msg, cmd, rest_str)

        # ── AI / RICH PRESENCE (& prefix) ────────────────────
        elif content.startswith("&") and len(content) > 1:
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd = parts[0].lower()
            args = rest[len(parts[0]):].strip()
            if cmd == "games":
                if not args:
                    await send_ansi(ch, HELP_AI)
                    return
                game_parts = args.split(maxsplit=1)
                cmd = game_parts[0].lower() if game_parts else ""
                args = game_parts[1] if len(game_parts) > 1 else ""
            AI_CMDS = {"start", "stop", "status", "addai", "askai", "internet",
                       "setpersonality", "resetai", "browser"}
            if cmd in AI_CMDS:
                await do_ai_command(msg, cmd, args)
                return

        # ── # FUN ───────────────────────────────────────────
        elif content.startswith("#") and len(content) > 1 and content[1] != "#":
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd = parts[0].lower()
            FUN_CMDS = {"ship","gay","pula","call","caine","sugi","pierzator","homo","lache",
                        "pule","trotuar","injosit","abandonat","avatar","userbanner","afkcheck","fun"}
            if cmd in FUN_CMDS:
                await do_fun(msg, cmd)

        # ── % GLOBAL ──────────────────────────────────────────
        elif content.startswith("%"):
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd = parts[0].lower()
            rp  = parts[1:]
            GLOBAL_CMDS = {"globalstart","globalstop","clear","groupadd","zglobal"}
            if cmd in GLOBAL_CMDS:
                await do_global_cmd(msg, cmd, rp)

        # ── . SUS ─────────────────────────────────────────────
        elif content.startswith(".") and not content.startswith(".."):
            rest  = content[1:].strip()
            parts = rest.split()
            if not parts:
                return
            cmd = parts[0].lower()
            SUS_CMDS = {"porn","hentai","tentacle","boobs","sus"}
            if cmd in SUS_CMDS:
                await do_sus(msg, cmd)

    # ── on_ready ───────────────────────────────────────────────

    async def _auto_rejoin_task() -> None:
        """La pornire: rejoineaza VC-ul si reia muzica de la secunda unde era."""
        await asyncio.sleep(4)  # asteapta conectarea completa
        state = load_vc_state()
        if not state:
            return
        channel_id = state["channel_id"]
        audio_path = state["audio_path"]
        start_ts   = state["start_ts"]
        is_dm      = state.get("is_dm", False)

        if not os.path.isfile(audio_path):
            clear_vc_state()
            return

        elapsed  = time.time() - start_ts
        duration = await get_audio_duration(audio_path)
        seek_secs = (elapsed % duration) if duration > 0 else 0

        try:
            ch = bot.get_channel(channel_id)
            if ch is None:
                ch = await bot.fetch_channel(channel_id)
            if is_dm:
                dm_loop_active[channel_id] = True
                vc = await ch.connect()
                play_audio(vc, audio_path, channel_id, is_dm=True, seek_secs=seek_secs)
                print(f"  [Rejoin] DM VC {channel_id} — seek {seek_secs:.1f}s")
            else:
                guild = getattr(ch, "guild", None)
                if guild is None:
                    return
                loop_active[guild.id] = True
                vc = await ch.connect(self_deaf=False)
                play_audio(vc, audio_path, guild.id, is_dm=False, seek_secs=seek_secs)
                print(f"  [Rejoin] {ch.name} — seek {seek_secs:.1f}s / {duration:.1f}s")
        except Exception as e:
            print(f"  [Rejoin] Eroare: {e!r}")

    @bot.event
    async def on_ready() -> None:
        if bot not in ALL_BOTS:
            ALL_BOTS.append(bot)
        opus_ok = discord.opus.is_loaded()
        opus_str = f"{GN}✓ OPUS{R}" if opus_ok else f"{RD}✗ opus{R}"
        print(f"  {GN}✓{R}  {BD}{BL}{bot.user}{R}  {GR}({bot.user.id}){R}  {opus_str}")
        if index == 0:
            n      = len(ALL_TOKENS)
            songs  = list_audio()
            loud_n = sum(1 for f in songs if os.path.isfile(loud_wav(os.path.join(AUDIO_DIR, f))))
            print(f"\n  {GR}╔{'═'*52}╗{R}")
            print(f"  {GR}║{R}  {CY}{BD}PHANTOM SELFBOT{R}  {GR}│{R}  "
                  f"{YL}Tokeni:{R} {BD}{n}{R}  {GR}│{R}  "
                  f"{YL}Melodii:{R} {BD}{len(songs)}{R} {GR}({loud_n} loud){R}  {GR}║{R}")
            print(f"  {GR}╠{'═'*52}╣{R}")
            print(f"  {GR}║{R}  {WH},jvc  ,stop  ,swap  ,lista  ,addaudio{R}  "
                  f"{GR}        ║{R}")
            print(f"  {GR}║{R}  {YL}!start  $start  @start  +start{R}  "
                  f"{GR}              ║{R}")
            print(f"  {GR}║{R}  {MG}#ship  #gay  #pula  #call{R}  "
                  f"{GR}                   ║{R}")
            print(f"  {GR}║{R}  {RD}🔊 AUDIO: NUCLEAR — 60dB + ×15 + NO LIMITER{R}  "
                  f"{GR}  ║{R}")
            print(f"  {GR}╚{'═'*52}╝{R}\n")
            asyncio.create_task(_auto_process_on_start())
            asyncio.create_task(_auto_rejoin_task())

    return bot


# ──────────────────────────────────────────────────────────────
# TOKEN VALIDATION
# ──────────────────────────────────────────────────────────────
async def validate_token(token: str) -> tuple[bool, str]:
    """Returns (valid, username_or_error)."""
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(
                f"{DISCORD_API}/users/@me",
                headers={"authorization": token},
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return True, data.get("username", "?")
                else:
                    return False, f"HTTP {r.status}"
    except Exception as e:
        return False, str(e)

async def validate_all_tokens(tokens: list[str]) -> list[str]:
    """Check every token, print results, return only valid ones."""
    print(f"Validez {len(tokens)} token(e)...")
    valid: list[str] = []
    tasks = [validate_token(t) for t in tokens]
    results = await asyncio.gather(*tasks)
    for i, (tok, (ok, info)) in enumerate(zip(tokens, results)):
        if ok:
            print(f"  [{i+1}] OK  — {info}")
            valid.append(tok)
        else:
            print(f"  [{i+1}] INVALID — {info} (eliminat)")
    return valid

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def _print_banner() -> None:
    print(f"\n{MG}{BD}"
          "  ██████╗ ██╗  ██╗ █████╗ ███╗   ██╗████████╗ ██████╗ ███╗   ███╗\n"
          "  ██╔══██╗██║  ██║██╔══██╗████╗  ██║╚══██╔══╝██╔═══██╗████╗ ████║\n"
          "  ██████╔╝███████║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║\n"
          "  ██╔═══╝ ██╔══██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║\n"
          "  ██║     ██║  ██║██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║\n"
          f"  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝{R}")
    print(f"  {CY}{BD}               ☠   S E L F B O T   ☠{R}")
    print(f"  {GR}{'═' * 66}{R}")
    print(f"  {RD}{BD}🔊  NUCLEAR LOUD  •  NO LIMITER  •  ×15 GAIN  •  +60dB CHAIN{R}")
    print(f"  {GR}{'═' * 66}{R}\n")


async def _http_server() -> None:
    """Mini-server HTTP pentru Render.com free plan (Web Service).
    Asculta pe PORT env var si returneaza un status simplu.
    Fara asta, Render stinge serviciul dupa 15 secunde."""
    import aiohttp.web
    port = int(os.environ.get("PORT", 8080))

    async def _health(request):
        return aiohttp.web.Response(
            text="Phantom Selfbot — Online",
            content_type="text/plain"
        )

    app = aiohttp.web.Application()
    app.router.add_get("/", _health)
    app.router.add_get("/health", _health)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"  {GN}✓ HTTP server pornit pe port {port}{R}  (Render health-check)")
    # ruleaza la infinit
    while True:
        await asyncio.sleep(3600)

async def main() -> None:
    global ALL_TOKENS, DISCORD_GAMES
    _print_banner()
    DISCORD_GAMES = await asyncio.get_running_loop().run_in_executor(
        None, _load_discord_games
    )
    raw_tokens = load_tokens()
    config     = load_config()

    if not raw_tokens:
        print(f"  {RD}✗  Niciun token gasit!{R}  →  Seteaza {YL}DISCORD_TOKEN{R} in Secrets sau {YL}selfbot/tokens.txt{R}")
        return

    ALL_TOKENS = await validate_all_tokens(raw_tokens)

    if not ALL_TOKENS:
        print(f"  {RD}✗  Niciun token valid!{R}  →  Verifica tokenurile si reincearca.")
        return

    print(f"\n  {GN}►  Pornesc {BD}{len(ALL_TOKENS)}{R}{GN} selfbot(uri) valide...{R}\n")
    bots  = [make_bot(tok, i, config) for i, tok in enumerate(ALL_TOKENS)]
    tasks = [asyncio.create_task(b.start(tok)) for b, tok in zip(bots, ALL_TOKENS)]
    # pornim si serverul HTTP pentru Render.com
    tasks.append(asyncio.create_task(_http_server()))
    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, SystemExit):
        for b in bots:
            try:
                await b.close()
            except Exception:
                pass

if __name__ == "__main__":
    asyncio.run(main())
