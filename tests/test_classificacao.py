# -*- coding: utf-8 -*-
"""Testes da classificação por departamento (casamento por palavras)."""

from backend.database import melhor_departamento

DEPS = [
    {"id": 1, "palavras_chave": "creatina,whey,whey protein,amendoim,pasta de amendoim,dr peanut"},
    {"id": 4, "palavras_chave": "notebook,fone,fone bluetooth,buds,airpods,tv,qled,headphone"},
    {"id": 6, "palavras_chave": "playstation,headset gamer,gamer,controle"},
]


def test_keyword_frase_casa_palavras_separadas():
    # "fone bluetooth" casa em "Fone De Ouvido Sem Fio Bluetooth"
    assert melhor_departamento("Fone De Ouvido Sem Fio Bluetooth F9", DEPS) == 4


def test_whey_isolate_split():
    assert melhor_departamento("Whey Isolate Protein Fuse 900g", DEPS) == 1


def test_tv_token_exato():
    assert melhor_departamento("Samsung Vision AI TV 55 QLED", DEPS) == 4


def test_pasta_amendoim_vai_fitness():
    assert melhor_departamento("Pasta de Amendoim Dr Peanut 600g", DEPS) == 1


def test_headset_gamer_ganha_de_token_curto():
    # "headset gamer" (len 13) + "gamer" supera matches curtos
    assert melhor_departamento("Headset Gamer Fallen Pro Wireless", DEPS) == 6


def test_token_unico_nao_casa_substring():
    # "tv" não deve casar dentro de "netvibes"
    assert melhor_departamento("Caixa Netvibes Organizadora", DEPS) is None


def test_sem_match_retorna_none():
    assert melhor_departamento("Produto Aleatorio XYZ", DEPS) is None


def test_titulo_vazio_retorna_none():
    assert melhor_departamento("", DEPS) is None
