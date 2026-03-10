# Regain-Access-To-The-Server

Prosty, kolorowy tool do uruchamiania w `cmd`, który:

- czyta tokeny botów Discord z pliku `tokens.txt`,
- pokazuje, które tokeny działają,
- pozwala wybrać token po numerze,
- daje menu akcji dla wybranego tokenu w stylu ASCII box.

## Wymagania

- Python 3.10+
- biblioteka `requests`

Instalacja:

```bash
pip install requests
```

## Uruchomienie

1. Wklej token(y) do `tokens.txt` (1 token na linię).
2. Odpal:

```bash
python discord_tool.py
```

## Funkcje

Po wybraniu poprawnego tokenu:

1. **Back** – powrót do listy tokenów.
2. **Copy Server Link** – tworzy i kopiuje link zaproszenia do serwera, na którym jest bot (najpierw wybierasz serwer).
3. **Copy Bot Invite Link** – tworzy i kopiuje link do dodania bota na serwer.
4. **Permisje** – tworzy rolę administracyjną (pełne permisje), próbuje przesunąć ją na najwyższą możliwą pozycję i przypisuje ją użytkownikowi po podaniu jego ID.
5. **Daj najlepszą istniejącą rangę** – nadaje najwyższą istniejącą rangę, którą bot realnie może nadać (zgodnie z hierarchią Discord).

> Uwaga: bot musi mieć odpowiednie uprawnienia na serwerze, żeby tworzyć zaproszenia, role i przypisywać role użytkownikom.
