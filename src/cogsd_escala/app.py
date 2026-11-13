# src/cogsd_escala/app.py
"""Aplicação principal - COGSD Escala"""

import streamlit as st
from datetime import date, datetime
import uuid

# Imports do projeto
from cogsd_escala.core.models import Trabalhador, Usuario, Escala, Ocorrencia, DiaEspecial
from cogsd_escala.core.rules import RegrasFrequencia, RegraArt12
from cogsd_escala.services.calendar_service import CalendarService
from cogsd_escala.services.log_service import LogService
from cogsd_escala.infrastructure.supabase_repository import SupabaseRepository
from cogsd_escala.config.auth import (
    gerar_hash_senha, verificar_senha, gerar_senha_temporaria,
    is_logado, get_usuario_logado, get_role,
    is_admin, is_editor, fazer_login, fazer_logout
)

# ============================================
# CONFIGURAÇÃO
# ============================================
st.set_page_config(
    page_title="COGSD Escala",
    page_icon="📋",
    layout="wide",
)


@st.cache_resource
def get_repo():
    return SupabaseRepository()


repo = get_repo()
log = LogService(repo)

# ============================================
# CSS
# ============================================
st.markdown("""
<style>
    .stApp { background: linear-gradient(135deg, #f5f7fa, #e4e8eb); }
    .header-title { text-align:center; color:#2c3e50; font-size:2.5em; font-weight:bold; margin-bottom:0; }
    .header-subtitle { text-align:center; color:#7f8c8d; font-size:1.1em; margin-top:0; }
    .card { background:white; border-radius:12px; padding:15px; margin:8px 0;
            box-shadow:0 2px 8px rgba(0,0,0,0.1); border-left:5px solid; }
</style>
""", unsafe_allow_html=True)


# ============================================
# TELA DE LOGIN
# ============================================
def tela_login():
    st.markdown('<h1 class="header-title">📋 COGSD Escala</h1>', unsafe_allow_html=True)
    st.markdown('<p class="header-subtitle">Sistema de Gestão de Escala</p>', unsafe_allow_html=True)
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 Login")

        with st.form("form_login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", use_container_width=True)

            if entrar:
                if not email or not senha:
                    st.error("Preencha e-mail e senha!")
                else:
                    usuario = repo.buscar_usuario_por_email(email)

                    if not usuario:
                        st.error("❌ E-mail não encontrado")
                    elif not usuario.get("ativo", True):
                        st.error("❌ Usuário inativo. Contate o administrador.")
                    elif not verificar_senha(senha, usuario["senha_hash"]):
                        st.error("❌ Senha incorreta")
                    else:
                        # Login OK
                        fazer_login(usuario)
                        log.log_login(email)
                        repo.atualizar_usuario(usuario["id"],
                                               ultimo_acesso=datetime.now().isoformat())
                        st.rerun()

        st.markdown("---")
        st.caption("Esqueceu a senha? Contate o administrador.")


# ============================================
# TELA DE TROCA DE SENHA (1º acesso)
# ============================================
def tela_troca_senha():
    st.markdown("### 🔑 Primeiro Acesso - Troque sua Senha")
    st.info("Por segurança, você precisa definir uma nova senha no primeiro acesso.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_troca_senha"):
            nova_senha = st.text_input("Nova senha", type="password")
            confirmar = st.text_input("Confirmar nova senha", type="password")
            trocar = st.form_submit_button("Definir senha", use_container_width=True)

            if trocar:
                if len(nova_senha) < 6:
                    st.error("Senha deve ter pelo menos 6 caracteres")
                elif nova_senha != confirmar:
                    st.error("Senhas não coincidem")
                else:
                    usuario = get_usuario_logado()
                    novo_hash = gerar_hash_senha(nova_senha)
                    repo.atualizar_usuario(
                        usuario["id"],
                        senha_hash=novo_hash,
                        senha_temporaria=False
                    )
                    log.registrar("UPDATE", "usuarios", usuario["id"],
                                  None, {"acao": "troca_senha"})
                    st.success("✅ Senha alterada! Redirecionando...")
                    st.session_state["usuario"]["senha_temporaria"] = False
                    st.rerun()


