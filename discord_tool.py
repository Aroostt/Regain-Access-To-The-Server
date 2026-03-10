import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

TOKENS_FILE = "tokens.txt"
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
    inner_width = max(len(line) for line in lines) + 2
    box_width = inner_width + 2
    indent = max(0, (get_terminal_width() - box_width) // 2)
    pad = " " * indent

    print(color_text(f"{pad}╭{'─' * inner_width}╮", UiColor.LIGHT_GRAY))
    for line in lines:
        print(color_text(f"{pad}│ {line.ljust(inner_width - 1)}│", UiColor.LIGHT_GRAY))
    print(color_text(f"{pad}╰{'─' * inner_width}╯", UiColor.LIGHT_GRAY))


def wait_for_enter(message: str = "Press ENTER to continue...") -> None:
    input(color_text(f"\n{center_line(message)}", UiColor.CYAN))


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


def api_get(path: str, token: str) -> requests.Response:
    return requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}"},
        timeout=REQUEST_TIMEOUT,
    )


def api_post(path: str, token: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )


def api_put(path: str, token: str) -> requests.Response:
    return requests.put(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}"},
        timeout=REQUEST_TIMEOUT,
    )


def api_patch(path: str, token: str, payload: object) -> requests.Response:
    return requests.patch(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        data=json.dumps(payload),
        timeout=REQUEST_TIMEOUT,
    )


def validate_single_token(index: int, token: str) -> BotTokenStatus:
    try:
        response = api_get("/users/@me", token)
        if response.status_code == 200:
            data = response.json()
            full_name = f"{data.get('username', '?')}#{data.get('discriminator', '0')}"
            return BotTokenStatus(index=index, token=token, is_valid=True, bot_name=full_name, bot_id=data.get("id", "-"))
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
            print_centered(f"Cannot load guilds (HTTP {response.status_code}).", UiColor.RED)
            return None

        guilds: List[GuildEntry] = []
        for item in response.json():
            if item.get("id"):
                guilds.append(GuildEntry(guild_id=item["id"], guild_name=item.get("name", "Unknown")))
        return guilds
    except requests.RequestException as exc:
        print_centered(f"Network error: {exc}", UiColor.RED)
        return None


def choose_guild(token: str) -> Optional[GuildEntry]:
    guilds = fetch_bot_guilds(token)
    if guilds is None:
        return None
    if not guilds:
        print_centered("Bot is not in any guild.", UiColor.YELLOW)
        return None

    while True:
        clear_console()
        print_banner()
        print()
        print_centered("Select guild", UiColor.LIGHT_GRAY)
        print()
        for idx, guild in enumerate(guilds, 1):
            print_centered(f"[{idx}] {guild.guild_name} ({guild.guild_id})", UiColor.DARK_GRAY)
        print_centered("[0] Back", UiColor.DARK_GRAY)

        choice = input(color_text(f"\n{center_line('-> ')}", UiColor.CYAN)).strip()
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
        if not app_id:
            return None
        return f"https://discord.com/oauth2/authorize?client_id={app_id}&permissions=8&scope=bot%20applications.commands"
    except requests.RequestException:
        return None


def create_guild_invite_link(token: str) -> Optional[str]:
    guild = choose_guild(token)
    if not guild:
        return None

    try:
        channels_response = api_get(f"/guilds/{guild.guild_id}/channels", token)
        if channels_response.status_code != 200:
            print_centered(f"Cannot load channels (HTTP {channels_response.status_code}).", UiColor.RED)
            return None

        text_channels = [c for c in channels_response.json() if c.get("type") == 0]
        if not text_channels:
            print_centered("No text channel found for invite.", UiColor.YELLOW)
            return None

        invite_response = api_post(
            f"/channels/{text_channels[0].get('id')}/invites",
            token,
            {"max_age": 0, "max_uses": 0, "temporary": False, "unique": True},
        )
        if invite_response.status_code not in (200, 201):
            print_centered(f"Cannot create invite (HTTP {invite_response.status_code}).", UiColor.RED)
            return None

        invite_code = invite_response.json().get("code")
        return f"https://discord.gg/{invite_code}" if invite_code else None
    except requests.RequestException as exc:
        print_centered(f"Network error: {exc}", UiColor.RED)
        return None


