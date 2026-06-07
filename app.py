# ============================================
# 📦 IMPORTS
# ============================================
from dash import Dash, html, dcc, Input, Output, State, ctx
from flask import Response, jsonify, redirect, render_template_string, request, send_from_directory, session
import pandas as pd
import plotly.express as px
from collections import Counter
from pathlib import Path
import csv
import io
import json
import math
import os
import re
import struct
import unicodedata
import urllib.error
import urllib.request
import wave

try:
    import nltk
    from nltk.classify import NaiveBayesClassifier
    from nltk.metrics.distance import edit_distance as nltk_edit_distance
    from nltk.tokenize import word_tokenize
except ImportError:
    nltk = None
    NaiveBayesClassifier = None
    nltk_edit_distance = None
    word_tokenize = None

# ============================================
# 📂 DADOS
# ============================================
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "psicogenise-main"
SUBMISSIONS_FILE = BASE_DIR / "submissoes_frontend.csv"
STUDENTS_FILE = BASE_DIR / "cadastros_alunos.csv"
RAG_PDF_PATH = Path(os.getenv(
    "PSICOGENISE_RAG_PDF",
    BASE_DIR / "Psicogenese da lingua escrita.pdf"
))
RAG_TEXT_PATH = Path(os.getenv("PSICOGENISE_RAG_TEXT", BASE_DIR / "rag_base.txt"))
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1/chat/completions")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5").strip()
OPENAI_RESPONSES_URL = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses").strip()
RAG_CHUNKS = None

RESULTADOS_COLUMNS = ["aluno_id", "nome", "serie", "matricula", "texto", "gabarito", "nivel", "score", "nivel_erro"]
ERROS_COLUMNS = ["aluno", "correto", "tipo", "distancia", "aluno_id", "nome", "matricula"]
INTERVENCOES_COLUMNS = ["aluno_id", "nome", "matricula", "recomendacoes"]


def carregar_csv(nome_arquivo, colunas):
    caminho = BASE_DIR / nome_arquivo
    if not caminho.exists():
        return pd.DataFrame(columns=colunas)

    df = pd.read_csv(caminho)
    for coluna in colunas:
        if coluna not in df.columns:
            df[coluna] = ""
    return df[colunas]


df_resultados = carregar_csv("alunos_resultado.csv", RESULTADOS_COLUMNS)
df_erros = carregar_csv("alunos_erros_detalhados.csv", ERROS_COLUMNS)
df_intervencoes = carregar_csv("alunos_intervencao.csv", INTERVENCOES_COLUMNS)

# ============================================
# 🎨 APP
# ============================================
app = Dash(
    __name__,
    routes_pathname_prefix="/dashboard/",
    requests_pathname_prefix="/dashboard/",
)
app.config.suppress_callback_exceptions = True
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


def ensure_nltk_resources():
    if nltk is None:
        return False

    resources = [
        ("tokenizers/punkt", "punkt"),
        ("tokenizers/punkt_tab", "punkt_tab"),
    ]
    for resource, package in resources:
        try:
            nltk.data.find(resource)
        except LookupError:
            try:
                nltk.download(package, quiet=True)
            except Exception:
                return False
    return True


def categorizar_features(features, score=0):
    total = features.get("total_palavras", 0)
    tamanho = features.get("tamanho_medio", 0)
    diversidade = features.get("diversidade_lexica", 0)
    erro = features.get("erro_medio", 0)

    return {
        "total_palavras": "curto" if total <= 2 else "medio" if total <= 5 else "longo",
        "tamanho_medio": "baixo" if tamanho <= 2 else "medio" if tamanho <= 4 else "alto",
        "diversidade_lexica": "baixa" if diversidade < 0.65 else "media" if diversidade < 0.9 else "alta",
        "erro_medio": "baixo" if erro <= 0.5 else "medio" if erro <= 2 else "alto",
        "score": "baixo" if score <= 1 else "moderado" if score <= 3 else "alto",
    }


def treinar_classificador_nltk():
    if NaiveBayesClassifier is None:
        return None

    train_data = [
        (categorizar_features({"total_palavras": 1, "tamanho_medio": 1, "diversidade_lexica": 1, "erro_medio": 3}, 6), "pre-silabico"),
        (categorizar_features({"total_palavras": 2, "tamanho_medio": 2, "diversidade_lexica": 0.8, "erro_medio": 2}, 4), "silabico"),
        (categorizar_features({"total_palavras": 3, "tamanho_medio": 3, "diversidade_lexica": 0.8, "erro_medio": 1.2}, 2), "silabico-alfabetico"),
        (categorizar_features({"total_palavras": 4, "tamanho_medio": 4, "diversidade_lexica": 0.9, "erro_medio": 0.4}, 1), "alfabetico"),
        (categorizar_features({"total_palavras": 6, "tamanho_medio": 5, "diversidade_lexica": 1, "erro_medio": 0}, 0), "alfabetizado"),
    ]
    return NaiveBayesClassifier.train(train_data)


NIVEL_CLASSIFIER = treinar_classificador_nltk()


