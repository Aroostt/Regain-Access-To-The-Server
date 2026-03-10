# Regain-Access-To-The-Server

Wyśrodkowany tool CLI do CMD w stylu biało/szarym, który:

- czyta tokeny botów Discord z `tokens.txt`,
- sprawdza, które tokeny działają,
- pozwala wybrać token po numerze,
- pokazuje czytelne menu w ramce.

## Wymagania

- Python 3.10+
- `requests`

Instalacja:

```bash
pip install requests
```

## Uruchomienie

1. Wklej token(y) do `tokens.txt` (1 token na linię).
2. Uruchom:

```bash
python discord_tool.py
```

## Funkcje

Po wybraniu poprawnego tokenu:

1. **Back** – return to token list.
2. **Copy server invite link** – creates and copies a server invite from a selected guild.
3. **Copy bot invite link** – creates and copies bot OAuth invite link.
4. **Give New Admin Role** – creates an admin role, tries to move it as high as possible, assigns it to user ID.
5. **Give Best Existing Role** – assigns the highest existing role the bot can legally grant in hierarchy.

> Uwaga: bot musi mieć odpowiednie uprawnienia na serwerze (tworzenie zaproszeń, zarządzanie rolami, przypisywanie ról).
