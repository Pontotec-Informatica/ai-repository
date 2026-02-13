import streamlit as st
from openai import OpenAI
import urllib.parse
from datetime import datetime
import requests
import pytz

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NomadAI Pro", page_icon="📍", layout="centered")

st.markdown("""
    <style>
    .main { max-width: 500px; margin: 0 auto; }
    .stButton>button { width: 100%; border-radius: 20px; background-color: #007BFF; color: white; font-weight: bold; height: 3em; }
    .premium-box { background-color: #f0f2f6; padding: 20px; border-radius: 15px; border: 1px solid #007BFF; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---
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

# --- SETUP IA ---
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("Configure sua API Key nos Secrets do Streamlit.")
    st.stop()

# --- INTERFACE ---
st.title("📍 NomadAI Pro")
st.subheader("Seu guia logístico inteligente")

cidade = st.text_input("Onde você está ou para onde vai?", placeholder="Ex: Paraty, RJ")

# Captura contexto temporal
agora = get_brasilia_time()
hora_atual = agora.strftime("%H:%M")
data_atual = agora.strftime("%d/%m/%Y")

# Estratégia de Negócio: Seleção de Tipo de Roteiro
tipo_roteiro = st.radio("O que você precisa?", ["Roteiro Rápido (Hoje)", "Planejamento de Vários Dias"])

col1, col2 = st.columns(2)
with col1:
    if tipo_roteiro == "Roteiro Rápido (Hoje)":
        duracao = st.number_input("Duração (em horas)", min_value=1, max_value=12, value=4)
        unidade = "horas"
    else:
        duracao = st.number_input("Duração (em dias)", min_value=2, max_value=30, value=3)
        unidade = "dias"
    
    veiculo = st.selectbox("Veículo", ["Carro", "Motorhome", "Van/Kombi", "A pé"])

with col2:
    grupo = st.selectbox("Grupo", ["Sozinho", "Casal", "Família (Crianças)", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

pet = st.toggle("Levando Pet? 🐾")
vibe = st.multiselect("Vibe do passeio", ["Natureza", "História/Cultura", "Gastronomia", "Trabalho/Wi-Fi", "Praia"])
pedidos = st.text_area("Pedidos específicos (ex: evitar ladeiras, vegetariano, trilhas leves)")

# --- LÓGICA DE PROCESSAMENTO ---
if st.button("Gerar Roteiro"):
    if not cidade:
        st.warning("Por favor, informe a cidade.")
    else:
        # Lógica de Paywall (Modelo de Negócio)
        # Exemplo: Mais de 6 horas ou Vários Dias são pagos
        is_premium = tipo_roteiro == "Planejamento de Vários Dias" or (tipo_roteiro == "Roteiro Rápido (Hoje)" and duracao > 6)
        
        # Simulação de verificação de cupom (Para parcerias com pousadas)
        # Se você passar ?pousada=nomedapousada na URL, poderia liberar aqui.
        cupom = st.text_input("Possui código de parceiro/pousada? (Opcional)")
        liberado = True if cupom.lower() == "tripfree" else not is_premium # "tripfree" é um exemplo de cupom

        if not liberado:
            st.markdown(f"""
            <div class="premium-box">
                <h4>🚀 Roteiro Premium Detectado</h4>
                <p>Planejamentos de <b>{duracao} {unidade}</b> exigem um nível maior de processamento logístico.</p>
                <p><b>Valor: R$ 9,90</b></p>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("💳 Desbloquear agora no Stripe", "https://seu-link-de-pagamento-aqui.com")
            st.info("Dica: Use o cupom 'tripfree' para testar a liberação agora.")
        else:
