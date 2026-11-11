from flask import Flask, render_template_string
import json
import urllib.request
import urllib.parse
import ssl
import os
from datetime import datetime, timedelta

app = Flask(__name__)

PAISES_ALVO = "US,EU,DE,FR,GB,JP,HK,CN"
MOEDAS_ALVO = {"USD", "EUR", "GBP", "JPY", "HKD", "CNY"}
NOME_TEMPLATE = "template.html"

# Configurações de Variáveis de Ambiente para o Telegram
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5544308887")

def enviar_mensagem_telegram(texto):
    if not TELEGRAM_TOKEN:
        print("TELEGRAM_TOKEN não configurado nas variáveis de ambiente.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    partes = [texto[i:i+3900] for i in range(0, len(texto), 3900)]
    
    for parte in partes:
        dados = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": parte,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }).encode("utf-8")
        
        req = urllib.request.Request(url, data=dados)
        try:
            with urllib.request.urlopen(req) as response:
                pass
        except Exception as e:
            print(f"Erro ao enviar mensagem Telegram: {e}")

def descarregar_noticias_intervalo(data_inicio, data_fim, ctx):
    params = urllib.parse.urlencode({
        'countries': PAISES_ALVO,
        'from': f"{data_inicio}T00:00:00Z",
        'to': f"{data_fim}T23:59:59Z"
    })
    url = f"https://biquote.io/api/calendar?{params}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Erro ao descarregar {data_inicio} a {data_fim}: {e}")
        return []

def obter_dados_macro():
    hoje = datetime.now()
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    domingo_prox = segunda_atual + timedelta(days=13)
    trinta_dias_atras = hoje - timedelta(days=30)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # 1. Histórico Passado (dos 30 dias atrás até ao início desta semana)
    dados_passados = descarregar_noticias_intervalo(
        trinta_dias_atras.strftime("%Y-%m-%d"), 
        (segunda_atual - timedelta(days=1)).strftime("%Y-%m-%d"), 
        ctx
    )

    # 2. Período Contínuo: Segunda-feira Atual até ao Domingo da Próxima Semana (14 Dias)
    dados_futuros = descarregar_noticias_intervalo(
        segunda_atual.strftime("%Y-%m-%d"), 
        domingo_prox.strftime("%Y-%m-%d"), 
        ctx
    )

    todos_dados = dados_passados + dados_futuros
    todos_registos = []
    chaves_vistas = set()

    for item in todos_dados:
        moeda = item.get("currency", item.get("countryCode", "")).upper()
        mapeamento_moedas = {
            "US": "USD", "EU": "EUR", "DE": "EUR", "FR": "EUR",
            "GB": "GBP", "JP": "JPY", "HK": "HKD", "CN": "CNY"
        }
        moeda = mapeamento_moedas.get(moeda, moeda)

        importance = str(item.get("importance", "")).capitalize()
        tipo = str(item.get("type", "")).lower()

        if (importance in ["Medium", "High"] or tipo == "holiday") and moeda in MOEDAS_ALVO:
            impacto_final = "Holiday" if tipo == "holiday" else importance
            data_evento = str(item.get("time", ""))[:16].replace("T", " ")
            nome_evento = str(item.get("name", "")).strip()

            chave = (data_evento, moeda, nome_evento)
            if chave not in chaves_vistas:
                chaves_vistas.add(chave)
                
                previsao_val = item.get("forecast")
                anterior_val = item.get("previous")
                real_val = item.get("actual")

                previsao = str(previsao_val) if previsao_val is not None else "N/A"
                anterior = str(anterior_val) if anterior_val is not None else "N/A"
                real = str(real_val) if real_val is not None else "N/A"

                todos_registos.append([data_evento, moeda, impacto_final, nome_evento, previsao, anterior, real])

    todos_registos.sort(key=lambda x: x[0])
    return todos_registos

@app.route("/")
def dashboard():
    hoje = datetime.now()
    amanha = hoje + timedelta(days=1)
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    domingo_atual = segunda_atual + timedelta(days=6)
    segunda_prox = segunda_atual + timedelta(days=7)
    domingo_prox = segunda_atual + timedelta(days=13)
    trinta_dias_atras = hoje - timedelta(days=30)

    inicio_atual = segunda_atual.strftime("%Y-%m-%d")
    fim_atual = domingo_atual.strftime("%Y-%m-%d")
    amanha_str = amanha.strftime("%Y-%m-%d")
    inicio_prox = segunda_prox.strftime("%Y-%m-%d")
    fim_prox = domingo_prox.strftime("%Y-%m-%d")
    hoje_str = hoje.strftime("%Y-%m-%d")
    trinta_dias_str = trinta_dias_atras.strftime("%Y-%m-%d")

    registos = obter_dados_macro()
    dados_js = json.dumps(registos, ensure_ascii=False)

    if not os.path.exists(NOME_TEMPLATE):
        return "Erro: Ficheiro template.html não encontrado no servidor.", 500

    with open(NOME_TEMPLATE, "r", encoding="utf-8") as f:
        html_template = f.read()

    html_content = (
        html_template
        .replace("__DATA_INICIO_ATUAL__", inicio_atual)
        .replace("__DATA_FIM_ATUAL__", fim_atual)
        .replace("__AMANHA_STR__", amanha_str)
        .replace("__DATA_INICIO_PROX__", inicio_prox)
        .replace("__DATA_FIM_PROX__", fim_prox)
        .replace("__HOJE_STR__", hoje_str)
        .replace("__TRINTA_DIAS_ATRAS__", trinta_dias_str)
        .replace("__DADOS_JSON__", dados_js)
    )

    return render_template_string(html_content)

