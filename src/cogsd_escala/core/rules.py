# src/cogsd_escala/core/rules.py
"""Regras de negócio do COGSD"""

from datetime import date, timedelta
from typing import List, Tuple
import math


class RegrasFrequencia:
    """Regras de frequência semanal"""

    # Frequência padrão
    MIN_DIAS_NORMAL = 2
    MIN_DIAS_CHEFIA = 3

    # Frequência especial (2+ dias especiais na semana)
    MIN_DIAS_NORMAL_ESPECIAL = 1
    MIN_DIAS_CHEFIA_ESPECIAL = 2

    @classmethod
    def min_dias_semana(cls, is_chefia: bool,
                        dias_especiais_semana: int) -> int:
        """
        Calcula mínimo de dias na semana

        Args:
            is_chefia: True se tem cargo de chefia
            dias_especiais_semana: qtd de feriados + pontos facultativos
        """
        if dias_especiais_semana >= 2:
            return cls.MIN_DIAS_CHEFIA_ESPECIAL if is_chefia else cls.MIN_DIAS_NORMAL_ESPECIAL
        return cls.MIN_DIAS_CHEFIA if is_chefia else cls.MIN_DIAS_NORMAL

    @classmethod
    def get_semana(cls, data_alvo: date) -> Tuple[date, date]:
        """Retorna (início, fim) da semana de uma data"""
        inicio = data_alvo - timedelta(days=data_alvo.weekday())
        fim = inicio + timedelta(days=6)
        return inicio, fim


class RegraArt12:
    """Regra de limite de 50% em trabalho remoto/híbrido (Art. 12)"""

    PERCENTUAL_MAXIMO = 0.50

    @classmethod
    def max_remotos_por_dia(cls, lotacao_efetiva: int) -> int:
        """Calcula o máximo de servidores remotos por dia (arredonda para cima)"""
        return math.ceil(lotacao_efetiva * cls.PERCENTUAL_MAXIMO)

    @classmethod
    def verificar_limite(cls, remotos_no_dia: int,
                         lotacao_efetiva: int,
                         excecoes: int = 0) -> Tuple[bool, str]:
        """
        Verifica se o limite foi respeitado

        Returns:
            (ok, mensagem)
        """
        remotos_validos = remotos_no_dia - excecoes
        maximo = cls.max_remotos_por_dia(lotacao_efetiva)

        if remotos_validos > maximo:
            return False, f"Limite excedido: {remotos_validos} remotos (máx: {maximo})"
        return True, f"Dentro do limite: {remotos_validos}/{maximo}"