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

## Menu funkcji

Po wybraniu poprawnego tokenu komendy są na jednym ekranie, a nazwy kategorii są wyśrodkowane:

- `[ Bot Information ]`
- `[ Backup ]`

Na górze zawsze są:

- `01` **Back**
- `00` **Zakończ program**

### Bot Information

2. **Copy server invite link** – creates and copies a server invite from a selected guild.
3. **Copy bot invite link** – creates and copies bot OAuth invite link.
4. **Give New Admin Role** – creates an admin role, tries to move it as high as possible, assigns it to user ID.
5. **Give Best Existing Role** – assigns the highest existing role the bot can legally grant in hierarchy.

### Backup

6. **Full backup** – zapisuje pełne dane serwera do JSON (dane serwera, role, kanały, emotki, stickery, eventy), opcjonalnie zapis wiadomości (max 100 na kanał).
7. **Restore backup to another server** – przywraca backup na wybrany inny serwer oraz opcjonalnie odtwarza wiadomości przez webhooki.
8. **Show backup information** – pokazuje informacje o backupie (data, serwer, owner ID, liczba ról/kanałów/emotek/wiadomości).

> Uwaga: bot musi mieć odpowiednie uprawnienia na serwerze (tworzenie zaproszeń, zarządzanie rolami/kanałami/webhookami, przypisywanie ról, odczyt danych serwera).
