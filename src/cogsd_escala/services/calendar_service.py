# src/cogsd_escala/services/calendar_service.py
"""Serviço de calendário"""

from datetime import date
from typing import List, Tuple


class CalendarService:
    """Gera datas do calendário"""

    PERIODOS_VALIDOS = {
        2026: (date(2026, 11, 1), date(2026, 12, 31)),
        2027: (date(2027, 1, 1), date(2027, 12, 31)),
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