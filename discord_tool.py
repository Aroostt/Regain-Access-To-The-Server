import json
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

import requests

TOKENS_FILE = "tokens.txt"
API_BASE = "https://discord.com/api/v10"
TIMEOUT = 12


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    WHITE = "\033[97m"


@dataclass
class TokenInfo:
    index: int
    token: str
    valid: bool
    bot_name: str = "-"
    bot_id: str = "-"
    error: str = ""


@dataclass
class GuildInfo:
    guild_id: str
    name: str


def color(text: str, tone: str) -> str:
    return f"{tone}{text}{Colors.RESET}"


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def banner() -> None:
    print(color("""
                                ██████╗██╗    ██╗███████╗██╗     ██╗██╗   ██╗███╗   ███╗
                               ██╔════╝██║    ██║██╔════╝██║     ██║██║   ██║████╗ ████║
                               ██║     ██║ █╗ ██║█████╗  ██║     ██║██║   ██║██╔████╔██║
                               ██║     ██║███╗██║██╔══╝  ██║     ██║██║   ██║██║╚██╔╝██║
                               ╚██████╗╚███╔███╔╝███████╗███████╗██║╚██████╔╝██║ ╚═╝ ██║
                                ╚═════╝ ╚══╝╚══╝ ╚══════╝╚══════╝╚═╝ ╚═════╝ ╚═╝     ╚═╝
""".rstrip("\n"), Colors.WHITE + Colors.BOLD))


def print_main_header(tokens_count: int) -> None:
    banner()
    print()
    info = f"Loaded <{tokens_count}> tokens"
    print(color(f"{' ' * 42}{info}", Colors.DIM + Colors.CYAN))
    print()


def print_box(lines: List[str]) -> None:
    width = max(len(line) for line in lines) + 2
    print(color(f"╭{'─' * width}╮", Colors.CYAN))
    for line in lines:
        print(color(f"│ {line.ljust(width - 1)}│", Colors.CYAN))
    print(color(f"╰{'─' * width}╯", Colors.CYAN))


def pause(msg: str = "Naciśnij ENTER, aby kontynuować...") -> None:
    input(color(f"\n{msg}", Colors.BLUE))


def read_tokens() -> List[str]:
    if not os.path.exists(TOKENS_FILE):
        return []

    tokens: List[str] = []
    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            token = line.strip()
            if token and not token.startswith("#"):
                tokens.append(token)
    return tokens


def mask_token(token: str) -> str:
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:5]}...{token[-5:]}"


def discord_get(path: str, token: str) -> requests.Response:
    return requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}"},
        timeout=TIMEOUT,
    )


def discord_post(path: str, token: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{API_BASE}{path}",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=TIMEOUT,
    )


def discord_put(path: str, token: str) -> requests.Response:
    return requests.put(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bot {token}"},
        timeout=TIMEOUT,
    )


def discord_patch(path: str, token: str, payload: object) -> requests.Response:
    return requests.patch(
        f"{API_BASE}{path}",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=TIMEOUT,
    )


def validate_token(index: int, token: str) -> TokenInfo:
    try:
        response = discord_get("/users/@me", token)
        if response.status_code == 200:
            data = response.json()
            username = f"{data.get('username', '?')}#{data.get('discriminator', '0')}"
            return TokenInfo(index=index, token=token, valid=True, bot_name=username, bot_id=data.get("id", "-"))
        return TokenInfo(index=index, token=token, valid=False, error=f"HTTP {response.status_code}")
    except requests.RequestException as exc:
        return TokenInfo(index=index, token=token, valid=False, error=str(exc))


def check_all_tokens(tokens: List[str]) -> List[TokenInfo]:
    return [validate_token(i + 1, token) for i, token in enumerate(tokens)]


def copy_to_clipboard(text: str) -> bool:
    try:
        if os.name == "nt":
            subprocess.run("clip", input=text.encode("utf-16le"), check=True)
            return True
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
        return True
    except Exception:
        return False


