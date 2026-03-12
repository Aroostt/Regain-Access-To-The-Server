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
11. **Token Health Check** – sprawdza kluczowe endpointy i możliwości tokena bota.

### [ Backup ]

7. **Backup settings** – osobna konfiguracja backupu:
   - limit wiadomości na kanał `1-1000`,
   - czy zapisywać wiadomości,
   - filtr ról,
   - zakres backupu (domyślnie wszystko włączone; wpisujesz numery do wyłączenia),
   - zakres czyszczenia serwera (domyślnie wszystko włączone; wpisujesz numery do wyłączenia).
8. **Full backup** – zapisuje dane serwera do JSON (role/kanały/emotki/stickery/eventy + wiadomości wg ustawień), zachowując kolejność kanałów/kategorii i metadane.
9. **Restore backup to another server** – ma dry-run (podgląd planu), opcjonalny szczegółowy podgląd, opcjonalne czyszczenie aktualnego serwera oraz odtwarzanie z backupu.
10. **Show backup information** – pokazuje informacje o backupie (data, serwer, owner ID, liczby elementów, limit, filtr ról, zakres).
12. **Server Cleanup** – osobna funkcja czyszczenia serwera zgodnie z ustawionym zakresem czyszczenia i trybem szybkim.

## Dodatkowo

- Tool tworzy logi działania w katalogu `logs/` (backup/restore/cleanup), co pomaga diagnozować błędy API.
- Ustawienia backupu zapisują się do `backup_settings.json` i są ładowane przy kolejnym uruchomieniu.
- Przy odtwarzaniu wiadomości webhook używa nazwy w formacie `GłównyNick | Pseudonim`.

> Uwaga: bot musi mieć odpowiednie uprawnienia na serwerze (tworzenie zaproszeń, zarządzanie rolami/kanałami/webhookami, przypisywanie ról, odczyt danych serwera).
