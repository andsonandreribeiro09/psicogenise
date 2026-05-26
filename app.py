# ============================================
# 📦 IMPORTS
# ============================================
from dash import Dash, html, dcc, Input, Output
from flask import Response, jsonify, redirect, render_template_string, request, send_from_directory, session
import pandas as pd
import plotly.express as px
from collections import Counter
from pathlib import Path
import csv
import io
import json
import math
import re
import struct
import wave

# ============================================
# 📂 DADOS
# ============================================
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "psicogenise-main"
SUBMISSIONS_FILE = BASE_DIR / "submissoes_frontend.csv"
STUDENTS_FILE = BASE_DIR / "cadastros_alunos.csv"

df_resultados = pd.read_csv(BASE_DIR / "alunos_resultado.csv")
df_erros = pd.read_csv(BASE_DIR / "alunos_erros_detalhados.csv")
df_intervencoes = pd.read_csv(BASE_DIR / "alunos_intervencao.csv")

# ============================================
# 🎨 APP
# ============================================
app = Dash(
    __name__,
    routes_pathname_prefix="/dashboard/",
    requests_pathname_prefix="/dashboard/",
)
server = app.server
server.secret_key = "psicogenise-dev-secret"


CADASTRO_TEMPLATE = """
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Cadastro do aluno | Psicogenise</title>
    <style>
      * { box-sizing: border-box; }
      body {
        min-height: 100vh;
        margin: 0;
        display: grid;
        place-items: center;
        padding: 24px;
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
        color: #072b73;
        background: url("/frontend/fundo.jpg") center / cover no-repeat fixed;
      }
      form {
        width: min(94vw, 460px);
        display: grid;
        gap: 14px;
        padding: 24px;
        border: 1px solid rgba(7, 43, 115, 0.14);
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.94);
        box-shadow: 0 18px 50px rgba(20, 40, 80, 0.18);
      }
      h1 { margin: 0 0 4px; font-size: 1.45rem; }
      p { margin: 0 0 8px; color: #4b5563; line-height: 1.35; }
      label { display: grid; gap: 6px; font-weight: 700; }
      input, select {
        width: 100%;
        height: 44px;
        padding: 0 12px;
        border: 1px solid rgba(0, 0, 255, 0.28);
        border-radius: 8px;
        color: #072b73;
        font: inherit;
        background: white;
      }
      button {
        height: 44px;
        border: 0;
        border-radius: 8px;
        background: #0033cc;
        color: white;
        font: inherit;
        font-weight: 800;
        cursor: pointer;
      }
      .error {
        padding: 10px 12px;
        border-radius: 8px;
        background: #fee2e2;
        color: #991b1b;
      }
    </style>
  </head>
  <body>
    <form method="post" action="/cadastro" autocomplete="on">
      <h1>Cadastro do aluno</h1>
      <p>Preencha os dados para iniciar o teste no prototipo.</p>
      {% if error %}<div class="error">{{ error }}</div>{% endif %}
      <label>
        Nome do aluno
        <input name="nome" required maxlength="120" placeholder="Ex.: Ana Souza" value="{{ nome }}">
      </label>
      <label>
        Serie
        <select name="serie" required>
          <option value="">Selecione</option>
          {% for item in series %}
            <option value="{{ item }}" {% if item == serie %}selected{% endif %}>{{ item }}</option>
          {% endfor %}
        </select>
      </label>
      <label>
        Numero da matricula
        <input name="matricula" required maxlength="40" inputmode="numeric" placeholder="Ex.: 2026001" value="{{ matricula }}">
      </label>
      <button type="submit">Iniciar teste</button>
    </form>
  </body>
</html>
"""


def tokenize_text(texto):
    return re.findall(r"\w+", str(texto).lower(), flags=re.UNICODE)


def distancia_edicao(p1, p2):
    len1, len2 = len(p1), len(p2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            custo = 0 if p1[i - 1] == p2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + custo,
            )

    return dp[len1][len2]


def classificar_erro(aluno, correto):
    if aluno == correto:
        return "correto"

    dist = distancia_edicao(aluno, correto)

    if len(aluno) < len(correto):
        return "omissao"
    if len(aluno) > len(correto):
        return "adicao"
    if dist == 1:
        return "substituicao"
    return "fonologico"


