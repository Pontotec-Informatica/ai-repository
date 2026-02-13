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
    st.error("Configuração pendente nos Secrets.")
    st.stop()

# --- ESTADO DA SESSÃO ---
if "historico_roteiro" not in st.session_state:
    st.session_state.historico_roteiro = None
if "link_whatsapp" not in st.session_state:
    st.session_state.link_whatsapp = None

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
            if place.get('user_ratings_total', 0) < 300: return None
            cidade_alvo = cidade_usuario.split(',')[0].strip().lower()
            if cidade_alvo not in place.get('formatted_address', '').lower(): return None
            
            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": url}
    except: return None
    return None

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# 1. PLANEJAMENTO
with st.expander("📝 Planejar ou Ver Configurações", expanded=st.session_state.historico_roteiro is None):
    cidade_input = st.text_input("Cidade:", placeholder="Piracicaba, SP", key="cidade_mem")
    tipo_op = st.radio("Duração:", ["Horas", "Dias"], horizontal=True, key="tipo_mem")
    
    c1, c2 = st.columns(2)
    with c1:
        duracao_val = st.number_input("Tempo:", 1, 30, key="dur_mem")
        veiculo = st.selectbox("Transporte:", ["Carro", "A pé", "Uber", "Público"], key="trans_mem")
    with c2:
        grupo = st.selectbox("Com quem?", ["Sozinho", "Casal", "Família", "Amigos"], key="grp_mem")
        orcamento = st.select_slider("Orçamento:", options=["Econômico", "Médio", "Luxo"], key="orc_mem")
    
    pet = st.toggle("Pet Friendly? 🐾", key="pet_mem")
    vibe = st.multiselect("Vibe:", ["Gastronomia", "Natureza", "História", "Cultura", "Lazer"], key="vibe_mem")
    pedidos_input = st.text_area("Pedidos específicos:", key="ped_mem")

    if st.button("🚀 Gerar Roteiro Inicial"):
        st.session_state.trigger_ai = "gerar"

# 2. ÁREA DE AJUSTE (Só aparece se já houver roteiro)
if st.session_state.historico_roteiro:
    st.markdown("---")
    st.markdown(st.session_state.historico_roteiro)
    
    st.markdown("### 🛠️ Ajustar este roteiro")
    txt_ajuste = st.text_area("O que deseja mudar?", placeholder="Ex: Troque o café da manhã...", key="input_ajuste")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        if st.button("🔄 Aplicar Ajuste"):
            st.session_state.trigger_ai = "ajustar"
    with col_a2:
        if st.button("🗑️ Reiniciar Tudo"):
            # Limpeza segura que não quebra o Streamlit
            for key in ["historico_roteiro", "link_whatsapp", "input_ajuste"]:
                if key in st.session_state: st.session_state[key] = None
            st.rerun()

# 3. LÓGICA DE IA
if st.session_state.get("trigger_ai"):
    with st.spinner('Processando...'):
        modo = st.session_state.trigger_ai
        ajuste_texto = st.session_state.get("input_ajuste", "") if modo == "ajustar" else ""
        
        contexto = f"\nROTEIRO ATUAL:\n{st.session_state.historico_roteiro}" if modo == "ajustar" else ""
        
        sys_msg = f"Você é um guia expert em {st.session_state.cidade_mem}. Use **Local** para nomes. Só locais com +300 avaliações."
        user_msg = f"Ajuste: {ajuste_texto}. Pedidos Iniciais: {st.session_state.ped_mem}. Contexto: {st.session_state.dur_mem} {st.session_state.tipo_mem}. {contexto}"

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.2
        )
        
        res_ia = completion.choices[0].message.content
        locais_ia = re.findall(r"\*\*(.*?)\*\*", res_ia)
        
        final_txt = res_ia
        processados = set()
        for loc in locais_ia:
            if loc not in processados:
                info = buscar_detalhes_google(loc, st.session_state.cidade_mem)
                if info:
                    final_txt = final_txt.replace(f"**{loc}**", f"**{loc}** [📍]({info['url']})", 1)
                    processados.add(loc)
                else:
                    linhas = final_txt.split('\n')
                    final_txt = '\n'.join([l for l in linhas if f"**{loc}**" not in l])
        
        st.session_state.historico_roteiro = final_txt
        
        # Salvar no Banco para Gerar Link de WhatsApp
        try:
            db_res = supabase.table("roteiros").insert({"cidade": st.session_state.cidade_mem, "conteudo": final_txt}).execute()
            if db_res.data:
                id_roteiro = db_res.data[0]['id']
                st.session_state.link_whatsapp = f"https://nomadia.streamlit.app?roteiro_id={id_roteiro}"
        except: pass
        
        st.session_state.trigger_ai = None # Reseta o gatilho
        st.rerun()

# 4. BOTÃO WHATSAPP (Sempre visível se o link existir)
if st.session_state.link_whatsapp:
    st.markdown("---")
    msg_wpp = urllib.parse.quote(f"Olha o roteiro que a NomadIA gerou para {st.session_state.cidade_mem}: {st.session_state.link_whatsapp}")
    st.link_button("📲 Compartilhar no WhatsApp", f"https://api.whatsapp.com/send?text={msg_wpp}")

st.markdown("<br><hr><center><small>NomadIA Pro v4.3</small></center>", unsafe_allow_html=True)
