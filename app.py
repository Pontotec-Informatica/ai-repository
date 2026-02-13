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
    """Busca o local no Google com filtro rígido de categoria e cidade"""
    try:
        # Lista de palavras que a IA costuma colocar em negrito mas não são locais
        blacklist_termos = ['dica', 'duração', 'bairro', 'descrição', 'roteiro', 'início', 'café', 'almoço', 'jantar']
        if nome_local.lower() in blacklist_termos:
            return None

        query_completa = f"{nome_local}, {cidade_usuario}"
        result = gmaps.find_place(
            input=query_completa,
            input_type="textquery",
            fields=["name", "formatted_address", "place_id", "types"],
            language="pt-BR"
        )
        
        if result['status'] == 'OK' and result['candidates']:
            place = result['candidates'][0]
            tipos = place.get('types', [])
            
            # Filtro de categorias (Lazer e Gastronomia)
            permitidos = ['park', 'restaurant', 'food', 'tourist_attraction', 'museum', 'church', 'point_of_interest', 'bakery', 'cafe', 'bar', 'shopping_mall', 'aquarium', 'art_gallery']
            if not any(t in permitidos for t in tipos):
                return None

            nome_google = place.get('name', '').lower()
            endereco = place.get('formatted_address', '').lower()
            cidade_base = cidade_usuario.split(',')[0].strip().lower()

            # Valida se está na cidade certa
            if cidade_base not in endereco:
                return None
            
            # Valida se o nome faz sentido
            palavras_ia = [p for p in re.findall(r'\w+', nome_local.lower()) if len(p) > 3]
            if not any(p in nome_google for p in palavras_ia):
                return None

            maps_url = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place['name'])}&query_place_id={place['place_id']}"
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
        st.success(f"Roteiro Carregado: {res.data[0]['cidade']}")
        st.markdown(res.data[0]['conteudo'])
        st.stop()

# FORMULÁRIO
cidade = st.text_input("Para onde vamos?", placeholder="Ex: Piracicaba, SP")
tipo_roteiro = st.radio("Duração:", ["Horas (Hoje)", "Vários Dias"], horizontal=True)

col1, col2 = st.columns(2)
with col1:
    duracao = st.number_input("Quantidade", 1, 30, 4)
    unidade = "horas" if tipo_roteiro == "Horas (Hoje)" else "dias"
    veiculo = st.selectbox("Transporte", ["A pé", "Uber/Táxi", "Carro", "Transporte Público"])

with col2:
    grupo = st.selectbox("Grupo", ["Sozinho", "Casal", "Família", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

pet = st.toggle("Levando Pet? 🐾")
pedidos = st.text_area("Pedidos específicos")
cupom = st.text_input("Cupom de Desconto")

if st.button("Gerar Roteiro Logístico 🚀"):
    if not cidade:
        st.warning("Informe a cidade.")
    else:
        is_premium = (tipo_roteiro == "Vários Dias") or (duracao > 6)
        pode_gerar = (cupom.lower() == "tripfree") if cupom else not is_premium

        if not pode_gerar:
            st.info("Use o cupom TRIPFREE para roteiros longos.")
        else:
            with st.spinner('Otimizando rota...'):
                agora = get_brasilia_time()
                clima = get_weather(cidade)
                
                system_prompt = f"""
                Você é o NomadIA Pro. Crie um roteiro em {cidade}.
                LOGÍSTICA: Agrupe locais próximos. Use uma sequência linear.
                REGRAS DE FORMATAÇÃO:
                - Coloque APENAS o nome dos estabelecimentos/parques em negrito (Ex: **Restaurante O Casarão**).
                - NÃO use negrito em palavras como 'Dica', 'Horário' ou 'Bairro'.
                - Informe o Bairro e uma Dica curta para cada parada.
                - Pet Friendly: {pet}.
                """

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_prompt}, 
                              {"role": "user", "content": f"Roteiro de {duracao} {unidade} em {cidade}. Orçamento {orcamento}. {pedidos}"}],
                    temperature=0.3
                )
                
                resposta_ia = completion.choices[0].message.content
                
                # BUSCA DE LINKS
                locais = re.findall(r"\*\*(.*?)\*\*", resposta_ia)
                roteiro_final = resposta_ia
                for local in set(locais):
                    info = buscar_detalhes_google(local, cidade)
                    if info:
                        roteiro_final = roteiro_final.replace(f"**{local}**", f"**[{local}]({info['url']})**")
                
                st.markdown("---")
                st.info(f"🌦️ {clima} | 🕒 {agora.strftime('%H:%M')}")
                st.markdown(roteiro_final)

                # SALVAR NO BANCO
                try:
                    res_db = supabase.table("roteiros").insert({"cidade": cidade, "conteudo": roteiro_final}).execute()
                    link_share = f"https://nomadia.streamlit.app?roteiro_id={res_db.data[0]['id']}"
                    st.code(link_share)
                    st.link_button("📲 Enviar WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link_share)}")
                except:
                    st.error("Roteiro pronto!")

st.markdown("<br><hr><center><small>NomadIA Pro v3.0</small></center>", unsafe_allow_html=True)