def escolher_gabarito(texto_aluno):
    texto_aluno = str(texto_aluno or "")
    if df_resultados.empty:
        return "bola toca casa"

    melhor_gabarito = str(df_resultados.iloc[0]["gabarito"])
    melhor_distancia = None

    for gabarito in df_resultados["gabarito"].dropna().unique():
        distancia = distancia_edicao(texto_aluno.lower(), str(gabarito).lower())
        if melhor_distancia is None or distancia < melhor_distancia:
            melhor_distancia = distancia
            melhor_gabarito = str(gabarito)

    return melhor_gabarito


def extrair_features(palavras_aluno, palavras_gabarito):
    total_palavras = len(palavras_aluno)
    tamanho_medio = (
        sum(len(palavra) for palavra in palavras_aluno) / total_palavras
        if total_palavras
        else 0
    )
    diversidade_lexica = len(set(palavras_aluno)) / total_palavras if total_palavras else 0
    distancias = [
        distancia_edicao(palavras_aluno[i], palavras_gabarito[i])
        for i in range(min(len(palavras_aluno), len(palavras_gabarito)))
    ]
    erro_medio = sum(distancias) / len(distancias) if distancias else 0

    return {
        "total_palavras": total_palavras,
        "tamanho_medio": round(tamanho_medio, 2),
        "diversidade_lexica": round(diversidade_lexica, 2),
        "erro_medio": round(erro_medio, 2),
    }


def estimar_nivel(features, score):
    total = features["total_palavras"]
    erro_medio = features["erro_medio"]

    if score == 0 and total >= 5:
        return "fluente"
    if score <= 1 and total >= 3:
        return "alfabetico"
    if erro_medio <= 1.5 and total >= 2:
        return "silabico-alfabetico"
    if total >= 2:
        return "silabico"
    return "pre-silabico"


def gerar_recomendacoes(resumo, nivel, score):
    recomendacoes = []

    if score > 3:
        nivel_erro = "alto"
        recomendacoes.append("Intervencao intensiva com acompanhamento individual")
    elif score > 0:
        nivel_erro = "moderado"
        recomendacoes.append("Reforco focado nos principais erros")
    else:
        nivel_erro = "baixo"
        recomendacoes.append("Aprimoramento e pratica leve")

    if resumo["omissao"] >= 1:
        recomendacoes.append("Treinar segmentacao silabica")
    if resumo["substituicao"] >= 1:
        recomendacoes.append("Exercicios fonema-grafema")
    if resumo["fonologico"] >= 1:
        recomendacoes.append("Consciencia fonologica")
    if resumo["adicao"] >= 1:
        recomendacoes.append("Revisao ortografica")
    if nivel == "silabico-alfabetico":
        recomendacoes.append("Consolidar escrita completa das palavras")

    return nivel_erro, recomendacoes


def analisar_resposta(texto_aluno, gabarito_texto=None):
    gabarito = gabarito_texto or escolher_gabarito(texto_aluno)
    palavras_aluno = tokenize_text(texto_aluno)
    palavras_gabarito = tokenize_text(gabarito)
    erros = []

    for i in range(max(len(palavras_aluno), len(palavras_gabarito))):
        aluno = palavras_aluno[i] if i < len(palavras_aluno) else ""
        correto = palavras_gabarito[i] if i < len(palavras_gabarito) else ""
        erros.append({
            "aluno": aluno,
            "correto": correto,
            "tipo": classificar_erro(aluno, correto),
            "distancia": distancia_edicao(aluno, correto),
        })

    contagem = Counter(erro["tipo"] for erro in erros)
    resumo = {
        "correto": contagem.get("correto", 0),
        "omissao": contagem.get("omissao", 0),
        "adicao": contagem.get("adicao", 0),
        "substituicao": contagem.get("substituicao", 0),
        "fonologico": contagem.get("fonologico", 0),
    }
    score = (resumo["omissao"] * 2) + resumo["substituicao"] + (resumo["fonologico"] * 3) + resumo["adicao"]
    features = extrair_features(palavras_aluno, palavras_gabarito)
    nivel = estimar_nivel(features, score)
    nivel_erro, recomendacoes = gerar_recomendacoes(resumo, nivel, score)

    return {
        "texto_aluno": texto_aluno,
        "gabarito": gabarito,
        "nivel": nivel,
        "score": score,
        "nivel_erro": nivel_erro,
        "features": features,
        "resumo_erros": resumo,
        "analise_erros": erros,
        "recomendacoes": recomendacoes,
    }


