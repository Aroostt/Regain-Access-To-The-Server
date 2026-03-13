import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import requests

TOKENS_FILE = "tokens.txt"
BACKUPS_DIR = "backups"
SETTINGS_FILE = "backup_settings.json"
LOGS_DIR = "logs"
API_BASE = "https://discord.com/api/v10"
REQUEST_TIMEOUT = 12


class UiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    WHITE = "\033[97m"
    LIGHT_GRAY = "\033[37m"
    DARK_GRAY = "\033[90m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class BotTokenStatus:
    index: int
    token: str
    is_valid: bool
    bot_name: str = "-"
    bot_id: str = "-"
    error: str = ""


@dataclass
class GuildEntry:
    guild_id: str
    guild_name: str


@dataclass
class BackupSettings:
    messages_per_channel: int = 100
    copy_messages: bool = False
    role_filter_ids: Optional[Set[str]] = None
    role_filter_names: List[str] = None
    included_scopes: Set[str] = None
    cleanup_scopes: Set[str] = None

    def __post_init__(self) -> None:
        if self.role_filter_names is None:
            self.role_filter_names = []
        if self.included_scopes is None:
            self.included_scopes = {"guild", "roles", "channels", "emojis", "stickers", "scheduled_events", "messages"}
        if self.cleanup_scopes is None:
            self.cleanup_scopes = {"channels", "roles", "emojis", "stickers", "events"}


BACKUP_SETTINGS_BY_GUILD: Dict[str, BackupSettings] = {}


def color_text(text: str, color: str) -> str:
    return f"{color}{text}{UiColor.RESET}"


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    return len(strip_ansi(text))


def pad_visible(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))


def clear_console() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def get_terminal_width(default_width: int = 120) -> int:
    try:
        return shutil.get_terminal_size((default_width, 30)).columns
    except Exception:
        return default_width


def center_line(text: str) -> str:
    return text.center(get_terminal_width())


def print_centered(text: str, color: str = UiColor.LIGHT_GRAY) -> None:
    print(color_text(center_line(text), color))


def centered_plain(text: str, width: int) -> str:
    return text.center(width)


def print_banner() -> None:
    art = [
        " ██████╗██╗    ██╗███████╗██╗     ██╗██╗   ██╗███╗   ███╗",
        "██╔════╝██║    ██║██╔════╝██║     ██║██║   ██║████╗ ████║",
        "██║     ██║ █╗ ██║█████╗  ██║     ██║██║   ██║██╔████╔██║",
        "██║     ██║███╗██║██╔══╝  ██║     ██║██║   ██║██║╚██╔╝██║",
        "╚██████╗╚███╔███╔╝███████╗███████╗██║╚██████╔╝██║ ╚═╝ ██║",
        " ╚═════╝ ╚══╝╚══╝ ╚══════╝╚══════╝╚═╝ ╚═════╝ ╚═╝     ╚═╝",
    ]
    for line in art:
        print_centered(line, UiColor.WHITE + UiColor.BOLD)


def draw_centered_box(lines: List[str]) -> None:
    inner_width = max(visible_len(line) for line in lines) + 2
    box_width = inner_width + 2
    indent = max(0, (get_terminal_width() - box_width) // 2)
    pad = " " * indent

    print(color_text(f"{pad}╭{'─' * inner_width}╮", UiColor.LIGHT_GRAY))
    for line in lines:
        print(color_text(f"{pad}│ {pad_visible(line, inner_width - 1)}│", UiColor.LIGHT_GRAY))
    print(color_text(f"{pad}╰{'─' * inner_width}╯", UiColor.LIGHT_GRAY))


def wait_for_enter(message: str = "Naciśnij ENTER, aby kontynuować...") -> None:
    input(color_text(f"\n{message}", UiColor.CYAN))


def print_inline_status(message: str) -> None:
    width = get_terminal_width() - 1
    trimmed = message[:max(1, width)]
    print(f"\r{trimmed.ljust(width)}", end="", flush=True)


def clear_inline_status() -> None:
    width = get_terminal_width() - 1
    print(f"\r{' ' * width}\r", end="", flush=True)


def format_backup_timestamp(raw: str) -> str:
    if not raw:
        return "-"
    try:
        return datetime.strptime(raw, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw


def ask_yes_no(question: str, default: bool = False) -> bool:
    hint = "[T/n]" if default else "[t/N]"
    value = input(color_text(f"\n{question} {hint}: ", UiColor.CYAN)).strip().lower()
    if not value:
        return default
    return value in {"t", "tak", "y", "yes"}


def ask_number(prompt: str, minimum: int, maximum: int, default: int) -> int:
    while True:
        value = input(color_text(f"\n{prompt} ({minimum}-{maximum}, domyślnie {default}): ", UiColor.CYAN)).strip()
        if not value:
            return default
        if value.isdigit() and minimum <= int(value) <= maximum:
            return int(value)
        print_centered("Podaj poprawną wartość liczbową.", UiColor.RED)


def fetch_json_data(token: str, path: str, params: Optional[dict] = None) -> Dict[str, object]:
    try:
        response = api_get(path, token, params=params)
        if response.status_code == 200:
            return {"ok": True, "status": 200, "data": response.json()}
        return {"ok": False, "status": response.status_code, "error": response.text}
    except requests.RequestException as exc:
        return {"ok": False, "status": None, "error": str(exc)}


def ensure_runtime_dirs() -> None:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)


def log_event(action: str, message: str) -> None:
    ensure_runtime_dirs()
    date_part = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(LOGS_DIR, f"tool_{date_part}.log")
    with open(log_path, "a", encoding="utf-8") as log_file:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"[{ts}] [{action}] {message}\n")


def save_backup_settings_to_disk() -> None:
    payload: Dict[str, dict] = {}
    for guild_id, settings in BACKUP_SETTINGS_BY_GUILD.items():
        payload[guild_id] = {
            "messages_per_channel": settings.messages_per_channel,
            "copy_messages": settings.copy_messages,
            "role_filter_ids": sorted(list(settings.role_filter_ids)) if settings.role_filter_ids else None,
            "role_filter_names": settings.role_filter_names,
            "included_scopes": sorted(list(settings.included_scopes)),
            "cleanup_scopes": sorted(list(settings.cleanup_scopes)),
        }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def load_backup_settings_from_disk() -> None:
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return
        for guild_id, item in data.items():
            if not isinstance(item, dict):
                continue
            BACKUP_SETTINGS_BY_GUILD[guild_id] = BackupSettings(
                messages_per_channel=int(item.get("messages_per_channel", 100)),
                copy_messages=bool(item.get("copy_messages", False)),
                role_filter_ids=set(item.get("role_filter_ids", [])) if isinstance(item.get("role_filter_ids"), list) else None,
                role_filter_names=item.get("role_filter_names", []) if isinstance(item.get("role_filter_names"), list) else [],
                included_scopes=set(item.get("included_scopes", [])) if isinstance(item.get("included_scopes"), list) and item.get("included_scopes") else None,
                cleanup_scopes=set(item.get("cleanup_scopes", [])) if isinstance(item.get("cleanup_scopes"), list) and item.get("cleanup_scopes") else None,
            )
    except Exception:
        return