def get_guilds(token: str) -> Optional[List[GuildInfo]]:
    try:
        response = discord_get("/users/@me/guilds", token)
        if response.status_code != 200:
            print(color(f"Nie udało się pobrać serwerów bota (HTTP {response.status_code}).", Colors.RED))
            return None
        guilds_raw = response.json()
        return [GuildInfo(guild_id=g.get("id", ""), name=g.get("name", "Unknown")) for g in guilds_raw if g.get("id")]
    except requests.RequestException as exc:
        print(color(f"Błąd połączenia: {exc}", Colors.RED))
        return None


def pick_guild(token: str) -> Optional[GuildInfo]:
    guilds = get_guilds(token)
    if guilds is None:
        return None
    if not guilds:
        print(color("Bot nie jest na żadnym serwerze.", Colors.YELLOW))
        return None

    while True:
        clear_screen()
        banner()
        print(color("\n  Wybór serwera:\n", Colors.CYAN))
        for i, guild in enumerate(guilds, 1):
            print(f"  [{i}] {guild.name} {color(f'(ID: {guild.guild_id})', Colors.DIM + Colors.BLUE)}")
        print("  [0] Powrót")
        choice = input(color("\n  -> ", Colors.CYAN)).strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(guilds):
            return guilds[int(choice) - 1]


def build_bot_invite_link(token: str) -> Optional[str]:
    try:
        response = discord_get("/oauth2/applications/@me", token)
        if response.status_code != 200:
            return None
        app_id = response.json().get("id")
        if not app_id:
            return None
        return f"https://discord.com/oauth2/authorize?client_id={app_id}&permissions=8&scope=bot%20applications.commands"
    except requests.RequestException:
        return None


def build_server_invite_link(token: str) -> Optional[str]:
    guild = pick_guild(token)
    if not guild:
        return None
    try:
        channels = discord_get(f"/guilds/{guild.guild_id}/channels", token)
        if channels.status_code != 200:
            print(color(f"Nie udało się pobrać kanałów (HTTP {channels.status_code}).", Colors.RED))
            return None
        text_channels = [channel for channel in channels.json() if channel.get("type") == 0]
        if not text_channels:
            print(color("Brak kanału tekstowego do utworzenia zaproszenia.", Colors.YELLOW))
            return None
        channel = text_channels[0]
        invite = discord_post(
            f"/channels/{channel.get('id')}/invites",
            token,
            {"max_age": 0, "max_uses": 0, "temporary": False, "unique": True},
        )
        if invite.status_code not in (200, 201):
            print(color(f"Nie udało się utworzyć zaproszenia (HTTP {invite.status_code}).", Colors.RED))
            return None
        code = invite.json().get("code")
        return f"https://discord.gg/{code}" if code else None
    except requests.RequestException as exc:
        print(color(f"Błąd połączenia: {exc}", Colors.RED))
        return None


def get_bot_member_and_positions(token: str, guild_id: str) -> Tuple[Optional[str], dict, List[str]]:
    roles_response = discord_get(f"/guilds/{guild_id}/roles", token)
    if roles_response.status_code != 200:
        return None, {}, []
    roles = roles_response.json()
    role_positions = {str(role.get("id")): int(role.get("position", 0)) for role in roles if role.get("id")}

    bot_response = discord_get("/users/@me", token)
    if bot_response.status_code != 200:
        return None, role_positions, []
    bot_id = bot_response.json().get("id")
    if not bot_id:
        return None, role_positions, []

    member_response = discord_get(f"/guilds/{guild_id}/members/{bot_id}", token)
    if member_response.status_code != 200:
        return None, role_positions, []

    bot_role_ids = member_response.json().get("roles", [])
    return bot_id, role_positions, bot_role_ids


