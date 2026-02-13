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

# --- INICIALIZAÇÃO DE SERVIÇOS ---
try:
    gmaps = googlemaps.Client(key=st.secrets["GOOGLE_PLACES_API_KEY"])
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"Erro ao carregar chaves (Secrets): {e}")
    st.stop()

# --- FUNÇÕES AUXILIARES ---

def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def get_weather(city):
    try:
        city_encoded = urllib.parse.quote(city.strip())
        url = f"https://wttr.in/{city_encoded}?format=%t+%C"
        response = requests.get(url, timeout=5)
        return response.text if response.status_code == 200 else "Clima indisponível"
    except:
        return "Clima indisponível"

def buscar_detalhes_google(nome_local, cidade):
    """Busca o link oficial e detalhes no Google Maps"""
    try:
        # Busca o lugar especificamente na cidade para evitar erros
        result = gmaps.places(query=f"{nome_local} em {cidade}")
        if result['status'] == 'OK':
            place = result['results'][0]
            name = place['name']
            place_id = place['place_id']
            # Cria o link direto do Google Maps
            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name)}&query_place_id={place_id}"
            return {"nome": name, "url": maps_url}
    except:
        return None
    return None

# --- ESTILO CUSTOMIZADO ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 20px; background-color: #007BFF; color: white; height: 3.5em; font-weight: bold; }
    .premium-box { background-color: #f0f2f6; padding: 20px; border-radius: 15px; border: 1px solid #007BFF; margin-bottom: 20px; text-align: center; }
    .stTextInput>div>div>input { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- INTERFACE PRINCIPAL ---
st.title("📍 NomadIA Pro")

# --- LÓGICA DE COMPARTILHAMENTO ---
if "roteiro_id" in st.query_params:
    try:
        res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
        if res.data:
            roteiro = res.data[0]
            st.success(f"Roteiro Carregado para {roteiro['cidade']}")
            st.markdown(roteiro['conteudo'])
            if st.button("✨ Criar meu Próprio Roteiro"):
                st.query_params.clear()
                st.rerun()
            st.stop()
    except:
        st.error("Roteiro não encontrado.")

# --- FORMULÁRIO DE ENTRADA ---
cidade = st.text_input("Para onde vamos?", placeholder="Ex: Piracicaba, SP")

tipo_roteiro = st.radio("Tipo de plano:", ["Roteiro Rápido (Horas)", "Viagem Completa (Dias)"], horizontal=True)

col1, col2 = st.columns(2)
with col1:
    if tipo_roteiro == "Roteiro Rápido (Horas)":
        duracao = st.number_input("Duração (horas)", min_value=1, max_value=24, value=4)
        unidade = "horas"
    else:
        duracao = st.number_input("Duração (dias)", min_value=1, max_value=30, value=3)
        unidade = "dias"
    
    veiculo = st.selectbox("Transporte", ["A pé", "Uber/Táxi", "Transporte Público", "Carro", "Motorhome"])

with col2:
    grupo = st.selectbox("Com quem?", ["Sozinho", "Casal", "Família", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

st.markdown("---")
col_extra1, col_extra2 = st.columns(2)
with col_extra1:
    pet = st.toggle("Levando Pet? 🐾")
with col_extra2:
    vibe = st.multiselect("Vibe", ["Gastronomia", "Natureza", "História", "Cultura", "Wi-Fi"])

pedidos = st.text_area("Notas extras (ex: evitar ladeiras, dieta vegana)")
cupom = st.text_input("Cupom de Desconto")

# --- BOTÃO GERAR ---
if st.button("Gerar Roteiro Inteligente 🚀"):
    if not cidade:
        st.warning("Diz a cidade aí!")
    else:
        # Lógica de Cupom / Regra de Negócio
        is_premium = (tipo_roteiro == "Viagem Completa (Dias)") or (duracao > 6 and unidade == "horas")
        pode_gerar = (cupom.lower() == "tripfree") if cupom else not is_premium

        if not pode_gerar:
            st.markdown(f'''
            <div class="premium-box">
                <h4>🚀 Roteiro Premium</h4>
                <p>Planos para {duracao} {unidade} exigem curadoria avançada.</p>
                <p><b>Use o cupom TRIPFREE ou faça o upgrade.</b></p>
            </div>
            ''', unsafe_allow_html=True)
            st.link_button("💳 Desbloquear Roteiro", "https://seu-link-pagamento.com")
        else:
            with st.spinner('Consultando Google Maps e Clima...'):
                agora = get_brasilia_time()
                clima = get_weather(cidade)
                
                # 1. IA Gera o texto base
                system_instruction = f"""
                Você é o guia NomadIA Pro. Crie um roteiro realista e logístico.
                Hoje é {agora.strftime('%A')}, agora são {agora.strftime('%H:%M')}.
                REGRAS:
                - Use APENAS locais reais e existentes.
                - Se Pet={pet}, sugira locais Pet Friendly.
                - TRANSPORTE: {veiculo}.
                - IMPORTANTE: Coloque o nome de CADA local/ponto turístico sugerido entre asteriscos duplos (Ex: **Mercado Municipal**).
                - Formate com horários (Ex: 14:00 - **Local**).
                """

                user_context = f"Cidade: {cidade}. Duração: {duracao} {unidade}. Grupo: {grupo}. Orçamento: {orcamento}. Vibe: {vibe}. Pedidos: {pedidos}."

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": user_context}],
                    temperature=0.2
                )
                
                resposta_ia = completion.choices[0].message.content

                # 2. PÓS-PROCESSAMENTO DE LINKS (A Mágica)
                locais_em_negrito = re.findall(r"\*\*(.*?)\*\*", resposta_ia)
                roteiro_com_links = resposta_ia
                
                # Criar um set para não buscar o mesmo local duas vezes
                for local in set(locais_em_negrito):
                    # Ignora negritos que não são locais (ex: horários ou títulos)
                    if len(local) > 3: 
                        dados_google = buscar_detalhes_google(local, cidade)
                        if dados_google:
                            link_markdown = f"**{local}** [📍]({dados_google['url']})"
                            roteiro_com_links = roteiro_com_links.replace(f"**{local}**", link_markdown)

                # 3. EXIBIÇÃO FINAL
                st.markdown("---")
                st.markdown(f"### 🗓️ Plano para {cidade}")
                st.info(f"🌦️ {clima} | 🕒 Início: {agora.strftime('%H:%M')}")
                
                st.markdown(roteiro_com_links)

                # 4. SALVAMENTO E COMPARTILHAMENTO
                try:
                    res_db = supabase.table("roteiros").insert({"cidade": cidade, "conteudo": roteiro_com_links}).execute()
                    if res_db.data:
                        novo_id = res_db.data[0]['id']
                        link_share = f"https://nomadia.streamlit.app?roteiro_id={novo_id}"
                        
                        st.markdown("### 📤 Compartilhar")
                        st.code(link_share)
                        
                        texto_wa = urllib.parse.quote(f"Olha o roteiro que fiz para {cidade}: {link_share}")
                        st.link_button("📲 Enviar para WhatsApp", f"https://api.whatsapp.com/send?text={texto_wa}")
                except Exception as e:
                    st.error("Erro ao gerar link de compartilhamento.")

st.markdown("<br><hr><center><small>NomadIA Pro v3.0</small></center>", unsafe_allow_html=True)
