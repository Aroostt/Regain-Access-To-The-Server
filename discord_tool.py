import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

TOKENS_FILE = "tokens.txt"
BACKUPS_DIR = "backups"
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

    copy_messages = input(color_text("\nCzy zapisać także wiadomości (max 100 na kanał)? [t/N]: ", UiColor.CYAN)).strip().lower() == 't'

    def fetch(path: str, params: Optional[dict] = None) -> Dict[str, object]:
        try:
            response = api_get(path, token, params=params)
            if response.status_code == 200:
                return {"ok": True, "status": 200, "data": response.json()}
            return {"ok": False, "status": response.status_code, "error": response.text}
        except requests.RequestException as exc:
            return {"ok": False, "status": None, "error": str(exc)}

    try:
        guild_info = fetch(f"/guilds/{guild.guild_id}")
        roles = fetch(f"/guilds/{guild.guild_id}/roles")
        channels = fetch(f"/guilds/{guild.guild_id}/channels")
        emojis = fetch(f"/guilds/{guild.guild_id}/emojis")
        stickers = fetch(f"/guilds/{guild.guild_id}/stickers")
        scheduled_events = fetch(f"/guilds/{guild.guild_id}/scheduled-events")

        messages_by_channel: Dict[str, List[dict]] = {}
        if copy_messages and channels.get("ok"):
            text_channels = [ch for ch in channels["data"] if ch.get("type") == 0 and ch.get("id")]
            for idx, ch in enumerate(text_channels, 1):
                print_centered(f"Pobieranie wiadomości: {idx}/{len(text_channels)}", UiColor.DARK_GRAY)
                msg_res = fetch(f"/channels/{ch['id']}/messages", params={"limit": 100})
                if not msg_res.get("ok"):
                    continue
                saved = []
                for msg in msg_res.get("data", []):
                    author = msg.get("author", {})
                    saved.append({
                        "id": msg.get("id"),
                        "content": msg.get("content", ""),
                        "author_name": author.get("username", "Unknown"),
                        "author_avatar": author.get("avatar"),
                        "author_id": author.get("id"),
                    })
                messages_by_channel[ch["id"]] = list(reversed(saved))

        owner_id = guild_info.get("data", {}).get("owner_id") if guild_info.get("ok") else None
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUPS_DIR, f"full_backup_{guild.guild_id}_{timestamp}.json")

        payload = {
            "guild_id": guild.guild_id,
            "guild_name": guild.guild_name,
            "owner_id": owner_id,
            "created_at": timestamp,
            "messages_saved": copy_messages,
            "backup_scope": ["guild", "roles", "channels", "emojis", "stickers", "scheduled_events", "messages_optional"],
            "guild": guild_info,
            "roles": roles,
            "channels": channels,
            "emojis": emojis,
            "stickers": stickers,
            "scheduled_events": scheduled_events,
            "messages": messages_by_channel,
        }
        with open(backup_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        print_centered(f"Sukces: zapisano backup do {backup_path}", UiColor.GREEN)
    except Exception as exc:
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
        info_lines = [
            f"Plik: {os.path.basename(path)}",
            f"Serwer: {data.get('guild_name', '-')}",
            f"ID serwera: {data.get('guild_id', '-')}",
            f"Owner ID: {data.get('owner_id', '-')}",
            f"Data utworzenia: {data.get('created_at', '-')}",
            f"Liczba ról: {roles_count}",
            f"Liczba kanałów: {channels_count}",
            f"Liczba emotek: {emojis_count}",
            f"Zapisane wiadomości: {messages_count}",
        ]
        draw_centered_box(info_lines)
    except Exception as exc:
        print_centered(f"Błąd odczytu backupu: {exc}", UiColor.RED)
    wait_for_enter()


def restore_backup_to_other_guild(token: str) -> None:
    backup_path = choose_backup_file()
    if not backup_path:
        wait_for_enter(); return
    target = choose_guild(token, "Wybierz serwer docelowy do odtworzenia")
    if not target:
        wait_for_enter(); return

    copy_messages = input(color_text("\nPrzywrócić także zapisane wiadomości przez webhooki? [t/N]: ", UiColor.CYAN)).strip().lower() == 't'

    try:
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup = json.load(f)

        roles_data = backup.get("roles", {}).get("data", []) if isinstance(backup.get("roles"), dict) else []
        channels_data = backup.get("channels", {}).get("data", []) if isinstance(backup.get("channels"), dict) else []
        messages_data = backup.get("messages", {}) if isinstance(backup.get("messages"), dict) else {}

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
            print_centered(f"Status ról: {idx}/{len(manageable_roles)}", UiColor.DARK_GRAY)

        category_channels = [c for c in channels_data if c.get("type") == 4]
        normal_channels = [c for c in channels_data if c.get("type") != 4]

        for idx, channel in enumerate(category_channels + normal_channels, 1):
            payload = {
                "name": channel.get("name", "restored-channel"),
                "type": channel.get("type", 0),
                "topic": channel.get("topic"),
                "nsfw": bool(channel.get("nsfw", False)),
                "rate_limit_per_user": int(channel.get("rate_limit_per_user", 0) or 0),
            }
            parent_id = channel.get("parent_id")
            if parent_id and str(parent_id) in channel_map:
                payload["parent_id"] = channel_map[str(parent_id)]

            res = api_post(f"/guilds/{target.guild_id}/channels", token, payload)
            if res.status_code in (200, 201):
                new_id = res.json().get("id")
                if new_id:
                    channel_map[str(channel.get("id"))] = new_id
                    created_channels += 1
            print_centered(f"Status kanałów: {idx}/{len(channels_data)}", UiColor.DARK_GRAY)

        restored_messages = 0
        if copy_messages and messages_data:
            for old_channel_id, messages in messages_data.items():
                new_channel_id = channel_map.get(str(old_channel_id))
                if not new_channel_id or not isinstance(messages, list):
                    continue
                wh_res = api_post(f"/channels/{new_channel_id}/webhooks", token, {"name": "Backup Restore"})
                if wh_res.status_code not in (200, 201):
                    continue
                webhook = wh_res.json()
                webhook_url = f"https://discord.com/api/webhooks/{webhook.get('id')}/{webhook.get('token')}"
                for msg in messages[:100]:
                    username = msg.get("author_name", "Unknown")
                    avatar_hash = msg.get("author_avatar")
                    author_id = msg.get("author_id")
                    avatar_url = f"https://cdn.discordapp.com/avatars/{author_id}/{avatar_hash}.png" if avatar_hash and author_id else None
                    content = msg.get("content", "")
                    if not content:
                        continue
                    try:
                        requests.post(webhook_url, json={"username": username, "avatar_url": avatar_url, "content": content}, timeout=REQUEST_TIMEOUT)
                        restored_messages += 1
                    except requests.RequestException:
                        continue
                try:
                    api_delete(f"/webhooks/{webhook.get('id')}/{webhook.get('token')}", token)
                except Exception:
                    pass

        print_centered(f"Przywracanie zakończone. Role: {created_roles}, Kanały: {created_channels}, Wiadomości: {restored_messages}", UiColor.GREEN)
    except Exception as exc:
        print_centered(f"Błąd przywracania backupu: {exc}", UiColor.RED)

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
            "«02» Copy server invite link",
            "«03» Copy bot invite link",
            "«04» Give New Admin Role",
            "«05» Give Best Existing Role",
            "────────────────────────────────────────────────────────",
            centered_plain("[ Backup ]", width),
            "«06» Full backup (roles/channels/emojis/stickers/etc)",
            "«07» Restore backup to another server",
            "«08» Show backup information",
        ]
        draw_centered_box(menu_lines)

        choice = input(color_text("\n-> ", UiColor.CYAN)).strip()
        if choice in {"1", "01"}:
            return
        if choice in {"0", "00"}:
            raise SystemExit
        if choice in {"2", "02"}:
            show_link_result_and_copy(create_guild_invite_link(selected_token.token), "Server invite link")
        elif choice in {"3", "03"}:
            show_link_result_and_copy(create_bot_invite_link(selected_token.token), "Bot invite link")
        elif choice in {"4", "04"}:
            grant_admin_role_to_user(selected_token.token)
        elif choice in {"5", "05"}:
            grant_best_existing_role_to_user(selected_token.token)
        elif choice in {"6", "06"}:
            backup_full_server_data(selected_token.token)
        elif choice in {"7", "07"}:
            restore_backup_to_other_guild(selected_token.token)
        elif choice in {"8", "08"}:
            show_backup_info()
        else:
            print_centered("Niepoprawna opcja.", UiColor.RED); wait_for_enter()


def main() -> None:
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
