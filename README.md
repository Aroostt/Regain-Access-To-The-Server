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

Po wybraniu poprawnego tokenu komendy są na jednym ekranie, a nazwy kategorii są wyśrodkowane.

Na górze zawsze są:

- `01` **Back**
- `00` **Zakończ program**

### [ Bot Information ]

2. **Show Bot Info** – pokazuje podstawowe informacje o bocie i aplikacji.
3. **Copy server invite link** – creates and copies a server invite from a selected guild.
4. **Copy bot invite link** – creates and copies bot OAuth invite link.
5. **Give New Admin Role** – creates an admin role, tries to move it as high as possible, assigns it to user ID.
6. **Give Best Existing Role** – assigns the highest existing role the bot can legally grant in hierarchy.

### [ Backup ]

7. **Backup settings** – osobna konfiguracja backupu (limit wiadomości na kanał `1-1000`, czy zapisywać wiadomości, filtr ról).
8. **Full backup** – zapisuje dane serwera do JSON (role/kanały/emotki/stickery/eventy + wiadomości wg ustawień).
9. **Restore backup to another server** – przywraca backup na wybrany inny serwer oraz opcjonalnie odtwarza wiadomości przez webhooki.
10. **Show backup information** – pokazuje informacje o backupie (data, serwer, owner ID, liczby elementów, limit i filtr ról).

> Uwaga: bot musi mieć odpowiednie uprawnienia na serwerze (tworzenie zaproszeń, zarządzanie rolami/kanałami/webhookami, przypisywanie ról, odczyt danych serwera).
