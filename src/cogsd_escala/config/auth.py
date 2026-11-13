# src/cogsd_escala/config/auth.py
"""Sistema de autenticação"""

from passlib.hash import bcrypt
import streamlit as st
import secrets
import string


def gerar_hash_senha(senha: str) -> str:
    """Gera hash bcrypt de uma senha"""
    return bcrypt.hash(senha)


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Verifica se a senha corresponde ao hash"""
    if not senha or not hash_armazenado:
        return False
    try:
        return bcrypt.verify(senha, hash_armazenado)
    except Exception:
        return False


def gerar_senha_temporaria(tamanho: int = 10) -> str:
    """Gera uma senha temporária aleatória"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


def is_logado() -> bool:
    """Verifica se há usuário logado"""
    return st.session_state.get("usuario") is not None


def get_usuario_logado() -> dict:
    """Retorna dados do usuário logado"""
    return st.session_state.get("usuario", {})


def get_role() -> str:
    """Retorna a role do usuário logado"""
    usuario = get_usuario_logado()
    return usuario.get("role", "viewer")


def is_admin() -> bool:
    """Verifica se é admin"""
    return get_role() == "admin"


def is_editor() -> bool:
    """Verifica se é editor ou admin"""
    return get_role() in ["admin", "editor"]


def fazer_login(usuario: dict):
    """Registra login na sessão"""
    st.session_state["usuario"] = usuario


def fazer_logout():
    """Remove login da sessão"""
    st.session_state["usuario"] = None