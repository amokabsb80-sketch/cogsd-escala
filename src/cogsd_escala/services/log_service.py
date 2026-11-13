# src/cogsd_escala/services/log_service.py
"""Serviço de auditoria"""

from datetime import datetime
from typing import Optional
import streamlit as st


class LogService:
    """Registra ações no log de auditoria"""

    def __init__(self, repo):
        self.repo = repo

    def _get_usuario_email(self) -> str:
        usuario = st.session_state.get("usuario", {})
        return usuario.get("email", "sistema")

    def registrar(self, acao: str, entidade: str, entidade_id: Optional[str] = None,
                  dados_anteriores: Optional[dict] = None,
                  dados_novos: Optional[dict] = None):
        """
        Registra uma ação no log

        Args:
            acao: INSERT, UPDATE, DELETE, LOGIN, LOGOUT
            entidade: trabalhadores, usuarios, escalas, ocorrencias, dias_especiais
            entidade_id: ID do registro afetado
            dados_anteriores: dados antes da alteração (UPDATE/DELETE)
            dados_novos: dados depois da alteração (INSERT/UPDATE)
        """
        try:
            self.repo.adicionar_log({
                "usuario_email": self._get_usuario_email(),
                "acao": acao,
                "entidade": entidade,
                "entidade_id": entidade_id,
                "dados_anteriores": dados_anteriores,
                "dados_novos": dados_novos,
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            # Não deixa o log quebrar a aplicação
            print(f"⚠️ Erro ao registrar log: {e}")

    # Atalhos
    def log_insert(self, entidade: str, entidade_id: str, dados: dict):
        self.registrar("INSERT", entidade, entidade_id, None, dados)

    def log_update(self, entidade: str, entidade_id: str,
                   dados_anteriores: dict, dados_novos: dict):
        self.registrar("UPDATE", entidade, entidade_id, dados_anteriores, dados_novos)

    def log_delete(self, entidade: str, entidade_id: str, dados_anteriores: dict):
        self.registrar("DELETE", entidade, entidade_id, dados_anteriores, None)

    def log_login(self, email: str):
        self.registrar("LOGIN", "usuarios", None, None, {"email": email})

    def log_logout(self, email: str):
        self.registrar("LOGOUT", "usuarios", None, None, {"email": email})