def tokenize_text(texto):
    texto = str(texto).lower()
    if word_tokenize is not None and ensure_nltk_resources():
        try:
            return [
                token
                for token in word_tokenize(texto, language="portuguese")
                if re.search(r"\w", token, flags=re.UNICODE)
            ]
        except LookupError:
            pass
    return re.findall(r"\w+", texto, flags=re.UNICODE)


def distancia_edicao(p1, p2):
    if nltk_edit_distance is not None:
        return nltk_edit_distance(p1, p2)

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
    if dist == 1 and tem_troca_fonologica(aluno, correto):
        return "fonologico"
    if dist == 1:
        return "substituicao"
    return "fonologico"


def tem_troca_fonologica(aluno, correto):
    if len(aluno) != len(correto):
        return False

    diferencas = [(a, c, pos) for pos, (a, c) in enumerate(zip(aluno, correto)) if a != c]
    if len(diferencas) != 1:
        return False

    aluno_letra, correto_letra, posicao = diferencas[0]
    pares_som_proximo = {
        ("u", "o"), ("o", "u"),
        ("l", "u"), ("u", "l"),
        ("s", "z"), ("z", "s"),
    }
    return posicao == len(correto) - 1 and (aluno_letra, correto_letra) in pares_som_proximo


def alinhar_palavras(palavras_aluno, palavras_gabarito):
    len_aluno, len_gabarito = len(palavras_aluno), len(palavras_gabarito)
    dp = [[0] * (len_gabarito + 1) for _ in range(len_aluno + 1)]
    op = [[""] * (len_gabarito + 1) for _ in range(len_aluno + 1)]

    for i in range(1, len_aluno + 1):
        dp[i][0] = i
        op[i][0] = "adicao"
    for j in range(1, len_gabarito + 1):
        dp[0][j] = j
        op[0][j] = "omissao"

    for i in range(1, len_aluno + 1):
        for j in range(1, len_gabarito + 1):
            custo_diagonal = 0 if palavras_aluno[i - 1] == palavras_gabarito[j - 1] else 1
            candidatos = [
                (dp[i - 1][j - 1] + custo_diagonal, "diagonal"),
                (dp[i][j - 1] + 1, "omissao"),
                (dp[i - 1][j] + 1, "adicao"),
            ]
            dp[i][j], op[i][j] = min(candidatos, key=lambda item: item[0])

    alinhamento = []
    i, j = len_aluno, len_gabarito
    while i > 0 or j > 0:
        operacao = op[i][j]
        if operacao == "diagonal":
            alinhamento.append((palavras_aluno[i - 1], palavras_gabarito[j - 1]))
            i -= 1
            j -= 1
        elif operacao == "omissao":
            alinhamento.append(("", palavras_gabarito[j - 1]))
            j -= 1
        else:
            alinhamento.append((palavras_aluno[i - 1], ""))
            i -= 1

    return list(reversed(alinhamento))


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
    if NIVEL_CLASSIFIER is not None:
        return NIVEL_CLASSIFIER.classify(categorizar_features(features, score))

    total = features["total_palavras"]
    erro_medio = features["erro_medio"]

    if score == 0 and total >= 5:
        return "alfabetizado"
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


def adicionar_chunks_rag(text, page):
    text = re.sub(r"\s+", " ", text or "").strip()
    words = text.split()
    chunk_size = 140
    step = 95

    for start in range(0, len(words), step):
        chunk_words = words[start:start + chunk_size]
        if len(chunk_words) < 35:
            continue
        chunk_text = " ".join(chunk_words)
        RAG_CHUNKS.append({
            "page": page,
            "text": chunk_text,
            "tokens": Counter(tokenize_text(chunk_text)),
        })


def carregar_pdf_com_pypdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        return False

    try:
        reader = PdfReader(str(path))
        for page_number, page in enumerate(reader.pages, start=1):
            adicionar_chunks_rag(page.extract_text() or "", page_number)
        return bool(RAG_CHUNKS)
    except Exception:
        return False


def carregar_pdf_com_pymupdf(path):
    try:
        import fitz
    except ImportError:
        return False

    try:
        with fitz.open(path) as doc:
            for page_index in range(doc.page_count):
                adicionar_chunks_rag(doc.load_page(page_index).get_text("text"), page_index + 1)
        return bool(RAG_CHUNKS)
    except Exception:
        return False


def carregar_chunks_rag():
    global RAG_CHUNKS

    if RAG_CHUNKS is not None:
        return RAG_CHUNKS

    RAG_CHUNKS = []
    if RAG_TEXT_PATH.exists():
        try:
            text = RAG_TEXT_PATH.read_text(encoding="utf-8")
            text = re.sub(r"\s+", " ", text).strip()
            words = text.split()
            chunk_size = 140
            step = 95
            for start in range(0, len(words), step):
                chunk_words = words[start:start + chunk_size]
                if len(chunk_words) < 35:
                    continue
                chunk_text = " ".join(chunk_words)
                RAG_CHUNKS.append({
                    "page": "texto",
                    "text": chunk_text,
                    "tokens": Counter(tokenize_text(chunk_text)),
                })
            if RAG_CHUNKS:
                return RAG_CHUNKS
        except Exception:
            RAG_CHUNKS = []

    if not RAG_PDF_PATH.exists():
        return RAG_CHUNKS

    if carregar_pdf_com_pypdf(RAG_PDF_PATH):
        return RAG_CHUNKS

    RAG_CHUNKS = []
    carregar_pdf_com_pymupdf(RAG_PDF_PATH)

    return RAG_CHUNKS


