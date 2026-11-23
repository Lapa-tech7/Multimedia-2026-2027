# Politicamente Correto

Site educativo desenvolvido por Gonçalo Lapa para ajudar as pessoas a conhecerem-se melhor,
explorando as suas próprias ideias, valores e convicções políticas de forma clara,
educativa e imparcial.

Feito só com **Python (Flask)** e **HTML** (templates Jinja2), com **CSS** próprio para o
aspeto. **Não usa JavaScript**: todas as páginas são geradas pelo Python e os jogos funcionam
com formulários HTML (ver [Como funciona sem JavaScript](#como-funciona-sem-javascript)).

## Como experimentar o site

O site corre no teu próprio computador. São precisos uns 5 minutos.

### 1. Descarregar o projeto

1. Nesta página do GitHub, carrega no botão verde **Code** → **Download ZIP**.
2. Extrai o ZIP (duplo clique no Mac; no Windows, botão direito → *Extrair tudo*).

### 2. Instalar o Python (se ainda não o tiveres)

1. Vai a [python.org/downloads](https://www.python.org/downloads/) e instala a versão mais recente.
2. **No Windows**, marca a caixa **«Add Python to PATH»** antes de carregar em *Install*.

### 3. Abrir um terminal dentro da pasta do projeto

- **Windows:** abre a pasta no Explorador, clica na barra de endereço, escreve `cmd` e carrega em Enter.
- **Mac:** no Finder, botão direito na pasta → *Serviços* → *Novo Terminal na Pasta*.

### 4. Instalar o Flask e arrancar o site

| | Windows | Mac |
|---|---|---|
| Instalar o Flask (só da primeira vez) | `pip install -r requirements.txt` | `pip3 install -r requirements.txt` |
| Arrancar o site | `python app.py` | `python3 app.py` |

Quando aparecer `Running on http://127.0.0.1:5050`, o site está ligado.
**Deixa o terminal aberto** enquanto usas o site.

### 5. Abrir no browser

Abre **[http://127.0.0.1:5050](http://127.0.0.1:5050)** no Chrome, Edge, Firefox ou Safari.

Para desligar o site, carrega em **Ctrl + C** no terminal.

### Se alguma coisa falhar

| Problema | Solução |
|---|---|
| `python` não é reconhecido (Windows) | Reinstala o Python com a caixa «Add Python to PATH» marcada, ou usa `py app.py` |
| `No module named flask` | Repete o passo 4 (no Windows também podes usar `py -m pip install flask`) |
| `Address already in use` | A porta já está ocupada: fecha o outro terminal ou usa outra porta (ver abaixo) |
| A página não abre | Confirma que o terminal do passo 4 continua aberto e sem erros |

> Só é preciso o Flask: os gráficos são desenhados em SVG e as animações em CSS.
> A porta 5050 é usada em vez da 5000 porque no macOS a 5000 está ocupada pelo AirPlay.
> Para usar outra porta: `PORT=8000 python3 app.py` (Mac) ou `set PORT=8000` e depois
> `python app.py` (Windows).

## Páginas

| Endereço | Página |
|---|---|
| `/` | Página principal: título, apresentação do projeto e os widgets das ferramentas |
| `/bussola` | Bússola Política: explicação dos eixos e escolha do nível |
| `/bussola/teste/1`, `/2`, `/3` | Questionário de cada nível (10, 20 ou 50 perguntas) |
| `/bussola/resultado` | Gráfico, personalidade, eixos e (nível 3) país ou regime mais semelhante |
| `/quiz` | Quiz de Geopolítica: ecrã inicial, perguntas com correção e resultado |
| `/lideres` | Jogo Adivinha o Líder: ecrã inicial, rondas e resultado |

Os botões dos jogos enviam formulários (`POST`) para endereços como `/quiz/responder` ou
`/lideres/pista`, descritos mais abaixo.

## Estrutura de pastas

```
Projeto python final/
├── app.py                 # Ficheiro principal: dados, lógica e rotas (bússola, quiz e líderes)
├── requirements.txt       # Dependências (só Flask)
├── README.md
├── templates/             # Páginas HTML (Jinja2)
│   ├── base.html          # Estrutura comum: cabeçalho, menu e rodapé
│   ├── _macros.html       # Componente reutilizável (mini-bússola decorativa)
│   ├── index.html         # Página principal "Politicamente Correto"
│   ├── bussola.html       # Bússola: como funciona + escolha do nível
│   ├── teste.html         # Questionário da bússola
│   ├── resultado.html     # Resultado da bússola
│   ├── quiz.html          # Quiz de Geopolítica (início, pergunta e resultado)
│   ├── lideres.html       # Jogo Adivinha o Líder (início, ronda e resultado)
│   └── erro.html          # Página 404
└── static/
    └── css/
        ├── style.css      # Design do site (tema claro/escuro, responsivo)
        ├── quiz.css       # Design do quiz (classes "qz-")
        └── lideres.css    # Design do jogo dos líderes (classes "ld-")
```

## Como funciona sem JavaScript

- **Cada jogada é um formulário.** Os botões dos jogos são `<button type="submit">`: ao
  carregar, o browser envia o formulário ao servidor, o Python atualiza o jogo e responde
  com um *redirect* para a página do jogo, que volta a ser gerada com o novo estado
  (padrão **POST → redirect → GET**: recarregar a página nunca repete uma jogada).
- **Onde fica o jogo.** Os jogos em curso ficam na memória do servidor. O browser só guarda,
  no cookie de sessão do Flask (assinado), o código do seu jogo; as respostas certas nunca
  vão para a página antes de o jogador responder. Os jogos parados há 2 horas são apagados.
- **Cliques repetidos.** Cada formulário leva um campo escondido com o número da pergunta
  (quiz) ou da jogada (líderes). Se já não corresponder ao estado do jogo (duplo clique ou
  botão «Voltar» do browser), o envio é ignorado.
- **Vários botões no mesmo formulário.** Em «Adivinha o Líder», «Pedir pista», «Ver 4 opções»
  e «Desistir» usam o atributo `formaction` para enviar o formulário do palpite para outro
  endereço (e `formnovalidate` para não exigirem o nome escrito).
- **Foco do teclado.** O atributo `autofocus` põe o cursor no sítio certo em cada passo (o
  campo do palpite, o botão «Pergunta seguinte»…), por isso dá para jogar só com o teclado.
- **Questionário da bússola.** O CSS conta as respostas (`counter-increment` em cada opção
  marcada), pinta a barra de progresso com o seletor `:has()` e assinala as perguntas em
  falta (`:user-invalid`). O atributo `required` impede o envio com perguntas por responder,
  e o Python volta a verificar as respostas.
- **Menu do telemóvel.** É um `<details>`/`<summary>`, que abre e fecha sem JavaScript.
- **Animações** (anel do resultado, pistas novas, pontuação a subir): só CSS (`@keyframes`).

## Quiz de Geopolítica

- Cada jogo tem **12 perguntas de escolha múltipla**, em dificuldade progressiva:
  4 do nível 1 (Básico, 10 pts), 4 do nível 2 (Intermédio, 20 pts) e 4 do nível 3
  (Avançado, 30 pts), num máximo de **240 pontos**.
- As perguntas de cada nível são sorteadas de um banco de 24 e a ordem das opções é
  baralhada, por isso cada jogo é diferente.
- Depois de cada resposta há **feedback imediato** (verde = certo, vermelho = errado), a
  resposta certa e uma explicação. No fim aparecem a pontuação, uma classificação, os
  acertos por nível e a revisão de todas as respostas.
- O **servidor** sorteia as perguntas, verifica as respostas e conta os pontos.

### Rotas (PARTE 5 de `app.py`)

| Pedido | O que faz |
|---|---|
| `GET /quiz` | mostra o ecrã inicial, a pergunta atual (com a correção, se já respondida) ou o resultado |
| `POST /quiz/novo` | começa um jogo novo |
| `POST /quiz/responder` com `opcao` (0–3) e `pergunta` | regista a resposta e soma os pontos |
| `POST /quiz/avancar` com `pergunta` | passa à pergunta seguinte ou ao resultado final |
| `POST /quiz/sair` | abandona o jogo e volta ao ecrã inicial |

### Acrescentar perguntas

No dicionário `_BANCO_QUIZ` de `app.py`, cada pergunta tem o formato
`(tema, pergunta, [4 opções], explicação)`. **A primeira opção é sempre a certa**: o site
baralha a ordem sozinho. Cada nível precisa de pelo menos 4 perguntas.

## Adivinha o Líder

- Cada jogo tem **5 rondas**. Em cada uma há um líder político misterioso (histórico ou
  atual, de qualquer parte do mundo) e **4 pistas**, da mais difícil à mais fácil.
- **Pontuação baseada nas pistas usadas:** acertar só com a 1.ª pista vale 10 pontos, com
  2 pistas 7, com 3 pistas 4 e com as 4 pistas 2 (máximo de 50 pontos por jogo).
- **Pedir pista** desbloqueia a pista seguinte; um **palpite errado** também. Se o
  jogador falhar depois da última pista (ou desistir), a ronda vale 0.
- **Ajudas para tornar o jogo mais fácil:**
  - o **país** do líder aparece desde o início de cada ronda;
  - ao escrever aparecem **sugestões com os nomes** dos 28 líderes (`<datalist>` do HTML);
  - **«Ver 4 opções»** transforma a ronda em escolha múltipla (o nome certo e mais três,
    de preferência do mesmo país); a partir daí a ronda vale **metade** (10 → 5, 7 → 4, 4 → 2, 2 → 1).
- Dificuldades: **Misto** (3 fáceis e 2 médios, o modo predefinido), **Fácil**, **Médio** ou **Difícil**.
- Os palpites são validados no servidor sem ligar a maiúsculas, acentos, artigos nem
  pequenos erros de escrita (ex.: «mandella», «gorbatchev», «o Napoleão»). Se o palpite
  estiver muito perto, o jogo avisa «Quase!» sem tirar pontos.
- O painel de pontuação (total, valor da ronda, pistas usadas, acertos e rondas)
  atualiza-se a cada jogada; no fim aparece a classificação e o resumo de cada ronda.

### Base de dados de líderes (PARTE 6 de `app.py`)

A lista `LIDERES` tem 28 líderes. Cada um tem `id`, `nome`, `pais`, `cargo`, `epoca`,
`dificuldade` (1, 2 ou 3), `imagem` (opcional), `aceites` (respostas aceites) e `pistas`
(exatamente 4, da mais difícil para a mais fácil). Para acrescentar um líder basta copiar
um dos blocos e mudar os valores; o site verifica os dados ao arrancar.

**Imagens (opcionais):** guarda a fotografia em `static/img/lideres/` (ex.:
`static/img/lideres/mandela.jpg`) e escreve `"imagem": "img/lideres/mandela.jpg"` no líder.
Sem imagem, o jogo mostra um círculo com as iniciais. Usa só imagens que possas usar
(por exemplo, do domínio público ou com licença livre, como muitas da Wikimedia Commons).

### Rotas

| Pedido | O que faz |
|---|---|
| `GET /lideres` | mostra o ecrã inicial, a ronda atual ou o resultado final |
| `POST /lideres/novo` com `dificuldade` (`misto`, 1, 2 ou 3) | começa um jogo |
| `POST /lideres/responder` com `resposta` (ex.: `Mandela`) | valida o palpite: certo, quase ou errado |
| `POST /lideres/pista` | desbloqueia a pista seguinte |
| `POST /lideres/opcoes` | mostra 4 nomes à escolha (a ronda passa a valer metade) |
| `POST /lideres/desistir` | revela o líder (0 pontos) |
| `POST /lideres/seguinte` | ronda seguinte ou resultado final |
| `POST /lideres/sair` | abandona o jogo e volta ao ecrã inicial |

Todas as jogadas levam também o campo escondido `passo` (ver acima).

### Adaptar as cores

As cores do jogo estão em variáveis no topo de `static/css/lideres.css` (`--ld-cor`,
`--ld-certo`, `--ld-errado`…). As superfícies e o texto usam as variáveis do site, por
isso o jogo segue automaticamente o tema claro/escuro.

## Como funciona a Bússola Política

### Níveis

| Nível | Nome | Perguntas | Escala |
|---|---|---|---|
| 1 | Base Essencial | 10 (5 económicas + 5 sociais) | −10 a +10 |
| 2 | Expansão Intermédia | 20 (10 + 10) | −20 a +20 |
| 3 | Versão Completa | 50 (25 + 25) | −50 a +50 |

Cada nível inclui as perguntas do anterior e acrescenta novas.

### Pontuação e inversão de sinal

Cada resposta vale `−2` (Discordo totalmente), `−1` (Discordo), `+1` (Concordo) ou `+2`
(Concordo totalmente). Cada pergunta tem uma **direção** em `app.py`:

- `DIREITA` / `AUTORITARIO` (`+1`): concordar soma pontos.
- `ESQUERDA` / `LIBERTARIO` (`−1`): concordar subtrai pontos, ou seja, o sinal é **invertido**.

```
contributo = resposta × direção
X = soma dos contributos das perguntas económicas
Y = soma dos contributos das perguntas sociais
```

Como cada eixo tem N perguntas de no máximo 2 pontos, o resultado fica sempre entre
−2N e +2N (±10, ±20 ou ±50). Na página de resultados, “Ver o detalhe das respostas”
mostra o cálculo pergunta a pergunta.

### Correspondências

As zonas das tabelas são retângulos (intervalos X e Y). A função
`ordenar_correspondencias()` ordena as zonas por:

1. distância do ponto ao retângulo (0 = dentro do intervalo);
2. distância ao centro da zona (desempata zonas sobrepostas).

Assim há sempre uma correspondência, mesmo nos espaços que as tabelas não cobrem.

No **nível 3**, cada uma das 32 perspetivas está ligada (campo `"pais"`) ao país ou regime
com a ideologia mais próxima, porque a tabela de países não tem intervalos X/Y.
A perspetiva 32 (*Socialismo de Mercado Democrático*, Oskar Lange) está ligada à corrente
“Socialismo de Mercado” (China / Vietname).

Os números mostrados no site (perguntas, perspetivas, países) são calculados a partir das
tabelas, por isso acompanham automaticamente qualquer perspetiva que seja acrescentada.

## Personalizar

- **Bússola:** perguntas, tabelas e países na PARTE 1 de `app.py`.
- **Quiz:** perguntas em `_BANCO_QUIZ`, pontos por nível em `QUIZ_NIVEIS` e
  classificações em `QUIZ_CLASSIFICACOES` (PARTE 5 de `app.py`).
- **Adivinha o Líder:** líderes em `LIDERES`, pontos em `LIDERES_PONTOS_POR_PISTA` e
  classificações em `LIDERES_CLASSIFICACOES` (PARTE 6 de `app.py`).
- **Textos da página principal:** `templates/index.html`.
- **Cores e aspeto:** variáveis no topo de `static/css/style.css` (site),
  `static/css/quiz.css` (quiz) e `static/css/lideres.css` (líderes).

Se algum dado ficar incoerente (um intervalo invertido, um país inexistente, uma pergunta
do quiz sem 4 opções…), o site mostra o erro logo ao arrancar.
