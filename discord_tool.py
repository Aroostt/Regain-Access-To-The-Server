import json
import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

import requests

TOKENS_FILE = "tokens.txt"
API_BASE = "https://discord.com/api/v10"
TIMEOUT = 12


@dataclass
class TokenInfo:
    index: int
    token: str
    valid: bool
    bot_name: str = "-"
    bot_id: str = "-"
    error: str = ""


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause(msg: str = "Naciśnij ENTER, aby kontynuować...") -> None:
    input(f"\n{msg}")


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


def validate_token(index: int, token: str) -> TokenInfo:
    try:
        r = discord_get("/users/@me", token)
        if r.status_code == 200:
            data = r.json()
            username = f"{data.get('username', '?')}#{data.get('discriminator', '0')}"
            return TokenInfo(index=index, token=token, valid=True, bot_name=username, bot_id=data.get("id", "-"))
        return TokenInfo(index=index, token=token, valid=False, error=f"HTTP {r.status_code}")
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


def build_invite_link(token: str) -> Optional[str]:
    try:
        r = discord_get("/oauth2/applications/@me", token)
        if r.status_code != 200:
            return None
        app_id = r.json().get("id")
        if not app_id:
            return None
        return f"https://discord.com/oauth2/authorize?client_id={app_id}&permissions=8&scope=bot%20applications.commands"
    except requests.RequestException:
        return None


def pick_guild(token: str) -> Optional[str]:
    try:
        r = discord_get("/users/@me/guilds", token)
        if r.status_code != 200:
            print(f"Nie udało się pobrać serwerów bota (HTTP {r.status_code}).")
            return None

        guilds = r.json()
        if not guilds:
            print("Bot nie jest na żadnym serwerze.")
            return None

        while True:
            clear_screen()
            print("=== Wybór serwera ===\n")
            for i, g in enumerate(guilds, 1):
                print(f"[{i}] {g.get('name', 'Unknown')} (ID: {g.get('id')})")
            print("[0] Powrót")

            choice = input("\nWybierz numer serwera: ").strip()
            if choice == "0":
                return None
            if choice.isdigit() and 1 <= int(choice) <= len(guilds):
                return guilds[int(choice) - 1].get("id")
    except requests.RequestException as exc:
        print(f"Błąd połączenia: {exc}")
        return None


def grant_admin_role(token: str) -> None:
    clear_screen()
    print("=== Nadawanie uprawnień administratora ===\n")

    guild_id = pick_guild(token)
    if not guild_id:
        pause()
        return

    user_id = input("Podaj ID użytkownika Discord: ").strip()
    if not user_id.isdigit():
        print("Niepoprawne ID użytkownika.")
        pause()
        return

    role_name = "Tool Admin"

    try:
        create_role = discord_post(
            f"/guilds/{guild_id}/roles",
            token,
            {
                "name": role_name,
                "permissions": "8",
                "reason": "Nadanie uprawnień administratora przez narzędzie CMD",
            },
        )
        if create_role.status_code not in (200, 201):
            print(f"Nie udało się utworzyć roli (HTTP {create_role.status_code}).")
            print(create_role.text)
            pause()
            return

        role_id = create_role.json().get("id")
        if not role_id:
            print("Nie udało się odczytać ID nowej roli.")
            pause()
            return

        assign_role = discord_put(f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", token)
        if assign_role.status_code in (200, 204):
            print("Sukces! Użytkownik otrzymał rolę z uprawnieniami administratora.")
        else:
            print(f"Nie udało się przypisać roli (HTTP {assign_role.status_code}).")
            print(assign_role.text)
    except requests.RequestException as exc:
        print(f"Błąd połączenia: {exc}")

    pause()


def token_menu(info: TokenInfo) -> None:
    while True:
        clear_screen()
        print("=== Panel tokenu ===\n")
        print(f"Token #{info.index}: {mask_token(info.token)}")
        print(f"Bot: {info.bot_name} | ID: {info.bot_id}\n")
        print("[1] Back")
        print("[2] Copy Serwer Link")
        print("[3] Permisje (admin dla użytkownika)")

        choice = input("\nWybierz opcję: ").strip()

        if choice == "1":
            return
        if choice == "2":
            link = build_invite_link(info.token)
            if not link:
                print("Nie udało się wygenerować linku zaproszenia.")
            else:
                copied = copy_to_clipboard(link)
                if copied:
                    print("Link został skopiowany do schowka.")
                else:
                    print("Nie udało się skopiować do schowka. Link poniżej:")
                    print(link)
            pause()
        elif choice == "3":
            grant_admin_role(info.token)
        else:
            print("Niepoprawny wybór.")
            pause()


def main() -> None:
    while True:
        clear_screen()
        print("============================")
        print("  Discord Bot Token Tool")
        print("============================\n")

        tokens = read_tokens()
        if not tokens:
            print(f"Brak tokenów w pliku: {TOKENS_FILE}")
            print("Dodaj minimum 1 token (1 linia = 1 token) i uruchom ponownie.")
            return

        token_infos = check_all_tokens(tokens)

        print("Dostępne tokeny:\n")
        for info in token_infos:
            status = "DZIAŁA" if info.valid else f"NIE DZIAŁA ({info.error})"
            print(f"[{info.index}] {mask_token(info.token)}  ->  {status}")

        print("\n[0] Zakończ")
        choice = input("\nWybierz numer tokenu: ").strip()

        if choice == "0":
            return

        if not choice.isdigit():
            print("Wpisz poprawny numer.")
            pause()
            continue

        selected_idx = int(choice)
        selected = next((x for x in token_infos if x.index == selected_idx), None)
        if not selected:
            print("Nie ma tokenu o takim numerze.")
            pause()
            continue

        if not selected.valid:
            print("Ten token jest nieprawidłowy, wybierz działający token.")
            pause()
            continue

        token_menu(selected)


if __name__ == "__main__":
    main()
