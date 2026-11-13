# src/cogsd_escala/infrastructure/supabase_repository.py
"""Persistência no Supabase"""

import streamlit as st
from st_supabase_connection import SupabaseConnection
from datetime import date, datetime
from typing import List, Dict, Optional
from calendar import monthrange
import uuid


class SupabaseRepository:
    """Gerencia a persistência no Supabase"""

    def __init__(self):
        self.conn = st.connection("supabase", type=SupabaseConnection)

    # ============================================
    # TRABALHADORES
    # ============================================

    def adicionar_trabalhador(self, dados: dict):
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("trabalhadores").insert(dados).execute()
        return dados["id"]

    def listar_trabalhadores(self, apenas_ativos: bool = False) -> List[Dict]:
        query = self.conn.table("trabalhadores").select("*")
        if apenas_ativos:
            query = query.eq("ativo", True)
        response = query.execute()
        return response.data if response.data else []

    def buscar_trabalhador(self, trabalhador_id: str) -> Optional[Dict]:
        response = (
            self.conn.table("trabalhadores")
            .select("*").eq("id", trabalhador_id).execute()
        )
        return response.data[0] if response.data else None

    def atualizar_trabalhador(self, trabalhador_id: str, **campos):
        self.conn.table("trabalhadores").update(campos).eq("id", trabalhador_id).execute()

    def remover_trabalhador(self, trabalhador_id: str):
        self.conn.table("trabalhadores").delete().eq("id", trabalhador_id).execute()

    # ============================================
    # USUÁRIOS
    # ============================================

    def adicionar_usuario(self, dados: dict):
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("usuarios").insert(dados).execute()
        return dados["id"]

    def listar_usuarios(self) -> List[Dict]:
        response = self.conn.table("usuarios").select("*").execute()
        return response.data if response.data else []

    def buscar_usuario_por_email(self, email: str) -> Optional[Dict]:
        response = (
            self.conn.table("usuarios")
            .select("*").eq("email", email.lower()).execute()
        )
        return response.data[0] if response.data else None

    def atualizar_usuario(self, usuario_id: str, **campos):
        self.conn.table("usuarios").update(campos).eq("id", usuario_id).execute()

    def remover_usuario(self, usuario_id: str):
        self.conn.table("usuarios").delete().eq("id", usuario_id).execute()

    # ============================================
    # ESCALAS
    # ============================================

    def adicionar_escala(self, dados: dict):
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("escalas").insert(dados).execute()
        return dados["id"]

    def listar_escalas_do_mes(self, ano: int, mes: int) -> List[Dict]:
        inicio = f"{ano}-{mes:02d}-01"
        ultimo_dia = monthrange(ano, mes)[1]
        fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

        response = (
            self.conn.table("escalas").select("*")
            .gte("data", inicio).lte("data", fim).execute()
        )
        return response.data if response.data else []

    def listar_escalas_por_data(self, data_alvo: date) -> List[Dict]:
        response = (
            self.conn.table("escalas").select("*")
            .eq("data", data_alvo.isoformat()).execute()
        )
        return response.data if response.data else []

    def remover_escala(self, escala_id: str):
        self.conn.table("escalas").delete().eq("id", escala_id).execute()

    # ============================================
    # OCORRÊNCIAS
    # ============================================

    def adicionar_ocorrencia(self, dados: dict):
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("ocorrencias").insert(dados).execute()
        return dados["id"]

    def listar_ocorrencias_do_mes(self, ano: int, mes: int) -> List[Dict]:
        inicio = f"{ano}-{mes:02d}-01"
        ultimo_dia = monthrange(ano, mes)[1]
        fim = f"{ano}-{mes:02d}-{ultimo_dia:02d}"

        response = (
            self.conn.table("ocorrencias").select("*")
            .gte("data", inicio).lte("data", fim).execute()
        )
        return response.data if response.data else []

    def remover_ocorrencia(self, ocorrencia_id: str):
        self.conn.table("ocorrencias").delete().eq("id", ocorrencia_id).execute()

    # ============================================
    # DIAS ESPECIAIS (atualizado)
    # ============================================

    def adicionar_dia_especial(self, dados: dict):
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("dias_especiais").insert(dados).execute()
        return dados["id"]

    def listar_dias_especiais(self, ano: Optional[int] = None,
                              ato_id: Optional[str] = None) -> List[Dict]:
        query = self.conn.table("dias_especiais").select("*")
        if ano:
            query = query.gte("data", f"{ano}-01-01").lte("data", f"{ano}-12-31")
        if ato_id:
            query = query.eq("ato_normativo_id", ato_id)
        response = query.order("data").execute()
        return response.data if response.data else []

    def remover_dia_especial(self, dia_id: str):
        self.conn.table("dias_especiais").delete().eq("id", dia_id).execute()

    def remover_dias_por_ato(self, ato_id: str):
        """Remove todos os dias de um ato normativo"""
        self.conn.table("dias_especiais").delete().eq("ato_normativo_id", ato_id).execute()

    # ============================================
    # LOGS
    # ============================================

    def adicionar_log(self, dados: dict):
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("logs_auditoria").insert(dados).execute()

    def listar_logs(self, limite: int = 100) -> List[Dict]:
        response = (
            self.conn.table("logs_auditoria").select("*")
            .order("timestamp", desc=True).limit(limite).execute()
        )
        return response.data if response.data else []

    # ============================================
    # ESTATÍSTICAS
    # ============================================

    def estatisticas(self) -> Dict:
        return {
            "total_trabalhadores": len(self.listar_trabalhadores()),
            "trabalhadores_ativos": len(self.listar_trabalhadores(apenas_ativos=True)),
            "total_usuarios": len(self.listar_usuarios()),
        }

    # ============================================
    # ATOS NORMATIVOS
    # ============================================

    def adicionar_ato_normativo(self, dados: dict) -> str:
        if not dados.get("id"):
            dados["id"] = str(uuid.uuid4())[:8]
        self.conn.table("atos_normativos").insert(dados).execute()
        return dados["id"]

    def listar_atos_normativos(self, ano: int = None, apenas_ativos: bool = True) -> List[Dict]:
        query = self.conn.table("atos_normativos").select("*")
        if ano:
            query = query.eq("ano", ano)
        if apenas_ativos:
            query = query.eq("ativo", True)
        response = query.order("created_at", desc=True).execute()
        return response.data if response.data else []

    def buscar_ato_normativo(self, ato_id: str) -> Optional[Dict]:
        response = (
            self.conn.table("atos_normativos")
            .select("*").eq("id", ato_id).execute()
        )
        return response.data[0] if response.data else None

    def desativar_ato_normativo(self, ato_id: str, substituido_por: str = None):
        campos = {"ativo": False}
        if substituido_por:
            campos["substituido_por"] = substituido_por
        self.conn.table("atos_normativos").update(campos).eq("id", ato_id).execute()

    def upload_pdf_ato(self, arquivo_bytes: bytes, nome_arquivo: str) -> str:
        """Faz upload do PDF no Storage e retorna URL pública"""
        import uuid as uuid_lib
        caminho = f"atos/{uuid_lib.uuid4().hex[:8]}_{nome_arquivo}"

        self.conn.storage.from_("atos-normativos").upload(
            path=caminho,
            file=arquivo_bytes,
            file_options={"content-type": "application/pdf"}
        )

        # Retorna URL pública
        url = self.conn.storage.from_("atos-normativos").get_public_url(caminho)
        return url

    def remover_pdf_ato(self, arquivo_url: str):
        """Remove PDF do Storage"""
        try:
            # Extrai o caminho da URL
            if "atos-normativos/" in arquivo_url:
                caminho = arquivo_url.split("atos-normativos/")[-1].split("?")[0]
                self.conn.storage.from_("atos-normativos").remove([caminho])
        except Exception as e:
            print(f"⚠️ Erro ao remover PDF: {e}")