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

# --- ESTADO DA SESSÃO ---
if "historico_roteiro" not in st.session_state:
    st.session_state.historico_roteiro = None

# --- FUNÇÕES ---
def buscar_detalhes_google(nome_local, cidade_usuario):
    try:
        query = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query, input_type="textquery",
            fields=["name", "formatted_address", "place_id", "user_ratings_total"],
            language="pt-BR"
        )
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            # FILTRO DE 300+ AVALIAÇÕES
            if place.get('user_ratings_total', 0) < 300: return None
            
            cidade_alvo = cidade_usuario.split(',')[0].strip().lower()
            if cidade_alvo not in place.get('formatted_address', '').lower(): return None
            
            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": url}
    except: return None
    return None

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# 1. FORMULÁRIO INICIAL (Sempre visível ou em expander se já tiver roteiro)
is_primeira_vez = st.session_state.historico_roteiro is None

with st.expander("📝 Planejar Novo Roteiro", expanded=is_primeira_vez):
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
    vibe = st.multiselect("Vibe:", ["Gastronomia", "Natureza", "História", "Cultura", "Lazer"], key="vibe_memoria")
    pedidos_especificos = st.text_area("Pedidos específicos:", placeholder="Ex: Evitar ladeiras, focar em cafés...", key="pedidos_memoria")

    if st.button("🚀 Gerar Roteiro"):
        st.session_state.acao = "gerar"

# 2. LÓGICA DE PROCESSAMENTO
if "acao" in st.session_state and st.session_state.acao in ["gerar", "ajustar"]:
    with st.spinner('Validando locais populares e organizando rota...'):
        ajuste = st.session_state.get("texto_ajuste", "")
        contexto_anterior = f"\nROTEIRO ATUAL:\n{st.session_state.historico_roteiro}" if st.session_state.historico_roteiro else ""
        
        system_prompt = f"Você é um guia expert em {st.session_state.cidade_memoria}. Só indique locais famosos (+300 avaliações). Use nomes em negrito: **Local**."
        user_msg = f"Pedidos: {st.session_state.pedidos_memoria}. Ajuste atual: {ajuste}. Contexto: {st.session_state.duracao_memoria} {st.session_state.tipo_memoria}, Orçamento: {st.session_state.orc_memoria}. {contexto_anterior}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            temperature=0.2
        )
        
        texto_ia = completion.choices[0].message.content
        locais = re.findall(r"\*\*(.*?)\*\*", texto_ia)
        
        # LÓGICA DE LINK ÚNICO: Usamos um set para rastrear locais já linkados
        roteiro_validado = texto_ia
        locais_processados = set()
        
        for loc in locais:
            if loc not in locais_processados:
                info = buscar_detalhes_google(loc, st.session_state.cidade_memoria)
                if info:
                    # Substitui APENAS a primeira ocorrência pelo nome + link
                    roteiro_validado = roteiro_validado.replace(f"**{loc}**", f"**{loc}** [📍]({info['url']})", 1)
                    # Substitui as demais ocorrências apenas pelo nome em negrito (limpando possíveis duplicatas anteriores)
                    roteiro_validado = roteiro_validado.replace(f"**{loc}**", f"**{loc}**")
                    locais_processados.add(loc)
                else:
                    # Remove linhas de locais não validados
                    linhas = roteiro_validado.split('\n')
                    roteiro_validado = '\n'.join([l for l in linhas if f"**{loc}**" not in l])
        
        st.session_state.historico_roteiro = roteiro_validado
        del st.session_state.acao
        st.rerun()

# 3. EXIBIÇÃO DO ROTEIRO E ÁREA DE AJUSTE (Só aparece se já houver roteiro)
if st.session_state.historico_roteiro:
    st.markdown("---")
    st.markdown(st.session_state.historico_roteiro)
    
    st.markdown("### 🛠️ Gostaria de mudar algo?")
    txt_ajuste = st.text_area("Digite o que deseja ajustar (ex: 'Troque o jantar')", key="input_ajuste")
    
    col_a1, col_a2, col_a3 = st.columns([1,1,1])
    with col_a1:
        if st.button("🔄 Ajustar"):
            st.session_state.texto_ajuste = txt_ajuste
            st.session
