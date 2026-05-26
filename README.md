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
- Classificacao de erros: correto, omissao, adicao, substituicao e fonologico.
- Calculo de score e nivel de erro.
- Recomendacoes pedagogicas com base nos tipos de erro.
- Dashboard em Dash para visualizacao das metricas pelo professor.
- Salvamento dos resultados em arquivos CSV.

## Tecnologias

- Python
- Flask
- Dash
- Pandas
- Plotly
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