# ============================================
# ABA: ESCALA
# ============================================
def aba_escala():
    st.markdown("### 📅 Escala Mensal")

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        anos = CalendarService.get_anos_disponiveis()
        ano = st.selectbox("Ano", anos, key="ano_escala")
    with col2:
        meses = CalendarService.get_meses(ano)
        mes_nome = st.selectbox("Mês", [m[1] for m in meses], key="mes_escala")
        mes = [m[0] for m in meses if m[1] == mes_nome][0]

    # Carrega dados do mês
    escalas_mes = repo.listar_escalas_do_mes(ano, mes)
    trabalhadores_dict = {t["id"]: t for t in repo.listar_trabalhadores(apenas_ativos=True)}

    # Agrupa escalas por data
    escalas_por_data = {}
    for e in escalas_mes:
        d = e["data"]
        if d not in escalas_por_data:
            escalas_por_data[d] = []
        escalas_por_data[d].append(e)

    # Gera calendário
    estrutura = CalendarService.get_estrutura_mes(ano, mes)
    offset = estrutura[0]['data'].weekday()

    # Cabeçalho
    dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    header_cols = st.columns(7)
    for i, dia in enumerate(dias_semana):
        with header_cols[i]:
            st.markdown(
                f"<div style='text-align:center; font-weight:bold; "
                f"background:#ecf0f1; padding:8px; border-radius:6px; "
                f"color:#2c3e50;'>{dia}</div>",
                unsafe_allow_html=True
            )

    # Monta grid
    todas_celulas = [None] * offset + estrutura
    while len(todas_celulas) % 7 != 0:
        todas_celulas.append(None)
    semanas = [todas_celulas[i:i + 7] for i in range(0, len(todas_celulas), 7)]

    # Carrega dias especiais do mês
    dias_especiais = repo.listar_dias_especiais(ano=ano)
    dias_especiais_set = {
        d["data"]: d for d in dias_especiais
        if d["data"].startswith(f"{ano}-{mes:02d}")
    }

    for semana in semanas:
        cols = st.columns(7)
        for i, dia_info in enumerate(semana):
            with cols[i]:
                if dia_info is None:
                    st.markdown("<div style='min-height:120px;'></div>", unsafe_allow_html=True)
                    continue

                data_str = dia_info['data'].isoformat()
                escalas_dia = escalas_por_data.get(data_str, [])

                # Carrega dias especiais do mês (deve estar antes do loop)
                # (isso já deve estar no código, se não, adicione antes do "for semana in semanas:")
                # dias_especiais = repo.listar_dias_especiais(ano=ano)
                # dias_especiais_set = {
                #     d["data"]: d for d in dias_especiais
                #     if d["data"].startswith(f"{ano}-{mes:02d}")
                # }

                data_str_iso = dia_info['data'].isoformat()
                dia_especial = dias_especiais_set.get(data_str_iso)

                # Cores por tipo
                if dia_especial:
                    if dia_especial["tipo"] == "Feriado":
                        bg = "#e8f5e9"  # verde claro
                        border = "#4caf50"  # verde
                    else:  # Ponto Facultativo
                        bg = "#fff8e1"  # amarelo claro
                        border = "#ffc107"  # amarelo
                elif dia_info['is_fim_semana']:
                    bg = "#fff5f5"
                    border = "#e74c3c"
                else:
                    bg = "#f8fbff"
                    border = "#3498db"

                card_html = (
                    f'<div style="background:{bg};border-left:4px solid {border};'
                    f'border-radius:8px;padding:8px;margin:4px 0;min-height:100px;">'
                    f'<div style="font-weight:bold;font-size:1.1em;color:#2c3e50;">'
                    f'{dia_info["dia"]}</div>'
                    f'<div style="color:#7f8c8d;font-size:0.75em;margin-bottom:5px;">'
                    f'{dia_info["dia_semana_curto"]}</div>'
                )

                # Descrição do dia especial (texto completo, quebra de linha)
                if dia_especial and dia_especial.get("descricao"):
                    card_html += (
                        f'<div style="color:{border};font-size:0.7em;'
                        f'font-weight:bold;margin:2px 0;line-height:1.1;'
                        f'word-wrap:break-word;">'
                        f'{dia_especial["descricao"]}</div>'
                    )
                elif dia_especial:
                    # Se não tem descrição, mostra só o tipo
                    card_html += (
                        f'<div style="color:{border};font-size:0.7em;'
                        f'font-weight:bold;margin:2px 0;">'
                        f'{dia_especial["tipo"]}</div>'
                    )

                # Turnos
                for e in escalas_dia:
                    trab = trabalhadores_dict.get(e["trabalhador_id"])
                    if trab:
                        turno_txt = e.get("turno") or "Diurno"
                        card_html += (
                            f'<div style="background:#3498db;color:white;'
                            f'border-radius:5px;padding:3px 6px;margin:2px 0;'
                            f'font-size:0.7em;">{trab["nome"][:15]} ({turno_txt[:7]})</div>'
                        )

                card_html += '</div>'
                st.markdown(card_html, unsafe_allow_html=True)

                if dia_especial and dia_especial.get("descricao"):
                    card_html += (
                        f'margin:1px 0;font-style:italic;">'
                        f'{dia_especial["descricao"][:20]}</div>'
                    )

                # Botões (admin/editor)
                if is_editor():
                    col_add, col_rm = st.columns(2)
                    with col_add:
                        with st.popover("➕"):
                            st.markdown(f"**{dia_info['data_formatada']}**")
                            if trabalhadores_dict:
                                nomes = [t["nome"] for t in trabalhadores_dict.values()]
                                trab_nome = st.selectbox("Trabalhador", nomes, key=f"add_{data_str}")
                                trab_id = [tid for tid, t in trabalhadores_dict.items() if t["nome"] == trab_nome][0]

                                turnos_opcoes = ["Manhã", "Tarde", "Diurno"]
                                turno = st.selectbox("Turno", turnos_opcoes, key=f"turno_{data_str}")
                                regime = st.selectbox("Regime", ["presencial", "hibrido", "remoto"],
                                                      key=f"regime_{data_str}")

                                if st.button("Confirmar", key=f"btn_add_{data_str}"):
                                    # Verifica se já existe
                                    existe = any(e["trabalhador_id"] == trab_id for e in escalas_dia)
                                    if existe:
                                        st.error("Já está escalado neste dia!")
                                    else:
                                        dados = {
                                            "data": data_str,
                                            "trabalhador_id": trab_id,
                                            "turno": None if turno == "Diurno" else turno,
                                            "regime": regime,
                                        }
                                        novo_id = repo.adicionar_escala(dados)
                                        log.log_insert("escalas", novo_id, dados)
                                        st.success("✅ Adicionado!")
                                        st.rerun()
                            else:
                                st.warning("Cadastre trabalhadores primeiro!")

                    with col_rm:
                        if escalas_dia:
                            with st.popover("🗑️"):
                                st.markdown(f"**Remover de {dia_info['data_formatada']}**")
                                for e in escalas_dia:
                                    trab = trabalhadores_dict.get(e["trabalhador_id"])
                                    if trab:
                                        if st.button(f"❌ {trab['nome']}", key=f"rm_{e['id']}"):
                                            log.log_delete("escalas", e["id"], e)
                                            repo.remover_escala(e["id"])
                                            st.rerun()




    # Legenda
    st.markdown("---")
    st.markdown(
                    "<div style='display:flex; gap:20px; justify-content:center; "
                    "font-size:0.85em; color:#555;'>"
                    "<div><span style='display:inline-block; width:14px; height:14px; "
                    "background:#4caf50; border-radius:50%; vertical-align:middle; "
                    "margin-right:6px;'></span>Feriado</div>"
                    "<div><span style='display:inline-block; width:14px; height:14px; "
                    "background:#ffc107; border-radius:50%; vertical-align:middle; "
                    "margin-right:6px;'></span>Ponto Facultativo</div>"
                    "<div><span style='display:inline-block; width:14px; height:14px; "
                    "background:#e74c3c; border-radius:50%; vertical-align:middle; "
                    "margin-right:6px;'></span>Fim de semana</div>"
                    "</div>",
                    unsafe_allow_html=True
                )

