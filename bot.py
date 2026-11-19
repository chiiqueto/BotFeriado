import os
import time
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv(".env")
BASE = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_TOKEN')}"


def formatar(f):
    return f"{date.fromisoformat(f['date']):%d/%m/%Y} - {f['name']}"


def responder(texto):
    hoje = date.today()
    lista = requests.get(f"https://brasilapi.com.br/api/feriados/v1/{hoje.year}", timeout=10).json()
    if texto.startswith("/feriados"):
        return "\n".join(formatar(f) for f in lista)
    for f in lista:  # /proximo (ou qualquer outro texto)
        if date.fromisoformat(f["date"]) >= hoje:
            return "Próximo feriado:\n" + formatar(f)
    return "Não há mais feriados este ano."


def main():
    offset = None
    while True:
        try:
            res = requests.get(f"{BASE}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40).json()
            for u in res["result"]:
                offset = u["update_id"] + 1
                msg = u.get("message", {})
                if "text" in msg:
                    requests.post(f"{BASE}/sendMessage",
                                  data={"chat_id": msg["chat"]["id"], "text": responder(msg["text"])})
        except Exception as erro:
            print("Erro:", type(erro).__name__)
            time.sleep(5)


if __name__ == "__main__":
    main()
