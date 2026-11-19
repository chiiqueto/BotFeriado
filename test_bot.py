"""Testes do FeriadoBot (não usam a internet). Rodar com: python -m unittest -v"""
import unittest
from datetime import date
from unittest import mock

import bot

FERIADOS = [
    {"date": "2026-01-01", "name": "Confraternização mundial", "type": "national"},
    {"date": "2026-11-20", "name": "Consciência Negra", "type": "national"},
    {"date": "2026-12-25", "name": "Natal", "type": "national"},
]


def responder_em(texto, hoje):
    """Chama bot.responder fingindo que 'hoje' é a data informada e que a API devolve FERIADOS."""
    class DataFalsa(date):
        @classmethod
        def today(cls):
            return hoje

    resposta_api = mock.Mock()
    resposta_api.json.return_value = FERIADOS
    with mock.patch.object(bot, "date", DataFalsa), \
         mock.patch.object(bot.requests, "get", return_value=resposta_api):
        return bot.responder(texto)


class TestFeriadoBot(unittest.TestCase):
    def test_formatar(self):
        self.assertEqual(bot.formatar(FERIADOS[0]), "01/01/2026 - Confraternização mundial")

    def test_proximo_feriado(self):
        resp = responder_em("/proximo", date(2026, 11, 19))
        self.assertIn("Consciência Negra", resp)
        self.assertIn("20/11/2026", resp)

    def test_feriado_de_hoje_conta_como_proximo(self):
        resp = responder_em("/proximo", date(2026, 11, 20))
        self.assertIn("Consciência Negra", resp)

    def test_lista_do_ano(self):
        resp = responder_em("/feriados", date(2026, 11, 19))
        for nome in ("Confraternização mundial", "Consciência Negra", "Natal"):
            self.assertIn(nome, resp)

    def test_outro_texto_mostra_o_proximo(self):
        resp = responder_em("oi", date(2026, 11, 19))
        self.assertIn("Próximo feriado", resp)

    def test_depois_do_ultimo_feriado(self):
        resp = responder_em("/proximo", date(2026, 12, 26))
        self.assertIn("Não há mais feriados", resp)


if __name__ == "__main__":
    unittest.main()