# ============================================
# ABA: TRABALHADORES
# ============================================
def aba_trabalhadores():
    st.markdown("### 👥 Trabalhadores")

    trabalhadores = repo.listar_trabalhadores()

    if trabalhadores:
        for t in trabalhadores:
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            with col1:
                chefia = "👔 " if t.get("is_chefia") else ""
                st.markdown(
                    f'<div class="card" style="border-left-color:#3498db;">'
                    f'{chefia}<b>{t["nome"]}</b><br>'
                    f'<small>{t.get("cargo", "—")} • {t["email"]} • {t.get("turno_preferencia", "—")}</small>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(f"**{'✅ Ativo' if t.get('ativo') else '❌ Inativo'}**")
            with col3:
                if t.get("ativo"):
                    if st.button("Desativar", key=f"toggle_t_{t['id']}"):
                        repo.atualizar_trabalhador(t["id"], ativo=False)
                        log.log_update("trabalhadores", t["id"], t, {**t, "ativo": False})
                        st.rerun()
                else:
                    if st.button("Ativar", key=f"toggle_t_{t['id']}"):
                        repo.atualizar_trabalhador(t["id"], ativo=True)
                        log.log_update("trabalhadores", t["id"], t, {**t, "ativo": True})
                        st.rerun()
            with col4:
                if st.button("🗑️", key=f"del_t_{t['id']}"):
                    log.log_delete("trabalhadores", t["id"], t)
                    repo.remover_trabalhador(t["id"])
                    st.rerun()
    else:
        st.info("Nenhum trabalhador cadastrado.")

    if is_admin():
        st.markdown("---")
        st.markdown("### ➕ Adicionar Trabalhador")

        with st.form("form_trabalhador"):
            nome = st.text_input("Nome")
            email = st.text_input("E-mail")
            cargo = st.text_input("Cargo")
            col1, col2 = st.columns(2)
            with col1:
                is_chefia = st.checkbox("Cargo de chefia")
            with col2:
                turno_pref = st.selectbox("Turno preferência", ["Manhã", "Tarde", "Diurno"])

            regime = st.selectbox("Regime", ["presencial", "hibrido", "remoto"])
            excecao = st.checkbox("Exceção Art. 12 (não conta no limite 50%)")

            if st.form_submit_button("Adicionar"):
                if nome and email:
                    dados = {
                        "nome": nome,
                        "email": email.lower(),
                        "cargo": cargo or None,
                        "is_chefia": is_chefia,
                        "turno_preferencia": turno_pref,
                        "regime_trabalho": regime,
                        "excecao_art12": excecao,
                        "ativo": True,
                    }
                    novo_id = repo.adicionar_trabalhador(dados)
                    log.log_insert("trabalhadores", novo_id, dados)
                    st.success(f"✅ {nome} adicionado!")
                    st.rerun()
                else:
                    st.error("Nome e e-mail são obrigatórios!")


# ============================================
# ABA: USUÁRIOS (admin)
# ============================================
def aba_usuarios():
    st.markdown("### 🔐 Usuários")

    usuarios = repo.listar_usuarios()
    trabalhadores = {t["id"]: t for t in repo.listar_trabalhadores()}

    if usuarios:
        for u in usuarios:
            trab = trabalhadores.get(u.get("trabalhador_id"))
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
            with col1:
                st.markdown(
                    f'<div class="card" style="border-left-color:#9b59b6;">'
                    f'<b>{u["email"]}</b><br>'
                    f'<small>Role: {u["role"]} • '
                    f'Trabalhador: {trab["nome"] if trab else "—"} • '
                    f'{"Senha temporária" if u.get("senha_temporaria") else "Senha definida"}</small>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with col2:
                novo_role = st.selectbox(
                    "Role", ["viewer", "editor", "admin"],
                    index=["viewer", "editor", "admin"].index(u.get("role", "viewer")),
                    key=f"role_{u['id']}"
                )
                if novo_role != u.get("role"):
                    if st.button("Salvar role", key=f"save_role_{u['id']}"):
                        repo.atualizar_usuario(u["id"], role=novo_role)
                        log.log_update("usuarios", u["id"], u, {**u, "role": novo_role})
                        st.rerun()
            with col3:
                if u.get("ativo"):
                    if st.button("Desativar", key=f"toggle_u_{u['id']}"):
                        repo.atualizar_usuario(u["id"], ativo=False)
                        st.rerun()
                else:
                    if st.button("Ativar", key=f"toggle_u_{u['id']}"):
                        repo.atualizar_usuario(u["id"], ativo=True)
                        st.rerun()
            with col4:
                col_reset, col_del = st.columns(2)
                with col_reset:
                    if st.button("🔑", key=f"reset_u_{u['id']}",
                                 help="Resetar senha"):
                        nova_temp = gerar_senha_temporaria()
                        repo.atualizar_usuario(
                            u["id"],
                            senha_hash=gerar_hash_senha(nova_temp),
                            senha_temporaria=True
                        )
                        log.log_update("usuarios", u["id"], u,
                                       {**u, "senha_temporaria": True})
                        st.success(f"Nova senha: `{nova_temp}`")
                        st.info("Repasse ao usuário. Ele trocará no próximo login.")
                with col_del:
                    if st.button("🗑️", key=f"del_u_{u['id']}"):
                        log.log_delete("usuarios", u["id"], u)
                        repo.remover_usuario(u["id"])
                        st.rerun()

    st.markdown("---")
    st.markdown("### ➕ Adicionar Usuário")

    with st.form("form_usuario"):
        email = st.text_input("E-mail")
        col1, col2 = st.columns(2)
        with col1:
            role = st.selectbox("Role", ["viewer", "editor", "admin"])
        with col2:
            trabalhadores_lista = repo.listar_trabalhadores(apenas_ativos=True)
            opcoes_trab = {"— Nenhum —": None}
            for t in trabalhadores_lista:
                opcoes_trab[t["nome"]] = t["id"]
            trab_nome = st.selectbox("Vincular a trabalhador", list(opcoes_trab.keys()))
            trab_id = opcoes_trab[trab_nome]

        if st.form_submit_button("Criar usuário"):
            if email:
                senha_temp = gerar_senha_temporaria()
                dados = {
                    "email": email.lower(),
                    "senha_hash": gerar_hash_senha(senha_temp),
                    "senha_temporaria": True,
                    "role": role,
                    "trabalhador_id": trab_id,
                    "ativo": True,
                }
                novo_id = repo.adicionar_usuario(dados)
                log.log_insert("usuarios", novo_id, {**dados, "senha_hash": "***"})

                st.success(f"✅ Usuário criado!")
                st.info(f"**Senha temporária:** `{senha_temp}` — Anote e repasse ao usuário!")
            else:
                st.error("E-mail é obrigatório!")


# ============================================
# ABA: DIAS ESPECIAIS
# ============================================
def aba_dias_especiais():
    st.markdown("### 📆 Dias Especiais (Feriados / Facultativos)")

    anos = [2026, 2027, 2028, 2029, 2030]
    ano = st.selectbox("Ano", anos, key="ano_dias")

    dias = repo.listar_dias_especiais(ano=ano)

    if dias:
        # Ordena por data
        dias_ordenados = sorted(dias, key=lambda d: d["data"])

        # Agrupa por mês
        from collections import defaultdict
        por_mes = defaultdict(list)
        for d in dias_ordenados:
            mes = int(d["data"][5:7])
            por_mes[mes].append(d)

        MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

        # Renderiza cada mês
        for mes_num in sorted(por_mes.keys()):
            mes_nome = MESES[mes_num - 1]

            st.markdown(
                f"<h4 style='margin-top:20px; margin-bottom:8px; "
                f"color:#2c3e50;'>{mes_nome}</h4>",
                unsafe_allow_html=True
            )

            for d in por_mes[mes_num]:
                # Formata data dd/mm/aaaa
                data_fmt = d["data"]  # "2026-01-01"
                ano_d, mes_d, dia_d = data_fmt.split("-")
                data_br = f"{dia_d}/{mes_d}/{ano_d}"

                # Busca o ato vinculado
                ato = repo.buscar_ato_normativo(d.get("ato_normativo_id")) if d.get("ato_normativo_id") else None

                cor_tipo = "#4caf50" if d["tipo"] == "Feriado" else "#f39c12"

                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(
                        f"<div style='margin-left:20px; padding:6px 10px; "
                        f"border-left:3px solid {cor_tipo}; "
                        f"background:#f8f9fa; border-radius:4px; margin-bottom:6px;'>"
                        f"<span style='color:#555; font-family:monospace;'>{data_br}</span> — "
                        f"<strong style='color:{cor_tipo};'>{d['tipo']}</strong>"
                        f"{(' — ' + d['descricao']) if d.get('descricao') else ''}"
                        f"{(' • 📜 ' + ato['titulo']) if ato else ''}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with col2:
                    if is_editor():
                        if st.button("🗑️", key=f"del_d_{d['id']}"):
                            repo.remover_dia_especial(d["id"])
                            st.rerun()
    else:
        st.info(f"Nenhum dia especial cadastrado para {ano}.")

    # Adicionar manualmente (sem mudanças)
    if is_editor():
        st.markdown("---")
        st.markdown("### ➕ Adicionar Dia Especial")
        st.caption("💡 Para cadastrar em lote via PDF, use a aba '📜 Atos Normativos'.")

        with st.form("form_dia"):
            col1, col2 = st.columns(2)
            with col1:
                data_dia = st.date_input("Data",
                                         min_value=date(ano, 1, 1),
                                         max_value=date(ano, 12, 31))
            with col2:
                tipo = st.selectbox("Tipo", ["Feriado", "Ponto Facultativo"])
            descricao = st.text_input("Descrição (opcional)")

            if st.form_submit_button("Adicionar"):
                dados = {
                    "data": data_dia.isoformat(),
                    "tipo": tipo,
                    "descricao": descricao,
                }
                repo.adicionar_dia_especial(dados)
                st.success("✅ Dia especial adicionado!")
                st.rerun()

# ============================================
# ABA: LOGS (admin)
# ============================================
def aba_logs():
    st.markdown("### 📝 Logs de Auditoria")

    logs = repo.listar_logs(limite=200)

    if logs:
        for l in logs:
            st.markdown(
                f"**{l['timestamp'][:19]}** — `{l['usuario_email']}` — "
                f"**{l['acao']}** em `{l['entidade']}` (ID: {l.get('entidade_id', '—')})"
            )
    else:
        st.info("Nenhum log registrado.")


# ============================================
# MAIN
# ============================================
def main():
    # Se não está logado
    if not is_logado():
        tela_login()
        return

    usuario = get_usuario_logado()

    # Se senha temporária, força troca
    if usuario.get("senha_temporaria"):
        tela_troca_senha()
        return

    # Header
    st.markdown('<h1 class="header-title">📋 COGSD Escala</h1>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="header-subtitle">Logado como: {usuario["email"]} '
        f'({get_role()})</p>', unsafe_allow_html=True
    )
    st.markdown("---")

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {usuario['email']}")
        st.markdown(f"**Role:** {get_role()}")
        st.markdown("---")

        # Trocar senha
        with st.expander("🔑 Trocar senha"):
            with st.form("form_troca_senha_logado"):
                senha_atual = st.text_input("Senha atual", type="password")
                nova_senha = st.text_input("Nova senha", type="password")
                confirmar = st.text_input("Confirmar nova senha", type="password")
                trocar = st.form_submit_button("Trocar senha")

                if trocar:
                    if not verificar_senha(senha_atual, usuario["senha_hash"]):
                        st.error("❌ Senha atual incorreta")
                    elif len(nova_senha) < 6:
                        st.error("Nova senha deve ter pelo menos 6 caracteres")
                    elif nova_senha != confirmar:
                        st.error("Senhas não coincidem")
                    else:
                        novo_hash = gerar_hash_senha(nova_senha)
                        repo.atualizar_usuario(usuario["id"], senha_hash=novo_hash)
                        log.registrar("UPDATE", "usuarios", usuario["id"],
                                      None, {"acao": "troca_senha_propria"})
                        st.success("✅ Senha alterada! Faça login novamente.")
                        fazer_logout()
                        st.rerun()

        st.markdown("---")
        if st.button("🚪 Sair", use_container_width=True):
            log.log_logout(usuario["email"])
            fazer_logout()
            st.rerun()

    # Tabs por role
    if is_admin():
        tabs = st.tabs(["📅 Escala", "👥 Trabalhadores", "⚠️ Ocorrências",
                        "📆 Dias Especiais", "📜 Atos Normativos",
                        "📊 Relatórios", "🔐 Usuários", "📝 Logs"])
        (tab_escala, tab_trab, tab_ocorr, tab_dias,
         tab_atos, tab_rel, tab_users, tab_logs) = tabs

        with tab_escala:
            aba_escala()
        with tab_trab:
            aba_trabalhadores()
        with tab_ocorr:
            st.info("Em breve (Fase 2)")
        with tab_dias:
            aba_dias_especiais()
        with tab_atos:
            aba_atos_normativos()
        with tab_rel:
            st.info("Em breve (Fase 3)")
        with tab_users:
            aba_usuarios()
        with tab_logs:
            aba_logs()

    elif is_editor():
        tabs = st.tabs(["📅 Escala", "👥 Trabalhadores", "⚠️ Ocorrências",
                        "📆 Dias Especiais", "📊 Relatórios"])
        tab_escala, tab_trab, tab_ocorr, tab_dias, tab_rel = tabs

        with tab_escala:
            aba_escala()
        with tab_trab:
            aba_trabalhadores()
        with tab_ocorr:
            st.info("Em breve (Fase 2)")
        with tab_dias:
            aba_dias_especiais()
        with tab_rel:
            st.info("Em breve (Fase 3)")

    else:  # viewer
        tabs = st.tabs(["📅 Escala", "👥 Trabalhadores", "📊 Relatórios"])
        tab_escala, tab_trab, tab_rel = tabs

        with tab_escala:
            aba_escala()
        with tab_trab:
            aba_trabalhadores()
        with tab_rel:
            st.info("Em breve (Fase 3)")


# ============================================
# ABA: ATOS NORMATIVOS (admin)
# ============================================
def aba_atos_normativos():
    st.markdown("### 📜 Atos Normativos de Dias Especiais")
    st.info(
        "Faça upload do PDF do ato normativo (ex: Portaria CNMP-SG nº 35/2026) "
        "para o ano correspondente. Se houver substituição, o ato anterior "
        "será desativado automaticamente."
    )

    # Lista atos existentes
    anos_disponiveis = [2026, 2027, 2028, 2029, 2030]
    ano_filtro = st.selectbox("Filtrar por ano", ["Todos"] + anos_disponiveis, key="ano_ato")

    atos = repo.listar_atos_normativos(
        ano=ano_filtro if ano_filtro != "Todos" else None,
        apenas_ativos=False
    )

    if atos:
        st.markdown("#### Atos cadastrados")
        for ato in atos:
            status = "✅ Ativo" if ato.get("ativo") else "❌ Substituído"
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

            with col1:
                st.markdown(
                    f"**{ato['ano']}** — {ato['titulo']}<br>"
                    f"<small>{ato.get('descricao', '')}</small>",
                    unsafe_allow_html=True
                )
                if ato.get("arquivo_url"):
                    st.markdown(f"[📄 Ver PDF]({ato['arquivo_url']})")

            with col2:
                st.markdown(status)

            with col3:
                # Contar dias associados
                dias_ato = repo.listar_dias_especiais(ato_id=ato["id"])
                st.markdown(f"**{len(dias_ato)} dias**")

            with col4:
                if ato.get("ativo") and is_admin():
                    if st.button("🗑️ Remover", key=f"rm_ato_{ato['id']}"):
                        # Desativa ato
                        repo.desativar_ato_normativo(ato["id"])
                        # Remove os dias associados
                        repo.remover_dias_por_ato(ato["id"])
                        # Remove PDF
                        if ato.get("arquivo_url"):
                            repo.remover_pdf_ato(ato["arquivo_url"])
                        log.log_delete("atos_normativos", ato["id"], ato)
                        st.success("Ato removido!")
                        st.rerun()
    else:
        st.info("Nenhum ato normativo cadastrado.")

    if not is_admin():
        return

    st.markdown("---")
    st.markdown("### ➕ Adicionar Ato Normativo")

    with st.form("form_ato"):
        col1, col2 = st.columns(2)
        with col1:
            ano = st.selectbox("Ano de referência", anos_disponiveis)
        with col2:
            titulo = st.text_input("Título do ato",
                                   placeholder="Ex: Portaria CNMP-SG nº 35/2026")

        descricao = st.text_area("Descrição (opcional)")

        st.markdown("**Upload do PDF:**")
        pdf = st.file_uploader("Selecione o PDF", type=["pdf"])

        st.markdown("**Datas especiais** (adicione manualmente):")
        st.caption("Opcionalmente, você pode adicionar as datas manualmente abaixo.")

        # Permite adicionar N datas
        num_datas = st.number_input("Quantas datas adicionar?",
                                    min_value=0, max_value=50, value=0)

        # Cria campos dinâmicos
        datas_input = []
        for i in range(int(num_datas)):
            st.markdown(f"**Data {i + 1}:**")
            col_d, col_t, col_desc = st.columns([2, 2, 3])
            with col_d:
                d = st.date_input(f"Data {i + 1}", key=f"data_{i}",
                                  min_value=date(ano, 1, 1),
                                  max_value=date(ano, 12, 31))
            with col_t:
                t = st.selectbox(f"Tipo {i + 1}",
                                 ["Feriado", "Ponto Facultativo"],
                                 key=f"tipo_{i}")
            with col_desc:
                desc = st.text_input(f"Descrição {i + 1}", key=f"desc_{i}")
            datas_input.append((d, t, desc))

        if st.form_submit_button("Salvar ato normativo"):
            if not titulo:
                st.error("Título é obrigatório!")
            else:
                # Verifica se já existe ato ativo para o ano
                atos_ano = repo.listar_atos_normativos(ano=ano, apenas_ativos=True)
                substituiu = None

                if atos_ano:
                    st.warning(
                        f"⚠️ Já existe ato ativo para {ano}. "
                        f"O ato anterior será desativado automaticamente."
                    )

                # Upload do PDF
                arquivo_url = None
                if pdf:
                    try:
                        arquivo_url = repo.upload_pdf_ato(pdf.read(), pdf.name)
                    except Exception as e:
                        st.error(f"Erro no upload: {e}")

                # Cria o ato
                dados_ato = {
                    "ano": ano,
                    "titulo": titulo,
                    "descricao": descricao,
                    "arquivo_nome": pdf.name if pdf else None,
                    "arquivo_url": arquivo_url,
                    "ativo": True,
                    "created_by": get_usuario_logado().get("email", ""),
                }
                ato_id = repo.adicionar_ato_normativo(dados_ato)
                log.log_insert("atos_normativos", ato_id, dados_ato)

                # Desativa atos anteriores
                if atos_ano:
                    for ato_ant in atos_ano:
                        repo.desativar_ato_normativo(ato_ant["id"], substituido_por=ato_id)
                        log.log_update("atos_normativos", ato_ant["id"],
                                       ato_ant, {**ato_ant, "ativo": False})

                # Adiciona as datas
                for d, t, desc in datas_input:
                    dados_dia = {
                        "data": d.isoformat(),
                        "tipo": t,
                        "descricao": desc,
                        "ato_normativo_id": ato_id,
                    }
                    repo.adicionar_dia_especial(dados_dia)

                st.success(
                    f"✅ Ato normativo salvo! "
                    f"{len(datas_input)} datas adicionadas."
                )
                st.rerun()

if __name__ == "__main__":
    main()