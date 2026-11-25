import unittest
from datetime import date
from unittest import mock

import requests

import bot

FERIADOS = [
    {"date": "2026-01-01", "name": "Confraternização mundial", "type": "national"},
    {"date": "2026-11-20", "name": "Consciência Negra", "type": "national"},
    {"date": "2026-12-25", "name": "Natal", "type": "national"},
]
FERIADOS_2027 = [{"date": "2027-01-01", "name": "Confraternização mundial", "type": "national"}]
ANOS = {2026: FERIADOS, 2027: FERIADOS_2027}


def responder_em(texto, hoje, anos=ANOS):
    """Chama bot.responder com API falsa. Devolve só o texto da resposta."""
    with mock.patch.object(bot, "buscar_feriados", side_effect=lambda ano: anos.get(ano, [])):
        return bot.responder(texto, hoje=hoje)[0]


class TestFormatacao(unittest.TestCase):
    def test_formatar(self):
        self.assertEqual(bot.formatar(FERIADOS[0]), "01/01/2026 - Confraternização mundial")

    def test_sem_acento(self):
        self.assertEqual(bot.sem_acento("Março"), "marco")

    def test_interpretar_mes(self):
        self.assertEqual(bot.interpretar_mes("11"), 11)
        self.assertEqual(bot.interpretar_mes("Novembro"), 11)
        self.assertEqual(bot.interpretar_mes("mar"), 3)
        self.assertIsNone(bot.interpretar_mes("13"))
        self.assertIsNone(bot.interpretar_mes("abc"))

    def test_contagem(self):
        hoje = date(2026, 11, 20)
        self.assertIn("hoje", bot.contagem(date(2026, 11, 20), hoje))
        self.assertIn("amanhã", bot.contagem(date(2026, 11, 21), hoje))
        self.assertIn("Faltam 5 dias", bot.contagem(date(2026, 11, 25), hoje))


class TestComandos(unittest.TestCase):
    def test_proximo_feriado(self):
        resp = responder_em("/proximo", date(2026, 11, 19))
        self.assertIn("Consciência Negra", resp)
        self.assertIn("20/11/2026", resp)
        self.assertIn("sexta-feira", resp)
        self.assertIn("amanhã", resp)

    def test_feriado_de_hoje_conta_como_proximo(self):
        resp = responder_em("/proximo", date(2026, 11, 20))
        self.assertIn("Consciência Negra", resp)
        self.assertIn("É hoje", resp)

    def test_depois_do_ultimo_feriado_olha_o_ano_seguinte(self):
        resp = responder_em("/proximo", date(2026, 12, 26))
        self.assertIn("01/01/2027", resp)

    def test_sem_mais_feriados(self):
        resp = responder_em("/proximo", date(2026, 12, 26), anos={2026: FERIADOS})
        self.assertIn("Não há mais feriados", resp)

    def test_lista_do_ano(self):
        resp = responder_em("/feriados", date(2026, 11, 19))
        for nome in ("Confraternização mundial", "Consciência Negra", "Natal"):
            self.assertIn(nome, resp)

    def test_lista_marca_passados_e_futuros(self):
        resp = responder_em("/feriados", date(2026, 11, 19))
        self.assertIn("✅ 01/01/2026", resp)
        self.assertIn("📌 20/11/2026", resp)

    def test_ano(self):
        resp = responder_em("/ano 2027", date(2026, 11, 19))
        self.assertIn("01/01/2027", resp)

    def test_ano_invalido(self):
        self.assertIn("entre 1900 e 2199", responder_em("/ano abc", date(2026, 11, 19)))
        self.assertIn("entre 1900 e 2199", responder_em("/ano 3000", date(2026, 11, 19)))

    def test_mes_por_numero_e_por_nome(self):
        for arg in ("12", "dezembro", "dez"):
            resp = responder_em(f"/mes {arg}", date(2026, 11, 19))
            self.assertIn("Natal", resp)
            self.assertNotIn("Consciência Negra", resp)

    def test_mes_sem_feriado(self):
        self.assertIn("Nenhum feriado", responder_em("/mes março", date(2026, 11, 19)))

    def test_mes_sem_argumento_mostra_botoes_dos_meses(self):
        with mock.patch.object(bot, "buscar_feriados", return_value=FERIADOS):
            texto, botoes = bot.responder("/mes", hoje=date(2026, 11, 19))
        self.assertEqual(botoes, bot.TECLADO_MESES)
        self.assertEqual(sum(len(l) for l in botoes["inline_keyboard"]), 12)

    def test_buscar_ignora_acento_e_maiuscula(self):
        resp = responder_em("/buscar CONSCIENCIA", date(2026, 11, 19))
        self.assertIn("Consciência Negra", resp)
        self.assertNotIn("Natal", resp)

    def test_buscar_sem_resultado(self):
        self.assertIn("Não encontrei", responder_em("/buscar carnaval", date(2026, 11, 19)))

    def test_comando_com_nome_do_bot(self):
        # Em grupos o Telegram envia "/proximo@NomeDoBot"
        self.assertIn("Consciência Negra", responder_em("/proximo@FeriadoBot", date(2026, 11, 19)))

    def test_start_cumprimenta_pelo_nome(self):
        texto, botoes = bot.responder("/start", hoje=date(2026, 11, 19), nome="Camilli")
        self.assertIn("Olá, Camilli", texto)
        self.assertEqual(botoes, bot.MENU)

    def test_texto_desconhecido(self):
        self.assertIn("Não entendi", responder_em("oi", date(2026, 11, 19)))

    def test_todo_botao_do_menu_e_um_comando_valido(self):
        # Garante que nenhum botão leva a "Não entendi".
        for linha in bot.MENU["inline_keyboard"]:
            for botao in linha:
                resp = responder_em(botao["callback_data"], date(2026, 11, 19))
                self.assertNotIn("Não entendi", resp)


class TestErros(unittest.TestCase):
    def test_api_fora_do_ar(self):
        with mock.patch.object(bot, "buscar_feriados", side_effect=requests.ConnectionError):
            texto, _ = bot.responder("/feriados", hoje=date(2026, 11, 19))
        self.assertIn("Não consegui consultar", texto)

    def test_cache_evita_segunda_chamada(self):
        bot._cache.clear()
        resposta = mock.Mock()
        resposta.json.return_value = FERIADOS
        with mock.patch.object(bot.requests, "get", return_value=resposta) as get:
            bot.buscar_feriados(2026)
            bot.buscar_feriados(2026)
        self.assertEqual(get.call_count, 1)
        bot._cache.clear()


if __name__ == "__main__":
    unittest.main()