def salvar_submissao(payload, resultado):
    existe = SUBMISSIONS_FILE.exists()
    with SUBMISSIONS_FILE.open("a", newline="", encoding="utf-8") as arquivo:
        campos = [
            "createdAt",
            "nome",
            "serie",
            "matricula",
            "source",
            "input_id",
            "texto",
            "gabarito",
            "nivel",
            "score",
            "nivel_erro",
            "recomendacoes",
        ]
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        if not existe:
            writer.writeheader()
        aluno = payload.get("aluno") or session.get("aluno") or {}
        writer.writerow({
            "createdAt": payload.get("createdAt", ""),
            "nome": aluno.get("nome", ""),
            "serie": aluno.get("serie", ""),
            "matricula": aluno.get("matricula", ""),
            "source": payload.get("source", ""),
            "input_id": payload.get("id", ""),
            "texto": payload.get("value", ""),
            "gabarito": resultado["gabarito"],
            "nivel": resultado["nivel"],
            "score": resultado["score"],
            "nivel_erro": resultado["nivel_erro"],
            "recomendacoes": " | ".join(resultado["recomendacoes"]),
        })


def get_aluno_id(aluno):
    matricula = str(aluno.get("matricula", "")).strip()
    if matricula.isdigit():
        return int(matricula)

    if df_resultados.empty:
        return 1

    return int(pd.to_numeric(df_resultados["aluno_id"], errors="coerce").max()) + 1


def salvar_resultado_dashboard(payload, resultado):
    global df_resultados, df_erros, df_intervencoes

    aluno = payload.get("aluno") or session.get("aluno") or {}
    aluno_id = get_aluno_id(aluno)
    recomendacoes = " | ".join(resultado["recomendacoes"])

    resultado_row = {
        "aluno_id": aluno_id,
        "texto": resultado["texto_aluno"],
        "gabarito": resultado["gabarito"],
        "nivel": resultado["nivel"],
        "score": resultado["score"],
        "nivel_erro": resultado["nivel_erro"],
    }
    erros_rows = [
        {
            "aluno": erro["aluno"],
            "correto": erro["correto"],
            "tipo": erro["tipo"],
            "distancia": erro["distancia"],
            "aluno_id": aluno_id,
        }
        for erro in resultado["analise_erros"]
    ]
    intervencao_row = {
        "aluno_id": aluno_id,
        "recomendacoes": recomendacoes,
    }

    df_resultados = pd.concat([df_resultados, pd.DataFrame([resultado_row])], ignore_index=True)
    df_erros = pd.concat([df_erros, pd.DataFrame(erros_rows)], ignore_index=True)
    df_intervencoes = pd.concat([df_intervencoes, pd.DataFrame([intervencao_row])], ignore_index=True)

    df_resultados.to_csv(BASE_DIR / "alunos_resultado.csv", index=False)
    df_erros.to_csv(BASE_DIR / "alunos_erros_detalhados.csv", index=False)
    df_intervencoes.to_csv(BASE_DIR / "alunos_intervencao.csv", index=False)


def salvar_cadastro(aluno):
    existe = STUDENTS_FILE.exists()
    with STUDENTS_FILE.open("a", newline="", encoding="utf-8") as arquivo:
        campos = ["nome", "serie", "matricula"]
        writer = csv.DictWriter(arquivo, fieldnames=campos)
        if not existe:
            writer.writeheader()
        writer.writerow(aluno)


def gerar_beep_wav():
    buffer = io.BytesIO()
    sample_rate = 44100
    duration = 0.22
    frequency = 660
    amplitude = 12000

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for i in range(int(sample_rate * duration)):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
            wav_file.writeframes(struct.pack("<h", sample))

    return buffer.getvalue()


@server.route("/")
def home():
    return render_cadastro()


def render_cadastro(error="", nome="", serie="", matricula=""):
    series = ["1 Ano", "2 Ano", "3 Ano", "4 Ano", "5 Ano"]
    return render_template_string(
        CADASTRO_TEMPLATE,
        error=error,
        nome=nome,
        serie=serie,
        matricula=matricula,
        series=series,
    )


@server.post("/cadastro")
def cadastrar_aluno():
    aluno = {
        "nome": request.form.get("nome", "").strip(),
        "serie": request.form.get("serie", "").strip(),
        "matricula": request.form.get("matricula", "").strip(),
    }

    if not all(aluno.values()):
        return render_cadastro(
            error="Preencha nome, serie e matricula.",
            nome=aluno["nome"],
            serie=aluno["serie"],
            matricula=aluno["matricula"],
        ), 400

    session["aluno"] = aluno
    salvar_cadastro(aluno)
    return redirect("/frontend/")


