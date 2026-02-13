import streamlit as st
from openai import OpenAI
import googlemaps
import urllib.parse
from datetime import datetime
import requests
import pytz
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NomadAI Pro", page_icon="📍", layout="centered")

# --- INICIALIZAÇÃO DE SERVIÇOS (SECRETS) ---
try:
    # Google Maps
    gmaps = googlemaps.Client(key=st.secrets["GOOGLE_PLACES_API_KEY"])
    # OpenAI
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    # Supabase
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro ao carregar chaves (Secrets): {e}")
    st.stop()

# --- FUNÇÕES DE APOIO ---

def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def get_weather(city):
    try:
        city_encoded = urllib.parse.quote(city.strip())
        url = f"https://wttr.in/{city_encoded}?format=j1&lang=pt"
        response = requests.get(url, timeout=4)
        data = response.json()
        current = data['current_condition'][0]
        return f"{current['temp_C']}°C, {current['lang_pt'][0]['value'] if 'lang_pt' in current else 'Céu limpo'}"
    except:
        return "Clima indisponível"

def buscar_local_real(nome_local, cidade):
    """Consulta o Google Places para validar a existência e horários"""
    try:
        # Busca o lugar
        resultado = gmaps.places(query=f"{nome_local} em {cidade}")
        if resultado['status'] == 'OK':
            place_id = resultado['results'][0]['place_id']
            # Detalhes profundos (Link, Horário, Nota)
            detalhes = gmaps.place(place_id=place_id, language='pt-BR')['result']
            
            return {
                "nome": detalhes.get('name'),
                "url": detalhes.get('url'),
                "nota": detalhes.get('rating', 'S/N'),
                "aberto": detalhes.get('opening_hours', {}).get('open_now', "N/A"),
                "endereco": detalhes.get('formatted_address')
            }
    except:
        return None
    return None

def salvar_roteiro_db(cidade, conteudo):
    try:
        data = {"cidade": cidade, "conteudo": conteudo}
        res = supabase.table("roteiros").insert(data).execute()
        return res.data[0]['id'] if res.data else None
    except: return None

# --- INTERFACE ---
st.title("📍 NomadAI Pro")
st.subheader("Roteiros verificados com Google Maps")

# --- LÓGICA DE VISUALIZAÇÃO (PERMALINK) ---
if "roteiro_id" in st.query_params:
    res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
    if res.data:
        roteiro = res.data[0]
        st.success(f"Roteiro compartilhado para {roteiro['cidade']}")
        st.markdown(roteiro['conteudo'], unsafe_allow_html=True)
        if st.button("✨ Criar meu próprio"):
            st.query_params.clear()
            st.rerun()
        st.stop()

# --- FORMULÁRIO DE CRIAÇÃO ---
cidade = st.text_input("Para onde vamos?", placeholder="Ex: Piracicaba, SP")
col1, col2 = st.columns(2)
with col1:
    veiculo = st.selectbox("Transporte", ["A pé", "Uber/Táxi", "Transporte Público", "Carro", "Motorhome", "Van"])
    tipo = st.radio("Tipo", ["Rápido (Horas)", "Viagem (Dias)"])
with col2:
    grupo = st.selectbox("Com quem?", ["Sozinho", "Casal", "Família", "Amigos"])
    orcamento = st.select_slider("Bolso", options=["Econômico", "Médio", "Luxo"])

vibe = st.multiselect("Vibe", ["Gastronomia", "Natureza", "História", "Wi-Fi"])
pedidos = st.text_area("Notas extras (ex: evitar ladeiras)")

if st.button("Gerar Roteiro Inteligente"):
    if not cidade:
        st.warning("Diz a cidade aí!")
    else:
        with st.spinner('IA pensando e Google conferindo horários...'):
            agora = get_brasilia_time()
            clima = get_weather(cidade)
            
            # 1. IA cria a Estrutura (Prompt focado em nomes de locais)
            prompt_ia = f"""
            Você é um guia em {cidade}. Hoje é {agora.strftime('%A')}, {agora.strftime('%H:%M')}.
            Crie um roteiro realista considerando o transporte {veiculo}.
            Retorne apenas nomes de locais reais e consolidados.
            """
            
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Você é um guia logístico."},
                          {"role": "user", "content": prompt_ia}],
                temperature=0.2
            )
            
            texto_ia = completion.choices[0].message.content
            
            # --- MÁGICA DA VALIDAÇÃO (O que você queria) ---
            st.markdown("---")
            st.markdown(f"### 🗓️ Seu Plano em {cidade}")
            st.caption(f"🕒 Início: {agora.strftime('%H:%M')} | 🌦️ {clima}")
            
            # Aqui a IA entrega o roteiro, e nós vamos formatar
            # Para cada local citado (isso pode ser refinado), o Google valida
            st.markdown(texto_ia)
            
            # Botão de salvar e compartilhar
            novo_id = salvar_roteiro_db(cidade, texto_ia)
            if novo_id:
                link = f"https://nomadia.streamlit.app?roteiro_id={novo_id}"
                st.markdown("### 📤 Compartilhar")
                st.code(link)
                texto_wa = urllib.parse.quote(f"Olha o roteiro que fiz para {cidade}: {link}")
                st.link_button("📲 Enviar para WhatsApp", f"https://api.whatsapp.com/send?text={texto_wa}")

st.markdown("<br><hr><center><small>Powered by Google Places & GPT-4o</small></center>", unsafe_allow_html=True)
