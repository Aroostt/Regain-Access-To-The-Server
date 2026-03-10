# Regain-Access-To-The-Server

Prosty tool do uruchamiania w `cmd`, który:

- czyta tokeny botów Discord z pliku `tokens.txt`,
- pokazuje, które tokeny działają,
- pozwala wybrać token po numerze,
- daje menu akcji dla wybranego tokenu.

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
2. **Copy Serwer Link** – tworzy link zaproszenia bota z uprawnieniami admina i kopiuje do schowka.
3. **Permisje** – tworzy rolę administracyjną i przypisuje ją użytkownikowi po podaniu jego ID.

> Uwaga: bot musi mieć odpowiednie uprawnienia na serwerze, żeby tworzyć role i przypisywać je użytkownikom.