def buscar_contexto_rag(resumo, nivel, score, limite=3):
    chunks = carregar_chunks_rag()
    if not chunks:
        return []

    termos = [
        nivel,
        "alfabetizacao",
        "escrita",
        "crianca",
        "intervencao",
        "erro",
    ]

    if resumo.get("omissao", 0):
        termos.extend(["omissao", "segmentacao", "silabica", "silaba"])
    if resumo.get("substituicao", 0):
        termos.extend(["substituicao", "fonema", "grafema", "correspondencia"])
    if resumo.get("fonologico", 0):
        termos.extend(["fonologico", "consciencia", "som"])
    if resumo.get("adicao", 0):
        termos.extend(["adicao", "revisao", "ortografica"])
    if score > 3:
        termos.extend(["dificuldade", "hipotese", "acompanhamento"])

    query = Counter(tokenize_text(" ".join(termos)))
    ranqueados = []

    for chunk in chunks:
        score_chunk = 0
        for token, peso in query.items():
            score_chunk += min(chunk["tokens"].get(token, 0), 3) * peso
        if score_chunk > 0:
            ranqueados.append((score_chunk, chunk))

    ranqueados.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in ranqueados[:limite]]


def extrair_texto_resposta_openai(result):
    output_text = result.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    partes = []
    for item in result.get("output", []):
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("text"):
                partes.append(str(content["text"]))
    return "\n".join(partes).strip()


def chamar_agente_openai(prompt):
    if not OPENAI_API_KEY:
        return ""

    system_prompt = (
        "Voce e um agente pedagogico de alfabetizacao. Use as metricas do aluno "
        "e os trechos recuperados pelo RAG para criar uma intervencao pratica para "
        "o professor. Nao faca diagnostico clinico, nao cite literalmente o material "
        "e nao invente dados fora do contexto recebido."
    )
    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
        "max_output_tokens": 360,
    }
    data = json.dumps(payload).encode("utf-8")
    request_openai = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_openai, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return extrair_texto_resposta_openai(result)
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError):
        return ""


def chamar_lm_studio(prompt):
    payload = {
        "model": "local-model",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Voce e um assistente pedagogico. Gere orientacoes curtas, "
                    "praticas e sem citar trechos longos do material consultado."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 260,
    }
    data = json.dumps(payload).encode("utf-8")
    request_lm = urllib.request.Request(
        LM_STUDIO_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_lm, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, TimeoutError, json.JSONDecodeError):
        return ""


def compactar_respostas_para_prompt(df_a):
    if df_a is None or df_a.empty:
        return "Sem respostas registradas."

    linhas = []
    for index, row in df_a.tail(8).reset_index(drop=True).iterrows():
        linhas.append(
            f"{index + 1}. aluno escreveu: \"{row.get('texto', '')}\" | "
            f"esperado: \"{row.get('gabarito', '')}\" | "
            f"nivel: {row.get('nivel', '')} | score: {row.get('score', '')}"
        )
    return "\n".join(linhas)


def compactar_erros_para_prompt(df_e):
    if df_e is None or df_e.empty:
        return "Sem erros detalhados registrados."

    linhas = []
    for index, row in df_e.tail(16).reset_index(drop=True).iterrows():
        linhas.append(
            f"{index + 1}. \"{texto_valido(row.get('aluno', ''))}\" -> "
            f"\"{texto_valido(row.get('correto', ''))}\" | "
            f"tipo: {row.get('tipo', '')} | distancia: {row.get('distancia', '')}"
        )
    return "\n".join(linhas)


def formatar_resultados_aluno_para_chat(aluno_info, df_a, df_e, resumo, score, nivel):
    nome = texto_valido(aluno_info.get("nome", "")) or "Aluno sem nome"
    serie = texto_valido(aluno_info.get("serie", "")) or "Serie nao informada"
    matricula = texto_valido(aluno_info.get("matricula", "")) or texto_valido(aluno_info.get("aluno_id", ""))
    nivel_erro, recomendacoes = gerar_recomendacoes(resumo, nivel, score)

    linhas = [
        f"**Resultado de {nome}**",
        f"- Serie: {serie}",
        f"- Matricula: {matricula}",
        f"- Nivel: {nivel}",
        f"- Pontuacao total: {score}",
        f"- Nivel de erro: {nivel_erro}",
        "",
        "**Resumo dos registros analisados**",
        f"- Corretos: {resumo.get('correto', 0)}",
        f"- Omissao: {resumo.get('omissao', 0)}",
        f"- Adicao: {resumo.get('adicao', 0)}",
        f"- Substituicao: {resumo.get('substituicao', 0)}",
        f"- Fonologico: {resumo.get('fonologico', 0)}",
        "",
        "**Escritas comparadas ao esperado**",
    ]

    if df_a is None or df_a.empty:
        linhas.append("- Sem respostas registradas para este aluno.")
    else:
        erros_indexados = []
        if df_e is not None and not df_e.empty:
            erros_indexados = df_e.reset_index(drop=True).to_dict("records")

        for index, row in df_a.reset_index(drop=True).iterrows():
            escrito = texto_valido(row.get("texto", "")) or "(em branco)"
            esperado = texto_valido(row.get("gabarito", "")) or "(sem gabarito)"
            nivel_item = texto_valido(row.get("nivel", ""))
            score_item = texto_valido(row.get("score", ""))

            tipo = ""
            distancia = ""
            if index < len(erros_indexados):
                tipo = texto_valido(erros_indexados[index].get("tipo", ""))
                distancia = texto_valido(erros_indexados[index].get("distancia", ""))

            detalhes = []
            if tipo:
                detalhes.append(f"tipo: {tipo}")
            if distancia:
                detalhes.append(f"distancia: {distancia}")
            if nivel_item:
                detalhes.append(f"nivel: {nivel_item}")
            if score_item:
                detalhes.append(f"score: {score_item}")

            sufixo = f" | {'; '.join(detalhes)}" if detalhes else ""
            linhas.append(f"{index + 1}. escreveu **{escrito}** | esperado **{esperado}**{sufixo}")

    linhas.extend([
        "",
        "**Leitura pedagogica rapida**",
        "A frase pode aparecer em mais de uma linha porque o sistema separa as palavras para comparar a escrita com o gabarito.",
        f"Foco sugerido: {' | '.join(recomendacoes)}.",
    ])
    return "\n".join(linhas)


