import streamlit as st
from supabase import create_client, Client
from openai import OpenAI

# ---------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------
st.set_page_config(
    page_title="NomadAI",
    page_icon="🧭",
    layout="wide"
)

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------------------------------------------
# FUNÇÃO REDIRECT (ESSENCIAL NO STREAMLIT)
# ---------------------------------------------------
def redirect(url: str):
    st.markdown(
        f"""
        <meta http-equiv="refresh" content="0; url={url}">
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------
# HEADER
# ---------------------------------------------------
st.title("🧭 NomadAI")
st.caption("Roteiros inteligentes para viajantes e hosts")

# ---------------------------------------------------
# VERIFICAR SESSÃO
# ---------------------------------------------------
session = supabase.auth.get_session()

# ---------------------------------------------------
# LOGIN
# ---------------------------------------------------
if not session or not session.session:

    st.markdown("### 🚐 Entre para usar o NomadAI")

    if st.button("🔐 Entrar com Google", use_container_width=True):

        data = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://nomadia.streamlit.app"
            }
        })

        # 🔥 AQUI ESTAVA O PROBLEMA
        redirect(data.url)

    st.stop()

# ---------------------------------------------------
# USUÁRIO LOGADO
# ---------------------------------------------------
user_email = session.session.user.email

col1, col2 = st.columns([4,1])

with col1:
    st.success(f"✅ Logado como {user_email}")

with col2:
    if st.button("Sair"):
        supabase.auth.sign_out()
        st.rerun()

st.divider()

# ---------------------------------------------------
# FORM NOMADAI
# ---------------------------------------------------
st.subheader("✨ Criar roteiro")

col1, col2 = st.columns(2)

with col1:
    localizacao = st.text_input("📍 Localização")
    vibe = st.selectbox(
        "🌴 Vibe",
        ["Relax", "Aventura", "Gastronomia", "Natureza", "Romântico"]
    )

with col2:
    orcamento = st.selectbox(
        "💰 Orçamento",
        ["Econômico", "Médio", "Premium"]
    )

    veiculo = st.selectbox(
        "🚐 Veículo",
        ["Carro", "Motorhome", "Van Camper", "Mochileiro"]
    )

gerar = st.button("⚡ Gerar roteiro")

# ---------------------------------------------------
# IA
# ---------------------------------------------------
if gerar and localizacao:

    with st.spinner("Planejando..."):

        prompt = f"""
Você é especialista em viagens on-the-go.

Local: {localizacao}
Vibe: {vibe}
Orçamento: {orcamento}
Veículo: {veiculo}

Regras:
- Evitar roubadas logísticas
- Motorhome precisa estacionamento seguro
- Sugestões até 20km
- Objetivo e prático
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Guia especialista em logística de viagem."},
                {"role": "user", "content": prompt}
            ]
        )

        roteiro = response.choices[0].message.content

        st.markdown("## 🗺️ Seu roteiro")
        st.write(roteiro)

elif gerar:
    st.warning("Informe a localização.")
