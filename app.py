import streamlit as st
from openai import OpenAI
import googlemaps
import urllib.parse
from datetime import datetime
import requests
import pytz
import re
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NomadIA Pro", page_icon="📍", layout="centered")

# --- SERVIÇOS ---
try:
    gmaps = googlemaps.Client(key=st.secrets["GOOGLE_PLACES_API_KEY"])
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Erro de configuração. Verifique os Secrets.")
    st.stop()

# --- FUNÇÕES DE APOIO ---
def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def get_weather(city):
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=%t+%C"
        r = requests.get(url, timeout=5)
        return r.text if r.status_code == 200 else "Clima disponível no local"
    except: return "Clima disponível no local"

def buscar_detalhes_google(nome_local, cidade_usuario):
    """Valida o local e garante que ele pertence à cidade correta."""
    try:
        blacklist = ['dica', 'bairro', 'duração', 'horário', 'obs', 'nota', 'atenção']
        if nome_local.lower() in blacklist: return None
        
        query = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query, input_type="textquery",
            fields=["name", "formatted_address", "place_id", "types"],
            language="pt-BR"
        )
        
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            endereco = place.get('formatted_address', '').lower()
            cidade_alvo = cidade_usuario.split(',')[0].strip().lower()

            # Se o local não for na cidade, o NomadIA Pro ignora para evitar erros
            if cidade_alvo not in endereco: return None
            
            permitidos = ['park', 'restaurant', 'food', 'tourist_attraction', 'museum', 'cafe', 'bar', 'shopping_mall', 'point_of_interest']
            if not any(t in permitidos for t in place.get('types', [])): return None

            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": url}
    except: return None
    return None

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# LÓGICA DE COMPARTILHAMENTO
if "roteiro_id" in st.query_params:
    res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
    if res.data:
        st.success(f"Roteiro: {res.data[0]['cidade']}")
        st.markdown(res.data[0]['conteudo'])
        if st.button("✨ Criar meu próprio"):
            st.query_params.clear()
            st.rerun()
        st.stop()

# --- FORMULÁRIO COMPLETO (RESTAURADO) ---
cidade_input = st.text_input("Para onde vamos?", placeholder="Ex: Piracicaba, SP")
tipo_op = st.radio("Duração:", ["Horas", "Dias"], horizontal=True)

col1, col2 = st.columns(2)
with col1:
    duracao_val = st.number_input("Quanto tempo?", 1, 30, 4)
    unidade = "horas" if tipo_op == "Horas" else "dias"
    veiculo = st.selectbox("Transporte", ["Carro", "A pé", "Uber/Táxi", "Transporte Público", "Motorhome"])

with col2:
    grupo = st.selectbox("Com quem?", ["Sozinho", "Casal", "Família", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

st.markdown("---")
col_extra1, col_extra2 = st.columns(2)
with col_extra1:
    pet_friendly = st.toggle("Levando Pet? 🐾")
with col_extra2:
    vibe = st.multiselect("Vibe", ["Gastronomia", "Natureza", "História", "Cultura", "Lazer"])

pedidos = st.text_area("Pedidos específicos (Ex: evitar ladeiras, lugares românticos)")
cupom_input = st.text_input("Cupom de Desconto")

# --- GERAÇÃO DO ROTEIRO ---
if st.button("Gerar Roteiro Nomad
