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
if st.button("Gerar Roteiro NomadIA 🚀"):
    if not cidade_input:
        st.warning("Informe a cidade.")
    else:
        is_premium = (tipo_op == "Dias") or (duracao_val > 6)
        liberado = (cupom_input.lower() == "tripfree") if cupom_input else not is_premium
        
        if not liberado:
            st.error("Roteiros de vários dias ou longos exigem o cupom TRIPFREE.")
        else:
            with st.spinner('Validando locais e otimizando logística...'):
                agora = get_brasilia_time()
                clima_txt = get_weather(cidade_input)
                
                system_instruction = f"""
                Você é o guia NomadIA Pro especializado em logística.
                Crie um roteiro de {duracao_val} {unidade} em {cidade_input}.
                
                REGRAS RÍGIDAS:
                1. Mantenha os locais em um raio de 15km do centro de {cidade_input}.
                2. LOGÍSTICA: Organize os locais em ordem geográfica lógica (proximidade).
                3. Pet={pet_friendly}: Se True, priorize locais conhecidos como pet friendly.
                4. Transporte={veiculo}: Considere o tempo de deslocamento.
                5. Grupo={grupo} e Orçamento={orcamento}.
                6. Coloque nomes de lugares entre asteriscos duplos (Ex: **Mercado Municipal**).
                """

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_instruction}, 
                              {"role": "user", "content": f"Foco: {vibe}. Pedidos: {pedidos}"}],
                    temperature=0.3
                )
                
                texto_original = completion.choices[0].message.content
                locais_extraidos = re.findall(r"\*\*(.*?)\*\*", texto_original)
                
                # FILTRO DE QUALIDADE: Apaga linhas de locais não encontrados/distantes
                roteiro_limpo = texto_original
                for loc in set(locais_extraidos):
                    info_g = buscar_detalhes_google(loc, cidade_input)
                    if info_g:
                        roteiro_limpo = roteiro_limpo.replace(f"**{loc}**", f"**{loc}** [📍]({info_g['url']})")
                    else:
                        linhas = roteiro_limpo.split('\n')
                        roteiro_limpo = '\n'.join([l for l in linhas if f"**{loc}**" not in l])

                # EXIBIÇÃO
                st.markdown("---")
                st.info(f"🌦️ {clima_txt} | 🕒 Início: {agora.strftime('%H:%M')}")
                st.markdown(roteiro_limpo)

                # OPÇÕES EXTRAS
                st.markdown("---")
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    city_q = urllib.parse.quote(f"Melhores lugares em {cidade_input} TripAdvisor")
                    st.link_button("🌐 Ver no TripAdvisor", f"https://www.google.com/search?q={city_q}")
                with col_f2:
                    if st.button("🔄 Ajustar este Roteiro"): st.rerun()

                # SALVAMENTO
                try:
                    res = supabase.table("roteiros").insert({"cidade": cidade_input, "conteudo": roteiro_limpo}).execute()
                    link_share = f"https://nomadia.streamlit.app?roteiro_id={res.data[0]['id']}"
                    st.code(link_share)
                    st.link_button("📲 Enviar WhatsApp", f"https://api.whatsapp.com/send?text={urllib.parse.quote(link_share)}")
                except: pass

st.markdown("<br><hr><center><small>NomadIA Pro v3.0</small></center>", unsafe_allow_html=True)