def get_bot_role_context(token: str, guild_id: str) -> Tuple[Dict[str, int], List[str]]:
    roles_response = api_get(f"/guilds/{guild_id}/roles", token)
    if roles_response.status_code != 200:
        return {}, []

    role_positions = {
        str(role.get("id")): int(role.get("position", 0))
        for role in roles_response.json()
        if role.get("id")
    }

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
            return False, "Cannot read role positions."

        bot_top_positions = [role_positions.get(rid, 0) for rid in bot_role_ids if rid in role_positions]
        if not bot_top_positions:
            return False, "Bot has no manageable role in hierarchy."

        target_position = max(1, max(bot_top_positions) - 1)
        response = api_patch(
            f"/guilds/{guild_id}/roles",
            token,
            [{"id": role_id, "position": target_position}],
        )
        if response.status_code in (200, 201):
            return True, "Role moved to highest possible position."
        return False, f"Role move failed (HTTP {response.status_code})."
    except requests.RequestException as exc:
        return False, f"Network error during role move: {exc}"


def grant_admin_role_to_user(token: str) -> None:
    clear_console()
    print_banner()
    print()
    print_centered("Grant admin role", UiColor.LIGHT_GRAY)

    guild = choose_guild(token)
    if not guild:
        wait_for_enter()
        return

    user_id = input(color_text(f"\n{center_line('Enter Discord user ID: ')}", UiColor.CYAN)).strip()
    if not user_id.isdigit():
        print_centered("Invalid user ID.", UiColor.RED)
        wait_for_enter()
        return

    try:
        create_role_response = api_post(
            f"/guilds/{guild.guild_id}/roles",
            token,
            {
                "name": "Tool Admin",
                "permissions": "8",
                "hoist": True,
                "mentionable": True,
                "reason": "Grant full admin role from CLI tool",
            },
        )
        if create_role_response.status_code not in (200, 201):
            print_centered(f"Role creation failed (HTTP {create_role_response.status_code}).", UiColor.RED)
            print(create_role_response.text)
            wait_for_enter()
            return

        role_id = create_role_response.json().get("id")
        if not role_id:
            print_centered("Cannot read created role ID.", UiColor.RED)
            wait_for_enter()
            return

        moved, move_message = move_role_to_highest_possible(token, guild.guild_id, role_id)
        print_centered(move_message, UiColor.GREEN if moved else UiColor.YELLOW)

        assign_response = api_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{role_id}", token)
        if assign_response.status_code in (200, 204):
            print_centered("Success: admin role granted.", UiColor.GREEN)
        else:
            print_centered(f"Role assign failed (HTTP {assign_response.status_code}).", UiColor.RED)
            print(assign_response.text)
    except requests.RequestException as exc:
        print_centered(f"Network error: {exc}", UiColor.RED)

    wait_for_enter()


