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
# CACHE DE LEITURA
# ============================================
@st.cache_data(ttl=None)
def get_trabalhadores(apenas_ativos=False):
    return repo.listar_trabalhadores(apenas_ativos=apenas_ativos)


@st.cache_data(ttl=None)
def get_usuarios():
    return repo.listar_usuarios()


@st.cache_data(ttl=None)
def get_escalas_mes(ano, mes):
    return repo.listar_escalas_do_mes(ano, mes)


@st.cache_data(ttl=None)
def get_dias_especiais(ano):
    return repo.listar_dias_especiais(ano=ano)


@st.cache_data(ttl=None)
def get_atos_normativos(ano=None, apenas_ativos=True):
    return repo.listar_atos_normativos(ano=ano, apenas_ativos=apenas_ativos)


def limpar_cache():
    """Limpa todo o cache de leitura"""
    st.cache_data.clear()


# ============================================
# LOG ASSÍNCRONO (FILA)
# ============================================
def log_async(acao: str, entidade: str, entidade_id=None,
              dados_anteriores=None, dados_novos=None):
    """Adiciona log à fila (processado no próximo rerun)"""
    if "log_queue" not in st.session_state:
        st.session_state["log_queue"] = []
    st.session_state["log_queue"].append({
        "acao": acao,
        "entidade": entidade,
        "entidade_id": entidade_id,
        "dados_anteriores": dados_anteriores,
        "dados_novos": dados_novos,
    })