def move_role_to_top(token: str, guild_id: str, role_id: str) -> Tuple[bool, str]:
    try:
        _, role_positions, bot_role_ids = get_bot_member_and_positions(token, guild_id)
        if not role_positions:
            return False, "Nie udało się pobrać pozycji ról."

        bot_positions = [pos for rid, pos in role_positions.items() if rid in set(bot_role_ids)]
        if not bot_positions:
            return False, "Bot nie ma roli do zarządzania hierarchią."

        highest_bot_position = max(bot_positions)
        target_position = max(1, highest_bot_position - 1)

        move_response = discord_patch(
            f"/guilds/{guild_id}/roles",
            token,
            [{"id": role_id, "position": target_position}],
        )
        if move_response.status_code in (200, 201):
            return True, "Rola została przesunięta na najwyższą możliwą pozycję."
        return False, f"Nie udało się przesunąć roli wyżej (HTTP {move_response.status_code})."
    except requests.RequestException as exc:
        return False, f"Błąd połączenia podczas przesuwania roli: {exc}"


def grant_admin_role(token: str) -> None:
    clear_screen()
    banner()
    print(color("\n  Nadawanie roli Administrator\n", Colors.CYAN))

    guild = pick_guild(token)
    if not guild:
        pause()
        return

    user_id = input(color("\n  Podaj ID użytkownika Discord: ", Colors.CYAN)).strip()
    if not user_id.isdigit():
        print(color("Niepoprawne ID użytkownika.", Colors.RED))
        pause()
        return

    try:
        create_role = discord_post(
            f"/guilds/{guild.guild_id}/roles",
            token,
            {
                "name": "Tool Admin",
                "permissions": "8",
                "hoist": True,
                "mentionable": True,
                "reason": "Nadanie roli administratora przez narzędzie",
            },
        )
        if create_role.status_code not in (200, 201):
            print(color(f"Nie udało się utworzyć roli (HTTP {create_role.status_code}).", Colors.RED))
            print(create_role.text)
            pause()
            return

        role_id = create_role.json().get("id")
        if not role_id:
            print(color("Nie udało się odczytać ID nowej roli.", Colors.RED))
            pause()
            return

        moved, msg = move_role_to_top(token, guild.guild_id, role_id)
        print(color(msg, Colors.GREEN if moved else Colors.YELLOW))

        assign_role = discord_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{role_id}", token)
        if assign_role.status_code in (200, 204):
            print(color("Sukces! Użytkownik otrzymał rolę Administrator.", Colors.GREEN))
        else:
            print(color(f"Nie udało się przypisać roli (HTTP {assign_role.status_code}).", Colors.RED))
            print(assign_role.text)
    except requests.RequestException as exc:
        print(color(f"Błąd połączenia: {exc}", Colors.RED))

    pause()


def assign_best_existing_role(token: str) -> None:
    clear_screen()
    banner()
    print(color("\n  Nadawanie najlepszej istniejącej rangi\n", Colors.CYAN))

    guild = pick_guild(token)
    if not guild:
        pause()
        return

    user_id = input(color("\n  Podaj ID użytkownika Discord: ", Colors.CYAN)).strip()
    if not user_id.isdigit():
        print(color("Niepoprawne ID użytkownika.", Colors.RED))
        pause()
        return

    try:
        _, role_positions, bot_role_ids = get_bot_member_and_positions(token, guild.guild_id)
        if not role_positions or not bot_role_ids:
            print(color("Nie udało się ustalić hierarchii ról bota.", Colors.RED))
            pause()
            return

        highest_bot_position = max(role_positions.get(role_id, 0) for role_id in bot_role_ids)

        roles_response = discord_get(f"/guilds/{guild.guild_id}/roles", token)
        if roles_response.status_code != 200:
            print(color(f"Nie udało się pobrać ról serwera (HTTP {roles_response.status_code}).", Colors.RED))
            pause()
            return

        roles = roles_response.json()
        manageable_roles = [
            role for role in roles
            if role.get("id")
            and role.get("name") != "@everyone"
            and not role.get("managed", False)
            and int(role.get("position", 0)) < highest_bot_position
        ]

        if not manageable_roles:
            print(color("Brak istniejącej rangi, którą bot może nadać.", Colors.YELLOW))
            pause()
            return

        best_role = max(manageable_roles, key=lambda r: int(r.get("position", 0)))
        role_id = best_role.get("id")
        role_name = best_role.get("name", "Unknown")

        assign_role = discord_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{role_id}", token)
        if assign_role.status_code in (200, 204):
            print(color(f"Sukces! Nadano istniejącą rangę: {role_name}", Colors.GREEN))
        else:
            print(color(f"Nie udało się nadać rangi (HTTP {assign_role.status_code}).", Colors.RED))
            print(assign_role.text)
    except requests.RequestException as exc:
        print(color(f"Błąd połączenia: {exc}", Colors.RED))

    pause()