@server.route("/finalizar")
def finalizar_teste():
    session.pop("aluno", None)
    return redirect("/")


@server.route("/frontend/")
def frontend_index():
    if not session.get("aluno"):
        return redirect("/")

    index_path = FRONTEND_DIR / "index.html"
    html_text = index_path.read_text(encoding="utf-8")
    aluno = session.get("aluno") or {}
    api_config = (
        '<script>'
        'window.__API_BASE_URL = window.location.origin;'
        f'window.__STUDENT = {json.dumps(aluno, ensure_ascii=False)};'
        '</script>'
    )
    html_text = html_text.replace('<script src="app.js" defer></script>', api_config + '\n\t\t<script src="app.js" defer></script>')
    return Response(html_text, mimetype="text/html")


@server.route("/frontend/<path:filename>")
def frontend_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@server.post("/api/messages")
@server.post("/api/cloud-inputs")
def receber_texto():
    payload = request.get_json(silent=True) or {}
    texto = str(payload.get("value", "")).strip()

    if not texto:
        return jsonify({"ok": False, "error": "Texto vazio"}), 400

    resultado = analisar_resposta(texto, payload.get("gabarito"))
    salvar_submissao(payload, resultado)
    salvar_resultado_dashboard(payload, resultado)
    return jsonify({"ok": True, "message": "Analise concluida", "analysis": resultado})


@server.post("/api/sound")
def receber_pedido_som():
    audio = gerar_beep_wav()
    return Response(audio, mimetype="audio/wav")

# ============================================
# 🎯 FUNÇÃO CARD
# ============================================
def card(titulo, valor):
    return html.Div([
        html.H4(titulo),
        html.H2(valor)
    ], style={
        "background": "white",
        "padding": "20px",
        "borderRadius": "12px",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.1)",
        "flex": "1",
        "textAlign": "center"
    })

# ============================================
# 🧱 LAYOUT
# ============================================
def make_dashboard_layout():
    aluno_ids = list(df_resultados["aluno_id"].dropna().unique())
    aluno_default = aluno_ids[0] if aluno_ids else None

    return html.Div(style={
        "fontFamily": "Arial",
        "background": "#f4f6f9",
        "padding": "20px"
    }, children=[

    html.H1("📊 Dashboard Inteligente de Alfabetização", style={"textAlign": "center"}),

    # =========================
    # 🎯 FILTRO
    # =========================
    dcc.Dropdown(
        id="aluno-dropdown",
        options=[{"label": f"Aluno {i}", "value": i} for i in aluno_ids],
        value=aluno_default
    ),

    # =========================
    # 🚨 ALERTA
    # =========================
    html.Div(id="alerta"),

    # =========================
    # 📊 CARDS KPI
    # =========================
    html.Div(id="kpis", style={"display": "flex", "gap": "10px", "marginTop": "20px"}),

    # =========================
    # 📈 GRÁFICO ERROS
    # =========================
    dcc.Graph(id="grafico-erros"),

    # =========================
    # ❌ RESUMO + 🧠 INTERVENÇÃO
    # =========================
    html.Div(id="resumo-erros", style={"marginTop": "20px"}),

    # =========================
    # 📋 TABELA DETALHADA
    # =========================
    html.Div(id="tabela-erros", style={"marginTop": "20px"}),

    # =========================
    # 🏆 RANKING
    # =========================
    html.Div([
        html.H3("🏆 Ranking de Alunos"),

        html.Div([
            html.Div([
                html.H4("🔴 Piores (maior score)"),
                html.Ul([
                    html.Li(f"Aluno {row.aluno_id} - Score {row.score}")
                    for _, row in df_resultados.sort_values(by="score", ascending=False).head(5).iterrows()
                ])
            ], style={"flex": 1}),

            html.Div([
                html.H4("🟢 Melhores (menor score)"),
                html.Ul([
                    html.Li(f"Aluno {row.aluno_id} - Score {row.score}")
                    for _, row in df_resultados.sort_values(by="score", ascending=True).head(5).iterrows()
                ])
            ], style={"flex": 1}),

        ], style={"display": "flex", "gap": "20px"})
    ], style={"marginTop": "40px"}),

    # =========================
    # 📊 ROSCA FINAL
    # =========================
    html.Div([
        html.H3("📊 Distribuição de Níveis (Todos os Alunos)", style={"textAlign": "center"}),

        dcc.Graph(
            figure=px.pie(
                df_resultados,
                names="nivel",
                color="nivel",
                hole=0.5
            )
        )
    ], style={"marginTop": "40px"})
    ])


