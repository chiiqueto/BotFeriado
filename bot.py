import html
import json
import os
import time
import unicodedata
from datetime import date

import requests
from dotenv import load_dotenv

# Lê o arquivo .env para que o token do bot NÃO fique escrito no código.
load_dotenv(".env")
TOKEN = os.getenv("TELEGRAM_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"
API_FERIADOS = "https://brasilapi.com.br/api/feriados/v1/{ano}"

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

# Comandos que aparecem no menu "/" do Telegram (registrados em `main`).
COMANDOS = [
    ("proximo", "Mostra o próximo feriado"),
    ("feriados", "Lista os feriados do ano"),
    ("mes", "Feriados de um mês (ex: /mes 11)"),
    ("ano", "Feriados de outro ano (ex: /ano 2027)"),
    ("buscar", "Procura um feriado pelo nome"),
    ("ajuda", "Mostra a ajuda"),
]

# ---------------------------------------------------------------------------
# Botões (inline keyboard)
# ---------------------------------------------------------------------------
# Truque do projeto: o `callback_data` de cada botão é o PRÓPRIO comando
# ("/proximo", "/mes 11"...). Assim, clicar no botão e digitar o comando
# passam exatamente pelo mesmo código (`responder`).

def teclado(*linhas):
    """Monta o JSON de botões que o Telegram espera. Cada linha = lista de (texto, comando)."""
    return {"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in linha]
                                for linha in linhas]}


MENU = teclado(
    [("📅 Próximo feriado", "/proximo"), ("📋 Lista do ano", "/feriados")],
    [("🗓️ Por mês", "/mes"), ("❓ Ajuda", "/ajuda")],
)

# 12 botões de meses, organizados em 4 linhas de 3.
TECLADO_MESES = teclado(*[
    [(MESES[i].capitalize(), f"/mes {i + 1}") for i in range(linha, linha + 3)]
    for linha in range(0, 12, 3)
])

TEXTO_AJUDA = (
    "<b>🎌 FeriadoBot</b>\n"
    "Eu mostro os feriados nacionais do Brasil.\n\n"
    "/proximo - próximo feriado (com contagem regressiva)\n"
    "/feriados - todos os feriados do ano\n"
    "/mes 11 ou /mes novembro - feriados de um mês\n"
    "/ano 2027 - feriados de outro ano\n"
    "/buscar natal - procura pelo nome\n\n"
    "Ou use os botões abaixo 👇"
)

# ---------------------------------------------------------------------------
# Acesso à API (com cache)
# ---------------------------------------------------------------------------
_cache = {}  # {ano: lista de feriados}. Feriados de um ano não mudam, então basta pedir 1 vez.


def buscar_feriados(ano):
    """Pede à BrasilAPI os feriados do ano. Guarda em cache para o bot responder rápido."""
    if ano not in _cache:
        resp = requests.get(API_FERIADOS.format(ano=ano), timeout=10)
        resp.raise_for_status()  # se a API devolver erro (404, 500...), levanta exceção
        _cache[ano] = resp.json()
    return _cache[ano]


# ---------------------------------------------------------------------------
# Funções de formatação (texto puro, fáceis de testar)
# ---------------------------------------------------------------------------

def sem_acento(texto):
    """'Março' -> 'marco'. Permite buscar sem se preocupar com acentos e maiúsculas."""
    base = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def formatar(f):
    """Uma linha: '25/12/2026 - Natal'. html.escape evita quebrar o parse_mode HTML do Telegram."""
    return f"{date.fromisoformat(f['date']):%d/%m/%Y} - {html.escape(f['name'])}"


def contagem(data, hoje):
    """Texto da contagem regressiva até o feriado."""
    dias = (data - hoje).days
    if dias == 0:
        return "🎉 É hoje!"
    if dias == 1:
        return "⏳ É amanhã!"
    return f"⏳ Faltam {dias} dias"


def formatar_lista(feriados, hoje, titulo):
    """Lista de feriados; ✅ para os que já passaram e 📌 para os que ainda vão acontecer."""
    linhas = [f"<b>{titulo}</b>"]
    for f in feriados:
        marca = "✅" if date.fromisoformat(f["date"]) < hoje else "📌"
        linhas.append(f"{marca} {formatar(f)}")
    return "\n".join(linhas)


def interpretar_mes(arg):
    """Aceita '11', 'novembro' ou 'nov'. Devolve o número do mês (1-12) ou None se inválido."""
    arg = sem_acento(arg.strip())
    if arg.isdigit():
        return int(arg) if 1 <= int(arg) <= 12 else None
    if len(arg) >= 3:
        for i, nome in enumerate(MESES, start=1):
            if sem_acento(nome).startswith(arg):
                return i
    return None


# ---------------------------------------------------------------------------
# Cérebro do bot: recebe um texto, devolve (resposta, botões)
# ---------------------------------------------------------------------------

def proximo_feriado(hoje):
    """Procura o próximo feriado. Se o ano acabou, olha o início do ano seguinte."""
    for ano in (hoje.year, hoje.year + 1):
        for f in buscar_feriados(ano):
            if date.fromisoformat(f["date"]) >= hoje:  # '>=' faz o feriado de hoje contar
                return f
    return None


