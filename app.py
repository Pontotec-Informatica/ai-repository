import streamlit as st
from supabase import create_client, Client
from openai import OpenAI

# ---------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------
st.set_page_config(
    page_title="NomadAI",
    page_icon="🧭",
    layout="wide"
)

# ---------------------------------------------------
# SECRETS (Streamlit Cloud)
# ---------------------------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

# ---------------------------------------------------
# CLIENTES
# ---------------------------------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

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
# TELA DE LOGIN
# ---------------------------------------------------
if not session or not session.session:

    st.markdown("### 🚐 Entre para gerar roteiros inteligentes")

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        if st.button("🔐 Entrar com Google", use_container_width=True):
            supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": "https://nomadia.streamlit.app"
                }
            })

    st.stop()

# ---------------------------------------------------
# USUÁRIO LOGADO
# ---------------------------------------------------
user_email = session.session.user.email

colA, colB = st.columns([4,1])

with colA:
    st.success(f"✅ Logado como: {user_email}")

with colB:
    if st.button("Sair"):
        supabase.auth.sign_out()
        st.rerun()

st.divider()

# ---------------------------------------------------
# FORMULÁRIO NOMADAI
# ---------------------------------------------------
st.subheader("✨ Criar roteiro agora")

col1, col2 = st.columns(2)

with col1:
    localizacao = st.text_input("📍 Localização atual")
    vibe = st.selectbox(
        "🌴 Vibe da viagem",
        ["Relax", "Aventura", "Gastronomia", "Natureza", "Romântico"]
    )

with col2:
    orcamento = st.selectbox(
        "💰 Orçamento",
        ["Econômico", "Médio", "Premium"]
    )

    veiculo = st.selectbox(
        "🚐 Tipo de veículo",
        ["Carro", "Motorhome", "Van Camper", "Mochileiro"]
    )

gerar = st.button("⚡ Gerar roteiro")

# ---------------------------------------------------
# CHAMADA OPENAI
# ---------------------------------------------------
if gerar and localizacao:

    with st.spinner("Planejando experiência..."):

        prompt = f"""
Você é um especialista em viagens on-the-go.

Crie um roteiro imediato para:
Localização: {localizacao}
Vibe: {vibe}
Orçamento: {orcamento}
Veículo: {veiculo}

REGRAS IMPORTANTES:
- Evitar locais perigosos ou inviáveis logisticamente
- Se for motorhome ou van, sugerir estacionamento possível
- Priorizar custo compatível com orçamento
- Sugerir atividades próximas (até 20km)
- Resposta prática e objetiva
"""

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você cria roteiros inteligentes e seguros."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        roteiro = response.choices[0].message.content

        st.markdown("## 🗺️ Seu roteiro agora")
        st.write(roteiro)

elif gerar:
    st.warning("Informe a localização primeiro.")
