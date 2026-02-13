import streamlit as st
from openai import OpenAI
import googlemaps
import urllib.parse
from datetime import datetime
import requests
import pytz
import re
from supabase import create_client, Client

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="NomadIA Pro", page_icon="📍", layout="centered")

# --- SERVIÇOS ---
try:
    gmaps = googlemaps.Client(key=st.secrets["GOOGLE_PLACES_API_KEY"])
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error("Erro nas chaves de API.")
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO (MEMÓRIA) ---
if "historico_roteiro" not in st.session_state:
    st.session_state.historico_roteiro = None

# --- FUNÇÕES ---
def buscar_detalhes_google(nome_local, cidade_usuario):
    try:
        query = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query, input_type="textquery",
            fields=["name", "formatted_address", "place_id", "types", "user_ratings_total"],
            language="pt-BR"
        )
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            # FILTRO DE 300 AVALIAÇÕES
            if place.get('user_ratings_total', 0) < 300: return None
            
            cidade_alvo = cidade_usuario.split(',')[0].strip().lower()
            if cidade_alvo not in place.get('formatted_address', '').lower(): return None
            
            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": url}
    except: return None
    return None

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# FORMULÁRIO COM PERSISTÊNCIA (Usando chaves no session_state)
with st.expander("⚙️ Configurações da Viagem", expanded=st.session_state.historico_roteiro is None):
    cidade_input = st.text_input("Cidade:", placeholder="Piracicaba, SP", key="cidade_memoria")
    tipo_op = st.radio("Duração:", ["Horas", "Dias"], horizontal=True, key="tipo_memoria")
    
    col1, col2 = st.columns(2)
    with col1:
        duracao_val = st.number_input("Tempo:", 1, 30, key="duracao_memoria")
        veiculo = st.selectbox("Transporte:", ["Carro", "A pé", "Uber", "Público"], key="transporte_memoria")
    with col2:
        grupo = st.selectbox("Com quem?", ["Sozinho", "Casal", "Família", "Amigos"], key="grupo_memoria")
        orcamento = st.select_slider("Orçamento:", options=["Econômico", "Médio", "Luxo"], key="orc_memoria")
    
    pet = st.toggle("Pet Friendly? 🐾", key="pet_memoria")
    vibe = st.multiselect("Vibe:", ["Gastronomia", "Compras","Natureza", "História", "Cultura", "Lazer"], key="vibe_memoria")

instrucao_usuario = st.text_area("O que deseja ajustar no roteiro?", placeholder="Ex: Mude o restaurante / Foque em locais históricos")

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    gerar = st.button("🚀 Gerar / Aplicar Ajuste")
with col_btn2:
    if st.button("🗑️ Limpar Tudo"):
        for key in st.session_state.keys(): del st.session_state[key]
        st.rerun()

if gerar:
    if not st.session_state.cidade_memoria:
        st.warning("Diga a cidade!")
    else:
        with st.spinner('Refinando locais populares...'):
            contexto_anterior = f"\nROTEIRO ATUAL:\n{st.session_state.historico_roteiro}" if st.session_state.historico_roteiro else ""
            
            system_prompt = f"""Você é um guia expert em {st.session_state.cidade_memoria}. 
            REGRAS: 1. Só locais famosos (+300 avaliações). 2. Mantenha o roteiro atual e mude APENAS o solicitado. 
            3. Use nomes em negrito: **Local**."""

            user_msg = f"{instrucao_usuario}\nContexto: {st.session_state.duracao_memoria} {st.session_state.tipo_memoria}, Pet: {st.session_state.pet_memoria}, Orçamento: {st.session_state.orc_memoria}. {contexto_anterior}"

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
                temperature=0.2
            )
            
            texto_ia = completion.choices[0].message.content
            locais = re.findall(r"\*\*(.*?)\*\*", texto_ia)
            
            roteiro_validado = texto_ia
            for loc in set(locais):
                info = buscar_detalhes_google(loc, st.session_state.cidade_memoria)
                if info:
                    roteiro_validado = roteiro_validado.replace(f"**{loc}**", f"**{loc}** [📍]({info['url']})")
                else:
                    linhas = roteiro_validado.split('\n')
                    roteiro_validado = '\n'.join([l for l in linhas if f"**{loc}**" not in l])

            st.session_state.historico_roteiro = roteiro_validado
            st.rerun()

if st.session_state.historico_roteiro:
    st.markdown("---")
    st.markdown(st.session_state.historico_roteiro)
    
    # Compartilhamento
    try:
        res = supabase.table("roteiros").insert({"cidade": st.session_state.cidade_memoria, "conteudo": st.session_state.historico_roteiro}).execute()
        link = f"https://nomadia.streamlit.app?roteiro_id={res.data[0]['id']}"
        st.code(link)
        st.link_button("📲 Enviar WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link)}")
    except: pass

st.markdown("<br><hr><center><small>NomadIA Pro v4.1 | Memória Persistente</small></center>", unsafe_allow_html=True)