def parse_disable_numbers(input_raw: str, labels: List[str]) -> Set[int]:
    if not input_raw.strip():
        return set()
    disabled: Set[int] = set()
    for part in input_raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part)
            if 1 <= idx <= len(labels):
                disabled.add(idx)
    return disabled


def sort_channels_in_backup_order(channels_data: List[dict]) -> List[dict]:
    categories = [c for c in channels_data if c.get("type") == 4]
    non_categories = [c for c in channels_data if c.get("type") != 4]
    categories.sort(key=lambda c: int(c.get("position", 0)))
    non_categories.sort(key=lambda c: (str(c.get("parent_id") or ""), int(c.get("position", 0))))
    return categories + non_categories


def read_tokens_file() -> List[str]:
    if not os.path.exists(TOKENS_FILE):
        return []
    result: List[str] = []
    with open(TOKENS_FILE, "r", encoding="utf-8") as file:
        for line in file:
            token = line.strip()
            if token and not token.startswith("#"):
                result.append(token)
    return result


def hide_token(token: str) -> str:
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:5]}...{token[-5:]}"


def api_get(path: str, token: str, params: Optional[dict] = None) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", headers={"Authorization": f"Bot {token}"}, params=params, timeout=REQUEST_TIMEOUT)


def api_post(path: str, token: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path: str, token: str) -> requests.Response:
    return requests.put(f"{API_BASE}{path}", headers={"Authorization": f"Bot {token}"}, timeout=REQUEST_TIMEOUT)


def api_patch(path: str, token: str, payload: object) -> requests.Response:
    return requests.patch(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )


def api_delete(path: str, token: str) -> requests.Response:
    return requests.delete(f"{API_BASE}{path}", headers={"Authorization": f"Bot {token}"}, timeout=REQUEST_TIMEOUT)


def validate_single_token(index: int, token: str) -> BotTokenStatus:
    try:
        response = api_get("/users/@me", token)
        if response.status_code == 200:
            data = response.json()
            return BotTokenStatus(index=index, token=token, is_valid=True, bot_name=f"{data.get('username', '?')}#{data.get('discriminator', '0')}", bot_id=data.get("id", "-"))
        return BotTokenStatus(index=index, token=token, is_valid=False, error=f"HTTP {response.status_code}")
    except requests.RequestException as exc:
        return BotTokenStatus(index=index, token=token, is_valid=False, error=str(exc))


def validate_all_tokens(tokens: List[str]) -> List[BotTokenStatus]:
    return [validate_single_token(i + 1, token) for i, token in enumerate(tokens)]


def copy_to_clipboard(text: str) -> bool:
    try:
        if os.name == "nt":
            subprocess.run("clip", input=text.encode("utf-16le"), check=True)
            return True
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
        return True
    except Exception:
        return False


def fetch_bot_guilds(token: str) -> Optional[List[GuildEntry]]:
    try:
        response = api_get("/users/@me/guilds", token)
        if response.status_code != 200:
            print_centered(f"Nie udało się pobrać serwerów (HTTP {response.status_code}).", UiColor.RED)
            return None
        return [GuildEntry(guild_id=item["id"], guild_name=item.get("name", "Unknown")) for item in response.json() if item.get("id")]
    except requests.RequestException as exc:
        print_centered(f"Błąd sieci: {exc}", UiColor.RED)
        return None


def choose_guild(token: str, message: str = "Wybierz serwer") -> Optional[GuildEntry]:
    guilds = fetch_bot_guilds(token)
    if guilds is None:
        return None
    if not guilds:
        print_centered("Bot nie jest na żadnym serwerze.", UiColor.YELLOW)
        return None

    while True:
        clear_console()
        print_banner()
        print()
        print_centered(message, UiColor.LIGHT_GRAY)
        print()
        for idx, guild in enumerate(guilds, 1):
            print_centered(f"[{idx}] {guild.guild_name} ({guild.guild_id})", UiColor.DARK_GRAY)
        print_centered("[0] Powrót", UiColor.DARK_GRAY)

        choice = input(color_text("\n-> ", UiColor.CYAN)).strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(guilds):
            return guilds[int(choice) - 1]


def create_bot_invite_link(token: str) -> Optional[str]:
    try:
        response = api_get("/oauth2/applications/@me", token)
        if response.status_code != 200:
            return None
        app_id = response.json().get("id")
        return f"https://discord.com/oauth2/authorize?client_id={app_id}&permissions=8&scope=bot%20applications.commands" if app_id else None
    except requests.RequestException:
        return None


def create_guild_invite_link(token: str) -> Optional[str]:
    guild = choose_guild(token)
    if not guild:
        return None
    try:
        channels_response = api_get(f"/guilds/{guild.guild_id}/channels", token)
        if channels_response.status_code != 200:
            print_centered(f"Nie udało się pobrać kanałów (HTTP {channels_response.status_code}).", UiColor.RED)
            return None
        text_channels = [c for c in channels_response.json() if c.get("type") == 0]
        if not text_channels:
            print_centered("Brak kanału tekstowego do utworzenia zaproszenia.", UiColor.YELLOW)
            return None
        invite_response = api_post(f"/channels/{text_channels[0].get('id')}/invites", token, {"max_age": 0, "max_uses": 0, "temporary": False, "unique": True})
        if invite_response.status_code not in (200, 201):
            print_centered(f"Nie udało się utworzyć zaproszenia (HTTP {invite_response.status_code}).", UiColor.RED)
            return None
        code = invite_response.json().get("code")
        return f"https://discord.gg/{code}" if code else None
    except requests.RequestException as exc:
        print_centered(f"Błąd sieci: {exc}", UiColor.RED)
        return None


def get_bot_role_context(token: str, guild_id: str) -> Tuple[Dict[str, int], List[str]]:
    roles_response = api_get(f"/guilds/{guild_id}/roles", token)
    if roles_response.status_code != 200:
        return {}, []
    role_positions = {str(role.get("id")): int(role.get("position", 0)) for role in roles_response.json() if role.get("id")}
    bot_response = api_get("/users/@me", token)
    if bot_response.status_code != 200 or not bot_response.json().get("id"):
        return role_positions, []
    bot_id = bot_response.json().get("id")
    member_response = api_get(f"/guilds/{guild_id}/members/{bot_id}", token)
    if member_response.status_code != 200:
        return role_positions, []
    return role_positions, member_response.json().get("roles", [])


