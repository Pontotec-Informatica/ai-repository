import streamlit as st
from openai import OpenAI
import urllib.parse
from datetime import datetime
import requests
import pytz
from supabase import create_client, Client

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NomadAI Pro", page_icon="📍", layout="centered")

# --- INICIALIZAÇÃO DO SUPABASE ---
# Certifique-se que as chaves estão no .streamlit/secrets.toml
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("Erro: Configuração do Supabase não encontrada nos Secrets.")
    st.stop()

# --- ESTILO ---
st.markdown("""
<style>
.main { max-width: 500px; margin: 0 auto; }
.stButton>button { width: 100%; border-radius: 20px; background-color: #007BFF; color: white; font-weight: bold; height: 3em; }
.premium-box { background-color: #f0f2f6; padding: 20px; border-radius: 15px; border: 1px solid #007BFF; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- FUNÇÕES AUXILIARES ---
def get_weather(city):
    """Função blindada para buscar clima"""
    try:
        if not city: return "Local não informado"
        
        # Codifica URL (trata espaços e acentos)
        city_encoded = urllib.parse.quote(city.strip())
        url = f"https://wttr.in/{city_encoded}?format=j1&lang=pt"
        
        # Headers para evitar bloqueio
        headers = {"User-Agent": "NomadAI-Bot/1.0"}
        
        response = requests.get(url, headers=headers, timeout=4)
        
        if response.status_code != 200:
            return "Clima offline"

        data = response.json()
        current = data['current_condition'][0]
        temp = current['temp_C']
        desc = current['lang_pt'][0]['value'] if 'lang_pt' in current else current['weatherDesc'][0]['value']
        
        return f"{temp}°C, {desc}"

    except Exception as e:
        print(f"⚠️ Erro Clima: {e}") # Aparece nos logs do servidor
        return "Clima indisponível"

def get_brasilia_time():
    tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz)

def salvar_roteiro(cidade, conteudo):
    """Salva o roteiro no Supabase e retorna o ID único"""
    try:
        data = {"cidade": cidade, "conteudo": conteudo}
        response = supabase.table("roteiros").insert(data).execute()
        if response.data:
            return response.data[0]['id']
        return None
    except Exception as e:
        st.error(f"Erro ao salvar banco de dados: {e}")
        return None

def carregar_roteiro(roteiro_id):
    """Busca um roteiro salvo pelo ID"""
    try:
        response = supabase.table("roteiros").select("*").eq("id", roteiro_id).execute()
        if response.data:
            return response.data[0]
        return None
    except:
        return None

# --- SETUP IA ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- LÓGICA DE ROTEIRO COMPARTILHADO (VIEW MODE) ---
query_params = st.query_params
roteiro_compartilhado = None

if "roteiro_id" in query_params:
    roteiro_id = query_params["roteiro_id"]
    roteiro_compartilhado = carregar_roteiro(roteiro_id)

if roteiro_compartilhado:
    st.title(f"📍 Roteiro: {roteiro_compartilhado['cidade']}")
    st.caption("Criado com NomadAI Pro")
    st.markdown("---")
    st.markdown(roteiro_compartilhado['conteudo'])
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("✨ Quero criar meu próprio roteiro"):
        st.query_params.clear()
        st.rerun()
    st.stop()

# --- MODO CRIAÇÃO (HOME PAGE) ---
st.title("📍 NomadAI Pro")
st.subheader("Seu copiloto inteligente de viagem")

cidade = st.text_input("Onde você está ou para onde vai?", placeholder="Ex: Piracicaba, SP")

agora = get_brasilia_time()
hora_atual = agora.strftime("%H:%M")

tipo_roteiro = st.radio("O que você precisa?", ["Roteiro Rápido (Hoje)", "Planejamento de Vários Dias"])

col1, col2 = st.columns(2)
with col1:
    if tipo_roteiro == "Roteiro Rápido (Hoje)":
        duracao = st.number_input("Duração (em horas)", min_value=1, max_value=12, value=4)
        unidade = "horas"
    else:
        duracao = st.number_input("Duração (em dias)", min_value=2, max_value=30, value=3)
        unidade = "dias"
    
    veiculo = st.selectbox("Como você vai se locomover?", 
                          ["A pé", "Uber/Táxi", "Transporte Público", "Carro", "Motorhome", "Van/Kombi"])

with col2:
    grupo = st.selectbox("Grupo", ["Sozinho", "Casal", "Família (Crianças)", "Amigos"])
    orcamento = st.select_slider("Orçamento", options=["Econômico", "Médio", "Luxo"])

pet = st.toggle("Levando Pet? 🐾")
vibe = st.multiselect("Vibe do passeio", ["Natureza", "História", "Gastronomia", "Wi-Fi", "Praia"])
pedidos = st.text_area("Pedidos específicos?")
cupom = st.text_input("Código de parceiro (Opcional)")

# --- GERAÇÃO ---
if st.button("Gerar Roteiro"):
    if not cidade:
        st.warning("Por favor, informe a cidade.")
    else:
        is_premium = (tipo_roteiro == "Planejamento de Vários Dias") or (tipo_roteiro == "Roteiro Rápido (Hoje)" and duracao > 6)
        liberado = (cupom.lower() == "tripfree") if cupom else not is_premium

        if not liberado:
            st.markdown(f"""
            <div class="premium-box">
                <h4>🚀 Roteiro Premium</h4>
                <p>Valor: R$ 9,90</p>
            </div>
            """, unsafe_allow_html=True)
            st.link_button("💳 Desbloquear agora", "https://seu-link-de-pagamento.com")
        else:
            with st.spinner('Analisando logística e clima...'):
                clima = get_weather(cidade)
                
                system_instruction = """
                Você é o NomadAI Pro. Crie roteiros logísticos realistas.
                1. Use dados reais da cidade (bairros, ruas famosas).
                2. Adapte ao transporte (Ex: Se 'A pé', tudo deve ser perto).
                3. Se for Motorhome/Van, foque em estacionamento.
                """

                user_context = f"""
                CIDADE: {cidade}.
                DURAÇÃO: {duracao} {unidade}.
                TRANSPORTE: {veiculo}.
                GRUPO: {grupo}.
                CLIMA ATUAL: {clima}.
                VIBE: {', '.join(vibe)}.
                PEDIDOS: {pedidos}.
                HORA INÍCIO: {hora_atual}.
                """

                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": user_context}
                    ],
                    temperature=0.7
                )

                resposta = completion.choices[0].message.content
                
                # Salvar e Gerar Link
                novo_id = salvar_roteiro(cidade, resposta)
                
                if novo_id:
                    # Link dinâmico (pega a URL atual do navegador se possível, senão usa a hardcoded)
                    link_compartilhavel = f"https://nomadia.streamlit.app?roteiro_id={novo_id}"
                    
                    st.success("Roteiro Gerado!")
                    st.info(f"☀️ Clima em {cidade}: {clima}")
                    st.markdown(resposta)
                    
                    texto_wa = f"Veja meu roteiro em {cidade} criado pela IA: {link_compartilhavel}"
                    link_wa = f"https://api.whatsapp.com/send?text={urllib.parse.quote(texto_wa)}"
                    
                    st.markdown("### 📤 Salvar e Compartilhar")
                    st.text_input("Link do seu roteiro:", link_compartilhavel)
                    st.link_button("📲 Enviar Link no WhatsApp", link_wa)
                else:
                    st.error("Erro ao gerar link (Verifique a tabela no Supabase).")
                    st.markdown(resposta) # Mostra o roteiro mesmo se falhar o save

st.markdown("<br><hr><center><small>NomadAI Pro v2.5</small></center>", unsafe_allow_html=True)
