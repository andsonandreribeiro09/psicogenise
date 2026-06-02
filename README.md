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

### Uso Com Agente GPT Pela API OpenAI

Para passar a intervencao por um agente GPT, configure uma chave da API OpenAI antes de iniciar o app. Nao coloque a chave dentro do codigo.

```powershell
$env:OPENAI_API_KEY="sua-chave-da-api"
$env:OPENAI_MODEL="gpt-5"
py app.py
```

Fluxo usado pelo sistema:

```text
metricas do aluno -> RAG busca trechos em rag_base.txt -> agente GPT gera intervencao -> dashboard
```

O prompt enviado ao agente inclui nome, serie, matricula, respostas digitadas, gabaritos, acertos, erros e tipos de erro do aluno selecionado no dashboard. Esses dados sao usados como contexto da intervencao atual; o modelo nao e treinado permanentemente com os dados do aluno.

Ordem de fallback:

1. Agente GPT via OpenAI API, se `OPENAI_API_KEY` existir.
2. LM Studio local, se estiver rodando.
3. Regras internas do sistema.

Observacao: assinatura ChatGPT Plus/Pro e uso da OpenAI API sao cobrancas separadas. O backend precisa de uma chave de API para chamar o modelo.

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

## Autores

Andson Andre da Silva Ribeiro
Maria Paula de Oliveira Fonseca