@app.route("/disparar-alerta-telegram-fd2026")
def disparar_alerta():
    hoje = datetime.now()
    eh_sexta = (hoje.weekday() == 4)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if eh_sexta:
        segunda_prox = hoje + timedelta(days=(7 - hoje.weekday()))
        domingo_prox = segunda_prox + timedelta(days=6)
        data_inicio = segunda_prox.strftime("%Y-%m-%d")
        data_fim = domingo_prox.strftime("%Y-%m-%d")
        cabecalho = (
            f"📅 *FAROL DECIMAL | PLANEAMENTO DA PRÓXIMA SEMANA*\n"
            f"🗓️ *Período:* {data_inicio} a {data_fim}\n"
            f"🎯 *Filtro:* Alto Impacto & Feriados Bancários\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    else:
        amanha = hoje + timedelta(days=1)
        data_inicio = amanha.strftime("%Y-%m-%d")
        data_fim = amanha.strftime("%Y-%m-%d")
        cabecalho = (
            f"🚨 *FAROL DECIMAL | ALERTAS PARA AMANHÃ*\n"
            f"📅 *Data:* {data_inicio}\n"
            f"🎯 *Filtro:* Alto Impacto & Feriados Bancários\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    dados_brutos = descarregar_noticias_intervalo(data_inicio, data_fim, ctx)
    eventos_filtrados = []
    chaves_vistas = set()

    for item in dados_brutos:
        moeda = item.get("currency", item.get("countryCode", "")).upper()
        mapeamento_moedas = {
            "US": "USD", "EU": "EUR", "DE": "EUR", "FR": "EUR",
            "GB": "GBP", "JP": "JPY", "HK": "HKD", "CN": "CNY"
        }
        moeda = mapeamento_moedas.get(moeda, moeda)

        importance = str(item.get("importance", "")).capitalize()
        tipo = str(item.get("type", "")).lower()

        if (importance == "High" or tipo == "holiday") and moeda in MOEDAS_ALVO:
            impacto_final = "Holiday" if tipo == "holiday" else "High"
            data_hora = str(item.get("time", ""))[:16].replace("T", " ")
            nome = str(item.get("name", "")).strip()

            chave = (data_hora, moeda, nome)
            if chave not in chaves_vistas:
                chaves_vistas.add(chave)
                prev = str(item.get("forecast")) if item.get("forecast") is not None else "N/A"
                ant = str(item.get("previous")) if item.get("previous") is not None else "N/A"
                
                eventos_filtrados.append({
                    "data_hora": data_hora,
                    "moeda": moeda,
                    "impacto": impacto_final,
                    "evento": nome,
                    "previsao": prev,
                    "anterior": ant
                })

    eventos_filtrados.sort(key=lambda x: x["data_hora"])

    if not eventos_filtrados:
        corpo = "✅ *Sem registos:* Não existem eventos de Alto Impacto nem Feriados agendados para este período."
        enviar_mensagem_telegram(cabecalho + corpo)
        return "Alerta de ausência enviado.", 200

    corpo = ""
    data_atual_grupo = ""

    for ev in eventos_filtrados:
        data_ev, hora_ev = ev["data_hora"].split(" ")
        
        if eh_sexta and data_ev != data_atual_grupo:
            data_atual_grupo = data_ev
            dt_obj = datetime.strptime(data_ev, "%Y-%m-%d")
            dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
            nome_dia = dias_semana[dt_obj.weekday()]
            corpo += f"\n📆 *{nome_dia} ({data_ev[8:10]}/{data_ev[5:7]})*\n"

        icone = "🔴 [HIGH]" if ev["impacto"] == "High" else "🏦 [FERIADO]"
        
        if ev["impacto"] == "Holiday":
            corpo += f"  • `{hora_ev}` | *{ev['moeda']}* {icone}\n    📌 *{ev['evento']}*\n"
        else:
            corpo += f"  • `{hora_ev} UTC` | *{ev['moeda']}* {icone}\n    📌 *{ev['evento']}*\n    📊 Prev: `{ev['previsao']}` | Ant: `{ev['anterior']}`\n"

    mensagem_final = cabecalho + corpo + "\n⚠️ *Farol Decimal:* Verifique a gestão de risco dos pares e índices associados."
    enviar_mensagem_telegram(mensagem_final)
    
    return "Alerta enviado com sucesso para o Telegram!", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