def gerar_intervencao_rag(resumo, nivel, score, aluno_info=None, df_a=None, df_e=None):
    nivel_erro, recomendacoes = gerar_recomendacoes(resumo, nivel, score)
    contexto = buscar_contexto_rag(resumo, nivel, score)

    if not contexto:
        return nivel_erro, " | ".join(recomendacoes), []

    aluno_info = aluno_info if aluno_info is not None else {}
    nome = texto_valido(aluno_info.get("nome", "")) or "Aluno sem nome"
    serie = texto_valido(aluno_info.get("serie", "")) or "Serie nao informada"
    matricula = texto_valido(aluno_info.get("matricula", "")) or texto_valido(aluno_info.get("aluno_id", ""))
    respostas_prompt = compactar_respostas_para_prompt(df_a)
    erros_prompt = compactar_erros_para_prompt(df_e)
    contexto_prompt = "\n\n".join(
        f"Pagina {item['page']}: {item['text'][:900]}"
        for item in contexto
    )
    prompt = f"""
Dados do aluno:
- Nome: {nome}
- Serie: {serie}
- Matricula: {matricula}
- Nivel: {nivel}
- Score: {score}
- Nivel de erro: {nivel_erro}
- Omissao: {resumo.get('omissao', 0)}
- Adicao: {resumo.get('adicao', 0)}
- Substituicao: {resumo.get('substituicao', 0)}
- Fonologico: {resumo.get('fonologico', 0)}

Producoes escritas do aluno:
{respostas_prompt}

Analise detalhada de acertos e erros:
{erros_prompt}

Base pedagogica recuperada do RAG:
{contexto_prompt}

Tarefa:
Gere uma leitura pedagogica para o professor em ate 8 linhas.
Organize em quatro partes curtas:
1. Padrao observado na escrita.
2. O que esses acertos e erros sugerem pedagogicamente.
3. Intervencao recomendada para esta semana.
4. Como acompanhar a evolucao no proximo teste.
Nao cite literalmente o livro. Nao faca diagnostico clinico. Use linguagem clara, pratica e aplicavel em sala.
"""

    resposta_gpt = chamar_agente_openai(prompt)
    if resposta_gpt:
        return nivel_erro, resposta_gpt, contexto

    resposta_llm = chamar_lm_studio(prompt)
    if resposta_llm:
        return nivel_erro, resposta_llm, contexto

    fallback = " | ".join(recomendacoes)
    fallback += " | Base RAG consultada: Psicogenese da lingua escrita"
    return nivel_erro, fallback, contexto


def mensagem_status_rag(contexto):
    if contexto:
        paginas = []
        for item in contexto:
            page = str(item["page"])
            if page not in paginas:
                paginas.append(page)
        if paginas == ["texto"]:
            return "RAG: base textual consultada em rag_base.txt."
        return f"RAG: base consultada nos trechos/paginas {', '.join(paginas)}."
    if RAG_TEXT_PATH.exists():
        return "RAG: arquivo de texto encontrado, mas sem trechos suficientes para recuperacao."
    if RAG_PDF_PATH.exists():
        return "RAG: PDF encontrado, mas sem texto extraivel. Gere OCR para rag_base.txt ou use um PDF textual."
    return "RAG: nenhum PDF/texto encontrado; usando regras internas."


def obter_contexto_aluno_dashboard(aluno_id):
    aluno_id_texto = str(aluno_id)
    df_a = df_resultados[df_resultados["aluno_id"].astype(str) == aluno_id_texto]
    df_e = df_erros[df_erros["aluno_id"].astype(str) == aluno_id_texto]
    if df_a.empty:
        return None

    aluno_info = df_a.tail(1).iloc[0]
    contagem = df_e["tipo"].value_counts()
    resumo = {
        "correto": int(contagem.get("correto", 0)),
        "omissao": int(contagem.get("omissao", 0)),
        "adicao": int(contagem.get("adicao", 0)),
        "substituicao": int(contagem.get("substituicao", 0)),
        "fonologico": int(contagem.get("fonologico", 0)),
    }
    score = (
        (resumo["omissao"] * 2)
        + resumo["substituicao"]
        + (resumo["fonologico"] * 3)
        + resumo["adicao"]
    )
    nivel = aluno_info["nivel"]
    return aluno_info, df_a, df_e, resumo, score, nivel


