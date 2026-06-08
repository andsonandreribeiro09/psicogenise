# Psicogenise

Psicogenise e um prototipo funcional para apoio a avaliacao inicial de alfabetizacao. O sistema combina uma tela ludica para o aluno ouvir palavras/frase e digitar o que entendeu, com um dashboard para o professor analisar erros, pontuacao, nivel estimado e recomendacoes de intervencao.

## Objetivo

O projeto foi criado para validar um fluxo simples de diagnostico:

1. O aluno faz um cadastro rapido com nome, serie e matricula.
2. O aluno acessa uma tela com nuvens e botoes de megafone.
3. Cada megafone fala uma palavra ou frase.
4. O aluno digita a resposta no campo correspondente.
5. As respostas sao enviadas ao backend.
6. O professor acompanha os resultados no dashboard.

## Funcionalidades

- Cadastro do aluno antes do teste.
- Frontend interativo com nuvens, campos de resposta e botoes de audio.
- Fala em portugues usando sintese de voz do navegador.
- Quatro palavras simples e uma frase curta para avaliacao.
- Processamento automatico de respostas com distancia de edicao.
- Tokenizacao e metricas textuais com NLTK.
- Estimativa de nivel com classificador Naive Bayes do NLTK.
- Classificacao de erros: correto, omissao, adicao, substituicao e fonologico.
- Calculo de score e nivel de erro.
- Recomendacoes pedagogicas com base nos tipos de erro.
- Apoio RAG para enriquecer as intervencoes do professor com um PDF pedagogico local.
- Dashboard em Dash para visualizacao das metricas pelo professor.
- Salvamento dos resultados em arquivos CSV.

## Tecnologias

- Python
- Flask
- Dash
- NLTK
- Pandas
- Plotly
- PyPDF
- HTML
- CSS
- JavaScript

## Estrutura

```text
psicogenise-main/
|-- app.py
|-- requirements.txt
|-- alunos_resultado.csv
|-- alunos_erros_detalhados.csv
|-- alunos_intervencao.csv
|-- README.md
`-- psicogenise-main/
    |-- index.html
    |-- app.js
    |-- styles.css
    |-- fundo.jpg
    |-- nuvem.png
    |-- som.gif
    `-- LICENSE
```

## Como Rodar Localmente

Entre na pasta raiz do projeto:

```powershell
cd "C:\Users\andso\Downloads\psicogenise-main"
```

Instale as dependencias:

```powershell
py -m pip install -r requirements.txt
```

Inicie o servidor:

```powershell
py app.py
```

Depois acesse no navegador:

```text
http://127.0.0.1:8050/
```

## Rotas Principais

| Rota | Descricao |
| --- | --- |
| `/` | Tela de cadastro do aluno |
| `/frontend/` | Tela do teste com nuvens e megafones |
| `/dashboard/` | Dashboard do professor |
| `/api/messages` | Recebe resposta do campo principal |
| `/api/cloud-inputs` | Recebe resposta dos campos das nuvens |
| `/api/sound` | Endpoint de som auxiliar |
| `/finalizar` | Finaliza o teste e volta ao cadastro |

## RAG Para Intervencoes

O campo **Intervencoes** do dashboard pode usar um PDF pedagogico local como base RAG. Por padrao, o projeto procura o PDF configurado no `app.py`.

Para usar outro caminho, defina a variavel de ambiente antes de iniciar o app:

```powershell
$env:PSICOGENISE_RAG_PDF="C:\caminho\para\material.pdf"
py app.py
```

O PDF nao deve ser enviado para o GitHub. Ele fica ignorado pelo `.gitignore`.

Observacao: se o PDF for escaneado como imagem, o Python nao consegue extrair texto diretamente. Nesse caso, gere um OCR do material e salve como `rag_base.txt` na raiz do projeto, ou informe outro arquivo de texto:

```powershell
$env:PSICOGENISE_RAG_TEXT="C:\caminho\para\base_ocr.txt"
py app.py
```

### Uso Com LM Studio

Se o LM Studio estiver rodando com uma API local compativel com OpenAI, o backend tenta gerar uma intervencao textual mais rica em:

```text
http://127.0.0.1:1234/v1/chat/completions
```

Tambem e possivel alterar esse endpoint:

```powershell
$env:LM_STUDIO_URL="http://127.0.0.1:1234/v1/chat/completions"
py app.py
```

Se o LM Studio estiver desligado, o sistema continua funcionando e usa recomendacoes internas com apoio dos trechos recuperados do PDF.

Importante para deploy: o LM Studio e um aplicativo desktop/local, nao uma dependencia Python. Ele nao deve entrar em `requirements.txt` e nao roda dentro do Render. Em producao no Render, use OpenAI API e/ou regras internas.

### Uso Com Langflow + LM Studio Local

Para atender ao fluxo visual do projeto, o sistema tambem pode chamar um fluxo do Langflow antes das outras camadas.

Fluxo recomendado:

```text
Dashboard -> app.py -> Langflow -> LM Studio -> resposta do professor
```

No LM Studio:

1. Abra o LM Studio.
2. Carregue um modelo local.
3. Inicie o servidor local em `http://127.0.0.1:1234`.
4. Confirme em `http://127.0.0.1:1234/v1/models`.

No Langflow:

1. Instale o Langflow em um ambiente local separado. Opcionalmente use:

```powershell
py -m pip install -r requirements-local.txt
```

2. Inicie o Langflow localmente.

```powershell
langflow run
```

3. Abra `http://127.0.0.1:7860`.
4. Crie um fluxo simples com entrada de chat, prompt, modelo local compativel com OpenAI e saida de chat.
5. Configure o componente do modelo para apontar para o LM Studio:

