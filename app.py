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
    st.error("Erro de configuração de chaves.")
    st.stop()

# --- FUNÇÕES ---
def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def buscar_detalhes_google(nome_local, cidade_usuario):
    try:
        query = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query,
            input_type="textquery",
            fields=["name", "formatted_address", "place_id", "types"],
            language="pt-BR"
        )
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            endereco = place.get('formatted_address', '').lower()
            cidade_alvo = cidade_usuario.split(',')[0].strip().lower()

            # Validação geográfica rigorosa
            if cidade_alvo not in endereco: return None
            
            # Validação de categoria (Lazer/Gastronomia)
            permitidos = ['park', 'restaurant', 'food', 'tourist_attraction', 'museum', 'cafe', 'bar', 'point_of_interest']
            if not any(t in permitidos for t in place.get('types', [])): return None

            url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": url}
    except: return None
    return None

# --- UI ---
st.title("📍 NomadIA Pro")

# COMPARTILHAMENTO
if "roteiro_id" in st.query_params:
    res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
    if res.data:
        st.success(f"Roteiro: {res.data[0]['cidade']}")
        st.markdown(res.data[0]['conteudo'])
        if st.button("✨ Criar meu próprio"):
            st.query_params.clear()
            st.rerun()
        st.stop()

# FORMULÁRIO
cidade_input = st.text_input("Para onde vamos?", placeholder="Ex: Piracicaba, SP")
tipo_op = st.radio("Duração:", ["Horas", "Dias"], horizontal=True)
duracao_val = st.number_input("Tempo", 1, 30, 4)
pet_friendly = st.toggle("Pet Friendly? 🐾")
pedidos = st.text_area("O que você busca? (Ex: roteiro histórico, lugares calmos)")
cupom_input = st.text_input("Cupom")

if st.button("Gerar Roteiro NomadIA 🚀"):
    if not cidade_input:
        st.warning("Informe a cidade.")
    else:
        is_premium = (tipo_op == "Dias") or (duracao_val > 6)
        liberado = (cupom_input.lower() == "tripfree") if cupom_input else not is_premium
        
        if not liberado:
            st.error("Roteiros premium exigem cupom.")
        else:
            with st.spinner('Validando locais e otimizando rota...'):
                agora = get_brasilia_time()
                
                system = f"""
                Você é o NomadIA Pro. Crie um roteiro de {duracao_val} {tipo_op} para {cidade_input}.
                REGRAS:
                1. Mantenha os locais no centro ou em um raio de 10km.
                2. Sugira apenas os locais mais famosos e bem avaliados de {cidade_input}.
                3. Coloque nomes de lugares entre asteriscos duplos (Ex: **Mercado Municipal**).
                4. Organize por horários e bairros.
                """

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": f"Foco: {pedidos}. Pet={pet_friendly}"}],
                    temperature=0.2
                )
                
                texto = completion.choices[0].message.content
                locais = re.findall(r"\*\*(.*?)\*\*", texto)
                
                # --- PROCESSAMENTO E FILTRO ---
                roteiro_limpo = texto
                for loc in set(locais):
                    info = buscar_detalhes_google(loc, cidade_input)
                    if info:
                        roteiro_limpo = roteiro_limpo.replace(f"**{loc}**", f"**{loc}** [📍]({info['url']})")
                    else:
                        # Se não tiver certeza, remove a linha/parágrafo que contém esse local
                        linhas = roteiro_limpo.split('\n')
                        roteiro_limpo = '\n'.join([l for l in linhas if f"**{loc}**" not in l])

                st.markdown("---")
                st.markdown(roteiro_limpo)

                # --- OPÇÕES EXTRAS E INTERAÇÃO ---
                st.markdown("---")
                st.markdown("### 🛠️ O que deseja fazer agora?")
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    city_query = urllib.parse.quote(f"O que fazer em {cidade_input}")
                    st.link_button("🌐 Ver mais no TripAdvisor", f"https://www.tripadvisor.com.br/Search?q={city_query}")
                
                with col_btn2:
                    if st.button("🔄 Ajustar Filtros / Mudar Roteiro"):
                        st.rerun()

                # SALVAMENTO
                try:
                    save = supabase.table("roteiros").insert({"cidade": cidade_input, "conteudo": roteiro_limpo}).execute()
                    link = f"https://nomadia.streamlit.app?roteiro_id={save.data[0]['id']}"
                    st.code(link)
                    st.link_button("📲 Enviar para WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link)}")
                except: pass

st.markdown("<br><hr><center><small>NomadIA Pro v3.0</small></center>", unsafe_allow_html=True)
