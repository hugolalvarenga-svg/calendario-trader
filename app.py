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

def obter_blocos_semanais():
    hoje = datetime.now()
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    blocos = []
    for i in range(-4, 2):
        inicio = segunda_atual + timedelta(weeks=i)
        fim = inicio + timedelta(days=6)
        blocos.append((inicio.strftime("%Y-%m-%d"), fim.strftime("%Y-%m-%d")))
    return blocos

def descarregar_noticias_bloco(data_inicio, data_fim, ctx):
    params = urllib.parse.urlencode({
        'countries': PAISES_ALVO,
        'from': f"{data_inicio}T00:00:00Z",
        'to': f"{data_fim}T23:59:59Z"
    })
    url = f"https://biquote.io/api/calendar?{params}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=12) as response:
            return json.loads(response.read().decode())
    except Exception:
        return []

def obter_dados_macro():
    blocos = obter_blocos_semanais()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    todos_registos = []
    chaves_vistas = set()

    for inicio, fim in blocos:
        dados = descarregar_noticias_bloco(inicio, fim, ctx)
        for item in dados:
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
    segunda_atual = hoje - timedelta(days=hoje.weekday())
    domingo_atual = segunda_atual + timedelta(days=6)
    segunda_prox = segunda_atual + timedelta(days=7)
    domingo_prox = segunda_atual + timedelta(days=13)
    trinta_dias_atras = hoje - timedelta(days=30)

    inicio_atual = segunda_atual.strftime("%Y-%m-%d")
    fim_atual = domingo_atual.strftime("%Y-%m-%d")
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
        .replace("__DATA_INICIO_PROX__", inicio_prox)
        .replace("__DATA_FIM_PROX__", fim_prox)
        .replace("__HOJE_STR__", hoje_str)
        .replace("__TRINTA_DIAS_ATRAS__", trinta_dias_str)
        .replace("__DADOS_JSON__", dados_js)
    )

    return render_template_string(html_content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)