app.layout = make_dashboard_layout

# ============================================
# 🔄 CALLBACK
# ============================================
@app.callback(
    [
        Output("kpis", "children"),
        Output("grafico-erros", "figure"),
        Output("alerta", "children"),
        Output("resumo-erros", "children"),
        Output("tabela-erros", "children"),
    ],
    [Input("aluno-dropdown", "value")]
)
def atualizar(aluno_id):
    if aluno_id is None:
        return [], px.bar(title="Erros do Aluno"), "", "", ""

    df_a = df_resultados[df_resultados["aluno_id"] == aluno_id]
    df_e = df_erros[df_erros["aluno_id"] == aluno_id]
    if df_a.empty:
        return [], px.bar(title="Erros do Aluno"), "", "", ""

    ultimo_resultado = df_a.tail(1)
    contagem = df_e["tipo"].value_counts()
    resumo_metricas = {
        "correto": int(contagem.get("correto", 0)),
        "omissao": int(contagem.get("omissao", 0)),
        "adicao": int(contagem.get("adicao", 0)),
        "substituicao": int(contagem.get("substituicao", 0)),
        "fonologico": int(contagem.get("fonologico", 0)),
    }
    score = (
        (resumo_metricas["omissao"] * 2)
        + resumo_metricas["substituicao"]
        + (resumo_metricas["fonologico"] * 3)
        + resumo_metricas["adicao"]
    )

    nivel = ultimo_resultado["nivel"].values[0]
    nivel_erro, recomendacoes = gerar_recomendacoes(resumo_metricas, nivel, score)

    # =========================
    # 🚨 ALERTA
    # =========================
    if score > 3:
        alerta = html.Div("🚨 Aluno em nível crítico! Intervenção urgente necessária.", style={
            "background": "#ffcccc",
            "padding": "10px",
            "borderRadius": "8px",
            "marginTop": "10px"
        })
    else:
        alerta = html.Div("✅ Situação sob controle", style={
            "background": "#ccffcc",
            "padding": "10px",
            "borderRadius": "8px",
            "marginTop": "10px"
        })

    # =========================
    # 📊 CARDS
    # =========================
    kpis = [
        card("Nível", nivel),
        card("Score total", score),
        card("Nível de Erro", nivel_erro)
    ]

    # =========================
    # 📈 GRÁFICO
    # =========================
    resumo_df = df_e["tipo"].value_counts().reset_index()
    resumo_df.columns = ["tipo", "quantidade"]

    fig = px.bar(resumo_df, x="tipo", y="quantidade", title="Erros do Aluno")

    # =========================
    # ❌ RESUMO DE ERROS
    # =========================
    contagem = resumo_metricas
    resumo = html.Div([
        html.H3("❌ Resumo de tipos"),
        html.Ul([
            html.Li(f"Omissão: {contagem.get('omissao', 0)}"),
            html.Li(f"Adição: {contagem.get('adicao', 0)}"),
            html.Li(f"Substituição: {contagem.get('substituicao', 0)}"),
            html.Li(f"Fonológico: {contagem.get('fonologico', 0)}"),
        ])
    ])

    # =========================
    # 🧠 INTERVENÇÃO
    # =========================
    intervencao = html.Div([
        html.H3("🧠 Intervenções"),
        html.Div(" | ".join(recomendacoes), style={
            "background": "#f8f9fa",
            "padding": "10px",
            "borderRadius": "8px"
        })
    ])

    bloco_resumo = html.Div([resumo, intervencao])

    # =========================
    # 📋 TABELA
    # =========================
    tabela = html.Table([
        html.Thead(
            html.Tr([html.Th(col) for col in df_e.columns])
        ),
        html.Tbody([
            html.Tr([
                html.Td(df_e.iloc[i][col]) for col in df_e.columns
            ]) for i in range(len(df_e))
        ])
    ], style={
        "width": "100%",
        "border": "1px solid #ccc",
        "marginTop": "10px"
    })

    return kpis, fig, alerta, bloco_resumo, tabela


# ============================================
# ▶️ RUN
# ============================================
if __name__ == "__main__":
    app.run(debug=True)
