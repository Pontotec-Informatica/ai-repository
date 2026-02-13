import streamlit as st
from openai import OpenAI
import urllib.parse
from datetime import datetime
import requests
import pytz
from supabase import create_client, Client

# ---------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------
st.set_page_config(page_title="NomadAI Pro", page_icon="📍", layout="centered")

# ---------------------------------
# SUPABASE
# ---------------------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------
# CAPTURA CALLBACK DO GOOGLE LOGIN
# ---------------------------------
query_params = st.query_params

if "code" in query_params:
    try:
        supabase.auth.exchange_code_for_session(
            {"auth_code": query_params["code"]}
        )
        st.query_params.clear()
        st.rerun()
    except:
        st.error("Erro ao validar login")

# recupera sessão ativa
session = supabase.auth.get_session()

if session and session.session:
    st.session_state["user"] = session.session.user.email

# ---------------------------------
# TELA LOGIN
# ---------------------------------
if "user" not in st.session_state:

    st.title("🚐 NomadAI")
    st.subheader("Seu copiloto inteligente de viagem")

    if st.button("🔵 Entrar com Google"):
        auth_url = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://nomadia.streamlit.app"
            }
        })
        st.link_button("👉 Clique aqui para fazer login", auth_url.url)

    st.stop()

# ---------------------------------
# SIDEBAR USUÁRIO
# ---------------------------------
st.sidebar.success(f"✅ Logado como\n{st.session_state['user']}")

if st.sidebar.button("Sair"):
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()

# ---------------------------------
# ESTILO
# ---------------------------------
st.markdown("""
<style>
.main { max-width: 500px; margin: 0 auto; }
.stButton>button { width: 100%; border-radius: 20px; background-color: #007BFF; color: white; font-weight: bold; height: 3em; }
.premium-box { background-color: #f0f2f6; padding: 20px; border-radius: 15px; border: 1px solid #007BFF; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------
def get_weather(city):
    try:
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=5)
        data = response.json()
        temp = data['current_condition'][0]['temp_C']
        desc = data['current_condition'][0]['lang_pt'][0]['value'] if 'lang_pt' in data['current_condition'][0] else data['current_condition'][0]['weatherDesc'][0]['value']
        return f"{temp}°C, {desc}"
    except:
        return "Clima não disponível"

def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

# ---------------------------------
# OPENAI
# ---------------------------------
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------------------------------
# INTERFACE
# ---------------------------------
st.title("📍 NomadAI Pro")
st.subheader("Seu guia logístico inteligente")

cidade = st.text_input("Onde você está ou para onde vai?", placeholder="Ex: Paraty, RJ")

agora = get_brasilia_time()
hora_atual = agora.strftime("%H:%M")

tipo_roteiro = st.radio("O que você precisa?", ["Roteiro Rápido (Hoje)", "Planejamento de Vários Dias"])

col1, col2 = st.columns(2)

with col1:
    if tipo_roteiro == "Roteiro Rápido (Hoje)":
        duracao = st.number_input("Duração (em horas)", 1, 12, 4)
        unidade = "horas"
    else:
        duracao = st.number_input("Duração (em dias)", 2, 30, 3)
        unidade = "dias"

    veiculo = st.selectbox("Veículo", ["Carro", "Motorhome", "Van/Kombi", "A pé"])

with col2:
    grupo = st.selectbox("Grupo", ["Sozinho", "Casal", "Família (Crianças)", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

pet = st.toggle("Levando Pet? 🐾")
vibe = st.multiselect("Vibe do passeio", ["Natureza", "História", "Gastronomia", "Wi-Fi", "Praia"])
pedidos = st.text_area("Pedidos específicos?")
cupom = st.text_input("Código de parceiro (Opcional)")

# ---------------------------------
# GERAR ROTEIRO
# ---------------------------------
if st.button("Gerar Roteiro"):

    if not cidade:
        st.warning("Informe a cidade.")
        st.stop()

    is_premium = (tipo_roteiro == "Planejamento de Vários Dias") or (duracao > 6)
    liberado = (cupom.lower() == "tripfree") if cupom else not is_premium

    if not liberado:
        st.markdown(f"""
        <div class="premium-box">
            <h4>🚀 Roteiro Premium</h4>
            <p>Planos de {duracao} {unidade} exigem curadoria profunda.</p>
            <p><b>Valor: R$ 9,90</b></p>
        </div>
        """, unsafe_allow_html=True)

        st.link_button("💳 Desbloquear agora", "https://seu-link-de-pagamento.com")
        st.stop()

    with st.spinner("Planejando..."):

        clima = get_weather(cidade)

        prompt_text = f"""
Cidade: {cidade}
Duração: {duracao} {unidade}
Clima: {clima}
Grupo: {grupo}
Pet: {pet}
Veículo: {veiculo}
Vibe: {vibe}
Pedidos: {pedidos}
Horário atual: {hora_atual}
"""

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Você é um especialista em roteiros logísticos, evitando locais perigosos ou impróprios para motorhome e respeitando orçamento."
                },
                {"role": "user", "content": prompt_text}
            ]
        )

        resposta = completion.choices[0].message.content

        st.success("Pronto!")
        st.info(f"☀️ {clima} | 🕒 {hora_atual}")
        st.markdown(resposta)

        link_wa = f"https://api.whatsapp.com/send?text={urllib.parse.quote(resposta[:500])}"
        st.link_button("📲 Enviar para WhatsApp", link_wa)

st.markdown("<br><hr><center><small>NomadAI Pro v2.1</small></center>", unsafe_allow_html=True)