def responder(texto, hoje=None, nome=""):
    """Interpreta o comando e devolve (texto_da_resposta, teclado).

    `hoje` pode ser informado para facilitar os testes (data fixa).
    """
    hoje = hoje or date.today()

    # Separa o comando do argumento: "/mes novembro" -> "/mes" + "novembro".
    # O split("@") trata "/proximo@FeriadoBot", como chega em grupos.
    partes = texto.strip().split(maxsplit=1)
    comando = partes[0].lower().split("@")[0] if partes else ""
    arg = partes[1].strip() if len(partes) > 1 else ""

    try:
        if comando in ("/start", "/ajuda", "/help"):
            saudacao = f"Olá, {html.escape(nome)}! 👋\n\n" if nome and comando == "/start" else ""
            return saudacao + TEXTO_AJUDA, MENU

        if comando == "/proximo":
            f = proximo_feriado(hoje)
            if f is None:
                return "Não há mais feriados este ano.", MENU
            data = date.fromisoformat(f["date"])
            return (f"<b>Próximo feriado:</b>\n{formatar(f)} ({DIAS_SEMANA[data.weekday()]})\n"
                    f"{contagem(data, hoje)}"), MENU

        if comando == "/feriados":
            return formatar_lista(buscar_feriados(hoje.year), hoje, f"Feriados de {hoje.year}"), MENU

        if comando == "/ano":
            if not (arg.isdigit() and 1900 <= int(arg) <= 2199):  # limite da BrasilAPI
                return "Informe um ano entre 1900 e 2199. Exemplo: /ano 2027", MENU
            ano = int(arg)
            return formatar_lista(buscar_feriados(ano), hoje, f"Feriados de {ano}"), MENU

        if comando == "/mes":
            if not arg:  # sem argumento: mostra os botões dos 12 meses
                return "Escolha o mês:", TECLADO_MESES
            mes = interpretar_mes(arg)
            if mes is None:
                return "Mês inválido. Exemplos: /mes 11 ou /mes novembro", TECLADO_MESES
            do_mes = [f for f in buscar_feriados(hoje.year)
                      if date.fromisoformat(f["date"]).month == mes]
            if not do_mes:
                return f"Nenhum feriado nacional em {MESES[mes - 1]}.", TECLADO_MESES
            return formatar_lista(do_mes, hoje, f"Feriados de {MESES[mes - 1]}"), TECLADO_MESES

        if comando == "/buscar":
            if not arg:
                return "Digite o que procurar. Exemplo: /buscar natal", MENU
            achados = [f for f in buscar_feriados(hoje.year)
                       if sem_acento(arg) in sem_acento(f["name"])]
            if not achados:
                return f"Não encontrei nenhum feriado com “{html.escape(arg)}”.", MENU
            return formatar_lista(achados, hoje, "Resultado da busca"), MENU

        # Qualquer outro texto: responde de forma amigável em vez de ficar em silêncio.
        return "Não entendi 🤔 Use um dos botões ou digite /ajuda.", MENU

    except requests.RequestException:
        # Tratamento de erro: se a BrasilAPI cair, o bot avisa em vez de travar.
        return "⚠️ Não consegui consultar a BrasilAPI agora. Tente de novo em instantes.", MENU


# ---------------------------------------------------------------------------
# Comunicação com o Telegram
# ---------------------------------------------------------------------------

def enviar(chat_id, texto, botoes=None):
    """Envia uma mensagem; os botões vão no campo reply_markup (como JSON)."""
    dados = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    if botoes:
        dados["reply_markup"] = json.dumps(botoes)
    requests.post(f"{BASE}/sendMessage", data=dados, timeout=10)


def tratar_update(u):
    """Trata uma novidade do Telegram: pode ser mensagem digitada OU clique em botão."""
    if "callback_query" in u:  # o usuário clicou em um botão
        cb = u["callback_query"]
        # Avisa ao Telegram que o clique foi recebido (senão o botão fica "carregando").
        requests.post(f"{BASE}/answerCallbackQuery", data={"callback_query_id": cb["id"]}, timeout=10)
        chat_id = cb["message"]["chat"]["id"]
        texto, botoes = responder(cb["data"], nome=cb["from"].get("first_name", ""))
        enviar(chat_id, texto, botoes)
        return

    msg = u.get("message", {})
    if "text" in msg:  # ignora figurinhas, fotos etc.
        texto, botoes = responder(msg["text"], nome=msg.get("from", {}).get("first_name", ""))
        enviar(msg["chat"]["id"], texto, botoes)


def main():
    if not TOKEN:
        raise SystemExit("Defina TELEGRAM_TOKEN no arquivo .env")

    # Registra a lista de comandos no menu "/" do Telegram.
    requests.post(f"{BASE}/setMyCommands", timeout=10, data={"commands": json.dumps(
        [{"command": c, "description": d} for c, d in COMANDOS])})

    print("FeriadoBot rodando... (Ctrl+C para parar)")
    offset = None  # id da próxima atualização; evita receber a mesma mensagem duas vezes
    while True:
        try:
            # Long polling: o Telegram segura a requisição até 30s esperando mensagens novas.
            res = requests.get(f"{BASE}/getUpdates",
                               params={"offset": offset, "timeout": 30}, timeout=40).json()
            for u in res["result"]:
                offset = u["update_id"] + 1  # marca como lida ANTES de tratar
                try:
                    tratar_update(u)
                except Exception as erro:  # um erro em uma conversa não derruba o bot
                    print("Erro ao tratar mensagem:", type(erro).__name__)
        except Exception as erro:
            print("Erro:", type(erro).__name__)
            time.sleep(5)  # espera um pouco antes de tentar de novo


if __name__ == "__main__":
    main()