def grant_best_existing_role_to_user(token: str) -> None:
    clear_console()
    print_banner()
    print()
    print_centered("Grant best existing role", UiColor.LIGHT_GRAY)

    guild = choose_guild(token)
    if not guild:
        wait_for_enter()
        return

    user_id = input(color_text(f"\n{center_line('Enter Discord user ID: ')}", UiColor.CYAN)).strip()
    if not user_id.isdigit():
        print_centered("Invalid user ID.", UiColor.RED)
        wait_for_enter()
        return

    try:
        role_positions, bot_role_ids = get_bot_role_context(token, guild.guild_id)
        if not role_positions or not bot_role_ids:
            print_centered("Cannot determine bot role hierarchy.", UiColor.RED)
            wait_for_enter()
            return

        highest_bot_position = max(role_positions.get(role_id, 0) for role_id in bot_role_ids)

        roles_response = api_get(f"/guilds/{guild.guild_id}/roles", token)
        if roles_response.status_code != 200:
            print_centered(f"Cannot read server roles (HTTP {roles_response.status_code}).", UiColor.RED)
            wait_for_enter()
            return

        manageable_roles = [
            role
            for role in roles_response.json()
            if role.get("id")
            and role.get("name") != "@everyone"
            and not role.get("managed", False)
            and int(role.get("position", 0)) < highest_bot_position
        ]

        if not manageable_roles:
            print_centered("No existing role can be granted by this bot.", UiColor.YELLOW)
            wait_for_enter()
            return

        best_role = max(manageable_roles, key=lambda role: int(role.get("position", 0)))
        assign_response = api_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{best_role.get('id')}", token)

        if assign_response.status_code in (200, 204):
            print_centered(f"Success: granted role '{best_role.get('name', 'Unknown')}'.", UiColor.GREEN)
        else:
            print_centered(f"Role assign failed (HTTP {assign_response.status_code}).", UiColor.RED)
            print(assign_response.text)
    except requests.RequestException as exc:
        print_centered(f"Network error: {exc}", UiColor.RED)

    wait_for_enter()


def show_link_result_and_copy(link: Optional[str], label: str) -> None:
    if not link:
        print_centered(f"Cannot generate: {label}", UiColor.RED)
        wait_for_enter()
        return

    if copy_to_clipboard(link):
        print_centered(f"Copied: {label}", UiColor.GREEN)
    else:
        print_centered("Clipboard copy failed. Link below:", UiColor.YELLOW)
        print(link)
    wait_for_enter()


def token_actions_menu(selected_token: BotTokenStatus) -> None:
    while True:
        clear_console()
        print_banner()
        print()
        print_centered(f"Token #{selected_token.index}: {hide_token(selected_token.token)}", UiColor.DARK_GRAY)
        print_centered(f"Bot: {selected_token.bot_name} | ID: {selected_token.bot_id}", UiColor.LIGHT_GRAY)
        print()

        menu_lines = [
            "«01» Back                              «04» Grant admin role",
            "«02» Copy server invite link           «05» Grant best existing role",
            "«03» Copy bot invite link              «00» Exit program",
        ]
        draw_centered_box(menu_lines)

        choice = input(color_text(f"\n{center_line('-> ')}", UiColor.CYAN)).strip()
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
        else:
            print_centered("Invalid option.", UiColor.RED)
            wait_for_enter()


def main() -> None:
    while True:
        clear_console()

        tokens = read_tokens_file()
        if not tokens:
            print_banner()
            print()
            print_centered(f"No tokens in file: {TOKENS_FILE}", UiColor.RED)
            print_centered("Add at least 1 token (1 line = 1 token) and start again.", UiColor.YELLOW)
            return

        statuses = validate_all_tokens(tokens)
        print_banner()
        print()
        print_centered(f"Loaded <{len(tokens)}> tokens", UiColor.DARK_GRAY)
        print()

        lines: List[str] = []
        for status in statuses:
            state = color_text("WORKING", UiColor.GREEN) if status.is_valid else color_text(f"INVALID ({status.error})", UiColor.RED)
            lines.append(f"«{str(status.index).zfill(2)}» {hide_token(status.token)} -> {state}")
        lines.append("«00» Exit")
        draw_centered_box(lines)

        choice = input(color_text(f"\n{center_line('-> ')}", UiColor.CYAN)).strip()
        if choice in {"0", "00"}:
            return
        if not choice.isdigit():
            print_centered("Enter a valid number.", UiColor.RED)
            wait_for_enter()
            continue

        selected_index = int(choice)
        selected = next((item for item in statuses if item.index == selected_index), None)
        if not selected:
            print_centered("Token number not found.", UiColor.RED)
            wait_for_enter()
            continue
        if not selected.is_valid:
            print_centered("This token is invalid. Select a working one.", UiColor.YELLOW)
            wait_for_enter()
            continue

        try:
            token_actions_menu(selected)
        except SystemExit:
            return


if __name__ == "__main__":
    main()
