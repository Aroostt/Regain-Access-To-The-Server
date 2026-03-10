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
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"


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


def print_header(title: str) -> None:
    print(color("=" * 46, Colors.CYAN))
    print(color(f"  {title}", Colors.BOLD + Colors.MAGENTA))
    print(color("=" * 46, Colors.CYAN))


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
            return TokenInfo(
                index=index,
                token=token,
                valid=True,
                bot_name=username,
                bot_id=data.get("id", "-"),
            )
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
        guilds = [GuildInfo(guild_id=g.get("id", ""), name=g.get("name", "Unknown")) for g in guilds_raw if g.get("id")]
        return guilds
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
        print_header("Wybór serwera")
        print()
        for i, guild in enumerate(guilds, 1):
            print(f"[{i}] {guild.name} {color(f'(ID: {guild.guild_id})', Colors.BLUE)}")
        print("[0] Powrót")

        choice = input(color("\nWybierz numer serwera: ", Colors.CYAN)).strip()
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
            {
                "max_age": 0,
                "max_uses": 0,
                "temporary": False,
                "unique": True,
            },
        )
        if invite.status_code not in (200, 201):
            print(color(f"Nie udało się utworzyć zaproszenia (HTTP {invite.status_code}).", Colors.RED))
            return None

        code = invite.json().get("code")
        if not code:
            return None

        return f"https://discord.gg/{code}"
    except requests.RequestException as exc:
        print(color(f"Błąd połączenia: {exc}", Colors.RED))
        return None


def move_role_to_top(token: str, guild_id: str, role_id: str) -> Tuple[bool, str]:
    try:
        roles_response = discord_get(f"/guilds/{guild_id}/roles", token)
        if roles_response.status_code != 200:
            return False, f"Nie udało się pobrać ról (HTTP {roles_response.status_code})."
        roles = roles_response.json()

        bot_response = discord_get("/users/@me", token)
        if bot_response.status_code != 200:
            return False, "Nie udało się pobrać danych bota."
        bot_id = bot_response.json().get("id")
        if not bot_id:
            return False, "Brak ID bota."

        member_response = discord_get(f"/guilds/{guild_id}/members/{bot_id}", token)
        if member_response.status_code != 200:
            return False, f"Nie udało się pobrać ról bota (HTTP {member_response.status_code})."

        bot_role_ids = set(member_response.json().get("roles", []))
        role_positions = {str(role.get("id")): int(role.get("position", 0)) for role in roles if role.get("id")}

        bot_positions = [pos for rid, pos in role_positions.items() if rid in bot_role_ids]
        if not bot_positions:
            return False, "Bot nie ma żadnej roli, więc nie może zarządzać pozycjami ról."

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
    print_header("Nadawanie uprawnień administratora")
    print()

    guild = pick_guild(token)
    if not guild:
        pause()
        return

    user_id = input(color("Podaj ID użytkownika Discord: ", Colors.CYAN)).strip()
    if not user_id.isdigit():
        print(color("Niepoprawne ID użytkownika.", Colors.RED))
        pause()
        return

    role_name = "Tool Admin"

    try:
        create_role = discord_post(
            f"/guilds/{guild.guild_id}/roles",
            token,
            {
                "name": role_name,
                "permissions": "8",
                "hoist": True,
                "mentionable": True,
                "reason": "Nadanie uprawnień administratora przez narzędzie CMD",
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

        moved, move_message = move_role_to_top(token, guild.guild_id, role_id)
        if moved:
            print(color(move_message, Colors.GREEN))
        else:
            print(color(move_message, Colors.YELLOW))

        assign_role = discord_put(f"/guilds/{guild.guild_id}/members/{user_id}/roles/{role_id}", token)
        if assign_role.status_code in (200, 204):
            print(color("Sukces! Użytkownik otrzymał rolę z pełnymi permisjami (Administrator).", Colors.GREEN))
        else:
            print(color(f"Nie udało się przypisać roli (HTTP {assign_role.status_code}).", Colors.RED))
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
        print_header("Panel tokenu")
        print()
        print(f"Token #{info.index}: {color(mask_token(info.token), Colors.BLUE)}")
        print(f"Bot: {color(info.bot_name, Colors.GREEN)} | ID: {color(info.bot_id, Colors.BLUE)}\n")
        print("[1] Back")
        print("[2] Copy Server Link (link do serwera)")
        print("[3] Copy Bot Invite Link (link do dodania bota)")
        print("[4] Permisje (admin dla użytkownika)")

        choice = input(color("\nWybierz opcję: ", Colors.CYAN)).strip()

        if choice == "1":
            return
        if choice == "2":
            link = build_server_invite_link(info.token)
            copy_link_with_feedback(link, "Link do serwera")
        elif choice == "3":
            link = build_bot_invite_link(info.token)
            copy_link_with_feedback(link, "Link do dodania bota")
        elif choice == "4":
            grant_admin_role(info.token)
        else:
            print(color("Niepoprawny wybór.", Colors.RED))
            pause()


def main() -> None:
    while True:
        clear_screen()
        print_header("Discord Bot Token Tool")
        print()

        tokens = read_tokens()
        if not tokens:
            print(color(f"Brak tokenów w pliku: {TOKENS_FILE}", Colors.RED))
            print(color("Dodaj minimum 1 token (1 linia = 1 token) i uruchom ponownie.", Colors.YELLOW))
            return

        token_infos = check_all_tokens(tokens)
        print(color("Dostępne tokeny:\n", Colors.BOLD + Colors.CYAN))

        for info in token_infos:
            status = color("DZIAŁA", Colors.GREEN) if info.valid else color(f"NIE DZIAŁA ({info.error})", Colors.RED)
            print(f"[{info.index}] {mask_token(info.token)}  ->  {status}")

        print("\n[0] Zakończ")
        choice = input(color("\nWybierz numer tokenu: ", Colors.CYAN)).strip()

        if choice == "0":
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

        token_menu(selected)


if __name__ == "__main__":
    main()