def processar_logs_pendentes():
    """Processa logs pendentes em lote"""
    if "log_queue" not in st.session_state:
        return
    fila = st.session_state["log_queue"]
    if not fila:
        return
    for item in fila:
        try:
            log.registrar(
                item["acao"], item["entidade"], item["entidade_id"],
                item["dados_anteriores"], item["dados_novos"]
            )
        except Exception:
            pass
    st.session_state["log_queue"] = []


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
    # Carrega dados do mês
    escalas_mes = get_escalas_mes(ano, mes)

    # Filtra trabalhadores conforme role
    todos_trabalhadores = get_trabalhadores(apenas_ativos=True)

    # Dicionário com TODOS (para exibir nomes no calendário)
    todos_dict = {t["id"]: t for t in todos_trabalhadores}

    if is_admin():
        # Admin vê todos (pode alocar qualquer um)
        trabalhadores_dict = todos_dict
    else:
        # Editor/viewer só pode se alocar a si mesmo
        usuario = get_usuario_logado()
        trabalhador_id = usuario.get("trabalhador_id")
        if trabalhador_id:
            trabalhadores_dict = {
                t["id"]: t for t in todos_trabalhadores
                if t["id"] == trabalhador_id
            }
        else:
            trabalhadores_dict = {}

    dias_especiais = get_dias_especiais(ano)

    # Aviso se não-admin não tem trabalhador vinculado
    if not is_admin() and not trabalhadores_dict:
        st.warning(
            "⚠️ Seu usuário não está vinculado a um trabalhador. "
            "Contate o administrador para vincular seu cadastro."
        )

    dias_especiais_set = {
        d["data"]: d for d in dias_especiais
        if d["data"].startswith(f"{ano}-{mes:02d}")
    }

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

    for semana in semanas:
        cols = st.columns(7)
        for i, dia_info in enumerate(semana):
            with cols[i]:
                if dia_info is None:
                    st.markdown("<div style='min-height:120px;'></div>", unsafe_allow_html=True)
                    continue

                data_str = dia_info['data'].isoformat()
                escalas_dia = escalas_por_data.get(data_str, [])

                data_str_iso = dia_info['data'].isoformat()
                dia_especial = dias_especiais_set.get(data_str_iso)

                # Cores por tipo de dia
                if dia_especial:
                    if dia_especial["tipo"] == "Feriado":
                        bg = "#e8f5e9"
                        border = "#4caf50"
                    else:
                        bg = "#fff8e1"
                        border = "#ffc107"
                elif dia_info['is_fim_semana']:
                    bg = "#fff5f5"
                    border = "#e74c3c"
                else:
                    bg = "#ffffff"
                    border = "#bdc3c7"

                card_html = (
                    f'<div style="background:{bg};border-left:4px solid {border};'
                    f'border-radius:8px;padding:8px;margin:4px 0;min-height:100px;">'
                    f'<div style="font-weight:bold;font-size:1.1em;color:#2c3e50;">'
                    f'{dia_info["dia"]}</div>'
                    f'<div style="color:#7f8c8d;font-size:0.75em;margin-bottom:5px;">'
                    f'{dia_info["dia_semana_curto"]}</div>'
                )

                # Descrição do dia especial
                if dia_especial and dia_especial.get("descricao"):
                    card_html += (
                        f'<div style="color:{border};font-size:0.7em;'
                        f'font-weight:bold;margin:2px 0;line-height:1.1;'
                        f'word-wrap:break-word;">'
                        f'{dia_especial["descricao"]}</div>'
                    )
                elif dia_especial:
                    card_html += (
                        f'<div style="color:{border};font-size:0.7em;'
                        f'font-weight:bold;margin:2px 0;">'
                        f'{dia_especial["tipo"]}</div>'
                    )

                # Turnos
                for e in escalas_dia:
                    trab = todos_dict.get(e["trabalhador_id"])
                    if trab:
                        turno_txt = e.get("turno") or "Diurno"
                        cor_trab = trab.get("cor", "#3498db")
                        card_html += (
                            f'<div style="background:{cor_trab};color:white;'
                            f'border-radius:5px;padding:3px 6px;margin:2px 0;'
                            f'font-size:0.7em;">{trab["nome"][:15]} ({turno_txt[:7]})</div>'
                        )

                card_html += '</div>'
                st.markdown(card_html, unsafe_allow_html=True)

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

                                if st.button("Confirmar", key=f"btn_add_{data_str}"):
                                    # Verificação de segurança
                                    if not is_admin():
                                        usuario = get_usuario_logado()
                                        if usuario.get("trabalhador_id") != trab_id:
                                            st.error("⛔ Você só pode se alocar a si mesmo!")
                                            st.stop()

                                    # Verifica se já existe
                                    existe = any(e["trabalhador_id"] == trab_id for e in escalas_dia)
                                    if existe:
                                        st.error("Já está escalado neste dia!")
                                    else:
                                        dados = {
                                            "data": data_str,
                                            "trabalhador_id": trab_id,
                                            "turno": None if turno == "Diurno" else turno,
                                            "regime": "presencial",
                                        }
                                        novo_id = repo.adicionar_escala(dados)
                                        log_async("INSERT", "escalas", novo_id, dados_novos=dados)
                                        get_escalas_mes.clear()
                                        st.success("✅ Adicionado!")
                                        st.rerun()
                            else:
                                if is_admin():
                                    st.warning("Cadastre trabalhadores primeiro!")
                                else:
                                    st.warning("⚠️ Você não está vinculado a um trabalhador.")

                    with col_rm:
                        if escalas_dia:
                            with st.popover("🗑️"):
                                st.markdown(f"**Remover de {dia_info['data_formatada']}**")
                                for e in escalas_dia:
                                    trab = todos_dict.get(e["trabalhador_id"])
                                    if not trab:
                                        continue

                                    # Admin pode remover qualquer um
                                    # Editor só pode remover a si mesmo
                                    pode_remover = is_admin() or (e["trabalhador_id"] in trabalhadores_dict)

                                    if pode_remover:
                                        if st.button(f"❌ {trab['nome']}", key=f"rm_{e['id']}"):
                                            log_async("DELETE", "escalas", e["id"], dados_anteriores=e)
                                            repo.remover_escala(e["id"])
                                            get_escalas_mes.clear()
                                            st.rerun()
                                    else:
                                        # Mostra nome mas sem botão
                                        st.markdown(
                                            f"<div style='padding:4px 8px; margin:2px 0; "
                                            f"background:#f0f0f0; border-radius:4px; "
                                            f"color:#999; font-size:0.85em;'>"
                                            f"🔒 {trab['nome']}</div>",
                                            unsafe_allow_html=True
                                        )

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

    trabalhadores = get_trabalhadores()

    if "editando_trabalhador" not in st.session_state:
        st.session_state["editando_trabalhador"] = None

    if trabalhadores:
        for t in trabalhadores:
            # Modo edição
            if st.session_state["editando_trabalhador"] == t["id"]:
                st.markdown(f"#### ✏️ Editando: {t['nome']}")
                with st.form(f"form_edit_{t['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nome = st.text_input("Nome", value=t["nome"], key=f"e_nome_{t['id']}")
                        email = st.text_input("E-mail", value=t["email"], key=f"e_email_{t['id']}")
                    with col2:
                        cargo = st.text_input("Cargo", value=t.get("cargo") or "", key=f"e_cargo_{t['id']}")
                        setor = st.text_input("Setor", value=t.get("setor") or "", key=f"e_setor_{t['id']}")

                    # Turno e Regime alinhados
                    col_turno, col_regime = st.columns(2)
                    with col_turno:
                        turno_pref = st.selectbox(
                            "Turno preferência",
                            ["Manhã", "Tarde", "Diurno"],
                            index=["Manhã", "Tarde", "Diurno"].index(t.get("turno_preferencia") or "Diurno"),
                            key=f"e_turno_{t['id']}"
                        )
                    with col_regime:
                        regime = st.selectbox(
                            "Regime",
                            ["presencial", "hibrido", "remoto"],
                            index=["presencial", "hibrido", "remoto"].index(t.get("regime_trabalho") or "presencial"),
                            key=f"e_regime_{t['id']}"
                        )

                    # Chefia e Exceção alinhados
                    col_chefia, col_excecao = st.columns(2)
                    with col_chefia:
                        is_chefia = st.checkbox("Cargo de chefia", value=t.get("is_chefia", False),
                                                key=f"e_chefia_{t['id']}")
                    with col_excecao:
                        excecao = st.checkbox("Exceção Art. 12", value=t.get("excecao_art12", False),
                                              key=f"e_excecao_{t['id']}")

                    cor_edit = st.color_picker(
                        "Cor do trabalhador",
                        t.get("cor", "#3498db"),
                        key=f"e_cor_{t['id']}"
                    )

                    col_salvar, col_cancelar = st.columns(2)
                    with col_salvar:
                        if st.form_submit_button("💾 Salvar", use_container_width=True):
                            dados_antigos = dict(t)
                            dados_novos = {
                                "nome": nome,
                                "email": email.lower(),
                                "cargo": cargo or None,
                                "setor": setor or None,
                                "turno_preferencia": turno_pref,
                                "is_chefia": is_chefia,
                                "regime_trabalho": regime,
                                "excecao_art12": excecao,
                                "cor": cor_edit,
                            }
                            repo.atualizar_trabalhador(t["id"], **dados_novos)
                            log_async("UPDATE", "trabalhadores", t["id"],
                                      dados_anteriores=dados_antigos, dados_novos=dados_novos)
                            get_trabalhadores.clear()
                            st.session_state["editando_trabalhador"] = None
                            st.success("✅ Salvo!")
                            st.rerun()
                    with col_cancelar:
                        if st.form_submit_button("❌ Cancelar", use_container_width=True):
                            st.session_state["editando_trabalhador"] = None
                            st.rerun()

                st.markdown("---")
                continue

            # Modo visualização
            col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])
            with col1:
                chefia = "👔 " if t.get("is_chefia") else ""
                cor_trab = t.get("cor", "#3498db")
                setor_txt = f' • {t.get("setor")}' if t.get("setor") else ''
                st.markdown(
                    f'<div class="card" style="border-left-color:{cor_trab};">'
                    f'{chefia}<b>{t["nome"]}</b><br>'
                    f'<small>{t.get("cargo", "—")}{setor_txt} • {t["email"]} • {t.get("turno_preferencia", "—")}</small>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(f"**{'✅ Ativo' if t.get('ativo') else '❌ Inativo'}**")
            with col3:
                if st.button("✏️", key=f"edit_t_{t['id']}", help="Editar"):
                    st.session_state["editando_trabalhador"] = t["id"]
                    st.rerun()
            with col4:
                if t.get("ativo"):
                    if st.button("Desativar", key=f"toggle_t_{t['id']}"):
                        repo.atualizar_trabalhador(t["id"], ativo=False)
                        log_async("UPDATE", "trabalhadores", t["id"],
                                  dados_anteriores=t, dados_novos={**t, "ativo": False})
                        get_trabalhadores.clear()
                        st.rerun()
                else:
                    if st.button("Ativar", key=f"toggle_t_{t['id']}"):
                        repo.atualizar_trabalhador(t["id"], ativo=True)
                        log_async("UPDATE", "trabalhadores", t["id"],
                                  dados_anteriores=t, dados_novos={**t, "ativo": True})
                        limpar_cache()
                        st.rerun()
            with col5:
                if st.button("🗑️", key=f"del_t_{t['id']}"):
                    for u in get_usuarios():
                        if u.get("trabalhador_id") == t["id"]:
                            repo.atualizar_usuario(u["id"], trabalhador_id=None)
                    log_async("DELETE", "trabalhadores", t["id"], dados_anteriores=t)
                    repo.remover_trabalhador(t["id"])
                    get_trabalhadores.clear()
                    st.rerun()
    else:
        st.info("Nenhum trabalhador cadastrado.")

    if is_admin():
        st.markdown("---")
        st.markdown("### ➕ Adicionar Trabalhador")

        if "form_trab_counter" not in st.session_state:
            st.session_state["form_trab_counter"] = 0

        form_key = f"form_trabalhador_{st.session_state['form_trab_counter']}"

        with st.form(form_key, clear_on_submit=False):
            nome_novo = st.text_input("Nome", key=f"nome_{form_key}")
            email_novo = st.text_input("E-mail", key=f"email_{form_key}")

            # Cargo e Setor alinhados
            col_cargo, col_setor = st.columns(2)
            with col_cargo:
                cargo_novo = st.text_input("Cargo", key=f"cargo_{form_key}")
            with col_setor:
                setor_novo = st.text_input("Setor", key=f"setor_{form_key}")

            # Turno e Regime alinhados
            col_turno, col_regime = st.columns(2)
            with col_turno:
                turno_pref_novo = st.selectbox("Turno preferência", ["Manhã", "Tarde", "Diurno"],
                                               key=f"turno_{form_key}")
            with col_regime:
                regime_novo = st.selectbox("Regime", ["presencial", "hibrido", "remoto"],
                                           key=f"regime_{form_key}")

            # Chefia e Exceção alinhados
            col_chefia, col_excecao = st.columns(2)
            with col_chefia:
                is_chefia_novo = st.checkbox("Cargo de chefia", key=f"chefia_{form_key}")
            with col_excecao:
                excecao_novo = st.checkbox("Exceção Art. 12 (não conta no limite 50%)",
                                           key=f"excecao_{form_key}")

            cor_novo = st.color_picker("Cor do trabalhador", "#3498db", key=f"cor_{form_key}")

            if st.form_submit_button("Adicionar"):
                # Valida ANTES de limpar
                campos_faltando = []
                if not nome_novo:
                    campos_faltando.append("Nome")
                if not email_novo:
                    campos_faltando.append("E-mail")

                if campos_faltando:
                    st.error(f"⚠️ Preencha os campos obrigatórios: {', '.join(campos_faltando)}")
                else:
                    dados = {
                        "nome": nome_novo,
                        "email": email_novo.lower(),
                        "cargo": cargo_novo or None,
                        "setor": setor_novo or None,
                        "is_chefia": is_chefia_novo,
                        "turno_preferencia": turno_pref_novo,
                        "regime_trabalho": regime_novo,
                        "excecao_art12": excecao_novo,
                        "ativo": True,
                        "cor": cor_novo,
                    }
                    novo_id = repo.adicionar_trabalhador(dados)
                    log_async("INSERT", "trabalhadores", novo_id, dados_novos=dados)
                    get_trabalhadores.clear()
                    # Só incrementa o contador (para limpar) se o cadastro deu certo
                    st.session_state["form_trab_counter"] += 1
                    st.success(f"✅ {nome_novo} adicionado!")
                    st.rerun()

# ============================================
# ABA: USUÁRIOS (admin)
# ============================================
def aba_usuarios():
    st.markdown("### 🔐 Usuários")

    usuarios = get_usuarios()
    trabalhadores = {t["id"]: t for t in get_trabalhadores()}

    if usuarios:
        for u in usuarios:
            trab = trabalhadores.get(u.get("trabalhador_id"))
            col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 1])
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
                        log_async("UPDATE", "usuarios", u["id"],
                                  dados_anteriores=u, dados_novos={**u, "role": novo_role})
                        get_usuarios.clear()
                        st.rerun()
            with col3:
                if u.get("ativo"):
                    if st.button("Desativar", key=f"toggle_u_{u['id']}"):
                        repo.atualizar_usuario(u["id"], ativo=False)
                        log_async("UPDATE", "usuarios", u["id"],
                                  dados_anteriores=u, dados_novos={**u, "ativo": False})
                        get_usuarios.clear()
                        st.rerun()
                else:
                    if st.button("Ativar", key=f"toggle_u_{u['id']}"):
                        repo.atualizar_usuario(u["id"], ativo=True)
                        log_async("UPDATE", "usuarios", u["id"],
                                  dados_anteriores=u, dados_novos={**u, "ativo": True})
                        get_usuarios.clear()
                        st.rerun()
            with col4:
                if st.button("🔑", key=f"reset_u_{u['id']}", help="Resetar senha"):
                    nova_temp = gerar_senha_temporaria()
                    repo.atualizar_usuario(
                        u["id"],
                        senha_hash=gerar_hash_senha(nova_temp),
                        senha_temporaria=True
                    )
                    log_async("UPDATE", "usuarios", u["id"],
                              dados_anteriores=u, dados_novos={**u, "senha_temporaria": True})
                    get_usuarios.clear()
                    st.success(f"Nova senha: `{nova_temp}`")
                    st.info("Repasse ao usuário. Ele trocará no próximo login.")
            with col5:
                if st.button("🗑️", key=f"del_u_{u['id']}"):
                    log_async("DELETE", "usuarios", u["id"], dados_anteriores=u)
                    repo.remover_usuario(u["id"])
                    get_usuarios.clear()
                    st.rerun()

    st.markdown("---")
    st.markdown("### ➕ Adicionar Usuário")

    if "form_user_counter" not in st.session_state:
        st.session_state["form_user_counter"] = 0

    user_form_key = f"form_usuario_{st.session_state['form_user_counter']}"

    with st.form(user_form_key):
        email = st.text_input("E-mail")
        col1, col2 = st.columns(2)
        with col1:
            role = st.selectbox("Role", ["viewer", "editor", "admin"])
        with col2:
            trabalhadores_lista = get_trabalhadores(apenas_ativos=True)
            opcoes_trab = {"— Nenhum —": None}
            for t in trabalhadores_lista:
                opcoes_trab[t["nome"]] = t["id"]
            trab_nome = st.selectbox("Vincular a trabalhador", list(opcoes_trab.keys()))
            trab_id = opcoes_trab[trab_nome]

        if st.form_submit_button("Criar usuário"):
            if not email:
                st.error("⚠️ E-mail é obrigatório!")
            else:
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
                log_async("INSERT", "usuarios", novo_id, dados_novos={**dados, "senha_hash": "***"})
                get_usuarios.clear()
                st.session_state["form_user_counter"] += 1
                st.success("✅ Usuário criado!")
                st.info(f"**Senha temporária:** `{senha_temp}` — Anote e repasse ao usuário!")
                st.rerun()


