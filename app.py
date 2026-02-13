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
    st.error(f"Erro de configuração: {e}")
    st.stop()

# --- FUNÇÕES DE APOIO ---

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

def buscar_detalhes_google(nome_local, cidade_usuario):
    """Busca o local com validação rigorosa para evitar links errados (vizinhança)"""
    try:
        query_completa = f"{nome_local}, {cidade_usuario}"
        
        # Uso do find_place para maior precisão
        result = gmaps.find_place(
            input=query_completa,
            input_type="textquery",
            fields=["name", "formatted_address", "place_id"],
            language="pt-BR"
        )
        
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            nome_google = place.get('name', '').lower()
            endereco = place.get('formatted_address', '').lower()
            cidade_base = cidade_usuario.split(',')[0].strip().lower()

            # VALIDAÇÃO 1: O endereço precisa conter a cidade correta
            if cidade_base not in endereco:
                return None
            
            # VALIDAÇÃO 2: O nome retornado deve ser minimamente parecido (evita trocar Cervejaria por Igreja)
            palavras_ia = set(re.findall(r'\w+', nome_local.lower()))
            palavras_google = set(re.findall(r'\w+', nome_google))
            
            # Se não houver nenhuma palavra em comum (com mais de 3 letras), descarta
            if not any(p in palavras_google for p in palavras_ia if len(p) > 3):
                return None

            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(nome_google)}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": maps_url}
    except:
        return None
    return None

# --- ESTILO ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 20px; background-color: #007BFF; color: white; height: 3.5em; font-weight: bold; }
    .premium-box { background-color: #f0f2f6; padding: 20px; border-radius: 15px; border: 1px solid #007BFF; margin-bottom: 20px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# COMPARTILHAMENTO (Permalinks)
if "roteiro_id" in st.query_params:
    try:
        res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
        if res.data:
            roteiro = res.data[0]
            st.success(f"Roteiro para: {roteiro['cidade']}")
            st.markdown(roteiro['conteudo'])
            if st.button("✨ Criar Novo Roteiro"):
                st.query_params.clear()
                st.rerun()
            st.stop()
    except: pass

# FORMULÁRIO
cidade = st.text_input("Para onde vamos?", placeholder="Ex: Piracicaba, SP")
tipo_roteiro = st.radio("Duração:", ["Horas (Hoje)", "Vários Dias"], horizontal=True)

col1, col2 = st.columns(2)
with col1:
    if tipo_roteiro == "Horas (Hoje)":
        duracao = st.number_input("Horas", 1, 24, 4)
        unidade = "horas"
    else:
        duracao = st.number_input("Dias", 1, 30, 3)
        unidade = "dias"
    veiculo = st.selectbox("Transporte", ["A pé", "Uber/Táxi", "Carro", "Transporte Público"])

with col2:
    grupo = st.selectbox("Grupo", ["Sozinho", "Casal", "Família", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

pet = st.toggle("Levando Pet? 🐾")
vibe = st.multiselect("Vibe", ["Gastronomia", "Natureza", "História", "Cultura", "Lazer"])
pedidos = st.text_area("Pedidos específicos (ex: lugares acessíveis)")
cupom = st.text_input("Cupom de Desconto")

if st.button("Gerar Roteiro NomadIA 🚀"):
    if not cidade:
        st.warning("Informe a cidade primeiro.")
    else:
        is_premium = (tipo_roteiro == "Vários Dias") or (duracao > 6)
        pode_gerar = (cupom.lower() == "tripfree") if cupom else not is_premium

        if not pode_gerar:
            st.markdown('<div class="premium-box"><h4>🚀 Roteiro Premium</h4><p>Use o cupom <b>TRIPFREE</b> para testar.</p></div>', unsafe_allow_html=True)
        else:
            with st.spinner('Consultando inteligência e mapas...'):
                agora = get_brasilia_time()
                clima = get_weather(cidade)
                
                system_prompt = f"""
                Você é o guia NomadIA Pro. Crie um roteiro realista para {cidade}.
                Agora são {agora.strftime('%H:%M')} de {agora.strftime('%A')}.
                REGRAS RÍGIDAS:
                1. Use o nome completo oficial dos locais em {cidade}.
                2. Verifique o horário: se o roteiro é à noite, não sugira locais que fecham às 17h.
                3. Pet={pet}: sugira apenas locais Pet Friendly se for True.
                4. Coloque CADA local sugerido entre asteriscos duplos (Ex: **Cervejaria Cevada Pura**).
                """

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_prompt}, 
                              {"role": "user", "content": f"Roteiro de {duracao} {unidade} em {cidade}. Vibe: {vibe}. {pedidos}"}],
                    temperature=0.2
                )
                
                resposta_ia = completion.choices[0].message.content

                # PROCESSAMENTO DE LINKS DO GOOGLE MAPS
                locais = re.findall(r"\*\*(.*?)\*\*", resposta_ia)
                roteiro_final = resposta_ia
                for local in set(locais):
                    if len(local) > 3:
                        info = buscar_detalhes_google(local, cidade)
                        if info:
                            # Substitui o texto pelo link oficial
                            roteiro_final = roteiro_final.replace(f"**{local}**", f"**{local}** [📍]({info['url']})")

                st.markdown("---")
                st.info(f"🌦️ Clima: {clima} | 🕒 Início: {agora.strftime('%H:%M')}")
                st.markdown(roteiro_final)

                # SALVAR NO SUPABASE E GERAR LINK
                try:
                    res_db = supabase.table("roteiros").insert({"cidade": cidade, "conteudo": roteiro_final}).execute()
                    if res_db.data:
                        link_share = f"https://nomadia.streamlit.app?roteiro_id={res_db.data[0]['id']}"
                        st.markdown("### 📤 Compartilhar")
                        st.code(link_share)
                        st.link_button("📲 Enviar WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link_share)}")
                except:
                    st.error("Roteiro gerado, mas falha ao criar link de compartilhamento.")

st.markdown("<br><hr><center><small>NomadIA Pro v1.0 - BETA </small></center>", unsafe_allow_html=True)
