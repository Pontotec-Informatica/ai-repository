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
    st.error("Erro de configuração. Verifique as chaves de API nos Secrets.")
    st.stop()

# --- ESTADO DA SESSÃO (MEMÓRIA PARA AJUSTES) ---
if "historico_roteiro" not in st.session_state:
    st.session_state.historico_roteiro = None
if "cidade_atual" not in st.session_state:
    st.session_state.cidade_atual = ""

# --- FUNÇÕES DE APOIO ---
def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def buscar_detalhes_google(nome_local, cidade_usuario):
    """Busca local e valida relevância rigorosa (Mínimo 300 avaliações)"""
    try:
        # Filtro de termos que a IA pode negritar por engano
        blacklist = ['dica', 'bairro', 'duração', 'horário', 'obs', 'nota', 'atenção']
        if nome_local.lower() in blacklist: return None

        query = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query, input_type="textquery",
            fields=["name", "formatted_address", "place_id", "types", "user_ratings_total"],
            language="pt-BR"
        )
        
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            
            # --- FILTRO DE RELEVÂNCIA (300+ AVALIAÇÕES) ---
            avaliacoes = place.get('user_ratings_total', 0)
            if avaliacoes < 300: 
                return None

            # Validação Geográfica
            endereco = place.get('formatted_address', '').lower()
            cidade_alvo = cidade_usuario.split(',')[0].strip().lower()
            if cidade_alvo not in endereco: 
                return None
            
            # Filtro de Categoria (Turismo e Gastronomia)
            permitidos = ['park', 'restaurant', 'food', 'tourist_attraction', 'museum', 'cafe', 'bar', 'shopping_mall', 'point_of_interest']
            if not any(t in permitidos for t in place.get('types', [])): 
                return None

            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": url}
    except: return None
    return None

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# COMPARTILHAMENTO (Permalinks)
if "roteiro_id" in st.query_params:
    res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
    if res.data:
        st.success(f"Roteiro Carregado: {res.data[0]['cidade']}")
        st.markdown(res.data[0]['conteudo'])
        if st.button("✨ Criar Novo"):
            st.query_params.clear()
            st.rerun()
        st.stop()

# --- PAINEL DE CONFIGURAÇÃO ---
with st.expander("⚙️ Configurações da Viagem", expanded=st.session_state.historico_roteiro is None):
    cidade_input = st.text_input("Para qual cidade?", value=st.session_state.cidade_atual, placeholder="Ex: Piracicaba, SP")
    tipo_op = st.radio("Duração:", ["Horas", "Dias"], horizontal=True)
    
    col1, col2 = st.columns(2)
    with col1:
        duracao_val = st.number_input("Quanto tempo?", 1, 30, 4)
        veiculo = st.selectbox("Transporte", ["Carro", "A pé", "Uber/Táxi", "Transporte Público"])
    with col2:
        grupo = st.selectbox("Com quem?", ["Sozinho", "Casal", "Família", "Amigos"])
        orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])
    
    pet_friendly = st.toggle("Levando Pet? 🐾")
    vibe = st.multiselect("Vibe do Roteiro", ["Gastronomia", "Natureza", "História", "Cultura", "Lazer"])

# --- CAMPO DE AJUSTE DINÂMICO ---
instrucao_usuario = st.text_area("O que quer ver ou o que deseja ajustar?", 
                                placeholder="Ex: Sugira um roteiro clássico / Troque o almoço por um lugar de peixe...")

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    btn_gerar = st.button("🚀 Gerar / Ajustar Roteiro")
with col_btn2:
    if st.button("🗑️ Limpar e Reiniciar"):
        st.session_state.historico_roteiro = None
        st.session_state.cidade_atual = ""
        st.rerun()

# --- LÓGICA DE GERAÇÃO ---
if btn_gerar:
    if not cidade_input:
        st.warning("Informe a cidade primeiro.")
    else:
        with st.spinner('Refinando locais populares e otimizando rota...'):
            st.session_state.cidade_atual = cidade_input
            agora = get_brasilia_time()
            
            # MEMÓRIA: Se já houver roteiro, ele envia como contexto para a IA ajustar
            contexto_anterior = f"\nESTE É O ROTEIRO ATUAL (Ajuste-o conforme o pedido): \n{st.session_state.historico_roteiro}" if st.session_state.historico_roteiro else ""
            
            system_prompt = f"""
            Você é um guia local expert em {cidade_input}.
            Sua tarefa é criar ou ajustar um roteiro inteligente.
            REGRAS DE QUALIDADE:
            1. Sugira APENAS locais reais, famosos e tradicionais de {cidade_input}.
            2. Se houver um 'ROTEIRO ATUAL', mantenha as partes boas e mude apenas o que o usuário solicitou.
            3. LOGÍSTICA: Organize os locais por proximidade geográfica para evitar deslocamentos inúteis.
            4. FORMATO: Coloque o nome dos locais em negrito (Ex: **Mercado Municipal**).
            """

            prompt_usuario = f"""
            Pedido do Usuário: {instrucao_usuario}
            Parâmetros: {duracao_val} {tipo_op}, Transporte: {veiculo}, Grupo: {grupo}, Orçamento: {orcamento}, Pet: {pet_friendly}, Vibe: {vibe}.
            {contexto_anterior}
            """

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt_usuario}],
                temperature=0.3
            )
            
            texto_ia = completion.choices[0].message.content
            locais_ext = re.findall(r"\*\*(.*?)\*\*", texto_ia)
            
            # FILTRO DE QUALIDADE (Mínimo 300 avaliações)
            roteiro_final = texto_ia
            for loc in set(locais_ext):
                info = buscar_detalhes_google(loc, cidade_input)
                if info:
                    roteiro_final = roteiro_final.replace(f"**{loc}**", f"**{loc}** [📍]({info['url']})")
                else:
                    # Se não for validado (longe ou pouca avaliação), removemos a sugestão para manter o padrão PRO
                    linhas = roteiro_final.split('\n')
                    roteiro_final = '\n'.join([l for l in linhas if f"**{loc}**" not in l])

            st.session_state.historico_roteiro = roteiro_final
            st.rerun()

# --- EXIBIÇÃO DO ROTEIRO ---
if st.session_state.historico_roteiro:
    st.markdown("---")
    st.markdown(st.session_state.historico_roteiro)
    
    # Compartilhamento e TripAdvisor
    st.markdown("---")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        q_trip = urllib.parse.quote(f"Melhores coisas para fazer em {st.session_state.cidade_atual} TripAdvisor")
        st.link_button("🌐 Pesquisar no TripAdvisor", f"https://www.google.com/search?q={q_trip}")
    
    with col_f2:
        try:
            res_db = supabase.table("roteiros").insert({"cidade": st.session_state.cidade_atual, "conteudo": st.session_state.historico_roteiro}).execute()
            link_sh = f"https://nomadia.streamlit.app?roteiro_id={res_db.data[0]['id']}"
            st.link_button("📲 Enviar WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link_sh)}")
        except: pass

st.markdown("<br><hr><center><small>NomadIA Pro v4.0 | Filtro de Qualidade 300+ Avaliações</small></center>", unsafe_allow_html=True)