# ============================================
# ABA: DIAS ESPECIAIS
# ============================================
def aba_dias_especiais():
    st.markdown("### 📆 Dias Especiais (Feriados / Facultativos)")

    anos = [2026, 2027, 2028, 2029, 2030]
    ano = st.selectbox("Ano", anos, key="ano_dias")

    dias = get_dias_especiais(ano)

    if dias:
        dias_ordenados = sorted(dias, key=lambda d: d["data"])

        from collections import defaultdict
        por_mes = defaultdict(list)
        for d in dias_ordenados:
            mes = int(d["data"][5:7])
            por_mes[mes].append(d)

        MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

        for mes_num in sorted(por_mes.keys()):
            mes_nome = MESES[mes_num - 1]

            st.markdown(
                f"<h4 style='margin-top:20px; margin-bottom:8px; "
                f"color:#2c3e50;'>{mes_nome}</h4>",
                unsafe_allow_html=True
            )

            for d in por_mes[mes_num]:
                data_fmt = d["data"]
                ano_d, mes_d, dia_d = data_fmt.split("-")
                data_br = f"{dia_d}/{mes_d}/{ano_d}"

                ato = repo.buscar_ato_normativo(d.get("ato_normativo_id")) if d.get("ato_normativo_id") else None

                cor_tipo = "#4caf50" if d["tipo"] == "Feriado" else "#f39c12"

                # ============================================
                # ⚠️ COLOQUE AQUI A URL DO DOCUMENTO
                # ============================================
                LINK_ATO_2026 = "https://www.cnmp.mp.br/portal/images/NORMAS/PORTARIAS/SG/2026/035_2026_PORTARIA_SG.pdf"

                # Mapa de links por ano (caso tenha atos de outros anos)
                LINKS_ATOS = {
                    2026: LINK_ATO_2026,
                    # 2027: "https://...",
                    # 2028: "https://...",
                }

                col1, col2 = st.columns([6, 1])
                with col1:
                    # Monta a menção ao ato (com hyperlink fixo por ano)
                    if ato:
                        ano_ato = ato.get("ano", 2026)
                        link = LINKS_ATOS.get(ano_ato)

                        if link:
                            ato_html = (
                                f" • 📜 <a href='{link}' "
                                f"target='_blank' rel='noopener noreferrer' "
                                f"style='color:#2980b9; text-decoration:underline; "
                                f"font-weight:bold;'>"
                                f"{ato['titulo']}</a>"
                            )
                        else:
                            ato_html = f" • 📜 {ato['titulo']}"
                    else:
                        ato_html = ""

                    st.markdown(
                        f"<div style='margin-left:20px; padding:6px 10px; "
                        f"border-left:3px solid {cor_tipo}; "
                        f"background:#f8f9fa; border-radius:4px; margin-bottom:6px;'>"
                        f"<span style='color:#555; font-family:monospace;'>{data_br}</span> — "
                        f"<strong style='color:{cor_tipo};'>{d['tipo']}</strong>"
                        f"{(' — ' + d['descricao']) if d.get('descricao') else ''}"
                        f"{ato_html}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                with col2:
                    if is_editor():
                        if st.button("🗑️", key=f"del_d_{d['id']}"):
                            repo.remover_dia_especial(d["id"])
                            get_dias_especiais.clear()
                            st.rerun()
    else:
        st.info(f"Nenhum dia especial cadastrado para {ano}.")

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
                get_dias_especiais.clear()
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
    processar_logs_pendentes()

    if not is_logado():
        tela_login()
        return

    usuario = get_usuario_logado()

    if usuario.get("senha_temporaria"):
        tela_troca_senha()
        return

    st.markdown('<h1 class="header-title">📋 COGSD Escala</h1>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="header-subtitle">Logado como: {usuario["email"]} '
        f'({get_role()})</p>', unsafe_allow_html=True
    )
    st.markdown("---")

    with st.sidebar:
        st.markdown(f"### 👤 {usuario['email']}")
        st.markdown(f"**Role:** {get_role()}")
        st.markdown("---")

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

        if st.button("🔄 Recarregar", use_container_width=True):
            limpar_cache()
            st.rerun()

        if st.button("🚪 Sair", use_container_width=True):
            log_async("LOGOUT", "usuarios", dados_novos={"email": usuario["email"]})
            processar_logs_pendentes()
            fazer_logout()
            st.rerun()

    # ============================================
    # TABS POR ROLE
    # ============================================
    if is_admin():
        tabs = st.tabs([
            "📅 Escala",
            "👥 Trabalhadores",
            "⚠️ Ocorrências",
            "📆 Dias Especiais",
            "📊 Relatórios",
            "🔐 Usuários",
            "📝 Logs",
        ])
        (tab_escala, tab_trab, tab_ocorr, tab_dias,
         tab_rel, tab_users, tab_logs) = tabs

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
        with tab_users:
            aba_usuarios()
        with tab_logs:
            aba_logs()

    elif is_editor():
        # EDITOR: vê Escala, Dias Especiais, Atos Normativos e Relatórios
        tabs = st.tabs([
            "📅 Escala",
            "📆 Dias Especiais",
            "📊 Relatórios",
        ])
        tab_escala, tab_dias, tab_rel = tabs

        with tab_escala:
            aba_escala()
        with tab_dias:
            aba_dias_especiais()
        with tab_rel:
            st.info("Em breve (Fase 3)")

    else:
        # VIEWER: vê apenas Escala e Relatórios
        tabs = st.tabs(["📅 Escala", "📊 Relatórios"])
        tab_escala, tab_rel = tabs

        with tab_escala:
            aba_escala()
        with tab_rel:
            st.info("Em breve (Fase 3)")


if __name__ == "__main__":
    main()