import streamlit as st
from openai import OpenAI
import urllib.parse

# Configuração visual do Web App
st.set_page_config(page_title="SeuGuia AI", page_icon="📍", layout="centered")

# Estilo para parecer um App de celular
st.markdown("""
    <style>
    .main { max-width: 500px; margin: 0 auto; }
    .stButton>button { 
        width: 100%; 
        border-radius: 20px; 
        height: 3em; 
        background-color: #007BFF; 
        color: white; 
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📍 Guia Local Inteligente")
st.caption("Roteiros logísticos para viajantes e motorhomes.")

# A chave da API virá das configurações do Streamlit Cloud (Segurança)
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("Erro de configuração: API Key não encontrada.")
    st.stop()

# Campos de entrada
cidade = st.text_input("Onde você está?", placeholder="Ex: Paraty, RJ")
veiculo = st.selectbox("Seu perfil/veículo", ["Carro de passeio", "Motorhome Grande", "Van/Kombi", "Mochileiro (a pé)"])
vibe = st.multiselect("O que busca hoje?", ["Natureza", "Trabalho (Starlink)", "Gastronomia", "História", "Praia"])
orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

if st.button("Gerar Roteiro Inteligente"):
    if not cidade:
        st.warning("Por favor, digite uma cidade.")
    else:
        with st.spinner('Analisando logística e locais...'):
            prompt = f"""
            Crie um roteiro de 4 horas em {cidade}. 
            Perfil: {veiculo}. Vibe: {vibe}. Orçamento: {orcamento}.
            FOCO LOGÍSTICO: Se for Motorhome/Van, indique locais com ruas largas e estacionamento fácil.
            Se for Trabalho, foque em locais com céu aberto para Starlink ou Wi-Fi estável.
            Responda em Markdown, use emojis e seja direto.
            """
            
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um guia de viagem expert em logística urbana e nomadismo digital."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            resposta = completion.choices[0].message.content
            st.markdown("---")
            st.markdown(resposta)

# Prepara a repostar para compartilhar no WhatsApp
texto_share = f"Veja o roteiro que o Travel-AI gerou para {cidade}:\n\n{resposta}"
link_whatsapp = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_share)}"

st.divider()
st.link_button("📲 Compartilhar no WhatsApp", link_whatsapp)

            st.balloons()