```text
Base URL: http://127.0.0.1:1234/v1
API Key: lm-studio
Model: nome do modelo carregado no LM Studio
```

6. Monte o fluxo visual assim:

```text
Entrada de bate-papo -> Modelo de prompt -> LM Studio -> Saida do chat
```

7. No componente **Modelo de prompt**, use um texto alinhado ao projeto:

```text
Voce e um assistente pedagogico de alfabetizacao.
Use os dados do aluno, os acertos/erros e os trechos RAG enviados pela aplicacao.
A base RAG vem do PDF/TXT "Psicogenese da lingua escrita".
Responda ao professor com linguagem clara, objetiva e acolhedora.
Sugira intervencoes praticas de sala de aula.
Nao faca diagnostico clinico, nao cite literalmente o livro e nao invente dados.
```

8. Copie o ID do fluxo e configure antes de iniciar o app:

```powershell
$env:LANGFLOW_URL="http://127.0.0.1:7860"
$env:LANGFLOW_FLOW_ID="id-do-seu-fluxo"
py app.py
```

Se o fluxo exigir chave de API:

```powershell
$env:LANGFLOW_API_KEY="sua-chave-do-langflow"
```

O dashboard mostra o status do fluxo em **Assistente de intervencao > Fluxo do agente**. Tambem e possivel abrir:

```text
http://127.0.0.1:8050/api/agent-status
```

Importante para deploy: o Langflow local tambem nao deve ser instalado no `requirements.txt` principal. No Render, `127.0.0.1:7860` apontaria para o proprio servidor do Render, nao para o computador local. Para evitar lentidao ou fallback desnecessario no Render, deixe `LANGFLOW_FLOW_ID` vazio e use `AGENT_PROVIDERS=openai,rules`.

### Uso Com Agente GPT Pela API OpenAI

Para passar a intervencao por um agente GPT, configure uma chave da API OpenAI antes de iniciar o app. Nao coloque a chave dentro do codigo.

```powershell
$env:OPENAI_API_KEY="sua-chave-da-api"
$env:OPENAI_MODEL="gpt-5"
py app.py
```

Fluxo usado pelo sistema:

```text
metricas do aluno -> RAG busca trechos em rag_base.txt -> Langflow/OpenAI/LM Studio gera intervencao -> dashboard
```

O prompt enviado ao agente inclui nome, serie, matricula, respostas digitadas, gabaritos, acertos, erros e tipos de erro do aluno selecionado no dashboard. Esses dados sao usados como contexto da intervencao atual; o modelo nao e treinado permanentemente com os dados do aluno.

Ordem de fallback:

1. Agente GPT via OpenAI API, se `OPENAI_API_KEY` existir.
2. Langflow, se `LANGFLOW_FLOW_ID` existir.
3. LM Studio local direto, se estiver rodando.
4. Regras internas do sistema.

No dashboard, a secao **Fluxo do agente** permite ligar ou desligar GPT-5, Langflow, LM Studio e Regras internas sem alterar codigo.

Observacao: assinatura ChatGPT Plus/Pro e uso da OpenAI API sao cobrancas separadas. O backend precisa de uma chave de API para chamar o modelo.

### Configuracao Recomendada No Render

No Render, mantenha os recursos locais desligados e use apenas API/remedios internos:

```text
OPENAI_API_KEY=sua-chave-da-api
OPENAI_MODEL=gpt-5
AGENT_PROVIDER=openai
AGENT_PROVIDERS=openai,rules
LANGFLOW_FLOW_ID=
```

Se a API OpenAI nao tiver cota disponivel, use:

```text
AGENT_PROVIDERS=rules
```

Assim o Render nao tenta depender de LM Studio ou Langflow locais.

## Fluxo de Uso

1. O professor abre `http://127.0.0.1:8050/`.
2. Informa nome, serie e matricula do aluno.
3. O aluno clica em cada megafone.
4. O aluno digita o que ouviu e pressiona `Enter`.
5. Depois das cinco respostas, o sistema volta automaticamente para o cadastro.
6. O professor acessa `http://127.0.0.1:8050/dashboard/` para analisar os resultados.

## Arquivos de Dados

O dashboard usa estes arquivos:

- `alunos_resultado.csv`
- `alunos_erros_detalhados.csv`
- `alunos_intervencao.csv`

Durante o uso local, o sistema tambem pode gerar:

- `cadastros_alunos.csv`
- `submissoes_frontend.csv`

Esses dois arquivos podem conter dados de alunos e, por isso, ficam no `.gitignore`.

## Observacoes Importantes

- O projeto e um prototipo de validacao, nao um sistema final de producao.
- Os dados gerados localmente podem conter informacoes pessoais de alunos.
- Antes de publicar no GitHub, revise os CSVs para garantir que nao ha dados sensiveis.
- A voz depende da sintese de fala disponivel no navegador do computador.
- A documentacao tecnica do prototipo esta em `docs/Documentacao_prototipo.txt`.

## Publicar no GitHub

Depois de revisar os arquivos, voce pode iniciar o repositorio e publicar:

```powershell
git init
git add README.md .gitignore app.py requirements.txt alunos_resultado.csv alunos_erros_detalhados.csv alunos_intervencao.csv psicogenise-main
git commit -m "first commit"
git branch -M main
git remote add origin git@github.com:andsonandreribeiro09/psicogenise.git
git push -u origin main
```

Se o repositorio ja tiver um remote configurado, confira com:

```powershell
git remote -v
```

## Licenca

O frontend original inclui um arquivo `LICENSE` dentro da pasta `psicogenise-main/`. Antes de publicar, confirme tambem a origem e permissao de uso das imagens e assets visuais.

## Autor 1

Andson Andre da Silva Ribeiro.

## Autor 2

Maria Paula de Oliveira Fonseca.
