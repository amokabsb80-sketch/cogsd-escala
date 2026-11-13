# src/cogsd_escala/services/calendar_service.py
"""Serviço de calendário"""

from datetime import date
from typing import List, Tuple


class CalendarService:
    """Gera datas do calendário"""

    PERIODOS_VALIDOS = {
        2026: (date(2026, 1, 1), date(2026, 12, 31)),
        2027: (date(2027, 1, 1), date(2027, 12, 31)),
        2028: (date(2028, 1, 1), date(2028, 12, 31)),
        2029: (date(2029, 1, 1), date(2029, 12, 31)),
        2030: (date(2030, 1, 1), date(2030, 12, 31)),
    }

    DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira",
                   "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    DIAS_SEMANA_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    NOMES_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                   "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

    @classmethod
    def get_anos_disponiveis(cls) -> List[int]:
        return sorted(cls.PERIODOS_VALIDOS.keys())

    @classmethod
    def get_periodo(cls, ano: int) -> Tuple[date, date]:
        return cls.PERIODOS_VALIDOS.get(ano, (None, None))

    @classmethod
    def get_meses(cls, ano: int) -> List[Tuple[int, str]]:
        inicio, fim = cls.get_periodo(ano)
        if inicio is None:
            return []
        return [(m, cls.NOMES_MESES[m - 1])
                for m in range(inicio.month, fim.month + 1)]

    @classmethod
    def get_estrutura_mes(cls, ano: int, mes: int) -> List[dict]:
        """Retorna estrutura do mês com dia da semana"""
        from calendar import monthrange
        ultimo_dia = monthrange(ano, mes)[1]

        estrutura = []
        for dia in range(1, ultimo_dia + 1):
            d = date(ano, mes, dia)
            estrutura.append({
                'data': d,
                'dia': d.day,
                'mes': d.month,
                'ano': d.year,
                'dia_semana': cls.DIAS_SEMANA[d.weekday()],
                'dia_semana_curto': cls.DIAS_SEMANA_CURTOS[d.weekday()],
                'is_fim_semana': d.weekday() >= 5,
                'data_formatada': f"{cls.DIAS_SEMANA[d.weekday()]}, {d.day} de {cls.NOMES_MESES[d.month - 1]} de {d.year}",
            })
        return estrutura

    @classmethod
    def extrair_datas_do_texto(cls, texto: str, ano: int) -> list:
        """
        Tenta extrair datas de um texto (ex: PDF do ato normativo)
        Retorna lista de (data_str, tipo, descricao)

        ⚠️ Funciona melhor se o texto tiver padrões como:
        "1º de janeiro", "16 de fevereiro", etc.
        """
        import re

        meses = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
            "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
            "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
        }

        resultados = []
        # Padrão: "1º de janeiro", "16 de fevereiro", etc.
        padrao = r'(\d{1,2})[ºo]?\s+de\s+(\w+)(?:.*?)(feriado|ponto facultativo)'

        for match in re.finditer(padrao, texto, re.IGNORECASE | re.DOTALL):
            dia = int(match.group(1))
            mes_nome = match.group(2).lower()
            tipo = match.group(3).lower()

            if mes_nome in meses:
                mes = meses[mes_nome]
                try:
                    data = date(ano, mes, dia)
                    tipo_fmt = "Feriado" if "feriado" in tipo else "Ponto Facultativo"
                    resultados.append((data.isoformat(), tipo_fmt, ""))
                except ValueError:
                    pass

        return resultados