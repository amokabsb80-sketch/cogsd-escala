# src/cogsd_escala/core/models.py
"""Modelos de dados do COGSD"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Trabalhador:
    """Representa um trabalhador do COGSD"""
    id: str
    nome: str
    email: str
    cargo: Optional[str] = None
    setor: Optional[str] = None
    is_chefia: bool = False
    turno_preferencia: Optional[str] = None  # Manhã, Tarde, Diurno
    regime_trabalho: str = "presencial"       # presencial, hibrido, remoto
    excecao_art12: bool = False               # True = não conta no limite 50%
    ativo: bool = True
    cor: str = "#3498db"

@dataclass
class Usuario:
    """Representa um usuário do sistema (login)"""
    id: str
    email: str
    senha_hash: str
    senha_temporaria: bool = True
    role: str = "viewer"                      # admin, editor, viewer
    trabalhador_id: Optional[str] = None
    ativo: bool = True
    ultimo_acesso: Optional[datetime] = None


@dataclass
class Escala:
    """Representa um dia de escala de um trabalhador"""
    id: str
    data: date
    trabalhador_id: str
    turno: Optional[str] = None               # Manhã, Tarde, ou None (Diurno)
    regime: str = "presencial"                # presencial, hibrido, remoto
    observacoes: str = ""


@dataclass
class Ocorrencia:
    """Representa uma ocorrência de um trabalhador"""
    id: str
    trabalhador_id: str
    data: date
    tipo: str                                 # Falta, Licença Médica, etc.
    descricao: str = ""
    created_by: Optional[str] = None


@dataclass
class DiaEspecial:
    """Representa um feriado ou ponto facultativo"""
    id: str
    data: date
    tipo: str                                 # Feriado, Ponto Facultativo
    descricao: str = ""


@dataclass
class LogAuditoria:
    """Representa um registro de auditoria"""
    id: str
    usuario_email: str
    acao: str                                 # INSERT, UPDATE, DELETE, LOGIN
    entidade: str                             # trabalhadores, escalas, etc.
    entidade_id: Optional[str] = None
    dados_anteriores: Optional[dict] = None
    dados_novos: Optional[dict] = None
    timestamp: Optional[datetime] = None