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
    """Valida se o local é turístico/lazer e se pertence à cidade correta"""
    try:
        query_completa = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query_completa,
            input_type="textquery",
            fields=["name", "formatted_address", "place_id", "types", "rating"],
            language="pt-BR"
        )
        
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            tipos_google = place.get('types', [])
            
            # Filtros de segurança contra locais irrelevantes ou de serviço
            proibidos = ['waste_management', 'garbage_collection', 'local_government_office', 'establishment', 'cemetery', 'industrial']
            permitidos = ['park', 'restaurant', 'food', 'tourist_attraction', 'museum', 'church', 'point_of_interest', 'bakery', 'cafe', 'bar', 'shopping_mall']
            
            if any(t in proibidos for t in tipos_google) or not any(t in permitidos for t in tipos_google):
                return None

            nome_google = place.get('name', '').lower()
            endereco = place.get('formatted_address', '').lower()
            cidade_base = cidade_usuario.split(',')[0].strip().lower()

            if cidade_base not in endereco:
                return None
            
            palavras_ia = set(re.findall(r'\w+', nome_local.lower()))
            palavras_google = set(re.findall(r'\w+', nome_google))
            if not any(p in palavras_google for p in palavras_ia if len(p) > 3):
                return None

            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(nome_google)}&query_place_id={place['place_id']}"
            return {"nome": place['name'], "url": maps_url}
    except:
        return None
    return None

# --- INTERFACE ---
st.title("📍 NomadIA Pro")

# COMPARTILHAMENTO
if "roteiro_id" in st.query_params:
    res = supabase.table("roteiros").select("*").eq("id", st.query_params["roteiro_id"]).execute()
    if res.data:
        roteiro = res.data[0]
        st.success(f"Roteiro para: {roteiro['cidade']}")
        st.markdown(roteiro['conteudo'])
        if st.button("✨ Criar Novo"):
            st.query_params.clear()
            st.rerun()
        st.stop()

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
pedidos = st.text_area("Pedidos específicos")
cupom = st.text_input("Cupom de Desconto")

if st.button("Gerar Roteiro Logístico 🚀"):
    if not cidade:
        st.warning("Informe a cidade.")
    else:
        is_premium = (tipo_roteiro == "Vários Dias") or (duracao > 6)
        pode_gerar = (cupom.lower() == "tripfree") if cupom else not is_premium

        if not pode_gerar:
            st.markdown('<div style="background-color:#f0f2f6;padding:20px;border-radius:15px;border:1px solid #007BFF;text-align:center;"><h4>🚀 Roteiro Premium</h4><p>Use o cupom <b>TRIPFREE</b></p></div>', unsafe_allow_html=True)
        else:
            with st.spinner('Otimizando rota e validando locais...'):
                agora = get_brasilia_time()
                clima = get_weather(cidade)
                
                system_prompt = f"""
                Você é o guia NomadIA Pro especializado em logística urbana. 
                Sua tarefa é criar um roteiro em {cidade} que faça sentido geográfico.
                
                DIRETRIZES DE LOGÍSTICA:
                1. Agrupe os locais por PROXIMIDADE. Não cruze a cidade sem necessidade.
                2. Priorize os pontos turísticos e restaurantes MAIS BEM AVALIADOS.
                3. Se o transporte for '{veiculo}', ajuste a distância entre as paradas.
                4. Comece o roteiro de onde o usuário provavelmente estaria (Centro ou entrada da cidade).
                5. Mencione o BAIRRO de cada local para o usuário se localizar.
                6. Pet={pet}: Se True, só indique locais com área externa ou conhecidos como pet friendly.
                7. Use nomes oficiais entre asteriscos duplos (Ex: **Parque da Rua do Porto**).
                """

                user_prompt = f"Crie um roteiro de {duracao} {unidade} em {cidade}. Orçamento {orcamento}. Vibe {vibe}. Pedidos: {pedidos}."

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=0.3
                )
                
                resposta_ia = completion.choices[0].message.content
                locais = re.findall(r"\*\*(.*?)\*\*", resposta_ia)
                roteiro_final = resposta_ia
                
                for local in set(locais):
                    if len(local) > 3:
                        info = buscar_detalhes_google(local, cidade)
                        if info:
                            roteiro_final = roteiro_final.replace(f"**{local}**", f"**{local}** [📍]({info['url']})")
                        else:
                            roteiro_final = roteiro_final.replace(f"**{local}**", f"*{local} (Verificar local)*")

                st.markdown("---")
                st.info(f"🌦️ {clima} | 🕒 Início: {agora.strftime('%H:%M')}")
                st.markdown(roteiro_final)

                try:
                    res_db = supabase.table("roteiros").insert({"cidade": cidade, "conteudo": roteiro_final}).execute()
                    link_share = f"https://nomadia.streamlit.app?roteiro_id={res_db.data[0]['id']}"
                    st.code(link_share)
                    st.link_button("📲 Enviar WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link_share)}")
                except:
                    st.error("Roteiro pronto!")

st.markdown("<br><hr><center><small>NomadIA Pro v3.0</small></center>", unsafe_allow_html=True)