def move_role_to_highest_possible(token: str, guild_id: str, role_id: str) -> Tuple[bool, str]:
    try:
        role_positions, bot_role_ids = get_bot_role_context(token, guild_id)
        if not role_positions:
            return False, "Nie udało się pobrać pozycji ról."
        bot_top_positions = [role_positions.get(rid, 0) for rid in bot_role_ids if rid in role_positions]
        if not bot_top_positions:
            return False, "Bot nie ma roli pozwalającej zarządzać hierarchią."
        target_position = max(1, max(bot_top_positions) - 1)
        response = api_patch(f"/guilds/{guild_id}/roles", token, [{"id": role_id, "position": target_position}])
        if response.status_code in (200, 201):
            return True, "Rola została przesunięta najwyżej jak to możliwe."
        return False, f"Nie udało się przesunąć roli (HTTP {response.status_code})."
    except requests.RequestException as exc:
        return False, f"Błąd sieci podczas przesuwania roli: {exc}"


def grant_admin_role_to_user(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Nadawanie nowej roli administratora", UiColor.LIGHT_GRAY)
    guild = choose_guild(token)
    if not guild:
        wait_for_enter(); return
    user_id = input(color_text("\nPodaj ID użytkownika Discord: ", UiColor.CYAN)).strip()
    if not user_id.isdigit():
        print_centered("Niepoprawne ID użytkownika.", UiColor.RED); wait_for_enter(); return
    try:
        create_role_response = api_post(f"/guilds/{guild.guild_id}/roles", token, {"name": "Tool Admin", "permissions": "8", "hoist": True, "mentionable": True, "reason": "Nadanie pełnej roli administratora z narzędzia CLI"})
        if create_role_response.status_code not in (200, 201):
            print_centered(f"Nie udało się utworzyć roli (HTTP {create_role_response.status_code}).", UiColor.RED); print(create_role_response.text); wait_for_enter(); return
        role_id = create_role_response.json().get("id")
        if not role_id:
            print_centered("Nie udało się odczytać ID nowej roli.", UiColor.RED); wait_for_enter(); return
        moved, msg = move_role_to_highest_possible(token, guild.guild_id, role_id)
        print_centered(msg, UiColor.GREEN if moved else UiColor.YELLOW)
        assign_response = api_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{role_id}", token)
        if assign_response.status_code in (200, 204):
            print_centered("Sukces: nadano nową rolę administratora.", UiColor.GREEN)
        else:
            print_centered(f"Nie udało się przypisać roli (HTTP {assign_response.status_code}).", UiColor.RED); print(assign_response.text)
    except requests.RequestException as exc:
        print_centered(f"Błąd sieci: {exc}", UiColor.RED)
    wait_for_enter()


def grant_best_existing_role_to_user(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Nadawanie najlepszej istniejącej roli", UiColor.LIGHT_GRAY)
    guild = choose_guild(token)
    if not guild:
        wait_for_enter(); return
    user_id = input(color_text("\nPodaj ID użytkownika Discord: ", UiColor.CYAN)).strip()
    if not user_id.isdigit():
        print_centered("Niepoprawne ID użytkownika.", UiColor.RED); wait_for_enter(); return
    try:
        role_positions, bot_role_ids = get_bot_role_context(token, guild.guild_id)
        if not role_positions or not bot_role_ids:
            print_centered("Nie udało się ustalić hierarchii ról bota.", UiColor.RED); wait_for_enter(); return
        highest_bot_position = max(role_positions.get(role_id, 0) for role_id in bot_role_ids)
        roles_response = api_get(f"/guilds/{guild.guild_id}/roles", token)
        if roles_response.status_code != 200:
            print_centered(f"Nie udało się pobrać ról serwera (HTTP {roles_response.status_code}).", UiColor.RED); wait_for_enter(); return
        manageable_roles = [r for r in roles_response.json() if r.get("id") and r.get("name") != "@everyone" and not r.get("managed", False) and int(r.get("position", 0)) < highest_bot_position]
        if not manageable_roles:
            print_centered("Brak istniejącej roli, którą ten bot może nadać.", UiColor.YELLOW); wait_for_enter(); return
        best_role = max(manageable_roles, key=lambda role: int(role.get("position", 0)))
        assign_response = api_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{best_role.get('id')}", token)
        if assign_response.status_code in (200, 204):
            print_centered(f"Sukces: nadano rolę '{best_role.get('name', 'Unknown')}'.", UiColor.GREEN)
        else:
            print_centered(f"Nie udało się przypisać roli (HTTP {assign_response.status_code}).", UiColor.RED); print(assign_response.text)
    except requests.RequestException as exc:
        print_centered(f"Błąd sieci: {exc}", UiColor.RED)
    wait_for_enter()


def show_bot_info(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Show Bot Info", UiColor.LIGHT_GRAY); print()
    bot = fetch_json_data(token, "/users/@me")
    app = fetch_json_data(token, "/oauth2/applications/@me")
    guilds = fetch_json_data(token, "/users/@me/guilds")
    if not bot.get("ok"):
        print_centered("Nie udało się pobrać informacji o bocie.", UiColor.RED)
        wait_for_enter(); return

    bot_data = bot.get("data", {}) if isinstance(bot.get("data"), dict) else {}
    app_data = app.get("data", {}) if isinstance(app.get("data"), dict) else {}
    guild_list = guilds.get("data", []) if isinstance(guilds.get("data"), list) else []

    lines = [
        f"Nazwa: {bot_data.get('username', '-')}",
        f"ID bota: {bot_data.get('id', '-')}",
        f"Zweryfikowany: {'Tak' if bot_data.get('verified') else 'Nie'}",
        f"Aplikacja ID: {app_data.get('id', '-')}",
        f"Nazwa aplikacji: {app_data.get('name', '-')}",
        f"Publiczny bot: {'Tak' if app_data.get('bot_public') else 'Nie'}" if app_data else "Publiczny bot: -",
        f"Na ilu serwerach: {len(guild_list)}",
    ]
    draw_centered_box(lines)
    wait_for_enter()


def run_token_health_check(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Token Health Check", UiColor.LIGHT_GRAY); print()
    checks: List[Tuple[str, bool, str]] = []
    try:
        me = api_get("/users/@me", token)
        checks.append(("Token /users/@me", me.status_code == 200, f"HTTP {me.status_code}"))
        guilds = api_get("/users/@me/guilds", token)
        checks.append(("Lista serwerów", guilds.status_code == 200, f"HTTP {guilds.status_code}"))
        app = api_get("/oauth2/applications/@me", token)
        checks.append(("Dane aplikacji", app.status_code == 200, f"HTTP {app.status_code}"))

        if guilds.status_code == 200 and guilds.json():
            first_guild_id = guilds.json()[0].get("id")
            if first_guild_id:
                roles = api_get(f"/guilds/{first_guild_id}/roles", token)
                checks.append(("Pobranie ról", roles.status_code == 200, f"HTTP {roles.status_code}"))
                channels = api_get(f"/guilds/{first_guild_id}/channels", token)
                checks.append(("Pobranie kanałów", channels.status_code == 200, f"HTTP {channels.status_code}"))
    except requests.RequestException as exc:
        checks.append(("Błąd sieci", False, str(exc)))

    lines: List[str] = []
    for name, ok, detail in checks:
        state = color_text("OK", UiColor.GREEN) if ok else color_text("BŁĄD", UiColor.RED)
        lines.append(f"{name}: {state} ({detail})")
    draw_centered_box(lines if lines else ["Brak danych health check."])
    wait_for_enter()


def get_restore_plan_summary(backup: dict, include_messages: bool) -> List[str]:
    roles_data = backup.get("roles", {}).get("data", []) if isinstance(backup.get("roles"), dict) else []
    channels_data = backup.get("channels", {}).get("data", []) if isinstance(backup.get("channels"), dict) else []
    emojis_data = backup.get("emojis", {}).get("data", []) if isinstance(backup.get("emojis"), dict) else []
    stickers_data = backup.get("stickers", {}).get("data", []) if isinstance(backup.get("stickers"), dict) else []
    events_data = backup.get("scheduled_events", {}).get("data", []) if isinstance(backup.get("scheduled_events"), dict) else []
    messages_data = backup.get("messages", {}) if isinstance(backup.get("messages"), dict) else {}
    messages_count = sum(len(v) for v in messages_data.values()) if include_messages else 0
    return [
        f"Plan restore dla: {backup.get('guild_name', '-')}",
        f"Role: {len(roles_data)}",
        f"Kanały: {len(channels_data)}",
        f"Emotki: {len(emojis_data)}",
        f"Stickery: {len(stickers_data)}",
        f"Eventy: {len(events_data)}",
        f"Wiadomości: {messages_count if include_messages else 0}",
    ]


def apply_guild_settings_from_backup(token: str, target_guild_id: str, backup: dict) -> Tuple[bool, str]:
    guild_payload = backup.get("guild", {}).get("data", {}) if isinstance(backup.get("guild"), dict) else {}
    if not isinstance(guild_payload, dict) or not guild_payload:
        return False, "Brak danych ustawień serwera w backupie."

    patch_payload = {
        "name": guild_payload.get("name"),
        "verification_level": guild_payload.get("verification_level"),
        "default_message_notifications": guild_payload.get("default_message_notifications"),
        "explicit_content_filter": guild_payload.get("explicit_content_filter"),
        "afk_timeout": guild_payload.get("afk_timeout"),
        "system_channel_id": guild_payload.get("system_channel_id"),
        "rules_channel_id": guild_payload.get("rules_channel_id"),
        "public_updates_channel_id": guild_payload.get("public_updates_channel_id"),
        "preferred_locale": guild_payload.get("preferred_locale"),
    }
    patch_payload = {k: v for k, v in patch_payload.items() if v is not None}
    if not patch_payload:
        return False, "Brak pól do zastosowania."

    try:
        response = api_patch(f"/guilds/{target_guild_id}", token, patch_payload)
        if response.status_code in (200, 201):
            return True, "Zastosowano ustawienia serwera z backupu."
        return False, f"Nie udało się zastosować ustawień (HTTP {response.status_code})."
    except requests.RequestException as exc:
        return False, f"Błąd sieci ustawień serwera: {exc}"


def parse_role_filter_selection(roles_data: List[dict]) -> Tuple[Optional[Set[str]], List[str]]:
    selectable = [r for r in roles_data if r.get("name") != "@everyone" and r.get("id")]
    if not selectable:
        return None, []

    clear_console(); print_banner(); print(); print_centered("Filtr ról do backupu", UiColor.LIGHT_GRAY); print()
    lines = ["Podaj numery ról (np. 1,2,3). ENTER = wszystkie role"]
    for idx, role in enumerate(selectable, 1):
        lines.append(f"[{idx}] {role.get('name', 'Unknown')}")
    draw_centered_box(lines)

    value = input(color_text("\n-> ", UiColor.CYAN)).strip()
    if not value:
        return None, []

    selected_ids: Set[str] = set()
    selected_names: List[str] = []
    for part in value.split(","):
        part = part.strip()
        if not part.isdigit():
            continue
        i = int(part)
        if 1 <= i <= len(selectable):
            role = selectable[i - 1]
            rid = str(role.get("id"))
            if rid not in selected_ids:
                selected_ids.add(rid)
                selected_names.append(role.get("name", "Unknown"))

    if not selected_ids:
        return None, []
    return selected_ids, selected_names


def configure_backup_settings(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Backup settings", UiColor.LIGHT_GRAY)
    guild = choose_guild(token, "Wybierz serwer dla Backup settings")
    if not guild:
        wait_for_enter(); return

    current = BACKUP_SETTINGS_BY_GUILD.get(guild.guild_id, BackupSettings())
    current.messages_per_channel = ask_number("Limit wiadomości na kanał", 1, 1000, current.messages_per_channel)
    current.copy_messages = ask_yes_no("Zapisywać wiadomości?", current.copy_messages)

    scope_labels = ["guild", "roles", "channels", "emojis", "stickers", "scheduled_events", "messages"]
    clear_console(); print_banner(); print(); print_centered("Zakres backupu", UiColor.LIGHT_GRAY); print()
    draw_centered_box([
        "Wszystkie zakresy są domyślnie WŁĄCZONE.",
        "Wpisz numery zakresów, które chcesz WYŁĄCZYĆ (np. 2,5).",
        "ENTER = nic nie wyłączaj.",
        "[1] guild", "[2] roles", "[3] channels", "[4] emojis", "[5] stickers", "[6] scheduled_events", "[7] messages",
    ])
    disabled_scope_numbers = parse_disable_numbers(input(color_text("\n-> ", UiColor.CYAN)).strip(), scope_labels)
    current.included_scopes = {name for idx, name in enumerate(scope_labels, 1) if idx not in disabled_scope_numbers}

    cleanup_labels = ["channels", "roles", "emojis", "stickers", "events"]
    clear_console(); print_banner(); print(); print_centered("Zakres czyszczenia serwera", UiColor.LIGHT_GRAY); print()
    draw_centered_box([
        "Przy opcji wipe_current wszystko jest domyślnie WŁĄCZONE.",
        "Wpisz numery, które chcesz WYŁĄCZYĆ z czyszczenia.",
        "ENTER = nic nie wyłączaj.",
        "[1] channels", "[2] roles", "[3] emojis", "[4] stickers", "[5] events",
    ])
    disabled_cleanup_numbers = parse_disable_numbers(input(color_text("\n-> ", UiColor.CYAN)).strip(), cleanup_labels)
    current.cleanup_scopes = {name for idx, name in enumerate(cleanup_labels, 1) if idx not in disabled_cleanup_numbers}

    roles = fetch_json_data(token, f"/guilds/{guild.guild_id}/roles")
    if roles.get("ok") and isinstance(roles.get("data"), list):
        role_ids, role_names = parse_role_filter_selection(roles["data"])
        current.role_filter_ids = role_ids
        current.role_filter_names = role_names

    BACKUP_SETTINGS_BY_GUILD[guild.guild_id] = current
    save_backup_settings_to_disk()

    clear_console(); print_banner(); print(); print_centered("Backup settings zapisane", UiColor.GREEN); print()
    draw_centered_box([
        f"Serwer: {guild.guild_name}",
        f"Limit wiadomości/kanał: {current.messages_per_channel}",
        f"Zapis wiadomości: {'Tak' if current.copy_messages else 'Nie'}",
        f"Filtr ról: {', '.join(current.role_filter_names) if current.role_filter_names else 'Wszystkie'}",
        f"Zakres backupu: {', '.join(sorted(current.included_scopes))}",
        f"Zakres czyszczenia: {', '.join(sorted(current.cleanup_scopes))}",
    ])
    wait_for_enter()


def show_link_result_and_copy(link: Optional[str], label: str) -> None:
    if not link:
        print_centered(f"Nie udało się wygenerować: {label}", UiColor.RED); wait_for_enter(); return
    if copy_to_clipboard(link):
        print_centered(f"Skopiowano: {label}", UiColor.GREEN)
    else:
        print_centered("Nie udało się skopiować do schowka. Link poniżej:", UiColor.YELLOW); print(link)
    wait_for_enter()


def choose_backup_file() -> Optional[str]:
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    files = sorted([f for f in os.listdir(BACKUPS_DIR) if f.endswith('.json')], reverse=True)
    if not files:
        print_centered("Brak plików backupu w folderze backups/", UiColor.YELLOW)
        return None
    while True:
        clear_console(); print_banner(); print(); print_centered("Wybierz backup", UiColor.LIGHT_GRAY); print()
        for i, name in enumerate(files, 1):
            print_centered(f"[{i}] {name}", UiColor.DARK_GRAY)
        print_centered("[0] Powrót", UiColor.DARK_GRAY)
        choice = input(color_text("\n-> ", UiColor.CYAN)).strip()
        if choice == '0':
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(files):
            return os.path.join(BACKUPS_DIR, files[int(choice)-1])


def backup_full_server_data(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Backup pełnych danych serwera", UiColor.LIGHT_GRAY)
    guild = choose_guild(token)
    if not guild:
        wait_for_enter(); return

    settings = BACKUP_SETTINGS_BY_GUILD.get(guild.guild_id, BackupSettings())
    copy_messages = settings.copy_messages and "messages" in settings.included_scopes
    messages_limit = settings.messages_per_channel

    def fetch(path: str, params: Optional[dict] = None) -> Dict[str, object]:
        try:
            response = api_get(path, token, params=params)
            if response.status_code == 200:
                return {"ok": True, "status": 200, "data": response.json()}
            log_event("backup", f"HTTP {response.status_code} {path}")
            return {"ok": False, "status": response.status_code, "error": response.text}
        except requests.RequestException as exc:
            log_event("backup", f"network_error {path}: {exc}")
            return {"ok": False, "status": None, "error": str(exc)}

    try:
        guild_info = fetch(f"/guilds/{guild.guild_id}") if "guild" in settings.included_scopes else {"ok": False, "data": {}}
        roles = fetch(f"/guilds/{guild.guild_id}/roles") if "roles" in settings.included_scopes else {"ok": False, "data": []}
        channels = fetch(f"/guilds/{guild.guild_id}/channels") if "channels" in settings.included_scopes else {"ok": False, "data": []}
        emojis = fetch(f"/guilds/{guild.guild_id}/emojis") if "emojis" in settings.included_scopes else {"ok": False, "data": []}
        stickers = fetch(f"/guilds/{guild.guild_id}/stickers") if "stickers" in settings.included_scopes else {"ok": False, "data": []}
        scheduled_events = fetch(f"/guilds/{guild.guild_id}/scheduled-events") if "scheduled_events" in settings.included_scopes else {"ok": False, "data": []}

        if channels.get("ok") and isinstance(channels.get("data"), list):
            channels["data"] = sort_channels_in_backup_order(channels["data"])

        messages_by_channel: Dict[str, List[dict]] = {}
        message_channel_order: List[str] = []
        if copy_messages and channels.get("ok"):
            text_channels = [ch for ch in channels["data"] if ch.get("type") == 0 and ch.get("id")]
            for idx, ch in enumerate(text_channels, 1):
                print_inline_status(f"Pobieranie wiadomości: {idx}/{len(text_channels)}")
                msg_res = fetch(f"/channels/{ch['id']}/messages", params={"limit": messages_limit})
                if not msg_res.get("ok"):
                    continue
                saved = []
                for msg in msg_res.get("data", []):
                    author = msg.get("author", {})
                    saved.append({
                        "id": msg.get("id"),
                        "content": msg.get("content", ""),
                        "author_name": author.get("username", "Unknown"),
                        "author_global_name": author.get("global_name") or "",
                        "author_avatar": author.get("avatar"),
                        "author_id": author.get("id"),
                        "embeds": msg.get("embeds", []),
                        "attachments": msg.get("attachments", []),
                    })
                channel_id = str(ch["id"])
                messages_by_channel[channel_id] = list(reversed(saved))
                message_channel_order.append(channel_id)
            clear_inline_status()

        owner_id = guild_info.get("data", {}).get("owner_id") if guild_info.get("ok") else None
        ensure_runtime_dirs()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUPS_DIR, f"full_backup_{guild.guild_id}_{timestamp}.json")

        role_ids = settings.role_filter_ids
        role_names = settings.role_filter_names
        roles_payload = roles
        if role_ids and roles.get("ok") and isinstance(roles.get("data"), list):
            roles_payload = {
                "ok": True,
                "status": 200,
                "data": [r for r in roles["data"] if r.get("name") == "@everyone" or str(r.get("id")) in role_ids],
            }

        payload = {
            "guild_id": guild.guild_id,
            "guild_name": guild.guild_name,
            "owner_id": owner_id,
            "created_at": timestamp,
            "messages_saved": copy_messages,
            "messages_limit_per_channel": messages_limit,
            "selected_role_names": role_names,
            "selected_scopes": sorted(list(settings.included_scopes)),
            "backup_scope": ["guild", "roles", "channels", "emojis", "stickers", "scheduled_events", "messages_optional"],
            "guild": guild_info,
            "roles": roles_payload,
            "channels": channels,
            "emojis": emojis,
            "stickers": stickers,
            "scheduled_events": scheduled_events,
            "messages": messages_by_channel,
            "messages_channel_order": message_channel_order,
        }
        with open(backup_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        log_event("backup", f"saved {backup_path}")
        print_centered(f"Sukces: zapisano backup do {backup_path}", UiColor.GREEN)
    except Exception as exc:
        log_event("backup", f"exception: {exc}")
        print_centered(f"Błąd podczas zapisywania backupu: {exc}", UiColor.RED)
    wait_for_enter()


def show_backup_info() -> None:
    path = choose_backup_file()
    if not path:
        wait_for_enter(); return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        roles_count = len(data.get("roles", {}).get("data", []) if isinstance(data.get("roles"), dict) else [])
        channels_count = len(data.get("channels", {}).get("data", []) if isinstance(data.get("channels"), dict) else [])
        emojis_count = len(data.get("emojis", {}).get("data", []) if isinstance(data.get("emojis"), dict) else [])
        messages_count = sum(len(v) for v in data.get("messages", {}).values()) if isinstance(data.get("messages"), dict) else 0
        clear_console(); print_banner(); print(); print_centered("Informacje o backupie", UiColor.LIGHT_GRAY); print()
        role_filter = data.get("selected_role_names", [])
        info_lines = [
            f"Plik: {os.path.basename(path)}",
            f"Serwer: {data.get('guild_name', '-')}",
            f"ID serwera: {data.get('guild_id', '-')}",
            f"Owner ID: {data.get('owner_id', '-')}",
            f"Data utworzenia: {format_backup_timestamp(data.get('created_at', ''))}",
            f"Liczba ról: {roles_count}",
            f"Liczba kanałów: {channels_count}",
            f"Liczba emotek: {emojis_count}",
            f"Limit wiadomości/kanał: {data.get('messages_limit_per_channel', 100)}",
            f"Filtr ról: {', '.join(role_filter) if isinstance(role_filter, list) and role_filter else 'Wszystkie'}",
            f"Zakres: {', '.join(data.get('selected_scopes', [])) if isinstance(data.get('selected_scopes'), list) else 'pełny'}",
            f"Zapisane wiadomości: {messages_count}",
        ]
        draw_centered_box(info_lines)
    except Exception as exc:
        print_centered(f"Błąd odczytu backupu: {exc}", UiColor.RED)
    wait_for_enter()




def wipe_current_guild_state(token: str, guild_id: str, scopes: Set[str], fast_mode: bool) -> Dict[str, int]:
    deleted = {"channels": 0, "roles": 0, "emojis": 0, "stickers": 0, "events": 0}

    def delete_many(label: str, paths: List[str]) -> int:
        count = 0
        if not paths:
            return count
        if fast_mode:
            with ThreadPoolExecutor(max_workers=6) as executor:
                future_map = {executor.submit(api_delete, path, token): idx for idx, path in enumerate(paths, 1)}
                for future in as_completed(future_map):
                    idx = future_map[future]
                    try:
                        future.result()
                        count += 1
                    except Exception as exc:
                        log_event("cleanup", f"delete_error {label}: {exc}")
                    print_inline_status(f"Czyszczenie {label}: {idx}/{len(paths)}")
            clear_inline_status()
            return count

        for idx, path in enumerate(paths, 1):
            try:
                api_delete(path, token)
                count += 1
            except Exception as exc:
                log_event("cleanup", f"delete_error {label}: {exc}")
            print_inline_status(f"Czyszczenie {label}: {idx}/{len(paths)}")
        clear_inline_status()
        return count

    try:
        if "channels" in scopes:
            channels_res = api_get(f"/guilds/{guild_id}/channels", token)
            if channels_res.status_code == 200:
                paths = [f"/channels/{c.get('id')}" for c in channels_res.json() if c.get("id")]
                deleted["channels"] = delete_many("kanałów", paths)

        if "events" in scopes:
            events_res = api_get(f"/guilds/{guild_id}/scheduled-events", token)
            if events_res.status_code == 200:
                paths = [f"/guilds/{guild_id}/scheduled-events/{e.get('id')}" for e in events_res.json() if e.get("id")]
                deleted["events"] = delete_many("eventów", paths)

        if "emojis" in scopes:
            emojis_res = api_get(f"/guilds/{guild_id}/emojis", token)
            if emojis_res.status_code == 200:
                paths = [f"/guilds/{guild_id}/emojis/{e.get('id')}" for e in emojis_res.json() if e.get("id")]
                deleted["emojis"] = delete_many("emotek", paths)

        if "stickers" in scopes:
            stickers_res = api_get(f"/guilds/{guild_id}/stickers", token)
            if stickers_res.status_code == 200:
                paths = [f"/guilds/{guild_id}/stickers/{s.get('id')}" for s in stickers_res.json() if s.get("id")]
                deleted["stickers"] = delete_many("stickerów", paths)

        if "roles" in scopes:
            roles_res = api_get(f"/guilds/{guild_id}/roles", token)
            if roles_res.status_code == 200:
                roles = [r for r in roles_res.json() if r.get("name") != "@everyone" and not r.get("managed", False) and r.get("id")]
                roles.sort(key=lambda r: int(r.get("position", 0)))
                paths = [f"/guilds/{guild_id}/roles/{r.get('id')}" for r in roles]
                deleted["roles"] = delete_many("ról", paths)
    except requests.RequestException as exc:
        log_event("cleanup", f"network_error: {exc}")

    return deleted


def restore_backup_to_other_guild(token: str) -> None:
    backup_path = choose_backup_file()
    if not backup_path:
        wait_for_enter(); return
    target = choose_guild(token, "Wybierz serwer docelowy do odtworzenia")
    if not target:
        wait_for_enter(); return

    wipe_current = ask_yes_no("Usunąć aktualny stan serwera przed odtworzeniem?", default=False)
    fast_cleanup = ask_yes_no("Tryb szybkiego czyszczenia (równoległy)?", default=True)
    copy_messages = ask_yes_no("Przywrócić także zapisane wiadomości przez webhooki?", default=False)

    try:
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup = json.load(f)

        summary_lines = get_restore_plan_summary(backup, copy_messages)
        clear_console(); print_banner(); print(); print_centered("Dry Run - Podgląd planu", UiColor.LIGHT_GRAY); print()
        draw_centered_box(summary_lines)
        if ask_yes_no("Pokaż szczegółowy dry-run?", default=False):
            details = [
                f"Role: {', '.join([r.get('name','?') for r in backup.get('roles',{}).get('data',[])[:20]]) or '-'}",
                f"Kanały: {', '.join([c.get('name','?') for c in backup.get('channels',{}).get('data',[])[:20]]) or '-'}",
            ]
            draw_centered_box(details)
        if not ask_yes_no("Kontynuować odtwarzanie?", default=True):
            print_centered("Przerwano odtwarzanie.", UiColor.YELLOW)
            wait_for_enter(); return

        roles_data = backup.get("roles", {}).get("data", []) if isinstance(backup.get("roles"), dict) else []
        channels_data = backup.get("channels", {}).get("data", []) if isinstance(backup.get("channels"), dict) else []
        messages_data = backup.get("messages", {}) if isinstance(backup.get("messages"), dict) else {}
        messages_order = backup.get("messages_channel_order", []) if isinstance(backup.get("messages_channel_order"), list) else []

        settings = BACKUP_SETTINGS_BY_GUILD.get(target.guild_id, BackupSettings())
        if wipe_current:
            deleted = wipe_current_guild_state(token, target.guild_id, settings.cleanup_scopes, fast_cleanup)
            log_event("restore", f"wipe target={target.guild_id} deleted={deleted}")
            print_centered(
                f"Wyczyszczono serwer. Kanały: {deleted['channels']}, Role: {deleted['roles']}, Emotki: {deleted['emojis']}, Stickery: {deleted['stickers']}, Eventy: {deleted['events']}",
                UiColor.YELLOW,
            )

        applied, msg = apply_guild_settings_from_backup(token, target.guild_id, backup)
        print_centered(msg, UiColor.GREEN if applied else UiColor.YELLOW)
        log_event("restore", f"guild_settings applied={applied} msg={msg}")

        created_roles = 0
        created_channels = 0
        role_map: Dict[str, str] = {}
        channel_map: Dict[str, str] = {}

        manageable_roles = [r for r in roles_data if r.get("name") != "@everyone" and not r.get("managed", False)]
        manageable_roles.sort(key=lambda r: int(r.get("position", 0)))
        for idx, role in enumerate(manageable_roles, 1):
            payload = {
                "name": role.get("name", "Restored Role"),
                "permissions": role.get("permissions", "0"),
                "hoist": bool(role.get("hoist", False)),
                "mentionable": bool(role.get("mentionable", False)),
                "color": int(role.get("color", 0)),
            }
            res = api_post(f"/guilds/{target.guild_id}/roles", token, payload)
            if res.status_code in (200, 201):
                new_id = res.json().get("id")
                if new_id:
                    role_map[str(role.get("id"))] = new_id
                    created_roles += 1
            else:
                log_event("restore", f"create_role_failed {role.get('name')} HTTP {res.status_code}")
            print_inline_status(f"Status ról: {idx}/{len(manageable_roles)}")
        clear_inline_status()

        ordered_channels = sort_channels_in_backup_order(channels_data)

        pending_channels = ordered_channels[:]
        safety_passes = 0
        while pending_channels and safety_passes < 5:
            safety_passes += 1
            next_pending = []
            for idx, channel in enumerate(pending_channels, 1):
                parent_id = channel.get("parent_id")
                if parent_id and str(parent_id) not in channel_map:
                    next_pending.append(channel)
                    continue

                payload = {
                    "name": channel.get("name", "restored-channel"),
                    "type": channel.get("type", 0),
                    "topic": channel.get("topic"),
                    "nsfw": bool(channel.get("nsfw", False)),
                    "rate_limit_per_user": int(channel.get("rate_limit_per_user", 0) or 0),
                    "position": int(channel.get("position", 0) or 0),
                }
                overwrites = channel.get("permission_overwrites")
                if isinstance(overwrites, list):
                    mapped_overwrites = []
                    for ow in overwrites:
                        target_id = str(ow.get("id")) if ow.get("id") else None
                        ow_type = int(ow.get("type", 0))
                        if ow_type == 0 and target_id in role_map:
                            target_id = role_map[target_id]
                        if not target_id:
                            continue
                        mapped_overwrites.append({
                            "id": target_id,
                            "type": ow_type,
                            "allow": ow.get("allow", "0"),
                            "deny": ow.get("deny", "0"),
                        })
                    payload["permission_overwrites"] = mapped_overwrites

                if parent_id and str(parent_id) in channel_map:
                    payload["parent_id"] = channel_map[str(parent_id)]

                res = api_post(f"/guilds/{target.guild_id}/channels", token, payload)
                if res.status_code in (200, 201):
                    new_id = res.json().get("id")
                    if new_id:
                        channel_map[str(channel.get("id"))] = new_id
                        created_channels += 1
                else:
                    log_event("restore", f"create_channel_failed {channel.get('name')} HTTP {res.status_code}")
                print_inline_status(f"Status kanałów: {created_channels}/{len(ordered_channels)}")
            if len(next_pending) == len(pending_channels):
                break
            pending_channels = next_pending
        clear_inline_status()

        restored_messages = 0
        if copy_messages and messages_data:
            ordered_message_channels = [cid for cid in messages_order if cid in messages_data]
            for cid in messages_data.keys():
                if cid not in ordered_message_channels:
                    ordered_message_channels.append(cid)

            for old_channel_id in ordered_message_channels:
                messages = messages_data.get(old_channel_id)
                new_channel_id = channel_map.get(str(old_channel_id))
                if not new_channel_id or not isinstance(messages, list):
                    continue
                wh_res = api_post(f"/channels/{new_channel_id}/webhooks", token, {"name": "Backup Restore"})
                if wh_res.status_code not in (200, 201):
                    log_event("restore", f"webhook_create_failed channel={new_channel_id} HTTP {wh_res.status_code}")
                    continue
                webhook = wh_res.json()
                webhook_url = f"https://discord.com/api/webhooks/{webhook.get('id')}/{webhook.get('token')}"

                for msg in messages:
                    username_base = msg.get("author_name", "Unknown")
                    pseudo = msg.get("author_global_name") or "-"
                    username = f"{username_base} | {pseudo}"
                    avatar_hash = msg.get("author_avatar")
                    author_id = msg.get("author_id")
                    avatar_url = f"https://cdn.discordapp.com/avatars/{author_id}/{avatar_hash}.png" if avatar_hash and author_id else None
                    content = msg.get("content", "")
                    embeds = msg.get("embeds", []) if isinstance(msg.get("embeds"), list) else []
                    attachments = msg.get("attachments", []) if isinstance(msg.get("attachments"), list) else []
                    attachment_urls = [a.get("url") for a in attachments if isinstance(a, dict) and a.get("url")]
                    if not content and not embeds and not attachment_urls:
                        continue
                    payload = {"username": username, "avatar_url": avatar_url}
                    if content:
                        payload["content"] = content
                    if embeds:
                        payload["embeds"] = embeds
                    if attachment_urls:
                        payload["content"] = (payload.get("content", "") + "\n" + "\n".join(attachment_urls)).strip()
                    try:
                        requests.post(webhook_url, json=payload, timeout=REQUEST_TIMEOUT)
                        restored_messages += 1
                    except requests.RequestException as exc:
                        log_event("restore", f"webhook_send_failed: {exc}")
                        continue
                try:
                    api_delete(f"/webhooks/{webhook.get('id')}/{webhook.get('token')}", token)
                except Exception:
                    pass

        log_event("restore", f"done target={target.guild_id} roles={created_roles} channels={created_channels} messages={restored_messages}")
        print_centered(f"Przywracanie zakończone. Role: {created_roles}, Kanały: {created_channels}, Wiadomości: {restored_messages}", UiColor.GREEN)
    except Exception as exc:
        log_event("restore", f"exception: {exc}")
        print_centered(f"Błąd przywracania backupu: {exc}", UiColor.RED)

    wait_for_enter()


def run_server_cleanup(token: str) -> None:
    clear_console(); print_banner(); print(); print_centered("Server Cleanup", UiColor.LIGHT_GRAY)
    guild = choose_guild(token, "Wybierz serwer do wyczyszczenia")
    if not guild:
        wait_for_enter(); return
    settings = BACKUP_SETTINGS_BY_GUILD.get(guild.guild_id, BackupSettings())
    fast_mode = ask_yes_no("Tryb szybki czyszczenia?", default=True)
    if not ask_yes_no("Na pewno czyścić serwer według cleanup scopes?", default=False):
        print_centered("Anulowano czyszczenie.", UiColor.YELLOW)
        wait_for_enter(); return

    deleted = wipe_current_guild_state(token, guild.guild_id, settings.cleanup_scopes, fast_mode)
    log_event("cleanup", f"manual target={guild.guild_id} deleted={deleted}")
    draw_centered_box([
        f"Kanały: {deleted['channels']}",
        f"Role: {deleted['roles']}",
        f"Emotki: {deleted['emojis']}",
        f"Stickery: {deleted['stickers']}",
        f"Eventy: {deleted['events']}",
    ])
    wait_for_enter()


def token_actions_menu(selected_token: BotTokenStatus) -> None:
    while True:
        clear_console(); print_banner(); print()
        print_centered(f"Token #{selected_token.index}: {hide_token(selected_token.token)}", UiColor.DARK_GRAY)
        print_centered(f"Bot: {selected_token.bot_name} | ID: {selected_token.bot_id}", UiColor.LIGHT_GRAY)
        print()

        width = 56
        menu_lines = [
            "«01» Back",
            "«00» Zakończ program",
            "────────────────────────────────────────────────────────",
            centered_plain("[ Bot Information ]", width),
            "«02» Show Bot Info",
            "«03» Copy server invite link",
            "«04» Copy bot invite link",
            "«05» Give New Admin Role",
            "«06» Give Best Existing Role",
            "«11» Token Health Check",
            "────────────────────────────────────────────────────────",
            centered_plain("[ Backup ]", width),
            "«07» Backup settings",
            "«08» Full backup (roles/channels/emojis/stickers/etc)",
            "«09» Restore backup to another server",
            "«10» Show backup information",
            "«12» Server Cleanup",
        ]
        draw_centered_box(menu_lines)

        choice = input(color_text("\n-> ", UiColor.CYAN)).strip()
        if choice in {"1", "01"}:
            return
        if choice in {"0", "00"}:
            raise SystemExit
        if choice in {"2", "02"}:
            show_bot_info(selected_token.token)
        elif choice in {"3", "03"}:
            show_link_result_and_copy(create_guild_invite_link(selected_token.token), "Server invite link")
        elif choice in {"4", "04"}:
            show_link_result_and_copy(create_bot_invite_link(selected_token.token), "Bot invite link")
        elif choice in {"5", "05"}:
            grant_admin_role_to_user(selected_token.token)
        elif choice in {"6", "06"}:
            grant_best_existing_role_to_user(selected_token.token)
        elif choice in {"7", "07"}:
            configure_backup_settings(selected_token.token)
        elif choice in {"8", "08"}:
            backup_full_server_data(selected_token.token)
        elif choice in {"9", "09"}:
            restore_backup_to_other_guild(selected_token.token)
        elif choice in {"10", "010"}:
            show_backup_info()
        elif choice in {"11", "011"}:
            run_token_health_check(selected_token.token)
        elif choice in {"12", "012"}:
            run_server_cleanup(selected_token.token)
        else:
            print_centered("Niepoprawna opcja.", UiColor.RED); wait_for_enter()


def main() -> None:
    ensure_runtime_dirs()
    load_backup_settings_from_disk()
    while True:
        clear_console()
        tokens = read_tokens_file()
        if not tokens:
            print_banner(); print()
            print_centered(f"Brak tokenów w pliku: {TOKENS_FILE}", UiColor.RED)
            print_centered("Dodaj minimum 1 token (1 linia = 1 token) i uruchom ponownie.", UiColor.YELLOW)
            return

        statuses = validate_all_tokens(tokens)
        print_banner(); print()
        print_centered(f"Załadowano <{len(tokens)}> tokenów", UiColor.DARK_GRAY)
        print()

        lines: List[str] = []
        for status in statuses:
            state = color_text("DZIAŁA", UiColor.GREEN) if status.is_valid else color_text(f"NIE DZIAŁA ({status.error})", UiColor.RED)
            lines.append(f"«{str(status.index).zfill(2)}» {hide_token(status.token)} -> {state}")
        lines.append("«00» Zakończ")
        draw_centered_box(lines)

        choice = input(color_text("\n-> ", UiColor.CYAN)).strip()
        if choice in {"0", "00"}:
            return
        if not choice.isdigit():
            print_centered("Wpisz poprawny numer.", UiColor.RED); wait_for_enter(); continue

        selected_index = int(choice)
        selected = next((item for item in statuses if item.index == selected_index), None)
        if not selected:
            print_centered("Nie ma tokenu o takim numerze.", UiColor.RED); wait_for_enter(); continue
        if not selected.is_valid:
            print_centered("Ten token jest nieprawidłowy, wybierz działający.", UiColor.YELLOW); wait_for_enter(); continue

        try:
            token_actions_menu(selected)
        except SystemExit:
            return


if __name__ == "__main__":
    main()
