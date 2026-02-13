import streamlit as st
from openai import OpenAI
import urllib.parse
from datetime import datetime
import requests
import pytz

# 1. Configuração da Página
st.set_page_config(page_title="NomadAI Pro", page_icon="📍", layout="centered")

# Estilo para Mobile
st.markdown("""
    <style>
    .main { max-width: 500px; margin: 0 auto; }
    .stButton>button { width: 100%; border-radius: 20px; background-color: #007BFF; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções Auxiliares (Clima e Hora de Brasília)
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

# 3. Cabeçalho e Setup
st.title("📍 NomadAI Pro")
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("Configure sua API Key nos Secrets.")
    st.stop()

# 4. Interface de Entrada
cidade = st.text_input("Onde você está?", placeholder="Ex: Paraty, RJ")

# Captura hora e data de Brasília
agora = get_brasilia_time()
hora_atual = agora.strftime("%H:%M")
data_atual = agora.strftime("%d/%m/%Y")

col1, col2 = st.columns(2)
with col1:
    veiculo = st.selectbox("Veículo", ["Carro", "Motorhome", "Mochileiro"])
    grupo = st.selectbox("Grupo", ["Sozinho", "Casal", "Família", "Amigos"])
with col2:
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])
    # SELETOR DE DURAÇÃO
    duracao = st.number_input("Duração (horas)", min_value=1, max_value=24, value=4)

vibe = st.multiselect("Vibe", ["Natureza", "Cultura", "Trabalho", "Gastronomia", "Praia"])
pet = st.toggle("Com Pet? 🐾")
pedidos = st.text_area("Pedidos específicos (ex: evitar ladeiras, wi-fi forte)")

# 5. Geração do Roteiro
if st.button("Gerar Roteiro Inteligente"):
    if not cidade:
        st.warning("Informe a cidade.")
    else:
        with st.spinner('Checando o tempo e planejando seu tempo...'):
            clima = get_weather(cidade)
            
            prompt = f"""
            Você é um guia local expert. Gere um roteiro baseado nestes dados reais:
            
            CONTEXTO TEMPORAL E CLIMÁTICO:
            - Cidade: {cidade}
            - Data: {data_atual}
            - Hora de Início: {hora_atual}
            - Duração Total: {duracao} horas
            - Clima agora: {clima}

            PERFIL DO VIAJANTE:
            - Veículo: {veiculo}. Grupo: {grupo}. Pet: {pet}. Orçamento: {orcamento}.
            - Vibe: {vibe}. Pedidos: {pedidos}.

            REGRAS DO ROTEIRO:
            1. O roteiro deve cobrir exatamente {duracao} horas, começando às {hora_atual}.
            2. Se o clima for de chuva, sugira apenas atividades em locais cobertos.
            3. Se for noite, foque em segurança e vida noturna.
            4. Se for Motorhome, garanta que o tempo de deslocamento e estacionamento seja realista.
            5. Formate com horários (ex: {hora_atual} - 10:30) e emojis.
            """
            
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Você é um guia de viagem ultra-preciso com horários e logística."},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                resposta = completion.choices[0].message.content
                
                # Exibição
                st.info(f"🕒 Gerado para início às {hora_atual} | Tempo total: {duracao}h | Clima: {clima}")
                st.markdown(resposta)
                
                # Botão WhatsApp
                link_wa = f"https://api.whatsapp.com/send?text={urllib.parse.quote(resposta)}"
                st.link_button("📲 Enviar para o WhatsApp", link_wa)
                st.balloons()
            except Exception as e:
                st.error(f"Erro na API: {e}")

st.markdown("<br><hr><center><small>NomadAI v1.2 | Horário de Brasília</small></center>", unsafe_allow_html=True)
