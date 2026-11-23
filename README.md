# Multimédia-2026-2027
Projeto Multimédia de programação com Inteligência Artificial

Nome do Autor: Gonçalo Lapa
Disciplina: Multimédia
Tema/nome do trabalho: Politicamente Correto
Link da Aplicação Web: http://127.0.0.1:5050

1. Visão Geral do Projeto

Descrição: O Politicamente Correto é uma aplicação web educativa que ajuda cada pessoa a conhecer melhor as suas ideias, valores e convicções políticas, de forma clara, educativa e imparcial. Reúne três ferramentas interativas:

Bússola Política: um teste em três níveis (10, 20 ou 50 perguntas) que coloca o utilizador num gráfico de dois eixos, o económico e o social. Associa o resultado a uma personalidade política e, na versão completa, a um país ou regime.
Quiz de Geopolítica: 12 perguntas de escolha múltipla com dificuldade progressiva (Básico, Intermédio e Avançado). Dá feedback imediato, uma explicação para cada resposta e, no fim, uma pontuação com classificação.
Adivinha o Líder: um jogo de pistas para descobrir líderes políticos históricos e atuais. A pontuação depende do número de pistas usadas. Tem ajudas: o país do líder, sugestões de nomes e uma opção de escolha múltipla.

2. Estrutura do Código e Funcionalidades Integradas

Não adaptei os exercícios das fichas: desenvolvi o projeto de raiz com o apoio de Inteligência Artificial (Claude). Parti de um documento meu com as tabelas de correspondência da bússola, que depois atualizei para 32 perspetivas políticas. O site usa só Python e HTML, com CSS para o aspeto.

Backend em Python (Flask): está todo no ficheiro app.py, organizado em seis partes.
Bússola: perguntas com regras de inversão de sinal, tabelas de correspondência dos três níveis e associação do resultado à zona política mais próxima.
Quiz: um banco de 24 perguntas, sorteadas por nível, com correção das respostas e contagem dos pontos.
Adivinha o Líder: uma base de dados de 28 líderes, com 4 pistas cada. Aceita palpites sem acentos e com pequenos erros de escrita. A pontuação baixa com as pistas e as ajudas usadas.
Frontend em HTML (templates Jinja2) e CSS próprio:
cada jogada é um formulário HTML enviado ao servidor, que gera a página seguinte;
o jogo em curso fica guardado no servidor e é identificado por um cookie de sessão;
usa recursos do próprio HTML: menu do telemóvel com <details>, sugestões de nomes com <datalist>, validação com required e foco automático com autofocus;
o CSS dá um design responsivo com tema claro e escuro, a barra de progresso da bússola e as animações;
o gráfico da bússola é desenhado em SVG.
Outras funcionalidades: o site tem testes automáticos às páginas, à pontuação e a jogos completos jogados através dos formulários.