def normalizar_pergunta(texto):
    texto = unicodedata.normalize("NFD", str(texto or "").lower())
    texto = "".join(char for char in texto if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def responder_dado_direto(pergunta, aluno_info, resumo, score, nivel, df_a=None, df_e=None):
    pergunta_normalizada = normalizar_pergunta(pergunta)
    nome = texto_valido(aluno_info.get("nome", "")) or "Aluno sem nome"
    serie = texto_valido(aluno_info.get("serie", "")) or "Serie nao informada"
    matricula = texto_valido(aluno_info.get("matricula", "")) or texto_valido(aluno_info.get("aluno_id", ""))

    termos_resultado = [
        "resultado",
        "resultados",
        "resposta",
        "respostas",
        "desempenho",
        "relatorio",
        "producao",
        "producoes",
        "escrita",
        "escritas",
        "gabarito",
        "gabaritos",
    ]
    termos_de_orientacao = [
        "atividade",
        "atividades",
        "intervencao",
        "intervencoes",
        "sugestao",
        "sugestoes",
        "aula",
    ]
    if (
        any(termo in pergunta_normalizada for termo in termos_resultado)
        and not any(termo in pergunta_normalizada for termo in termos_de_orientacao)
    ):
        return formatar_resultados_aluno_para_chat(aluno_info, df_a, df_e, resumo, score, nivel)

    if "nome" in pergunta_normalizada and "aluno" in pergunta_normalizada:
        return f"O nome do aluno selecionado e {nome}."
    if "matricula" in pergunta_normalizada:
        return f"A matricula de {nome} e {matricula}."
    if "serie" in pergunta_normalizada or "ano" in pergunta_normalizada:
        return f"{nome} esta na serie {serie}."
    if "nivel" in pergunta_normalizada:
        return f"O nivel atual de {nome} e {nivel}, com nivel de erro {gerar_recomendacoes(resumo, nivel, score)[0]}."
    if "score" in pergunta_normalizada or "pontuacao" in pergunta_normalizada or "nota" in pergunta_normalizada:
        return f"A pontuacao total de {nome} e {score}."
    if "acerto" in pergunta_normalizada or "correto" in pergunta_normalizada:
        return f"{nome} teve {resumo.get('correto', 0)} registro(s) correto(s) na analise detalhada."
    if "erro" in pergunta_normalizada or "erros" in pergunta_normalizada:
        return (
            f"Resumo dos erros de {nome}: "
            f"omissao {resumo.get('omissao', 0)}, "
            f"adicao {resumo.get('adicao', 0)}, "
            f"substituicao {resumo.get('substituicao', 0)} e "
            f"fonologico {resumo.get('fonologico', 0)}."
        )
    return ""


def formatar_historico_prompt(historico):
    historico = historico or []
    if not historico:
        return "Sem conversas anteriores nesta sessao."

    linhas = []
    for index, item in enumerate(historico[-8:], start=1):
        pergunta = str(item.get("pergunta", "")).strip()
        resposta = str(item.get("resposta", "")).strip()
        if pergunta or resposta:
            linhas.append(f"{index}. Professor: {pergunta}\nAssistente: {resposta}")
    return "\n\n".join(linhas) or "Sem conversas anteriores nesta sessao."


def responder_pergunta_professor(pergunta, aluno_id, historico=None):
    pergunta = str(pergunta or "").strip()
    if not pergunta:
        return "Digite uma pergunta para o assistente."

    contexto_aluno = obter_contexto_aluno_dashboard(aluno_id)
    if not contexto_aluno:
        return "Selecione um aluno com resultados registrados."

    aluno_info, df_a, df_e, resumo, score, nivel = contexto_aluno
    nivel_erro, recomendacoes = gerar_recomendacoes(resumo, nivel, score)
    resposta_direta = responder_dado_direto(pergunta, aluno_info, resumo, score, nivel, df_a=df_a, df_e=df_e)
    if resposta_direta:
        return resposta_direta

    contexto = buscar_contexto_rag(resumo, nivel, score)
    contexto_prompt = "\n\n".join(
        f"Pagina {item['page']}: {item['text'][:700]}"
        for item in contexto
    ) or "Sem trechos RAG recuperados."

    nome = texto_valido(aluno_info.get("nome", "")) or "Aluno sem nome"
    serie = texto_valido(aluno_info.get("serie", "")) or "Serie nao informada"
    matricula = texto_valido(aluno_info.get("matricula", "")) or texto_valido(aluno_info.get("aluno_id", ""))
    prompt = f"""
O professor perguntou:
{pergunta}

Historico recente da conversa:
{formatar_historico_prompt(historico)}

Aluno em foco:
- Nome: {nome}
- Serie: {serie}
- Matricula: {matricula}
- Nivel: {nivel}
- Score: {score}
- Nivel de erro: {nivel_erro}
- Resumo: {resumo}

Producoes escritas:
{compactar_respostas_para_prompt(df_a)}

Erros detalhados:
{compactar_erros_para_prompt(df_e)}

Base pedagogica recuperada:
{contexto_prompt}

Responda ao professor em linguagem clara, objetiva e acolhedora.
Inclua uma sugestao pratica de atividade e uma forma simples de acompanhar evolucao.
Nao faca diagnostico clinico e nao cite literalmente o material.
"""
    resposta = chamar_agente_openai(prompt) or chamar_lm_studio(prompt)
    if resposta:
        return resposta

    return (
        "Sugestao: retome as escritas do aluno uma a uma, compare oralmente o que ele escreveu "
        "com o som esperado e proponha uma atividade curta de reescrita mediada. "
        f"Foco inicial: {' | '.join(recomendacoes)}."
    )


def renderizar_chat_professor(historico):
    historico = historico or []
    if not historico:
        return html.Div(
            "As perguntas e respostas desta sessao aparecerao aqui.",
            style={
                "color": "#64748b",
                "fontSize": "13px",
                "fontStyle": "italic",
            },
        )

    mensagens = []
    for item in historico:
        pergunta = str(item.get("pergunta", "")).strip()
        resposta = str(item.get("resposta", "")).strip()
        if pergunta:
            mensagens.append(html.Div([
                html.Div("Professor", style={"fontSize": "11px", "fontWeight": "700", "color": "#1e3a8a"}),
                html.Div(pergunta),
            ], style={
                "marginLeft": "auto",
                "maxWidth": "82%",
                "background": "#dbeafe",
                "border": "1px solid rgba(37, 99, 235, 0.18)",
                "padding": "10px 12px",
                "borderRadius": "8px",
                "marginBottom": "8px",
                "color": "#0f172a",
            }))
        if resposta:
            mensagens.append(html.Div([
                html.Div("Assistente", style={"fontSize": "11px", "fontWeight": "700", "color": "#047857"}),
                dcc.Markdown(resposta, style={"margin": "0", "lineHeight": "1.5"}),
            ], style={
                "maxWidth": "88%",
                "background": "rgba(255,255,255,0.86)",
                "border": "1px solid rgba(16, 185, 129, 0.18)",
                "padding": "10px 12px",
                "borderRadius": "8px",
                "marginBottom": "8px",
                "color": "#111827",
            }))

    return mensagens


def analisar_resposta(texto_aluno, gabarito_texto=None):
    gabarito = gabarito_texto or escolher_gabarito(texto_aluno)
    palavras_aluno = tokenize_text(texto_aluno)
    palavras_gabarito = tokenize_text(gabarito)
    erros = []

    for aluno, correto in alinhar_palavras(palavras_aluno, palavras_gabarito):
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
    nome = str(aluno.get("nome", "")).strip()
    serie = str(aluno.get("serie", "")).strip()
    matricula = str(aluno.get("matricula", "")).strip()
    recomendacoes = " | ".join(resultado["recomendacoes"])

    resultado_row = {
        "aluno_id": aluno_id,
        "nome": nome,
        "serie": serie,
        "matricula": matricula,
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
            "nome": nome,
            "matricula": matricula,
        }
        for erro in resultado["analise_erros"]
    ]
    intervencao_row = {
        "aluno_id": aluno_id,
        "nome": nome,
        "matricula": matricula,
        "recomendacoes": recomendacoes,
    }

    df_resultados = pd.concat([df_resultados, pd.DataFrame([resultado_row])], ignore_index=True)
    df_erros = pd.concat([df_erros, pd.DataFrame(erros_rows)], ignore_index=True)
    df_intervencoes = pd.concat([df_intervencoes, pd.DataFrame([intervencao_row])], ignore_index=True)

    df_resultados.to_csv(BASE_DIR / "alunos_resultado.csv", index=False, columns=RESULTADOS_COLUMNS)
    df_erros.to_csv(BASE_DIR / "alunos_erros_detalhados.csv", index=False, columns=ERROS_COLUMNS)
    df_intervencoes.to_csv(BASE_DIR / "alunos_intervencao.csv", index=False, columns=INTERVENCOES_COLUMNS)


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
    app_js_version = int((FRONTEND_DIR / "app.js").stat().st_mtime)
    aluno = session.get("aluno") or {}
    api_config = (
        '<script>'
        'window.__API_BASE_URL = window.location.origin;'
        f'window.__STUDENT = {json.dumps(aluno, ensure_ascii=False)};'
        '</script>'
    )
    html_text = html_text.replace(
        '<script src="app.js" defer></script>',
        api_config + f'\n\t\t<script src="app.js?v={app_js_version}" defer></script>'
    )
    response = Response(html_text, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@server.route("/frontend/<path:filename>")
def frontend_static(filename):
    response = send_from_directory(FRONTEND_DIR, filename, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


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
def grafico_distribuicao_niveis():
    if df_resultados.empty:
        return px.imshow(
            [[0]],
            x=["sem dados"],
            y=["sem dados"],
            text_auto=True,
            labels={"x": "Nivel de erro", "y": "Nivel", "color": "Quantidade"},
            title="Distribuicao de Niveis (Todos os Alunos)"
        )

    matriz = pd.crosstab(df_resultados["nivel"], df_resultados["nivel_erro"])
    ordem_niveis = [
        "pre-silabico",
        "silabico",
        "silabico-alfabetico",
        "alfabetico",
        "alfabetizado",
    ]
    ordem_erros = ["baixo", "moderado", "alto"]

    matriz = matriz.reindex(
        index=[nivel for nivel in ordem_niveis if nivel in matriz.index],
        columns=[erro for erro in ordem_erros if erro in matriz.columns],
        fill_value=0,
    )

    fig = px.imshow(
        matriz,
        text_auto=True,
        aspect="auto",
        color_continuous_scale="YlGnBu",
        labels={"x": "Nivel de erro", "y": "Nivel", "color": "Quantidade"},
        title="Distribuicao de Niveis (Todos os Alunos)"
    )
    fig.update_layout(margin={"l": 40, "r": 20, "t": 60, "b": 40})
    return fig


def texto_valido(valor):
    texto = str(valor or "").strip()
    return "" if texto.lower() == "nan" else texto


def rotulo_aluno(row):
    nome = texto_valido(row.get("nome", ""))
    matricula = texto_valido(row.get("matricula", ""))
    aluno_id = texto_valido(row.get("aluno_id", ""))

    rotulo = nome or f"Aluno {aluno_id}"
    if matricula:
        rotulo += f" - Matricula {matricula}"
    return rotulo


def alunos_para_dropdown():
    if df_resultados.empty:
        return []
    return (
        df_resultados
        .drop_duplicates(subset=["aluno_id"], keep="last")
        .sort_values(by="nome", na_position="last")
        .to_dict("records")
    )


def ranking_alunos(ascendente=False):
    if df_resultados.empty:
        return []

    ranking = (
        df_resultados
        .groupby(["aluno_id", "nome", "matricula"], dropna=False, as_index=False)["score"]
        .sum()
        .sort_values(by="score", ascending=ascendente)
        .head(5)
    )
    return ranking.to_dict("records")


def make_dashboard_layout():
    alunos = alunos_para_dropdown()
    aluno_default = alunos[0]["aluno_id"] if alunos else None

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
        options=[{"label": rotulo_aluno(aluno), "value": aluno["aluno_id"]} for aluno in alunos],
        value=aluno_default,
        placeholder="Selecione um aluno"
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
                    html.Li(f"{rotulo_aluno(row)} - Score {row['score']}")
                    for row in ranking_alunos(ascendente=False)
                ])
            ], style={"flex": 1}),

            html.Div([
                html.H4("🟢 Melhores (menor score)"),
                html.Ul([
                    html.Li(f"{rotulo_aluno(row)} - Score {row['score']}")
                    for row in ranking_alunos(ascendente=True)
                ])
            ], style={"flex": 1}),

        ], style={"display": "flex", "gap": "20px"})
    ], style={"marginTop": "40px"}),

    # =========================
    # 📊 ROSCA FINAL
    # =========================
    html.Div([
        html.H3("📊 Distribuição de Níveis (Todos os Alunos)", style={"textAlign": "center"}),

        dcc.Graph(figure=grafico_distribuicao_niveis())
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

    aluno_id_texto = str(aluno_id)
    df_a = df_resultados[df_resultados["aluno_id"].astype(str) == aluno_id_texto]
    df_e = df_erros[df_erros["aluno_id"].astype(str) == aluno_id_texto]
    if df_a.empty:
        return [], px.bar(title="Erros do Aluno"), "", "", ""

    ultimo_resultado = df_a.tail(1)
    aluno_info = ultimo_resultado.iloc[0]
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
    nivel_erro, intervencao_texto, contexto_rag = gerar_intervencao_rag(
        resumo_metricas,
        nivel,
        score,
        aluno_info=aluno_info,
        df_a=df_a,
        df_e=df_e,
    )

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
        card("Aluno", texto_valido(aluno_info.get("nome", "")) or "Sem nome"),
        card("Matricula", texto_valido(aluno_info.get("matricula", "")) or texto_valido(aluno_info.get("aluno_id", ""))),
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
    intervencao_markdown = str(intervencao_texto or "").replace(" | ", "\n\n")
    nome_aluno = texto_valido(aluno_info.get("nome", "")) or "Aluno sem nome"
    serie_aluno = texto_valido(aluno_info.get("serie", "")) or "Serie nao informada"
    matricula_aluno = texto_valido(aluno_info.get("matricula", "")) or texto_valido(aluno_info.get("aluno_id", ""))
    intervencao = html.Div([
        html.Div([
            html.Div("AI", style={
                "width": "44px",
                "height": "44px",
                "borderRadius": "50%",
                "display": "grid",
                "placeItems": "center",
                "background": "linear-gradient(135deg, #e0f2fe, #dcfce7)",
                "border": "1px solid rgba(37, 99, 235, 0.22)",
                "color": "#1d4ed8",
                "fontWeight": "800",
                "boxShadow": "0 8px 20px rgba(37, 99, 235, 0.12)",
                "flex": "0 0 auto",
            }),
            html.Div([
                html.H3("Assistente de intervencao", style={
                    "margin": "0",
                    "fontSize": "18px",
                    "color": "#0f172a",
                }),
                html.Div(f"{nome_aluno} | {serie_aluno} | Matricula {matricula_aluno}", style={
                    "marginTop": "3px",
                    "fontSize": "13px",
                    "color": "#475569",
                }),
            ]),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "gap": "12px",
            "marginBottom": "12px",
        }),
        dcc.Markdown(intervencao_markdown, style={
            "background": "rgba(248, 250, 252, 0.78)",
            "border": "1px solid rgba(37, 99, 235, 0.12)",
            "padding": "14px 16px",
            "borderRadius": "8px",
            "lineHeight": "1.55",
            "color": "#111827",
            "whiteSpace": "pre-wrap",
        }),
        html.Div([
            html.Div("Pergunte ao assistente sobre este aluno", style={
                "fontWeight": "700",
                "fontSize": "13px",
                "color": "#1e3a8a",
                "marginBottom": "6px",
            }),
            dcc.Store(id="professor-chat-history", data=[]),
            html.Div(id="professor-chat-thread", children=renderizar_chat_professor([]), style={
                "maxHeight": "320px",
                "overflowY": "auto",
                "padding": "12px",
                "borderRadius": "8px",
                "background": "rgba(248, 250, 252, 0.62)",
                "border": "1px dashed rgba(37, 99, 235, 0.22)",
                "marginBottom": "10px",
            }),
            dcc.Textarea(
                id="professor-prompt",
                placeholder="Ex.: Que atividade posso fazer com este aluno na proxima aula?",
                style={
                    "width": "100%",
                    "minHeight": "72px",
                    "resize": "vertical",
                    "border": "1px solid rgba(37, 99, 235, 0.25)",
                    "borderRadius": "8px",
                    "padding": "10px 12px",
                    "fontFamily": "Arial",
                    "fontSize": "14px",
                    "boxSizing": "border-box",
                    "background": "rgba(255,255,255,0.9)",
                },
            ),
            html.Div([
                html.Button("Enviar pergunta", id="professor-prompt-button", n_clicks=0, style={
                    "padding": "9px 14px",
                    "borderRadius": "999px",
                    "border": "1px solid rgba(37, 99, 235, 0.28)",
                    "background": "#2563eb",
                    "color": "white",
                    "fontWeight": "700",
                    "cursor": "pointer",
                }),
                html.Button("Encerrar interacao", id="professor-chat-clear", n_clicks=0, style={
                    "padding": "9px 14px",
                    "borderRadius": "999px",
                    "border": "1px solid rgba(100, 116, 139, 0.28)",
                    "background": "rgba(255,255,255,0.9)",
                    "color": "#334155",
                    "fontWeight": "700",
                    "cursor": "pointer",
                }),
            ], style={
                "display": "flex",
                "gap": "8px",
                "flexWrap": "wrap",
                "marginTop": "8px",
            }),
        ], style={
            "marginTop": "12px",
            "paddingTop": "12px",
            "borderTop": "1px solid rgba(37, 99, 235, 0.12)",
        }),
        html.Small(
            mensagem_status_rag(contexto_rag),
            style={"display": "block", "marginTop": "8px", "color": "#6b7280"}
        )
    ], style={
        "background": "linear-gradient(135deg, rgba(255,255,255,0.92), rgba(239,246,255,0.78))",
        "border": "1px solid rgba(37, 99, 235, 0.14)",
        "borderRadius": "8px",
        "padding": "14px",
        "boxShadow": "0 12px 28px rgba(15, 23, 42, 0.07)",
    })

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


@app.callback(
    [
        Output("professor-chat-thread", "children"),
        Output("professor-prompt", "value"),
        Output("professor-chat-history", "data"),
    ],
    [
        Input("professor-prompt-button", "n_clicks"),
        Input("professor-chat-clear", "n_clicks"),
    ],
    [
        State("professor-prompt", "value"),
        State("aluno-dropdown", "value"),
        State("professor-chat-history", "data"),
    ],
    prevent_initial_call=True,
)
def conversar_com_assistente(n_clicks, clear_clicks, pergunta, aluno_id, historico):
    historico = historico or []
    if ctx.triggered_id == "professor-chat-clear":
        return renderizar_chat_professor([]), "", []

    if not n_clicks:
        return renderizar_chat_professor(historico), "", historico

    pergunta = str(pergunta or "").strip()
    if not pergunta:
        return renderizar_chat_professor(historico), "", historico

    resposta = responder_pergunta_professor(pergunta, aluno_id, historico=historico)
    historico_atualizado = historico + [{
        "pergunta": pergunta,
        "resposta": str(resposta or ""),
    }]
    return renderizar_chat_professor(historico_atualizado), "", historico_atualizado


@app.callback(
    [
        Output("professor-chat-thread", "children", allow_duplicate=True),
        Output("professor-chat-history", "data", allow_duplicate=True),
        Output("professor-prompt", "value", allow_duplicate=True),
    ],
    [Input("aluno-dropdown", "value")],
    prevent_initial_call=True,
)
def limpar_chat_ao_trocar_aluno(aluno_id):
    return renderizar_chat_professor([]), [], ""


# ============================================
# ▶️ RUN
# ============================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