def copy_link_with_feedback(link: Optional[str], kind: str) -> None:
    if not link:
        print(color(f"Nie udało się pobrać linku: {kind}", Colors.RED))
        pause()
        return
    if copy_to_clipboard(link):
        print(color(f"Skopiowano: {kind}", Colors.GREEN))
    else:
        print(color("Nie udało się skopiować do schowka. Link poniżej:", Colors.YELLOW))
        print(link)
    pause()


def token_menu(info: TokenInfo) -> None:
    while True:
        clear_screen()
        banner()
        print(color(f"\n  Token #{info.index}: {mask_token(info.token)}", Colors.BLUE))
        print(color(f"  Bot: {info.bot_name} | ID: {info.bot_id}\n", Colors.GREEN))

        menu_lines = [
            "«01» Back                                 «04» Permisje (admin dla użytkownika)",
            "«02» Copy Server Link                     «05» Daj najlepszą istniejącą rangę",
            "«03» Copy Bot Invite Link                 «00» Zakończ program",
        ]
        print_box(menu_lines)

        choice = input(color("\n  -> ", Colors.CYAN)).strip()
        if choice in {"1", "01"}:
            return
        if choice in {"0", "00"}:
            raise SystemExit
        if choice in {"2", "02"}:
            copy_link_with_feedback(build_server_invite_link(info.token), "Link do serwera")
        elif choice in {"3", "03"}:
            copy_link_with_feedback(build_bot_invite_link(info.token), "Link do dodania bota")
        elif choice in {"4", "04"}:
            grant_admin_role(info.token)
        elif choice in {"5", "05"}:
            assign_best_existing_role(info.token)
        else:
            print(color("Niepoprawny wybór.", Colors.RED))
            pause()


def main() -> None:
    while True:
        clear_screen()
        tokens = read_tokens()

        if not tokens:
            banner()
            print(color(f"\n  Brak tokenów w pliku: {TOKENS_FILE}", Colors.RED))
            print(color("  Dodaj minimum 1 token (1 linia = 1 token) i uruchom ponownie.", Colors.YELLOW))
            return

        token_infos = check_all_tokens(tokens)
        print_main_header(len(tokens))

        token_lines = []
        for info in token_infos:
            status = color("DZIAŁA", Colors.GREEN) if info.valid else color(f"NIE DZIAŁA ({info.error})", Colors.RED)
            token_lines.append(f"«{str(info.index).zfill(2)}» {mask_token(info.token)} -> {status}")

        token_lines.append("«00» Zakończ")
        print_box(token_lines)

        choice = input(color("\n  -> ", Colors.CYAN)).strip()
        if choice in {"0", "00"}:
            return
        if not choice.isdigit():
            print(color("Wpisz poprawny numer.", Colors.RED))
            pause()
            continue

        selected_idx = int(choice)
        selected = next((x for x in token_infos if x.index == selected_idx), None)
        if not selected:
            print(color("Nie ma tokenu o takim numerze.", Colors.RED))
            pause()
            continue
        if not selected.valid:
            print(color("Ten token jest nieprawidłowy, wybierz działający token.", Colors.YELLOW))
            pause()
            continue

        try:
            token_menu(selected)
        except SystemExit:
            return


if __name__ == "__main__":
    main()
