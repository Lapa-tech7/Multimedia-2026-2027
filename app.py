"""
Politicamente Correto — site educativo em Flask
===============================================

Projeto desenvolvido por Gonçalo Lapa para ajudar as pessoas a conhecerem-se
melhor, explorando as suas ideias, valores e convicções políticas de forma
clara, educativa e imparcial.

Ferramentas:
  1. Bússola Política (3 níveis: 10, 20 ou 50 perguntas)
  2. Quiz de Geopolítica (12 perguntas em 3 níveis de dificuldade progressivos)
  3. Adivinha o Líder (jogo de pistas sobre líderes políticos históricos e atuais)

Este ficheiro contém TUDO o que é Python:
  PARTE 1 — Dados da bússola: níveis, perguntas, tabelas de correspondência e países
  PARTE 2 — Lógica da bússola: pontuação, correspondências e gráfico
  PARTE 3 — Filtros e variáveis para os templates HTML
  PARTE 4 — Rotas (páginas) do site
  PARTE 5 — Quiz de Geopolítica: perguntas, jogos, pontuação e páginas
  PARTE 6 — Adivinha o Líder: base de dados de líderes, palpites, pontuação e páginas

O site usa só Python e HTML (mais CSS para o aspeto), sem JavaScript: todas as
páginas são geradas aqui, e os jogos funcionam com formulários HTML que enviam
cada jogada ao servidor.

Executar localmente:
    pip install -r requirements.txt
    python app.py
    → abrir http://127.0.0.1:5050
"""

import difflib
import math
import os
import random
import re
import secrets
import threading
import time
import unicodedata

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

NOME_SITE = "Politicamente Correto"

app = Flask(__name__)
# Chave que assina o cookie de sessão onde ficam guardadas as respostas.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


# ===========================================================================
# PARTE 1 — DADOS
# ===========================================================================
# Convenção dos eixos (a mesma das tabelas de correspondência):
#   X (Económico):  negativo = Esquerda    |  positivo = Direita
#   Y (Social):     negativo = Libertário  |  positivo = Autoritário

# ---------------------------------------------------------------------------
# 1.1 Níveis do teste
# ---------------------------------------------------------------------------
# Cada pergunta vale no máximo 2 pontos, por isso o limite de cada eixo é
# 2 × (n.º de perguntas por eixo):  5 → ±10  |  10 → ±20  |  25 → ±50
NIVEIS = {
    1: {
        "nome": "Base Essencial",
        "perguntas_por_eixo": 5,
        "limite": 10,
        "tempo": "≈ 2 min",
        "descricao": "Um retrato rápido da tua posição política a partir das 10 afirmações essenciais.",
        "destaques": [
            "5 perguntas económicas + 5 sociais",
            "Escala de −10 a +10",
            "12 personalidades de referência",
        ],
    },
    2: {
        "nome": "Expansão Intermédia",
        "perguntas_por_eixo": 10,
        "limite": 20,
        "tempo": "≈ 4 min",
        "descricao": "Acrescenta 10 afirmações ao nível essencial para um resultado mais preciso.",
        "destaques": [
            "10 perguntas económicas + 10 sociais",
            "Escala de −20 a +20",
            "12 personalidades com perfil de referência",
        ],
    },
    3: {
        "nome": "Versão Completa",
        "perguntas_por_eixo": 25,
        "limite": 50,
        "tempo": "≈ 10 min",
        # {perspetivas} é substituído pelo n.º real de perspetivas da tabela (ver ESTATISTICAS).
        "descricao": "O teste integral, com {perspetivas} perspetivas políticas e o país ou regime mais semelhante.",
        "destaques": [
            "25 perguntas económicas + 25 sociais",
            "Escala de −50 a +50",
            "{perspetivas} perspetivas políticas",
            "País atual ou regime histórico mais semelhante",
        ],
    },
}

# ---------------------------------------------------------------------------
# 1.2 Escala de resposta (Likert de 4 pontos, sem opção neutra)
# ---------------------------------------------------------------------------
OPCOES = [
    {"valor": -2, "texto": "Discordo totalmente", "classe": "dt"},
    {"valor": -1, "texto": "Discordo", "classe": "d"},
    {"valor": 1, "texto": "Concordo", "classe": "c"},
    {"valor": 2, "texto": "Concordo totalmente", "classe": "ct"},
]

# ---------------------------------------------------------------------------
# 1.3 Perguntas e regras de inversão de sinal
# ---------------------------------------------------------------------------
# A "direção" indica para onde CONCORDAR com a afirmação empurra a pontuação.
# O contributo de cada resposta é:   contributo = resposta × direção
#
#   Eixo X:  DIREITA  (+1) → concordar soma pontos   (vai para a Direita)
#            ESQUERDA (−1) → concordar subtrai pontos (sinal invertido)
#   Eixo Y:  AUTORITARIO (+1) → concordar soma pontos   (vai para o Autoritário)
#            LIBERTARIO  (−1) → concordar subtrai pontos (sinal invertido)
#
# Exemplo: "O Estado deve controlar os setores estratégicos…" é ESQUERDA.
#          Quem responde "Concordo totalmente" (+2) recebe +2 × −1 = −2 no eixo X.
DIREITA = +1
ESQUERDA = -1
AUTORITARIO = +1
LIBERTARIO = -1


def _criar_perguntas(prefixo, eixo, lista):
    """Transforma a lista (texto, direção) em dicionários com id e eixo."""
    return [
        {"id": f"{prefixo}{numero:02d}", "eixo": eixo, "texto": texto, "direcao": direcao}
        for numero, (texto, direcao) in enumerate(lista, start=1)
    ]


# A ordem importa: o nível 1 usa as 5 primeiras de cada eixo, o nível 2 as 10
# primeiras e o nível 3 todas as 25.
PERGUNTAS_ECONOMICAS = _criar_perguntas("E", "x", [
    # --- Nível 1 (base essencial) ---
    ("O Estado deve controlar os setores estratégicos da economia, como a energia, "
     "os transportes e as telecomunicações.", ESQUERDA),
    ("O mercado livre, com pouca intervenção do Estado, é a melhor forma de criar "
     "riqueza para todos.", DIREITA),
    ("Quem tem rendimentos mais elevados deve pagar mais impostos para financiar os "
     "serviços públicos.", ESQUERDA),
    ("A privatização das empresas públicas torna-as, em geral, mais eficientes.", DIREITA),
    ("O Estado deve garantir saúde e educação gratuitas para todos, mesmo que isso "
     "exija impostos elevados.", ESQUERDA),
    # --- Nível 2 (expansão intermédia) ---
    ("Subsídios de desemprego demasiado generosos desincentivam a procura de trabalho.", DIREITA),
    ("O salário mínimo nacional deve aumentar de forma significativa todos os anos.", ESQUERDA),
    ("As leis laborais devem ser mais flexíveis, facilitando a contratação e o despedimento.", DIREITA),
    ("Os sindicatos são essenciais para defender os trabalhadores e devem ter mais "
     "poder negocial.", ESQUERDA),
    ("Menos regulamentação beneficia mais os consumidores do que uma economia "
     "fortemente regulada.", DIREITA),
    # --- Nível 3 (versão completa) ---
    ("O Estado deve fixar limites aos preços de bens essenciais, como as rendas da "
     "habitação e os alimentos.", ESQUERDA),
    ("As heranças devem pagar poucos ou nenhuns impostos, porque esse património já "
     "foi tributado.", DIREITA),
    ("A banca e as grandes empresas devem ser fortemente reguladas para evitar abusos "
     "e crises.", ESQUERDA),
    ("O comércio livre entre países beneficia todas as economias envolvidas.", DIREITA),
    ("É legítimo nacionalizar empresas privadas quando isso serve o interesse público.", ESQUERDA),
    ("O Estado deve reduzir a despesa pública, mesmo que isso implique cortes nos "
     "apoios sociais.", DIREITA),
    ("As grandes fortunas devem pagar um imposto especial sobre o património.", ESQUERDA),
    ("As pensões de reforma devem depender, pelo menos em parte, de contas de "
     "poupança privadas e individuais.", DIREITA),
    ("O Estado deve travar a especulação imobiliária, mesmo que isso limite o "
     "direito de propriedade.", ESQUERDA),
    ("A desigualdade económica é uma consequência natural e aceitável de uma "
     "economia livre.", DIREITA),
    ("Os transportes públicos devem ser gratuitos e pagos através dos impostos.", ESQUERDA),
    ("A principal responsabilidade de uma empresa é gerar lucro para os seus acionistas.", DIREITA),
    ("O Estado deve garantir um emprego a todos os cidadãos que queiram trabalhar.", ESQUERDA),
    ("Um imposto sobre o rendimento com taxa única, igual para todos, seria mais justo "
     "do que os escalões progressivos.", DIREITA),
    ("Recursos naturais como a água devem ser sempre propriedade pública.", ESQUERDA),
])

PERGUNTAS_SOCIAIS = _criar_perguntas("S", "y", [
    # --- Nível 1 (base essencial) ---
    ("A obediência e o respeito pela autoridade são valores essenciais que as "
     "crianças devem aprender.", AUTORITARIO),
    ("O consumo de drogas leves, como a canábis, deve ser legal para adultos.", LIBERTARIO),
    ("O Estado deve poder vigiar comunicações privadas para combater o terrorismo "
     "e o crime.", AUTORITARIO),
    ("A liberdade de expressão deve ser protegida, mesmo quando as opiniões são "
     "ofensivas ou impopulares.", LIBERTARIO),
    ("O país precisa de um líder forte que não fique bloqueado pelo parlamento nem "
     "pelos tribunais.", AUTORITARIO),
    # --- Nível 2 (expansão intermédia) ---
    ("O casamento e a adoção por casais do mesmo sexo devem ser plenamente "
     "reconhecidos por lei.", LIBERTARIO),
    ("As penas de prisão devem ser mais duras para combater a criminalidade.", AUTORITARIO),
    ("Cada pessoa deve ter o direito de decidir sobre o fim da própria vida (eutanásia).", LIBERTARIO),
    ("A imigração deve ser fortemente limitada para proteger a identidade e a "
     "cultura nacionais.", AUTORITARIO),
    ("A religião e a moral tradicional não devem influenciar as leis do Estado.", LIBERTARIO),
    # --- Nível 3 (versão completa) ---
    ("O serviço militar obrigatório deve ser reintroduzido.", AUTORITARIO),
    ("A interrupção voluntária da gravidez deve ser um direito garantido por lei.", LIBERTARIO),
    ("Em situações de crise, o governo deve poder suspender temporariamente direitos "
     "e liberdades.", AUTORITARIO),
    ("Os cidadãos devem poder manifestar-se livremente, mesmo contra o governo.", LIBERTARIO),
    ("Os meios de comunicação social devem ser controlados para impedir notícias que "
     "prejudiquem o país.", AUTORITARIO),
    ("O trabalho sexual entre adultos deve ser legalizado e regulamentado.", LIBERTARIO),
    ("A pena de morte é justificável para os crimes mais graves.", AUTORITARIO),
    ("As escolas devem estimular o pensamento crítico, mesmo que os alunos passem a "
     "questionar a autoridade e a tradição.", LIBERTARIO),
    ("A família tradicional é o pilar da sociedade e deve ser protegida e promovida "
     "pelo Estado.", AUTORITARIO),
    ("O Estado não deve interferir na vida privada dos adultos, desde que não "
     "prejudiquem terceiros.", LIBERTARIO),
    ("As forças de segurança devem ter mais poderes, mesmo que isso reduza algumas "
     "liberdades individuais.", AUTORITARIO),
    ("A desobediência civil é legítima quando uma lei é injusta.", LIBERTARIO),
    ("Desrespeitar símbolos nacionais, como a bandeira ou o hino, deve ser punido "
     "por lei.", AUTORITARIO),
    ("A videovigilância com reconhecimento facial em espaços públicos é uma ameaça "
     "inaceitável à privacidade.", LIBERTARIO),
    ("A ordem e a estabilidade são mais importantes do que a liberdade individual.", AUTORITARIO),
])

# ---------------------------------------------------------------------------
# 1.4 Tabelas de correspondência
# ---------------------------------------------------------------------------
# "x" e "y" são intervalos (mínimo, máximo), tal como nas tabelas do documento.
# As zonas podem sobrepor-se e não cobrem todo o plano: a função
# ordenar_correspondencias() (PARTE 2) trata desses casos.

# --- Nível 1 · Base Essencial (−10 a +10) ---------------------------------
PERSPETIVAS_NIVEL_1 = [
    {"posicao": "Extrema-Esquerda Autoritária", "personalidade": "Mao Tsé-Tung",
     "x": (-10, -6), "y": (4, 10),
     "descricao": "Coletivização económica absoluta aliada a controlo social rigoroso e centralização."},
    {"posicao": "Esquerda Autoritária", "personalidade": "Evo Morales",
     "x": (-6, -2), "y": (3, 8),
     "descricao": "Socialismo comunitário andino, nacionalização de setores estratégicos e tradições."},
    {"posicao": "Centro-Esquerda Autoritária", "personalidade": "Olof Palme / Afonso Costa",
     "x": (-2, 0), "y": (2, 6),
     "descricao": "Social-democracia e 1.ª República; proteção social com papel regulador do Estado."},
    {"posicao": "Extrema-Esquerda Libertária", "personalidade": "Piotr Kropotkin",
     "x": (-10, -5), "y": (-10, -4),
     "descricao": "Anarcocomunismo; abolição da propriedade privada e eliminação total da autoridade estatal."},
    {"posicao": "Esquerda Libertária", "personalidade": "Jacinda Ardern",
     "x": (-5, -1), "y": (-10, -4),
     "descricao": "Partido Trabalhista NZ; investimento público universal e reformas sociais progressistas."},
    {"posicao": "Centro Libertário", "personalidade": "Barack Obama",
     "x": (-1, 1), "y": (-6, -2),
     "descricao": "Liberalismo moderno; comércio livre, proteção social equilibrada e direitos civis."},
    {"posicao": "Centro Político (Neutro)", "personalidade": "Durão Barroso",
     "x": (-1, 1), "y": (-2, 2),
     "descricao": "Compromisso institucional entre economia social de mercado e estabilidade jurídica."},
    {"posicao": "Centro-Direita Autoritária", "personalidade": "Helmut Kohl",
     "x": (1, 4), "y": (2, 6),
     "descricao": "Democracia Cristã alemã; economia social de mercado ancorada em valores familiares."},
    {"posicao": "Direita Autoritária", "personalidade": "Giorgia Meloni",
     "x": (3, 7), "y": (5, 10),
     "descricao": "Fratelli d'Italia; redução de impostos, identidade nacional, família tradicional e segurança."},
    {"posicao": "Extrema-Direita Autoritária", "personalidade": "Adolf Hitler / Benito Mussolini",
     "x": (-2, 4), "y": (8, 10),
     "descricao": "Fascismo e Nacional-Socialismo; autoridade absoluta, vigilância e economia dirigida."},
    {"posicao": "Direita Liberal / Moderada", "personalidade": "Sá Carneiro / Ronald Reagan",
     "x": (4, 8), "y": (-3, 2),
     "descricao": "Iniciativa privada, desregulamentação e redução fiscal com reformismo cívico."},
    {"posicao": "Extrema-Direita Libertária", "personalidade": "Ayn Rand",
     "x": (7, 10), "y": (-10, -5),
     "descricao": "Objetivismo; capitalismo laissez-faire puro e individualismo radical sem intervenção moral."},
]

# --- Nível 2 · Expansão Intermédia (−20 a +20) -----------------------------
PERSPETIVAS_NIVEL_2 = [
    {"posicao": "Extrema-Esquerda Autoritária", "personalidade": "Che Guevara",
     "x": (-20, -12), "y": (8, 20),
     "descricao": "Revolucionário anti-imperialista, defesa do coletivismo armado e forte disciplina."},
    {"posicao": "Esquerda Autoritária", "personalidade": "Luiz Inácio Lula da Silva (inicial)",
     "x": (-12, -4), "y": (6, 16),
     "descricao": "Forte intervenção do Estado na economia, defesa de sindicatos e valores sociais moderados."},
    {"posicao": "Centro-Esquerda Autoritária", "personalidade": "Mário Soares (fundação PS)",
     "x": (-4, 0), "y": (4, 12),
     "descricao": "Social-democracia reformista, defesa intransigente da democracia e sentido de Estado."},
    {"posicao": "Extrema-Esquerda Libertária", "personalidade": "Emma Goldman",
     "x": (-20, -10), "y": (-20, -8),
     "descricao": "Anarquista clássica, opositora ferrenha do capitalismo e de qualquer autoridade estatal."},
    {"posicao": "Esquerda Libertária", "personalidade": "Alexandria Ocasio-Cortez (AOC)",
     "x": (-10, -2), "y": (-20, -8),
     "descricao": "Esquerda progressista moderna, foco em justiça climática e direitos sociais amplos."},
    {"posicao": "Centro Libertário", "personalidade": "Rui Rocha (Iniciativa Liberal)",
     "x": (-2, 2), "y": (-12, -4),
     "descricao": "Defesa de mercados abertos com forte pendor de liberdades individuais e civis nos costumes."},
    {"posicao": "Centro Político (Neutro)", "personalidade": "António Guterres (gestão ONU)",
     "x": (-2, 2), "y": (-4, 4),
     "descricao": "Pragmatismo político, foco em consensos globais, equilíbrio técnico e moderação."},
    {"posicao": "Centro-Direita Autoritária", "personalidade": "Aníbal Cavaco Silva",
     "x": (2, 8), "y": (4, 12),
     "descricao": "Rigor orçamental e iniciativa privada regulada, com conservadorismo institucional."},
    {"posicao": "Direita Autoritária", "personalidade": "André Ventura",
     "x": (6, 14), "y": (10, 20),
     "descricao": "Economia de mercado com forte ênfase na segurança, controlo de fronteiras e patriotismo."},
    {"posicao": "Extrema-Direita Autoritária", "personalidade": "António de Oliveira Salazar / Adolf Hitler",
     "x": (-4, 8), "y": (16, 20),
     "descricao": "Nacionalismo económico corporativo/totalitário, controlo estatal cerrado e autoridade absoluta."},
    {"posicao": "Direita Liberal / Moderada", "personalidade": "Luís Montenegro",
     "x": (8, 16), "y": (-6, 4),
     "descricao": "Baixa de impostos e apoio ao tecido empresarial, aceitando o quadro social progressista."},
    {"posicao": "Extrema-Direita Libertária", "personalidade": "Friedrich Hayek",
     "x": (14, 20), "y": (-20, -10),
     "descricao": "Fundador do liberalismo clássico radical; mercado livre e oposição estrita a controlo estatal."},
]

# --- Nível 3 · Versão Completa (−50 a +50) — 32 perspetivas ----------------
# "pais" liga cada perspetiva à entrada de PAISES com a ideologia mais próxima
# (a tabela de países do documento não tem intervalos X/Y, por isso a ligação
# é feita através da ideologia de cada perspetiva).
PERSPETIVAS_NIVEL_3 = [
    {"numero": 1, "posicao": "Extrema-Esquerda Totalitária", "nome": "Comunismo Estalinista",
     "x": (-50, -42), "y": (40, 50), "personalidade": "Josef Stalin / Enver Hoxha", "pais": "urss",
     "descricao": "Partido único, planificação central de toda a economia e repressão de qualquer oposição em nome da revolução."},
    {"numero": 2, "posicao": "Extrema-Esquerda Revolucionária", "nome": "Maoísmo / Agrarianismo Radical",
     "x": (-50, -40), "y": (25, 40), "personalidade": "Mao Tsé-Tung / Pol Pot", "pais": "urss",
     "descricao": "Coletivização forçada do campo, mobilização revolucionária das massas e rejeição radical da sociedade burguesa."},
    {"numero": 3, "posicao": "Esquerda Revolucionária Anticolonial", "nome": "Socialismo Vanguardista",
     "x": (-42, -32), "y": (20, 35), "personalidade": "Fidel Castro / Thomas Sankara", "pais": "cuba",
     "descricao": "Partido de vanguarda, nacionalizações e anti-imperialismo, com prioridade à saúde, à educação e à soberania."},
    {"numero": 4, "posicao": "Esquerda Estatista Ortodoxa", "nome": "Comunismo Europeu Tradicional",
     "x": (-35, -22), "y": (15, 30), "personalidade": "Álvaro Cunhal / Georges Marchais", "pais": "cuba",
     "descricao": "Marxismo-leninismo ortodoxo: nacionalização dos setores-chave, centralismo democrático e forte ligação sindical."},
    {"numero": 5, "posicao": "Esquerda Nacional-Populista", "nome": "Populismo Bolivariano",
     "x": (-30, -15), "y": (25, 45), "personalidade": "Hugo Chávez / Nicolás Maduro", "pais": "cuba",
     "descricao": "Liderança carismática, nacionalização de recursos naturais, programas sociais estatais e concentração de poder."},
    {"numero": 6, "posicao": "Esquerda Soberanista", "nome": "Esquerda Radical Anti-Globalização",
     "x": (-25, -12), "y": (10, 25), "personalidade": "Jean-Luc Mélenchon / Pablo Iglesias (inicial)", "pais": "nordicos",
     "descricao": "Rejeição da austeridade e dos tratados de livre comércio, defesa dos serviços públicos e da soberania popular."},
    {"numero": 7, "posicao": "Esquerda Comunitária Indigenista", "nome": "Socialismo Comunitário",
     "x": (-22, -10), "y": (15, 30), "personalidade": "Evo Morales / Rafael Correa", "pais": "cuba",
     "descricao": "Socialismo de raiz comunitária e indígena: controlo estatal dos recursos estratégicos e valorização das tradições."},
    {"numero": 8, "posicao": "Centro-Esquerda Trabalhista", "nome": "Trabalhismo Clássico / Desenvolvimentismo",
     "x": (-18, -6), "y": (10, 25), "personalidade": "Clement Attlee / Getúlio Vargas", "pais": "nordicos",
     "descricao": "Estado social, direitos laborais e industrialização dirigida pelo Estado numa economia mista."},
    {"numero": 9, "posicao": "Esquerda Conservadora", "nome": "Comunitarismo Protecionista",
     "x": (-12, -2), "y": (18, 35), "personalidade": "Sahra Wagenknecht / Pedro Castillo", "pais": "china",
     "descricao": "Economia de esquerda com valores sociais conservadores: protecionismo, controlo migratório e coesão nacional."},
    {"numero": 10, "posicao": "Centro-Esquerda Securitária", "nome": "Social-Democracia de Ordem",
     "x": (-10, 0), "y": (5, 18), "personalidade": "Pedro Sánchez / Olaf Scholz", "pais": "nordicos",
     "descricao": "Social-democracia pragmática que junta Estado social e economia de mercado com ênfase na segurança."},
    {"numero": 11, "posicao": "Extrema-Esquerda Anarquista", "nome": "Anarcocomunismo / Anarcossindicalismo",
     "x": (-50, -38), "y": (-50, -38), "personalidade": "Piotr Kropotkin / Buenaventura Durruti", "pais": "catalunha",
     "descricao": "Abolição do Estado e da propriedade privada; sociedade organizada em comunas e sindicatos autogeridos."},
    {"numero": 12, "posicao": "Esquerda Libertária Radical", "nome": "Socialismo Libertário / Ecologia Social",
     "x": (-40, -28), "y": (-38, -22), "personalidade": "Noam Chomsky / Murray Bookchin", "pais": "catalunha",
     "descricao": "Socialismo sem Estado centralizado: democracia direta, municipalismo, autogestão e crítica às hierarquias."},
    {"numero": 13, "posicao": "Esquerda Democrática", "nome": "Socialismo Democrático",
     "x": (-28, -16), "y": (-30, -15), "personalidade": "Bernie Sanders / Catarina Martins", "pais": "nordicos",
     "descricao": "Transformação social por via eleitoral: serviços públicos universais, impostos progressivos e direitos laborais."},
    # Perspetiva 32 (acrescentada na versão atualizada do documento, a seguir à 13 na tabela).
    {"numero": 32, "posicao": "Esquerda de Mercado Democrática", "nome": "Socialismo de Mercado Democrático",
     "x": (-28, -16), "y": (-12, 5), "personalidade": "Oskar Lange", "pais": "china",
     "descricao": "Empresas de propriedade social ou cooperativa que concorrem num mercado com preços livres, dentro de um regime democrático."},
    {"numero": 14, "posicao": "Nova Esquerda Progressista", "nome": "Progressismo Urbano / Interseccional",
     "x": (-18, -8), "y": (-42, -25), "personalidade": "Alexandria Ocasio-Cortez / Mariana Mortágua", "pais": "canada",
     "descricao": "Justiça social, climática e racial, defesa das minorias e alargamento dos direitos individuais."},
    {"numero": 15, "posicao": "Esquerda Verde", "nome": "Ecossocialismo / Ecologismo Político",
     "x": (-20, -8), "y": (-25, -10), "personalidade": "Annalena Baerbock / Rui Tavares", "pais": "nordicos",
     "descricao": "Transição ecológica como prioridade, regulação ambiental exigente e ligação entre justiça social e sustentabilidade."},
    {"numero": 16, "posicao": "Centro-Esquerda Cosmopolita", "nome": "Social-Liberalismo Progressista",
     "x": (-8, 2), "y": (-32, -15), "personalidade": "Justin Trudeau / Jacinda Ardern", "pais": "canada",
     "descricao": "Economia de mercado regulada, Estado social moderado e forte aposta na diversidade e nos direitos individuais."},
    {"numero": 17, "posicao": "Centro-Direita Libertária Cultural", "nome": "Liberalismo Cultural / Individualismo",
     "x": (0, 12), "y": (-38, -18), "personalidade": "Nick Clegg / Rui Rocha", "pais": "canada",
     "descricao": "Liberdades individuais e civis em primeiro lugar, Estado ausente dos costumes e economia de mercado aberta."},
    {"numero": 18, "posicao": "Centro Reformista", "nome": "Terceira Via / Social-Democracia Moderna",
     "x": (-8, 4), "y": (-15, 5), "personalidade": "Tony Blair / António Costa", "pais": "nordicos",
     "descricao": "Síntese entre mercado e Estado social: contas públicas equilibradas, modernização e políticas sociais focadas."},
    {"numero": 19, "posicao": "Centro Neutro", "nome": "Tecnocracia Institucional",
     "x": (-5, 5), "y": (-10, 10), "personalidade": "Mario Draghi / António Guterres", "pais": "canada",
     "descricao": "Pragmatismo e consenso: decisões técnicas, respeito pelas instituições multilaterais e moderação ideológica."},
    {"numero": 20, "posicao": "Centro-Direita Social", "nome": "Democracia Cristã Clássica",
     "x": (5, 16), "y": (10, 25), "personalidade": "Konrad Adenauer / Angela Merkel", "pais": "suica",
     "descricao": "Economia social de mercado, valores cristãos e familiares, construção europeia e coesão social."},
    {"numero": 21, "posicao": "Centro-Direita Institucional", "nome": "Conservadorismo Moderado",
     "x": (6, 20), "y": (15, 30), "personalidade": "Marcelo Rebelo de Sousa / Jacques Chirac", "pais": "suica",
     "descricao": "Defesa da ordem institucional, das tradições e da estabilidade, com reformas graduais e economia de mercado."},
    {"numero": 22, "posicao": "Direita Nacional-Conservadora", "nome": "Conservadorismo Iliberal",
     "x": (8, 22), "y": (30, 45), "personalidade": "Viktor Orbán / Jarosław Kaczyński", "pais": "hungria",
     "descricao": "Soberania nacional, valores tradicionais e reforço do executivo face aos contrapoderes e às instituições europeias."},
    {"numero": 23, "posicao": "Direita Soberanista", "nome": "Nacional-Populismo Europeu",
     "x": (10, 25), "y": (25, 40), "personalidade": "Marine Le Pen / Giorgia Meloni", "pais": "hungria",
     "descricao": "Controlo das fronteiras e da imigração, identidade nacional e ceticismo face à União Europeia."},
    {"numero": 24, "posicao": "Direita Populista Securitária", "nome": "Conservadorismo de Lei e Ordem",
     "x": (18, 35), "y": (25, 45), "personalidade": "Jair Bolsonaro / André Ventura", "pais": "hungria",
     "descricao": "Segurança e combate ao crime como prioridade, discurso antissistema, economia de mercado e valores tradicionais."},
    {"numero": 25, "posicao": "Extrema-Direita Corporativa", "nome": "Fascismo Clássico / Corporativismo",
     "x": (-10, 12), "y": (42, 50), "personalidade": "Benito Mussolini / António de Oliveira Salazar", "pais": "italia",
     "descricao": "Nacionalismo integral, partido único, censura e economia corporativa tutelada pelo Estado."},
    {"numero": 26, "posicao": "Extrema-Direita Totalitária Racial", "nome": "Nacional-Socialismo (Nazismo)",
     "x": (-5, 15), "y": (48, 50), "personalidade": "Adolf Hitler / Heinrich Himmler", "pais": "alemanha",
     "descricao": "Totalitarismo, ideologia racial, militarismo expansionista e subordinação total da sociedade ao Estado."},
    {"numero": 27, "posicao": "Extrema-Direita Militarista", "nome": "Nacional-Capitalismo Autoritário",
     "x": (22, 42), "y": (38, 50), "personalidade": "Augusto Pinochet / Jorge Rafael Videla", "pais": "chile",
     "descricao": "Ditadura militar combinada com liberalização económica radical, privatizações e repressão política."},
    {"numero": 28, "posicao": "Centro-Direita Liberal", "nome": "Reformismo Fiscal",
     "x": (15, 28), "y": (-10, 10), "personalidade": "Luís Montenegro / Pedro Passos Coelho", "pais": "suica",
     "descricao": "Redução de impostos, contas públicas equilibradas e apoio às empresas, aceitando o quadro social existente."},
    {"numero": 29, "posicao": "Direita Neoliberal Conservadora", "nome": "Conservadorismo Thatcheriano",
     "x": (28, 42), "y": (5, 25), "personalidade": "Margaret Thatcher / Ronald Reagan", "pais": "suica",
     "descricao": "Privatizações, desregulamentação e redução do peso do Estado, aliadas a valores conservadores e autoridade."},
    {"numero": 30, "posicao": "Direita Libertária Clássica", "nome": "Liberalismo Clássico / Minarquismo",
     "x": (32, 43), "y": (-35, -15), "personalidade": "Milton Friedman / Friedrich Hayek", "pais": "argentina",
     "descricao": "Estado mínimo limitado à justiça, segurança e defesa; mercado livre e amplas liberdades individuais."},
    {"numero": 31, "posicao": "Extrema-Direita Libertária", "nome": "Anarcocapitalismo / Objetivismo",
     "x": (43, 50), "y": (-50, -32), "personalidade": "Javier Milei / Murray Rothbard", "pais": "argentina",
     "descricao": "Redução extrema ou abolição do Estado: propriedade privada absoluta, mercado totalmente livre e individualismo radical."},
]

PERSPETIVAS = {1: PERSPETIVAS_NIVEL_1, 2: PERSPETIVAS_NIVEL_2, 3: PERSPETIVAS_NIVEL_3}

# ---------------------------------------------------------------------------
# 1.5 Países representativos (atuais e históricos) — usados no nível 3
# ---------------------------------------------------------------------------
PAISES = {
    "urss": {
        "ideologia": "Comunismo Totalitário / Estalinista",
        "pais": "União Soviética (URSS) / Coreia do Norte",
        "periodo": "1922–1991 / Atualidade",
        "caracteristicas": "Planificação económica centralizada a 100%, partido único e controlo estatal total da sociedade.",
    },
    "cuba": {
        "ideologia": "Socialismo Revolucionário",
        "pais": "Cuba",
        "periodo": "1959–Atualidade",
        "caracteristicas": "Propriedade estatal dos meios de produção, saúde e educação gratuitas, sistema de partido único.",
    },
    "china": {
        "ideologia": "Socialismo de Mercado",
        "pais": "China / Vietname",
        "periodo": "Pós-1978 / Atualidade",
        "caracteristicas": "Economia mista altamente competitiva sob forte direção estatal e controlo político autoritário.",
    },
    "catalunha": {
        "ideologia": "Anarcossindicalismo / Comunismo Libertário",
        "pais": "Catalunha Revolucionária (Espanha)",
        "periodo": "1936–1939",
        "caracteristicas": "Coletivização operária autogerida sem hierarquia estatal nem propriedade privada.",
    },
    "nordicos": {
        "ideologia": "Social-Democracia Nórdica",
        "pais": "Suécia / Dinamarca / Noruega",
        "periodo": "Pós-1945–Atualidade",
        "caracteristicas": "Impostos elevados, Estado social universal e forte proteção laboral aliados a economia aberta e liberdades civis.",
    },
    "canada": {
        "ideologia": "Social-Liberalismo Progressista",
        "pais": "Canadá / Nova Zelândia",
        "periodo": "Atualidade (décadas recentes)",
        "caracteristicas": "Economia de mercado regulada com políticas muito abertas na imigração, diversidade e direitos individuais.",
    },
    "suica": {
        "ideologia": "Liberalismo Económico / Conservadorismo Fiscal",
        "pais": "Suíça / Singapura (vertente económica)",
        "periodo": "Atualidade",
        "caracteristicas": "Impostos baixos, forte proteção da propriedade privada, comércio livre e grande estabilidade financeira.",
    },
    "argentina": {
        "ideologia": "Libertarismo / Anarcocapitalismo (Transição)",
        "pais": "Argentina (Governo Milei) / Hong Kong (pré-2020)",
        "periodo": "2023–Atualidade / Séc. XX",
        "caracteristicas": "Desregulamentação extrema, cortes profundos na despesa pública e abertura total ao livre mercado.",
    },
    "hungria": {
        "ideologia": "Conservadorismo Nacionalista / Iliberal",
        "pais": "Hungria (Governo Orbán) / Polónia (PiS)",
        "periodo": "2010–Atualidade / 2015–2023",
        "caracteristicas": "Soberania nacional acima de instituições supranacionais, valores familiares tradicionais e controlo de fronteiras.",
    },
    "italia": {
        "ideologia": "Fascismo Clássico / Corporativismo",
        "pais": "Itália Fascista / Portugal (Estado Novo)",
        "periodo": "1922–1943 / 1933–1974",
        "caracteristicas": "Nacionalismo integral, partido único, censura, valores tradicionais e economia corporativa tutelada pelo Estado.",
    },
    "alemanha": {
        "ideologia": "Nacional-Socialismo (Nazismo)",
        "pais": "Alemanha Nazi (Terceiro Reich)",
        "periodo": "1933–1945",
        "caracteristicas": "Totalitarismo absoluto, militarismo expansionista, supremacia racial e economia subordinada ao esforço de guerra.",
    },
    "chile": {
        "ideologia": "Nacional-Capitalismo Autoritário",
        "pais": "Chile (Regime de Pinochet)",
        "periodo": "1973–1990",
        "caracteristicas": "Privatizações radicais e abertura total ao mercado livre impostas por ditadura militar repressiva.",
    },
}


# ---------------------------------------------------------------------------
# 1.6 Verificação dos dados
# ---------------------------------------------------------------------------
# Corre quando o site arranca: se alguém editar os dados e se enganar
# (ex.: um intervalo ao contrário ou um país inexistente), o erro aparece logo.
def _verificar_dados():
    for nivel, info in NIVEIS.items():
        n = info["perguntas_por_eixo"]
        assert info["limite"] == 2 * n, f"Nível {nivel}: o limite tem de ser 2 × perguntas por eixo."
        assert len(PERGUNTAS_ECONOMICAS) >= n and len(PERGUNTAS_SOCIAIS) >= n, (
            f"Nível {nivel}: faltam perguntas.")
    for pergunta in PERGUNTAS_ECONOMICAS + PERGUNTAS_SOCIAIS:
        assert pergunta["direcao"] in (-1, 1), f"{pergunta['id']}: a direção tem de ser +1 ou −1."
    for nivel, zonas in PERSPETIVAS.items():
        limite = NIVEIS[nivel]["limite"]
        for zona in zonas:
            for eixo in ("x", "y"):
                minimo, maximo = zona[eixo]
                assert -limite <= minimo < maximo <= limite, (
                    f"Nível {nivel}, {zona['personalidade']}: intervalo {eixo} inválido.")
            if nivel == 3:
                assert zona["pais"] in PAISES, f"Perspetiva {zona['numero']}: país '{zona['pais']}' desconhecido."


_verificar_dados()

# Números mostrados no site (calculados a partir dos dados, nunca escritos à mão).
ESTATISTICAS = {
    "niveis": len(NIVEIS),
    "perguntas": len(PERGUNTAS_ECONOMICAS) + len(PERGUNTAS_SOCIAIS),
    "perspetivas": len(PERSPETIVAS_NIVEL_3),
    "paises": len(PAISES),
}

# Preenche os números nos textos dos níveis (ex.: "{perspetivas} perspetivas" → "32 perspetivas").
for _info in NIVEIS.values():
    _info["descricao"] = _info["descricao"].format(**ESTATISTICAS)
    _info["destaques"] = [texto.format(**ESTATISTICAS) for texto in _info["destaques"]]


# ===========================================================================
# PARTE 2 — LÓGICA DA BÚSSOLA
# ===========================================================================
VALORES_VALIDOS = {opcao["valor"] for opcao in OPCOES}
TEXTO_RESPOSTA = {opcao["valor"]: opcao["texto"] for opcao in OPCOES}


# ---------------------------------------------------------------------------
# 2.1 Perguntas
# ---------------------------------------------------------------------------
def perguntas_do_nivel(nivel):
    """Devolve as perguntas do nível, alternando uma económica e uma social.

    O nível 1 usa as 5 primeiras de cada eixo, o nível 2 as 10 primeiras e o
    nível 3 todas as 25 — cada nível é uma expansão do anterior.
    """
    n = NIVEIS[nivel]["perguntas_por_eixo"]
    perguntas = []
    for economica, social in zip(PERGUNTAS_ECONOMICAS[:n], PERGUNTAS_SOCIAIS[:n]):
        perguntas.extend([economica, social])
    return perguntas


def ler_respostas(formulario, perguntas):
    """Lê o formulário. Devolve (respostas válidas, ids das perguntas em falta)."""
    respostas, em_falta = {}, []
    for pergunta in perguntas:
        try:
            valor = int(formulario.get(pergunta["id"], ""))
        except ValueError:
            valor = None
        if valor in VALORES_VALIDOS:
            respostas[pergunta["id"]] = valor
        else:
            em_falta.append(pergunta["id"])
    return respostas, em_falta


# ---------------------------------------------------------------------------
# 2.2 Pontuação (com inversão de sinal)
# ---------------------------------------------------------------------------
def calcular_pontuacao(nivel, respostas):
    """Calcula X (Económico) e Y (Social) a partir das respostas.

    Cada resposta vale −2, −1, +1 ou +2 (grau de concordância). O contributo
    para o eixo da pergunta é   resposta × direção,   em que a direção é:
      +1 → concordar empurra para a Direita (X) ou para o Autoritário (Y)
      −1 → concordar empurra para a Esquerda (X) ou para o Libertário (Y),
           ou seja, o sinal da resposta é INVERTIDO.

    Cada eixo tem N perguntas que valem no máximo 2 pontos, logo o resultado
    fica sempre entre −2N e +2N:
      Nível 1: −10 a +10  |  Nível 2: −20 a +20  |  Nível 3: −50 a +50
    """
    x = y = 0
    detalhe = []
    for numero, pergunta in enumerate(perguntas_do_nivel(nivel), start=1):
        resposta = respostas[pergunta["id"]]
        contributo = resposta * pergunta["direcao"]
        if pergunta["eixo"] == "x":
            x += contributo
        else:
            y += contributo
        detalhe.append({
            "numero": numero,
            "pergunta": pergunta,
            "resposta": resposta,
            "resposta_texto": TEXTO_RESPOSTA[resposta],
            "contributo": contributo,
        })

    # Garantia extra: a pontuação nunca sai dos limites do nível.
    limite = NIVEIS[nivel]["limite"]
    x = max(-limite, min(limite, x))
    y = max(-limite, min(limite, y))
    return x, y, detalhe


# ---------------------------------------------------------------------------
# 2.3 Correspondências (personalidades, perspetivas e países)
# ---------------------------------------------------------------------------
def _centro(intervalo):
    return (intervalo[0] + intervalo[1]) / 2


def _distancia_ao_intervalo(valor, intervalo):
    """0 se o valor está dentro do intervalo; senão, a distância ao extremo mais perto."""
    minimo, maximo = intervalo
    if valor < minimo:
        return minimo - valor
    if valor > maximo:
        return valor - maximo
    return 0


def ordenar_correspondencias(nivel, x, y):
    """Ordena as zonas da tabela do nível, da mais para a menos semelhante.

    Critério de ordenação:
      1.º distância do ponto (x, y) ao retângulo da zona
          (0 quando a pontuação está dentro dos intervalos X e Y da tabela);
      2.º distância ao centro da zona — desempata zonas que se sobrepõem.

    As tabelas não cobrem todo o plano, por isso, quando o ponto não está em
    nenhum intervalo, a zona escolhida é simplesmente a mais próxima.
    """
    zonas = []
    for zona in PERSPETIVAS[nivel]:
        dx = _distancia_ao_intervalo(x, zona["x"])
        dy = _distancia_ao_intervalo(y, zona["y"])
        distancia = math.hypot(dx, dy)
        distancia_centro = math.hypot(x - _centro(zona["x"]), y - _centro(zona["y"]))
        zonas.append({
            **zona,
            "distancia": distancia,
            "distancia_centro": distancia_centro,
            "dentro": distancia == 0,
        })
    zonas.sort(key=lambda z: (z["distancia"], z["distancia_centro"]))
    return zonas


def paises_semelhantes(zonas_ordenadas, quantos_extra=2):
    """Nível 3: país/regime da perspetiva principal + outros das zonas seguintes."""
    principal = PAISES[zonas_ordenadas[0]["pais"]]
    chaves_vistas = {zonas_ordenadas[0]["pais"]}
    outros = []
    for zona in zonas_ordenadas[1:]:
        if len(outros) == quantos_extra:
            break
        if zona["pais"] not in chaves_vistas:
            chaves_vistas.add(zona["pais"])
            outros.append(PAISES[zona["pais"]])
    return principal, outros


def classificar_quadrante(x, y, limite):
    """Nome do quadrante e classe CSS da cor (zona central = ±10 % da escala)."""
    margem = limite * 0.1
    economico = "Esquerda" if x <= -margem else "Direita" if x >= margem else "Centro"
    social = "autoritario" if y >= margem else "libertario" if y <= -margem else "moderado"

    if economico == "Centro":
        nome = {"autoritario": "Centro Autoritário",
                "libertario": "Centro Libertário",
                "moderado": "Centro"}[social]
    else:
        nome = economico + {"autoritario": " Autoritária",
                            "libertario": " Libertária",
                            "moderado": " Moderada"}[social]

    if economico == "Centro" and social == "moderado":
        classe = "centro"
    else:
        classe = ("a" if y > 0 else "l") + ("e" if x < 0 else "d")  # ae, ad, le, ld
    return {"nome": nome, "classe": classe}


# ---------------------------------------------------------------------------
# 2.4 Gráfico (coordenadas para o SVG desenhado em resultado.html)
# ---------------------------------------------------------------------------
GRAFICO_MARGEM = 40   # espaço à volta da área do gráfico (para os rótulos)
GRAFICO_LADO = 400    # lado da área do gráfico, em píxeis do viewBox


def construir_grafico(nivel, x, y, zonas_ordenadas):
    """Converte pontuações (−limite…+limite) em coordenadas do SVG (0…480)."""
    limite = NIVEIS[nivel]["limite"]
    escala = GRAFICO_LADO / (2 * limite)
    centro = GRAFICO_MARGEM + GRAFICO_LADO / 2

    def px(valor_x):
        return round(GRAFICO_MARGEM + (valor_x + limite) * escala, 2)

    def py(valor_y):  # no SVG o y cresce para baixo, por isso invertemos
        return round(GRAFICO_MARGEM + (limite - valor_y) * escala, 2)

    principal = zonas_ordenadas[0]
    zona = {
        "x": px(principal["x"][0]),
        "y": py(principal["y"][1]),
        "largura": round((principal["x"][1] - principal["x"][0]) * escala, 2),
        "altura": round((principal["y"][1] - principal["y"][0]) * escala, 2),
    }

    # Pontos de referência (centro de cada zona). A principal fica por cima.
    referencias = []
    for indice, z in reversed(list(enumerate(zonas_ordenadas))):
        nome_zona = z.get("nome") or z["posicao"]
        referencias.append({
            "cx": px(_centro(z["x"])),
            "cy": py(_centro(z["y"])),
            "titulo": f"{z['personalidade']} — {nome_zona}",
            "principal": indice == 0,
        })

    # Posição do rótulo "Tu": evita que saia da área do gráfico.
    ux, uy = px(x), py(y)
    rotulo = {"x": ux + 14, "y": uy - 14, "ancora": "start"}
    if ux > GRAFICO_MARGEM + GRAFICO_LADO - 110:
        rotulo.update(x=ux - 14, ancora="end")
    if uy < GRAFICO_MARGEM + 28:
        rotulo["y"] = uy + 26

    # Valores marcados na moldura do gráfico (ex.: −50, −25, +25, +50):
    # os de X por baixo da área do gráfico e os de Y à esquerda.
    marcas = [
        {"valor": valor, "x": px(valor), "y": round(py(valor) + 4, 2)}
        for valor in (-limite, -limite // 2, limite // 2, limite)
    ]

    passo = GRAFICO_LADO / 10
    return {
        "inicio": GRAFICO_MARGEM,
        "fim": GRAFICO_MARGEM + GRAFICO_LADO,
        "lado": GRAFICO_LADO,
        "metade": GRAFICO_LADO / 2,
        "centro": centro,
        "grelha": [round(GRAFICO_MARGEM + i * passo, 2) for i in range(1, 10)],
        "marcas": marcas,
        "zona": zona,
        "referencias": referencias,
        "tu": {"x": ux, "y": uy},
        "rotulo": rotulo,
    }


# ===========================================================================
# PARTE 3 — FILTROS E VARIÁVEIS PARA OS TEMPLATES
# ===========================================================================
@app.template_filter("sinal")
def filtro_sinal(valor):
    """Número com sinal sempre visível: +12, −5, 0."""
    if valor > 0:
        return f"+{valor:g}"
    if valor < 0:
        return f"−{abs(valor):g}"
    return "0"


@app.template_filter("decimal")
def filtro_decimal(valor, casas=1):
    """Número decimal com vírgula (formato português): 2,5."""
    return f"{valor:.{casas}f}".replace(".", ",")


@app.template_filter("percentagem")
def filtro_percentagem(valor, limite):
    """Posição (0–100 %) de um valor entre −limite e +limite, para as barras."""
    return round((valor + limite) / (2 * limite) * 100, 2)


@app.context_processor
def injetar_dados_comuns():
    """Variáveis disponíveis em todos os templates."""
    return {
        "nome_site": NOME_SITE,
        "niveis": NIVEIS,
        "opcoes": OPCOES,
        "estatisticas": ESTATISTICAS,
    }


# ===========================================================================
# PARTE 4 — ROTAS (PÁGINAS DO SITE)
# ===========================================================================
@app.route("/")
def inicio():
    """Página principal: apresentação do projeto e os widgets das três ferramentas."""
    return render_template("index.html")


@app.route("/bussola")
def bussola():
    """Bússola Política: explicação dos eixos e escolha do nível."""
    return render_template("bussola.html")


@app.route("/bussola/teste/<int:nivel>", methods=["GET", "POST"])
def teste(nivel):
    """Mostra o questionário (GET) e recebe as respostas (POST)."""
    if nivel not in NIVEIS:
        abort(404)

    perguntas = perguntas_do_nivel(nivel)
    respostas, em_falta = {}, []

    if request.method == "POST":
        respostas, em_falta = ler_respostas(request.form, perguntas)
        if not em_falta:
            # Padrão POST → redirect → GET: atualizar a página de resultados
            # não volta a submeter o formulário.
            session["resultado"] = {"nivel": nivel, "respostas": respostas}
            return redirect(url_for("resultado"))

    return render_template(
        "teste.html",
        nivel=nivel,
        info=NIVEIS[nivel],
        perguntas=perguntas,
        respostas=respostas,
        em_falta=em_falta,
    )


@app.route("/bussola/resultado")
def resultado():
    """Calcula a pontuação a partir das respostas guardadas e mostra o resultado."""
    guardado = session.get("resultado")
    if not guardado or guardado.get("nivel") not in NIVEIS:
        return redirect(url_for("bussola"))

    nivel = guardado["nivel"]
    respostas = guardado.get("respostas", {})
    if any(respostas.get(p["id"]) not in VALORES_VALIDOS for p in perguntas_do_nivel(nivel)):
        return redirect(url_for("teste", nivel=nivel))

    limite = NIVEIS[nivel]["limite"]
    x, y, detalhe = calcular_pontuacao(nivel, respostas)
    zonas = ordenar_correspondencias(nivel, x, y)

    pais, outros_paises = (None, [])
    if nivel == 3:
        pais, outros_paises = paises_semelhantes(zonas)

    return render_template(
        "resultado.html",
        nivel=nivel,
        info=NIVEIS[nivel],
        limite=limite,
        x=x,
        y=y,
        principal=zonas[0],
        alternativas=zonas[1:4],
        pais=pais,
        outros_paises=outros_paises,
        quadrante=classificar_quadrante(x, y, limite),
        grafico=construir_grafico(nivel, x, y, zonas),
        detalhe=detalhe,
    )


@app.errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template("erro.html"), 404


# ===========================================================================
# PARTE 5 — QUIZ DE GEOPOLÍTICA
# ===========================================================================
# Cada jogo tem 12 perguntas: 4 do nível 1, depois 4 do nível 2 e por fim 4 do
# nível 3 (dificuldade progressiva). As perguntas de cada nível são sorteadas
# do banco abaixo e a ordem das opções é baralhada, por isso cada jogo é
# diferente. O servidor guarda o jogo, verifica as respostas, conta os pontos e
# gera a página HTML de cada passo (templates/quiz.html).

# ---------------------------------------------------------------------------
# 5.1 Níveis, pontos e classificações
# ---------------------------------------------------------------------------
QUIZ_PERGUNTAS_POR_NIVEL = 4
QUIZ_NIVEIS = {
    1: {"nome": "Básico", "pontos": 10},
    2: {"nome": "Intermédio", "pontos": 20},
    3: {"nome": "Avançado", "pontos": 30},
}
QUIZ_TOTAL = QUIZ_PERGUNTAS_POR_NIVEL * len(QUIZ_NIVEIS)                                    # 12
QUIZ_MAXIMO = sum(QUIZ_PERGUNTAS_POR_NIVEL * info["pontos"] for info in QUIZ_NIVEIS.values())  # 240

# (percentagem mínima dos pontos, título, mensagem) — da melhor para a pior.
QUIZ_CLASSIFICACOES = [
    (85, "Mestre da Geopolítica", "Dominas os grandes temas internacionais. Impressionante!"),
    (60, "Analista Internacional", "Tens uma visão sólida do mundo. Mais um jogo e chegas ao topo!"),
    (35, "Diplomata em Formação", "Boa base! Revê as explicações para subires de nível."),
    (0, "Explorador do Mundo", "Cada pergunta é uma descoberta. Experimenta outra vez!"),
]

# ---------------------------------------------------------------------------
# 5.2 Banco de perguntas
# ---------------------------------------------------------------------------
# Formato: (tema, pergunta, [4 opções], explicação mostrada depois de responder)
# ATENÇÃO: a PRIMEIRA opção da lista é sempre a resposta certa — o site
# baralha a ordem das opções em cada jogo.
_BANCO_QUIZ = {
    # ------------------------------------------------------- Nível 1 · Básico
    1: [
        ("Organizações internacionais",
         "Que organização, criada em 1945, reúne quase todos os países do mundo para promover a paz?",
         ["ONU", "NATO", "UEFA", "OPEP"],
         "A Organização das Nações Unidas foi criada em 1945, logo depois da Segunda Guerra Mundial, e tem "
         "hoje 193 Estados-membros."),
        ("União Europeia",
         "Qual é a moeda usada em Portugal e na maioria dos países da União Europeia?",
         ["Euro", "Dólar", "Libra", "Escudo"],
         "O euro começou a circular em 2002 e substituiu moedas nacionais como o escudo português."),
        ("União Europeia",
         "Qual destes países faz parte da União Europeia?",
         ["Espanha", "Brasil", "Japão", "Canadá"],
         "Espanha pertence à União Europeia, tal como Portugal, França ou Itália. Brasil, Japão e Canadá "
         "ficam noutros continentes."),
        ("História de Portugal",
         "Que revolução, a 25 de Abril de 1974, devolveu a democracia a Portugal?",
         ["Revolução dos Cravos", "Revolução Francesa", "Revolução Industrial", "Revolução de Outubro"],
         "Os militares do Movimento das Forças Armadas derrubaram a ditadura do Estado Novo e a população "
         "encheu as ruas com cravos vermelhos."),
        ("História",
         "Que muro dividiu uma cidade alemã em duas durante a Guerra Fria?",
         ["Muro de Berlim", "Muralha da China", "Muro de Adriano", "Muro das Lamentações"],
         "Construído em 1961, o Muro de Berlim separou a parte ocidental da parte oriental da cidade até "
         "cair, em 1989."),
        ("Geografia política",
         "Qual é o maior país do mundo em área?",
         ["Rússia", "Canadá", "China", "Estados Unidos"],
         "A Rússia tem cerca de 17 milhões de km², bem mais do que o Canadá, o segundo maior país do "
         "mundo, com perto de 10 milhões."),
        ("Comunidades e língua",
         "A CPLP reúne países que partilham que língua oficial?",
         ["Português", "Espanhol", "Francês", "Inglês"],
         "A Comunidade dos Países de Língua Portuguesa foi criada em 1996 e junta nove Estados, de "
         "Portugal e do Brasil a Angola, Moçambique e Timor-Leste."),
        ("Alianças e blocos",
         "O que é a NATO?",
         ["Uma aliança militar de defesa entre países da Europa e da América do Norte",
          "Um banco internacional que empresta dinheiro aos países",
          "Uma organização de países produtores de petróleo",
          "Um tribunal que julga crimes de guerra"],
         "Criada em 1949, a NATO junta países que se comprometem a defender-se uns aos outros. Portugal é "
         "um dos membros fundadores."),
    ],
    # --------------------------------------------------- Nível 2 · Intermédio
    2: [
        ("União Europeia",
         "Quantos países fazem parte da União Europeia?",
         ["27", "12", "50", "100"],
         "A UE tem 27 Estados-membros desde a saída do Reino Unido, em 2020. Antes do Brexit eram 28."),
        ("União Europeia",
         "Que país saiu da União Europeia em 2020?",
         ["Reino Unido", "França", "Alemanha", "Portugal"],
         "Depois de um referendo em 2016, o Reino Unido saiu da UE a 31 de janeiro de 2020, num processo "
         "conhecido como «Brexit»."),
        ("Alianças e blocos",
         "Em que cidade fica a sede da NATO?",
         ["Bruxelas", "Moscovo", "Pequim", "Rio de Janeiro"],
         "A sede da NATO fica em Bruxelas, na Bélgica, a mesma cidade onde funcionam várias instituições "
         "da União Europeia."),
        ("Organizações internacionais",
         "Quantos membros permanentes, com direito de veto, tem o Conselho de Segurança da ONU?",
         ["Cinco", "Dois", "Vinte", "Cem"],
         "São cinco: EUA, Rússia, China, Reino Unido e França. Os outros dez lugares do Conselho são "
         "ocupados por países eleitos para mandatos de dois anos."),
        ("Portugal no mundo",
         "O português António Guterres foi escolhido em 2016 para que cargo?",
         ["Secretário-Geral da ONU", "Presidente da Comissão Europeia", "Presidente da FIFA",
          "Secretário-Geral da NATO"],
         "Antigo primeiro-ministro de Portugal, Guterres assumiu o cargo de Secretário-Geral da ONU em "
         "2017. Presidente da Comissão Europeia foi outro português, Durão Barroso, entre 2004 e 2014."),
        ("História",
         "A Guerra Fria opôs sobretudo que dois países?",
         ["Estados Unidos e União Soviética", "França e Alemanha", "China e Japão", "Portugal e Espanha"],
         "Entre 1947 e 1991, as duas superpotências disputaram influência em todo o mundo sem nunca "
         "entrarem em guerra direta uma com a outra."),
        ("Conflitos atuais",
         "Que país foi invadido pela Rússia em fevereiro de 2022?",
         ["Ucrânia", "Polónia", "Finlândia", "Portugal"],
         "A invasão começou a 24 de fevereiro de 2022 e provocou a maior crise de refugiados na Europa "
         "desde a Segunda Guerra Mundial."),
        ("Organizações internacionais",
         "Que agência da ONU trabalha para proteger as crianças em todo o mundo?",
         ["UNICEF", "NATO", "OPEP", "FIFA"],
         "A UNICEF foi criada em 1946 e trabalha em mais de 190 países e territórios, em áreas como a "
         "saúde, a educação e a nutrição."),
    ],
    # ---------------------------------------------------- Nível 3 · Avançado
    3: [
        ("Portugal no mundo",
         "Em que ano Portugal aderiu à CEE, a atual União Europeia?",
         ["1986", "1974", "2002", "1960"],
         "Portugal e Espanha entraram na Comunidade Económica Europeia a 1 de janeiro de 1986. O tratado "
         "de adesão de Portugal tinha sido assinado em Lisboa, em 1985."),
        ("União Europeia",
         "Que tratado, assinado em 2007, reformou o funcionamento da União Europeia?",
         ["Tratado de Lisboa", "Tratado de Roma", "Tratado de Versalhes", "Tratado de Tordesilhas"],
         "Foi assinado no Mosteiro dos Jerónimos, em Lisboa, durante a presidência portuguesa da UE, e "
         "entrou em vigor em 2009."),
        ("União Europeia",
         "Que tratado, assinado em 1992, criou a União Europeia e preparou a chegada do euro?",
         ["Tratado de Maastricht", "Tratado de Tordesilhas", "Tratado de Versalhes",
          "Carta das Nações Unidas"],
         "Assinado nos Países Baixos, o Tratado de Maastricht criou a União Europeia e definiu as regras "
         "para a criação do euro."),
        ("Alianças e blocos",
         "Que país nórdico aderiu à NATO em 2023, depois da invasão russa da Ucrânia?",
         ["Finlândia", "Suíça", "Portugal", "Áustria"],
         "A Finlândia, que tem uma longa fronteira com a Rússia, entrou na NATO em abril de 2023. A Suécia "
         "seguiu-se em 2024; Portugal é membro fundador, desde 1949."),
        ("Organizações internacionais",
         "Em que cidade funciona o Tribunal Internacional de Justiça, o principal tribunal da ONU?",
         ["Haia", "Lisboa", "Roma", "Nova Iorque"],
         "Funciona no Palácio da Paz, em Haia, nos Países Baixos. Em Nova Iorque fica a sede da ONU."),
        ("Recursos e energia",
         "O Estreito de Ormuz, entre o Irão e Omã, é muito importante para o transporte de…",
         ["petróleo", "café", "automóveis", "trigo"],
         "Por este estreito passa cerca de um quinto do petróleo consumido no mundo. Um bloqueio faria "
         "subir os preços da energia em todo o planeta."),
        ("Portugal no mundo",
         "Porque é que Portugal tem uma das maiores zonas marítimas exclusivas (ZEE) da Europa?",
         ["Por causa dos arquipélagos dos Açores e da Madeira", "Por ter a costa mais comprida da Europa",
          "Por causa de um acordo com o Brasil", "Por ser o país mais antigo da Europa"],
         "A ZEE estende-se até 200 milhas náuticas da costa. Como os Açores e a Madeira ficam em pleno "
         "Atlântico, a zona marítima portuguesa é cerca de 18 vezes maior do que o território terrestre."),
        ("Alianças e blocos",
         "Segundo o Artigo 5.º do tratado da NATO, o que acontece se um país membro for atacado?",
         ["Os outros membros consideram que foram todos atacados e ajudam a defendê-lo",
          "O país atacado é expulso da NATO",
          "A NATO fica neutra até a guerra acabar",
          "A ONU passa a governar esse país"],
         "É o princípio da defesa coletiva: um por todos e todos por um. Só foi invocado uma vez, depois "
         "dos atentados de 11 de setembro de 2001 nos EUA."),
    ],
}


def _criar_banco_quiz(banco):
    """Transforma o banco num dicionário {id: pergunta} (ids do tipo "Q2-05")."""
    perguntas = {}
    for nivel, lista in banco.items():
        for numero, (tema, texto, opcoes, explicacao) in enumerate(lista, start=1):
            pid = f"Q{nivel}-{numero:02d}"
            perguntas[pid] = {"id": pid, "nivel": nivel, "tema": tema, "pergunta": texto,
                              "opcoes": opcoes, "explicacao": explicacao}
    return perguntas


QUIZ_PERGUNTAS = _criar_banco_quiz(_BANCO_QUIZ)
QUIZ_IDS_POR_NIVEL = {
    nivel: [pid for pid, p in QUIZ_PERGUNTAS.items() if p["nivel"] == nivel] for nivel in QUIZ_NIVEIS
}
QUIZ_INFO_NIVEIS = [
    {"nivel": nivel, "nome": info["nome"], "pontos": info["pontos"], "perguntas": QUIZ_PERGUNTAS_POR_NIVEL}
    for nivel, info in sorted(QUIZ_NIVEIS.items())
]


def _verificar_quiz():
    for nivel, ids in QUIZ_IDS_POR_NIVEL.items():
        assert len(ids) >= QUIZ_PERGUNTAS_POR_NIVEL, f"Quiz, nível {nivel}: faltam perguntas no banco."
    for p in QUIZ_PERGUNTAS.values():
        assert len(p["opcoes"]) == 4 and len(set(p["opcoes"])) == 4, f"{p['id']}: são precisas 4 opções diferentes."


_verificar_quiz()

ESTATISTICAS.update({
    "quiz_niveis": len(QUIZ_NIVEIS),
    "quiz_perguntas": QUIZ_TOTAL,
    "quiz_banco": len(QUIZ_PERGUNTAS),
    "quiz_maximo": QUIZ_MAXIMO,
})


# ---------------------------------------------------------------------------
# 5.3 Jogos em curso (guardados na memória do servidor)
# ---------------------------------------------------------------------------
# Cada jogo tem um código aleatório, guardado no cookie de sessão do Flask. O
# cookie só leva esse código: as perguntas e as respostas certas ficam no
# servidor, por isso não dá para espreitar a resposta. Os jogos parados há mais
# de 2 horas são apagados.
QUIZ_VALIDADE = 2 * 60 * 60   # segundos
QUIZ_MAX_JOGOS = 5000
_jogos = {}
# Evita que dois pedidos alterem o mesmo jogo ao mesmo tempo. É um RLock para as
# rotas poderem verificar o formulário e fazer a jogada sem largar o cadeado.
_jogos_cadeado = threading.RLock()


class ErroQuiz(Exception):
    """Erro de um jogo: a mensagem aparece em cima do jogo, na página indicada."""

    pagina = "quiz"              # página para onde o jogador volta
    chave_sessao = "quiz_jogo"   # onde fica o código do jogo no cookie de sessão

    def __init__(self, mensagem, codigo=400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


def _limpar_jogos(agora, armazem=None):
    """Apaga os jogos parados há mais de 2 horas (por omissão, os do quiz)."""
    armazem = _jogos if armazem is None else armazem
    for jogo_id in [jid for jid, j in armazem.items() if agora - j["atualizado"] > QUIZ_VALIDADE]:
        del armazem[jogo_id]
    while len(armazem) >= QUIZ_MAX_JOGOS:   # proteção: apaga os jogos mais antigos
        del armazem[min(armazem, key=lambda jid: armazem[jid]["atualizado"])]


def criar_jogo():
    """Sorteia 4 perguntas de cada nível (por ordem 1 → 2 → 3) e baralha as opções."""
    perguntas = []
    for nivel in sorted(QUIZ_NIVEIS):
        for pid in random.sample(QUIZ_IDS_POR_NIVEL[nivel], QUIZ_PERGUNTAS_POR_NIVEL):
            # "ordem" diz que opção original aparece em cada posição (0 = a certa).
            perguntas.append({"id": pid, "ordem": random.sample(range(4), 4)})
    agora = time.time()
    jogo = {"id": secrets.token_urlsafe(12), "perguntas": perguntas, "atual": 0,
            "escolhas": [], "pontos": 0, "atualizado": agora}
    with _jogos_cadeado:
        _limpar_jogos(agora)
        _jogos[jogo["id"]] = jogo
    return jogo


def obter_jogo(jogo_id):
    """Devolve o jogo ou dá erro 404 se não existir (ou tiver expirado)."""
    with _jogos_cadeado:
        jogo = _jogos.get(jogo_id)
        if jogo and time.time() - jogo["atualizado"] > QUIZ_VALIDADE:
            del _jogos[jogo_id]
            jogo = None
    if jogo is None:
        raise ErroQuiz("Este jogo já não existe ou expirou. Começa um jogo novo.", 404)
    return jogo


# ---------------------------------------------------------------------------
# 5.4 Lógica do jogo: respostas, pontuação e resultado
# ---------------------------------------------------------------------------
def _progresso(jogo):
    """Barra de progresso: um segmento por pergunta, agrupados por nível.
    Cada segmento é "certo", "errado", "atual" ou "" (pergunta ainda por fazer)."""
    grupos, indice = [], 0
    for nivel in QUIZ_INFO_NIVEIS:
        segmentos = []
        for _ in range(nivel["perguntas"]):
            if indice < len(jogo["escolhas"]):
                segmentos.append("certo" if jogo["escolhas"][indice] == 0 else "errado")
            else:
                segmentos.append("atual" if indice == jogo["atual"] else "")
            indice += 1
        grupos.append({**nivel, "segmentos": segmentos})
    return grupos


def _resumo(jogo):
    """Informação comum a todos os ecrãs do jogo (pontuação e barra de progresso)."""
    return {
        "jogo": jogo["id"],
        "numero": min(jogo["atual"] + 1, QUIZ_TOTAL),
        "total": QUIZ_TOTAL,
        "pontuacao": jogo["pontos"],
        "maximo": QUIZ_MAXIMO,
        "acertos": sum(escolha == 0 for escolha in jogo["escolhas"]),
        "historico": [escolha == 0 for escolha in jogo["escolhas"]],   # True = certa
        "progresso": _progresso(jogo),
    }


def _feedback(jogo, indice):
    """Correção de uma pergunta já respondida (posições tal como aparecem no ecrã)."""
    entrada = jogo["perguntas"][indice]
    pergunta = QUIZ_PERGUNTAS[entrada["id"]]
    escolha = jogo["escolhas"][indice]
    certa = escolha == 0
    return {
        "certa": certa,
        "opcao_escolhida": entrada["ordem"].index(escolha),
        "opcao_certa": entrada["ordem"].index(0),
        "resposta_certa": pergunta["opcoes"][0],
        "explicacao": pergunta["explicacao"],
        "pontos_ganhos": QUIZ_NIVEIS[pergunta["nivel"]]["pontos"] if certa else 0,
        "ultima": indice == QUIZ_TOTAL - 1,
    }


def estado_do_jogo(jogo):
    """Pergunta atual (sem revelar a resposta certa) ou, no fim, o resultado."""
    indice = jogo["atual"]
    if indice >= QUIZ_TOTAL:
        return resultado_do_jogo(jogo)
    entrada = jogo["perguntas"][indice]
    pergunta = QUIZ_PERGUNTAS[entrada["id"]]
    nivel = pergunta["nivel"]
    nivel_anterior = QUIZ_PERGUNTAS[jogo["perguntas"][indice - 1]["id"]]["nivel"] if indice else nivel
    return {
        **_resumo(jogo),
        "tipo": "pergunta",
        "nivel": nivel,
        "nivel_nome": QUIZ_NIVEIS[nivel]["nome"],
        "pontos_pergunta": QUIZ_NIVEIS[nivel]["pontos"],
        "novo_nivel": nivel != nivel_anterior,   # 1.ª pergunta de um nível novo
        "tema": pergunta["tema"],
        "pergunta": pergunta["pergunta"],
        "opcoes": [pergunta["opcoes"][i] for i in entrada["ordem"]],
        "ultima": indice == QUIZ_TOTAL - 1,
        # Só existe se a pergunta já foi respondida (ex.: a página foi recarregada).
        "feedback": _feedback(jogo, indice) if len(jogo["escolhas"]) > indice else None,
    }


def responder(jogo, opcao):
    """Regista a resposta (posição 0–3 no ecrã), soma os pontos e devolve a correção."""
    with _jogos_cadeado:
        indice = jogo["atual"]
        if indice >= QUIZ_TOTAL:
            raise ErroQuiz("O jogo já terminou.", 409)
        if len(jogo["escolhas"]) == indice:      # 1.ª resposta a esta pergunta
            entrada = jogo["perguntas"][indice]
            escolha = entrada["ordem"][opcao]       # posição no ecrã → opção original
            jogo["escolhas"].append(escolha)
            if escolha == 0:
                jogo["pontos"] += QUIZ_NIVEIS[QUIZ_PERGUNTAS[entrada["id"]]["nivel"]]["pontos"]
        # Se a pergunta já tinha resposta (ex.: duplo clique), devolve a mesma
        # correção sem voltar a contar pontos.
        jogo["atualizado"] = time.time()
        return {**_resumo(jogo), "tipo": "feedback", **_feedback(jogo, indice)}


def avancar(jogo):
    """Passa à pergunta seguinte (ou ao resultado, depois da última)."""
    with _jogos_cadeado:
        if len(jogo["escolhas"]) <= jogo["atual"]:
            raise ErroQuiz("Responde à pergunta antes de avançar.", 409)
        jogo["atual"] += 1
        jogo["atualizado"] = time.time()
    return estado_do_jogo(jogo)


def resultado_do_jogo(jogo):
    """Pontuação final, classificação, desempenho por nível e revisão das respostas."""
    percentagem = round(jogo["pontos"] / QUIZ_MAXIMO * 100)
    titulo, mensagem = next((t, m) for minimo, t, m in QUIZ_CLASSIFICACOES if percentagem >= minimo)

    revisao = []
    por_nivel = {nivel: {"nivel": nivel, "nome": info["nome"], "acertos": 0, "total": 0, "pontos": 0}
                 for nivel, info in QUIZ_NIVEIS.items()}
    for numero, (entrada, escolha) in enumerate(zip(jogo["perguntas"], jogo["escolhas"]), start=1):
        pergunta = QUIZ_PERGUNTAS[entrada["id"]]
        nivel = por_nivel[pergunta["nivel"]]
        nivel["total"] += 1
        if escolha == 0:
            nivel["acertos"] += 1
            nivel["pontos"] += QUIZ_NIVEIS[pergunta["nivel"]]["pontos"]
        revisao.append({
            "numero": numero,
            "nivel": pergunta["nivel"],
            "pergunta": pergunta["pergunta"],
            "tua_resposta": pergunta["opcoes"][escolha],
            "resposta_certa": pergunta["opcoes"][0],
            "certa": escolha == 0,
            "explicacao": pergunta["explicacao"],
        })
    return {
        **_resumo(jogo),
        "tipo": "resultado",
        "percentagem": percentagem,
        "titulo": titulo,
        "mensagem": mensagem,
        "por_nivel": [por_nivel[nivel] for nivel in sorted(por_nivel)],
        "revisao": revisao,
    }


# ---------------------------------------------------------------------------
# 5.5 Página do quiz (só HTML: cada botão é um formulário)
# ---------------------------------------------------------------------------
# Cada botão do quiz envia um formulário (POST) ao servidor. O Python atualiza o
# jogo e redireciona de volta para /quiz, que mostra o passo seguinte — é o
# padrão POST → redirect → GET, como na bússola: recarregar a página nunca
# repete uma jogada.
#   GET  /quiz              → ecrã inicial, pergunta atual (com a correção) ou resultado
#   POST /quiz/novo         → começa um jogo novo
#   POST /quiz/responder    → opcao (0–3) e pergunta (índice da pergunta no ecrã)
#   POST /quiz/avancar      → pergunta seguinte ou resultado final
#   POST /quiz/sair         → abandona o jogo e volta ao ecrã inicial
@app.route("/quiz")
def quiz():
    """Mostra o ecrã certo para o jogo guardado no cookie de sessão."""
    jogo_id = session.get("quiz_jogo")
    estado = estado_do_jogo(obter_jogo(jogo_id)) if jogo_id else None
    return render_template("quiz.html", estado=estado, niveis_quiz=QUIZ_INFO_NIVEIS)


@app.post("/quiz/novo")
def quiz_novo():
    session["quiz_jogo"] = criar_jogo()["id"]
    return redirect(url_for("quiz"))


@app.post("/quiz/responder")
def quiz_responder():
    jogo = obter_jogo(session.get("quiz_jogo"))
    opcao = request.form.get("opcao", type=int)
    if opcao is None or not 0 <= opcao <= 3:
        raise ErroQuiz("Escolhe uma das quatro opções.")
    with _jogos_cadeado:
        # Só conta se o formulário for o da pergunta atual: um duplo clique ou um
        # formulário antigo (botão "Voltar" do browser) não respondem à pergunta errada.
        if request.form.get("pergunta", type=int) == jogo["atual"]:
            responder(jogo, opcao)
    return redirect(url_for("quiz"))


@app.post("/quiz/avancar")
def quiz_avancar():
    jogo = obter_jogo(session.get("quiz_jogo"))
    with _jogos_cadeado:
        if request.form.get("pergunta", type=int) == jogo["atual"]:
            avancar(jogo)
    return redirect(url_for("quiz"))


@app.post("/quiz/sair")
def quiz_sair():
    jogo_id = session.pop("quiz_jogo", None)
    with _jogos_cadeado:
        _jogos.pop(jogo_id, None)
    return redirect(url_for("quiz"))


@app.errorhandler(ErroQuiz)
def erro_de_um_jogo(erro):
    """Erros do quiz e do Adivinha o Líder: volta à página do jogo com um aviso.
    Se o jogo já não existe (ex.: expirou), esquece-o e mostra o ecrã inicial."""
    if erro.codigo == 404:
        session.pop(erro.chave_sessao, None)
    flash(erro.mensagem, "erro")
    return redirect(url_for(erro.pagina, _anchor="jogo" if erro.codigo == 404 else None))


# ===========================================================================
# PARTE 6 — ADIVINHA O LÍDER
# ===========================================================================
# Jogo de pistas: em cada ronda há um líder político misterioso (histórico ou
# atual) e 4 pistas, da mais difícil para a mais fácil. Quanto menos pistas o
# jogador usar, mais pontos ganha. O servidor guarda o jogo, valida os palpites,
# conta os pontos e gera a página HTML de cada jogada (templates/lideres.html).

# ---------------------------------------------------------------------------
# 6.1 Regras e pontuação
# ---------------------------------------------------------------------------
LIDERES_RONDAS = 5
# Pontos de uma resposta certa conforme o n.º de pistas já vistas (1, 2, 3 ou 4).
LIDERES_PONTOS_POR_PISTA = [10, 7, 4, 2]
LIDERES_MAXIMO = LIDERES_RONDAS * LIDERES_PONTOS_POR_PISTA[0]   # 50
LIDERES_DIFICULDADES = {1: "Fácil", 2: "Médio", 3: "Difícil"}
# Modo "misto" (o predefinido): 3 líderes fáceis e 2 médios, por esta ordem.
# Os difíceis ficam só para quem escolher o modo "Difícil".
LIDERES_MISTO = [1, 1, 1, 2, 2]

# (percentagem mínima dos pontos, título, mensagem) — da melhor para a pior.
LIDERES_CLASSIFICACOES = [
    (80, "Enciclopédia Política", "Reconheces os líderes logo às primeiras pistas. Impressionante!"),
    (55, "Comentador Político", "Tens bom faro para a política mundial. Mais um jogo?"),
    (30, "Eleitor Atento", "Já reconheces muitos rostos do poder. Continua a jogar!"),
    (0, "Turista da História", "Cada ronda é uma lição. Experimenta outra vez!"),
]

# ---------------------------------------------------------------------------
# 6.2 Base de dados de líderes
# ---------------------------------------------------------------------------
# Cada líder tem:
#   id           identificador único, sem espaços
#   nome, pais, cargo, epoca
#   dificuldade  1 (Fácil), 2 (Médio) ou 3 (Difícil)
#   imagem       opcional: caminho dentro de static/ (ex.: "img/lideres/mandela.jpg");
#                None mostra um círculo com as iniciais
#   aceites      respostas aceites (nome completo, apelido, alcunhas…). Maiúsculas,
#                acentos e pequenos erros de escrita são tolerados automaticamente.
#   pistas       4 pistas, da MAIS DIFÍCIL para a MAIS FÁCIL
LIDERES = [
    # ------------------------------------------------------------- Fácil
    {"id": "mandela", "nome": "Nelson Mandela", "pais": "África do Sul",
     "cargo": "Presidente da África do Sul (1994–1999)", "epoca": "Século XX", "dificuldade": 1, "imagem": None,
     "aceites": ["Nelson Mandela", "Mandela", "Madiba", "Nelson Rolihlahla Mandela"],
     "pistas": [
         "Durante anos parti pedra numa pedreira de calcário, sob uma luz tão intensa que me deixou os olhos "
         "danificados para sempre — e não estava lá por vontade própria.",
         "Passei 27 anos na prisão, a maior parte deles numa ilha ao largo da Cidade do Cabo.",
         "Partilhei o Prémio Nobel da Paz de 1993 com o presidente que me libertou, F. W. de Klerk.",
         "Fui o primeiro presidente negro da África do Sul, eleito em 1994, depois do fim do apartheid.",
     ]},
    {"id": "churchill", "nome": "Winston Churchill", "pais": "Reino Unido",
     "cargo": "Primeiro-ministro do Reino Unido (1940–1945 e 1951–1955)", "epoca": "Século XX", "dificuldade": 1,
     "imagem": None,
     "aceites": ["Winston Churchill", "Churchill", "Winston"],
     "pistas": [
         "Recebi um Prémio Nobel — não o da Paz, mas o da Literatura.",
         "Como jovem correspondente de guerra, fui capturado na África do Sul e fugi de um campo de prisioneiros.",
         "Num discurso de 1940, prometi aos meus compatriotas apenas «sangue, trabalho, lágrimas e suor».",
         "Fui primeiro-ministro britânico durante a Segunda Guerra Mundial e raramente era visto sem um charuto.",
     ]},
    {"id": "gandhi", "nome": "Mahatma Gandhi", "pais": "Índia",
     "cargo": "Líder do movimento pela independência da Índia", "epoca": "Século XX", "dificuldade": 1,
     "imagem": None,
     "aceites": ["Mahatma Gandhi", "Gandhi", "Mohandas Gandhi", "Mohandas Karamchand Gandhi", "Mahatma"],
     "pistas": [
         "Estudei Direito em Londres e trabalhei mais de 20 anos como advogado na África do Sul.",
         "Em 1930 caminhei quase 400 km até ao mar para fazer sal, desafiando um imposto colonial.",
         "Defendi a resistência não violenta, a que chamei «satyagraha».",
         "Sou considerado o pai da independência da Índia; o título por que sou conhecido significa «grande alma».",
     ]},
    {"id": "lincoln", "nome": "Abraham Lincoln", "pais": "Estados Unidos",
     "cargo": "16.º Presidente dos Estados Unidos (1861–1865)", "epoca": "Século XIX", "dificuldade": 1,
     "imagem": None,
     "aceites": ["Abraham Lincoln", "Lincoln", "Abe Lincoln"],
     "pistas": [
         "Sou o único presidente do meu país com uma patente registada: um sistema para soltar barcos encalhados "
         "em bancos de areia.",
         "Fui praticamente autodidata e trabalhei como advogado no Illinois.",
         "O meu discurso de Gettysburg, com cerca de dois minutos, é um dos mais célebres da história.",
         "Liderei os EUA durante a Guerra Civil, assinei a Proclamação de Emancipação e fui assassinado num "
         "teatro, em 1865.",
     ]},
    {"id": "napoleao", "nome": "Napoleão Bonaparte", "pais": "França",
     "cargo": "Imperador dos Franceses (1804–1814 e 1815)", "epoca": "Séculos XVIII–XIX", "dificuldade": 1,
     "imagem": None,
     "aceites": ["Napoleão Bonaparte", "Napoleão", "Napoleon", "Napoleon Bonaparte", "Bonaparte", "Napoleão I"],
     "pistas": [
         "Nasci numa ilha mediterrânica que tinha passado para o domínio francês apenas um ano antes.",
         "Criei um código civil que influenciou o direito de muitos países, incluindo Portugal.",
         "As minhas tropas invadiram Portugal três vezes e a família real portuguesa partiu para o Brasil.",
         "Coroei-me imperador dos franceses e fui derrotado em Waterloo, em 1815.",
     ]},
    {"id": "obama", "nome": "Barack Obama", "pais": "Estados Unidos",
     "cargo": "44.º Presidente dos Estados Unidos (2009–2017)", "epoca": "Século XXI", "dificuldade": 1,
     "imagem": None,
     "aceites": ["Barack Obama", "Obama", "Barack Hussein Obama"],
     "pistas": [
         "Passei parte da infância na Indonésia e cresci no Havai, onde me chamavam «Barry».",
         "Fui o primeiro afro-americano a presidir à prestigiada revista Harvard Law Review.",
         "Recebi o Prémio Nobel da Paz em 2009, logo no primeiro ano de mandato.",
         "Fui o primeiro presidente afro-americano dos EUA, eleito com o lema «Yes we can».",
     ]},
    {"id": "castro", "nome": "Fidel Castro", "pais": "Cuba",
     "cargo": "Líder de Cuba (1959–2008)", "epoca": "Séculos XX–XXI", "dificuldade": 1, "imagem": None,
     "aceites": ["Fidel Castro", "Fidel", "Castro", "Fidel Castro Ruz"],
     "pistas": [
         "Estudei num colégio jesuíta e formei-me em Direito na Universidade de Havana.",
         "Depois de um ataque falhado a um quartel, terminei a minha defesa em tribunal com a frase «A história "
         "absolver-me-á».",
         "Os meus serviços de segurança afirmam que sobrevivi a centenas de planos para me assassinar.",
         "Liderei a Revolução Cubana em 1959 e governei Cuba durante quase 50 anos.",
     ]},
    {"id": "merkel", "nome": "Angela Merkel", "pais": "Alemanha",
     "cargo": "Chanceler da Alemanha (2005–2021)", "epoca": "Século XXI", "dificuldade": 1, "imagem": None,
     "aceites": ["Angela Merkel", "Merkel"],
     "pistas": [
         "Antes da política, fiz um doutoramento em Química Quântica.",
         "Cresci na Alemanha de Leste, onde o meu pai era pastor luterano.",
         "Fui a primeira mulher a chefiar o governo do meu país e ganhei a alcunha de «Mutti» (mãezinha).",
         "Fui chanceler da Alemanha durante 16 anos, de 2005 a 2021.",
     ]},
    {"id": "zelensky", "nome": "Volodymyr Zelensky", "pais": "Ucrânia",
     "cargo": "Presidente da Ucrânia (eleito em 2019)", "epoca": "Atualidade", "dificuldade": 1, "imagem": None,
     "aceites": ["Volodymyr Zelensky", "Zelensky", "Zelenskyy", "Zelenski", "Zelenskiy", "Vladimir Zelensky",
                 "Volodimir Zelensky"],
     "pistas": [
         "Fui a voz do urso Paddington nas versões ucranianas dos filmes.",
         "Ganhei a versão ucraniana do concurso «Dança com as Estrelas», em 2006.",
         "Numa série de televisão interpretei um professor que chega a presidente do país — e depois "
         "aconteceu-me o mesmo na vida real.",
         "Fui eleito presidente da Ucrânia em 2019 e liderei o país durante a invasão russa de 2022.",
     ]},
    {"id": "macron", "nome": "Emmanuel Macron", "pais": "França",
     "cargo": "Presidente de França (eleito em 2017 e reeleito em 2022)", "epoca": "Atualidade", "dificuldade": 1,
     "imagem": None,
     "aceites": ["Emmanuel Macron", "Macron"],
     "pistas": [
         "Antes da política, fui assistente do filósofo Paul Ricœur.",
         "Trabalhei como banqueiro de investimento no banco Rothschild.",
         "Criei o meu próprio movimento político, «En Marche!», cujas iniciais são as mesmas do meu nome.",
         "Tornei-me, aos 39 anos, o presidente mais jovem da história de França.",
     ]},
    # ------------------------------------------------------------- Médio
    {"id": "gorbachev", "nome": "Mikhail Gorbachev", "pais": "União Soviética",
     "cargo": "Último líder da União Soviética (1985–1991)", "epoca": "Século XX", "dificuldade": 2, "imagem": None,
     "aceites": ["Mikhail Gorbachev", "Gorbachev", "Gorbatchov", "Mikhail Gorbatchov", "Gorbachov", "Gorbatchev",
                 "Gorby"],
     "pistas": [
         "Aos 17 anos fui condecorado por trabalhar nas colheitas com uma ceifeira-debulhadora, ao lado do meu pai.",
         "Tinha uma marca de nascença na testa que se tornou famosa em todo o mundo.",
         "Lancei a «perestroika» e a «glasnost»: reestruturação e transparência.",
         "Fui o último líder da União Soviética e recebi o Prémio Nobel da Paz em 1990.",
     ]},
    {"id": "thatcher", "nome": "Margaret Thatcher", "pais": "Reino Unido",
     "cargo": "Primeira-ministra do Reino Unido (1979–1990)", "epoca": "Século XX", "dificuldade": 2, "imagem": None,
     "aceites": ["Margaret Thatcher", "Thatcher", "Maggie Thatcher"],
     "pistas": [
         "Antes da política, trabalhei como química numa empresa alimentar.",
         "Como ministra da Educação, acabei com o leite gratuito nas escolas para as crianças mais velhas e ganhei "
         "uma alcunha pouco simpática.",
         "Enfrentei uma longa greve dos mineiros e uma guerra nas Malvinas, em 1982.",
         "Fui a primeira mulher a chefiar o governo do Reino Unido, conhecida como a «Dama de Ferro».",
     ]},
    {"id": "degaulle", "nome": "Charles de Gaulle", "pais": "França",
     "cargo": "Presidente de França (1959–1969)", "epoca": "Século XX", "dificuldade": 2, "imagem": None,
     "aceites": ["Charles de Gaulle", "De Gaulle", "General de Gaulle", "Gaulle"],
     "pistas": [
         "Fui ferido e feito prisioneiro na Primeira Guerra Mundial e tentei fugir várias vezes dos campos alemães.",
         "Em 1940, num apelo transmitido de Londres pela rádio BBC, pedi aos meus compatriotas que continuassem "
         "a lutar.",
         "Fundei a V República, cuja constituição ainda hoje está em vigor no meu país.",
         "General que liderou a França Livre na Segunda Guerra Mundial; o maior aeroporto de Paris tem o meu nome.",
     ]},
    {"id": "indira", "nome": "Indira Gandhi", "pais": "Índia",
     "cargo": "Primeira-ministra da Índia (1966–1977 e 1980–1984)", "epoca": "Século XX", "dificuldade": 2,
     "imagem": None,
     "aceites": ["Indira Gandhi", "Indira", "Indira Priyadarshini Gandhi"],
     "pistas": [
         "Em criança, organizei uma «brigada de macacos» de crianças que ajudava o movimento independentista.",
         "O meu pai foi o primeiro chefe de governo do meu país depois da independência.",
         "Em 1975 declarei o estado de emergência e governei durante 21 meses com poderes excecionais.",
         "Fui a primeira mulher a chefiar o governo da Índia e fui assassinada em 1984.",
     ]},
    {"id": "bolivar", "nome": "Simón Bolívar", "pais": "Venezuela",
     "cargo": "Libertador de vários países da América do Sul", "epoca": "Século XIX", "dificuldade": 2,
     "imagem": None,
     "aceites": ["Simón Bolívar", "Bolívar", "O Libertador", "El Libertador", "Libertador"],
     "pistas": [
         "Fiquei órfão em criança e viúvo muito jovem; em Roma, no cimo de um monte, jurei libertar a minha terra.",
         "Sonhei unir a América do Sul numa grande república chamada Grã-Colômbia.",
         "Um país inteiro foi batizado com o meu nome.",
         "Conhecido como «O Libertador», levei vários países sul-americanos à independência do domínio espanhol.",
     ]},
    {"id": "soares", "nome": "Mário Soares", "pais": "Portugal",
     "cargo": "Primeiro-ministro e Presidente da República Portuguesa (1986–1996)", "epoca": "Século XX",
     "dificuldade": 2, "imagem": None,
     "aceites": ["Mário Soares", "Soares", "Mário Alberto Nobre Lopes Soares"],
     "pistas": [
         "Fui preso várias vezes pela polícia política e deportado para a ilha de São Tomé.",
         "Ajudei a fundar um partido político em 1973, na Alemanha, ainda durante a ditadura.",
         "Como primeiro-ministro, assinei em 1985 o tratado de adesão de Portugal à CEE.",
         "Fui primeiro-ministro e depois Presidente da República Portuguesa, entre 1986 e 1996.",
     ]},
    {"id": "golda", "nome": "Golda Meir", "pais": "Israel",
     "cargo": "Primeira-ministra de Israel (1969–1974)", "epoca": "Século XX", "dificuldade": 2, "imagem": None,
     "aceites": ["Golda Meir", "Golda", "Meir", "Golda Meyerson"],
     "pistas": [
         "Nasci em Kiev, cresci nos Estados Unidos e fui professora em Milwaukee.",
         "Fui uma das duas mulheres que assinaram a declaração de independência do meu país, em 1948.",
         "Ben-Gurion terá dito que eu era «o único homem do governo».",
         "Fui a primeira mulher a chefiar o governo de Israel e enfrentei a Guerra do Yom Kippur, em 1973.",
     ]},
    {"id": "lula", "nome": "Lula da Silva", "pais": "Brasil",
     "cargo": "Presidente do Brasil (2003–2010; eleito de novo em 2022)", "epoca": "Século XXI", "dificuldade": 2,
     "imagem": None,
     "aceites": ["Lula", "Lula da Silva", "Luiz Inácio Lula da Silva", "Luís Inácio Lula da Silva"],
     "pistas": [
         "Perdi um dedo da mão num acidente com uma prensa, quando era operário metalúrgico.",
         "Liderei grandes greves de metalúrgicos em São Paulo no final dos anos 70.",
         "Ajudei a fundar o Partido dos Trabalhadores, em 1980.",
         "Fui presidente do Brasil entre 2003 e 2010 e voltei a ser eleito em 2022.",
     ]},
    {"id": "xi", "nome": "Xi Jinping", "pais": "China",
     "cargo": "Secretário-geral do Partido Comunista Chinês (desde 2012)", "epoca": "Atualidade", "dificuldade": 2,
     "imagem": None,
     "aceites": ["Xi Jinping", "Xi", "Xi Jin Ping"],
     "pistas": [
         "Na juventude, durante a Revolução Cultural, vivi vários anos numa casa escavada numa encosta, numa "
         "aldeia rural.",
         "O meu pai foi um dirigente revolucionário que caiu em desgraça e foi perseguido durante anos.",
         "Em 2013 lancei a «Iniciativa Faixa e Rota», um enorme plano de infraestruturas entre a Ásia, a Europa e "
         "a África.",
         "Sou secretário-geral do Partido Comunista Chinês desde 2012 e presidente da China desde 2013.",
     ]},
    {"id": "modi", "nome": "Narendra Modi", "pais": "Índia",
     "cargo": "Primeiro-ministro da Índia (desde 2014)", "epoca": "Atualidade", "dificuldade": 2, "imagem": None,
     "aceites": ["Narendra Modi", "Modi"],
     "pistas": [
         "Conto que, em criança, ajudava o meu pai a vender chá numa estação de comboios.",
         "Chefiei o governo do estado do Gujarate durante mais de 12 anos.",
         "O meu partido, o BJP, venceu as eleições gerais de 2014, 2019 e 2024.",
         "Sou primeiro-ministro da Índia, o país mais populoso do mundo, desde 2014.",
     ]},
    # ----------------------------------------------------------- Difícil
    {"id": "sankara", "nome": "Thomas Sankara", "pais": "Burkina Faso",
     "cargo": "Presidente do Burkina Faso (1983–1987)", "epoca": "Século XX", "dificuldade": 3, "imagem": None,
     "aceites": ["Thomas Sankara", "Sankara"],
     "pistas": [
         "Vendi os carros de luxo do governo e pus os ministros a andar em modestos Renault 5.",
         "Tocava guitarra e cheguei a ter uma banda de jazz.",
         "Mudei o nome do meu país de Alto Volta para um nome que significa «terra dos homens íntegros».",
         "Revolucionário conhecido como «o Che Guevara de África», fui assassinado em 1987.",
     ]},
    {"id": "leekuanyew", "nome": "Lee Kuan Yew", "pais": "Singapura",
     "cargo": "Primeiro-ministro de Singapura (1959–1990)", "epoca": "Século XX", "dificuldade": 3, "imagem": None,
     "aceites": ["Lee Kuan Yew", "Lee", "Harry Lee", "LKY"],
     "pistas": [
         "Estudei Direito em Cambridge, onde era conhecido pelo nome inglês «Harry».",
         "Chorei em direto na televisão quando o meu país foi afastado de uma federação vizinha, em 1965.",
         "Transformei uma pequena ilha sem recursos naturais num dos centros financeiros mais ricos do mundo.",
         "Fui o primeiro primeiro-ministro de Singapura e governei-a durante mais de 30 anos.",
     ]},
    {"id": "nkrumah", "nome": "Kwame Nkrumah", "pais": "Gana",
     "cargo": "Primeiro presidente do Gana (1960–1966)", "epoca": "Século XX", "dificuldade": 3, "imagem": None,
     "aceites": ["Kwame Nkrumah", "Nkrumah"],
     "pistas": [
         "Estudei nos Estados Unidos e em Londres e ajudei a organizar o Congresso Pan-Africano de 1945, em "
         "Manchester.",
         "Fui derrubado por um golpe militar enquanto estava em visita oficial à China.",
         "Defendi a união dos países africanos e ajudei a fundar a Organização da Unidade Africana, em 1963.",
         "Levei a antiga Costa do Ouro à independência, em 1957, com o nome de Gana.",
     ]},
    {"id": "ataturk", "nome": "Mustafa Kemal Atatürk", "pais": "Turquia",
     "cargo": "Fundador e 1.º Presidente da República da Turquia (1923–1938)", "epoca": "Século XX",
     "dificuldade": 3, "imagem": None,
     "aceites": ["Atatürk", "Mustafa Kemal Atatürk", "Mustafa Kemal", "Kemal Atatürk", "Kemal"],
     "pistas": [
         "Ganhei fama militar a defender a península de Galípoli contra os Aliados, em 1915.",
         "Substituí o alfabeto árabe pelo latino e dei às mulheres o direito de voto.",
         "O apelido por que sou conhecido significa «pai dos turcos» e foi-me atribuído pelo parlamento.",
         "Fundei a República da Turquia em 1923, sobre as ruínas do Império Otomano.",
     ]},
    {"id": "hochiminh", "nome": "Ho Chi Minh", "pais": "Vietname",
     "cargo": "Presidente do Vietname do Norte (1945–1969)", "epoca": "Século XX", "dificuldade": 3, "imagem": None,
     "aceites": ["Ho Chi Minh", "Ho Chi Min", "Ho", "Tio Ho"],
     "pistas": [
         "Trabalhei como ajudante de cozinha num navio e, segundo a lenda, como pasteleiro num hotel de luxo em "
         "Londres.",
         "Em 1919, tentei entregar aos líderes reunidos em Versalhes uma petição pelos direitos do meu povo.",
         "Declarei a independência do meu país em 1945, citando a Declaração de Independência dos EUA.",
         "Liderei o Vietname do Norte; a antiga Saigão tem hoje o meu nome.",
     ]},
    {"id": "evita", "nome": "Eva Perón", "pais": "Argentina",
     "cargo": "Primeira-dama e líder política da Argentina (1946–1952)", "epoca": "Século XX", "dificuldade": 3,
     "imagem": None,
     "aceites": ["Eva Perón", "Evita", "Evita Perón", "Eva Duarte", "Eva Duarte de Perón"],
     "pistas": [
         "Antes da política, fui atriz de rádio e de cinema em Buenos Aires.",
         "Dirigi uma grande fundação de ajuda social e lutei pelo voto das mulheres, aprovado em 1947.",
         "Morri com apenas 33 anos e o meu corpo embalsamado esteve desaparecido durante 16 anos.",
         "Casada com o presidente Juan Perón, sou recordada como «Evita».",
     ]},
    {"id": "allende", "nome": "Salvador Allende", "pais": "Chile",
     "cargo": "Presidente do Chile (1970–1973)", "epoca": "Século XX", "dificuldade": 3, "imagem": None,
     "aceites": ["Salvador Allende", "Allende"],
     "pistas": [
         "Era médico e, como ministro da Saúde, lutei por melhores condições de vida para os trabalhadores.",
         "Candidatei-me quatro vezes à presidência do meu país até ser eleito.",
         "Fui o primeiro presidente marxista eleito democraticamente na América Latina.",
         "Morri no palácio de La Moneda durante o golpe militar de 11 de setembro de 1973.",
     ]},
    {"id": "bhutto", "nome": "Benazir Bhutto", "pais": "Paquistão",
     "cargo": "Primeira-ministra do Paquistão (1988–1990 e 1993–1996)", "epoca": "Século XX", "dificuldade": 3,
     "imagem": None,
     "aceites": ["Benazir Bhutto", "Benazir", "Bhutto"],
     "pistas": [
         "Estudei em Harvard e em Oxford, onde presidi à famosa sociedade de debates Oxford Union.",
         "O meu pai, antigo primeiro-ministro, foi executado depois de um golpe militar.",
         "Fui a primeira mulher a chefiar o governo de um país de maioria muçulmana, em 1988.",
         "Fui duas vezes primeira-ministra do Paquistão e fui assassinada num comício, em 2007.",
     ]},
]
LIDERES_POR_ID = {lider["id"]: lider for lider in LIDERES}


# ---------------------------------------------------------------------------
# 6.3 Validação dos palpites
# ---------------------------------------------------------------------------
_PALAVRAS_IGNORADAS = {"o", "a", "os", "as", "e", "el", "de", "do", "da", "dos", "das",
                       "presidente", "rei", "rainha", "general", "sr", "senhor", "dona"}
LIMIAR_CERTO = 0.86   # semelhança a partir da qual um palpite com pequenos erros conta como certo
LIMIAR_QUASE = 0.75   # entre os dois limiares, o jogador é avisado de que está quase


def normalizar_nome(texto):
    """'O Napoleão Bonaparte!' → 'napoleao bonaparte' (sem acentos, maiúsculas, pontuação nem artigos)."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(p for p in re.findall(r"[a-z0-9]+", texto) if p not in _PALAVRAS_IGNORADAS)


# Respostas aceites já normalizadas, e a que líder pertence cada uma.
_ACEITES = {
    lider["id"]: sorted({normalizar_nome(n) for n in lider["aceites"] + [lider["nome"]]} - {""})
    for lider in LIDERES
}
_DONO_DO_NOME = {nome: lid for lid, nomes in _ACEITES.items() for nome in nomes}


def _contem_sequencia(palavras, partes):
    n = len(partes)
    return any(palavras[i:i + n] == partes for i in range(len(palavras) - n + 1))


def avaliar_palpite(palpite, lider):
    """Compara o palpite com as respostas aceites. Devolve "certo", "quase" ou "errado"."""
    tentativa = normalizar_nome(palpite)
    if not tentativa:
        return "errado"
    aceites = _ACEITES[lider["id"]]
    if tentativa in aceites:
        return "certo"
    # O nome exato de OUTRO líder da base de dados é sempre errado (ex.: Indira vs. Mahatma Gandhi).
    if _DONO_DO_NOME.get(tentativa, lider["id"]) != lider["id"]:
        return "errado"
    # "Nelson Mandela da África do Sul" contém "nelson mandela". Só para nomes com 2+ palavras
    # e sem permitir listas de vários nomes de uma vez.
    palavras = tentativa.split()
    for nome in aceites:
        partes = nome.split()
        if len(partes) >= 2 and len(palavras) <= len(partes) + 2 and _contem_sequencia(palavras, partes):
            return "certo"
    # Pequenos erros de escrita: "Mandella", "Gorbatchev"…
    semelhanca = max(difflib.SequenceMatcher(None, tentativa, nome).ratio() for nome in aceites)
    if semelhanca >= LIMIAR_CERTO:
        return "certo"
    return "quase" if semelhanca >= LIMIAR_QUASE else "errado"


def _verificar_lideres():
    for lider in LIDERES:
        assert lider["dificuldade"] in LIDERES_DIFICULDADES, f"{lider['id']}: dificuldade inválida."
        assert len(lider["pistas"]) == len(LIDERES_PONTOS_POR_PISTA), (
            f"{lider['id']}: precisa de exatamente {len(LIDERES_PONTOS_POR_PISTA)} pistas.")
        assert _ACEITES[lider["id"]], f"{lider['id']}: falta pelo menos uma resposta aceite."
    assert len(LIDERES_POR_ID) == len(LIDERES), "Há ids de líderes repetidos."
    for nivel in LIDERES_DIFICULDADES:
        disponiveis = sum(lider["dificuldade"] == nivel for lider in LIDERES)
        assert disponiveis >= max(LIDERES_RONDAS, LIDERES_MISTO.count(nivel)), (
            f"Líderes: são precisos pelo menos {LIDERES_RONDAS} de dificuldade {nivel}.")


_verificar_lideres()

ESTATISTICAS.update({
    "lideres": len(LIDERES),
    "lideres_rondas": LIDERES_RONDAS,
    "lideres_pistas": len(LIDERES_PONTOS_POR_PISTA),
    "lideres_maximo": LIDERES_MAXIMO,
})


# ---------------------------------------------------------------------------
# 6.4 Jogos em curso (memória do servidor, como no quiz)
# ---------------------------------------------------------------------------
_jogos_lideres = {}


class ErroLideres(ErroQuiz):
    """Erro do jogo dos líderes (mesmo tratamento dos erros do quiz, noutra página)."""

    pagina = "lideres"
    chave_sessao = "lideres_jogo"


def criar_jogo_lideres(modo):
    """modo = "misto" ou uma dificuldade (1, 2 ou 3). Sorteia os líderes de cada ronda."""
    composicao = LIDERES_MISTO if modo == "misto" else [modo] * LIDERES_RONDAS
    escolhidos = []
    for nivel in sorted(set(composicao)):
        candidatos = [lider["id"] for lider in LIDERES if lider["dificuldade"] == nivel]
        escolhidos += random.sample(candidatos, composicao.count(nivel))
    agora = time.time()
    # "passo" conta as jogadas (vai em cada formulário, para ignorar envios repetidos);
    # "evento" é a última jogada, para a página seguinte mostrar a mensagem certa.
    jogo = {"id": secrets.token_urlsafe(12), "modo": modo, "lideres": escolhidos, "ronda": 0,
            "pistas_vistas": 1, "tentativas": [], "opcoes": None, "fim_ronda": None, "resultados": [],
            "pontos": 0, "passo": 0, "evento": None, "atualizado": agora}
    with _jogos_cadeado:
        _limpar_jogos(agora, _jogos_lideres)
        _jogos_lideres[jogo["id"]] = jogo
    return jogo


def obter_jogo_lideres(jogo_id):
    with _jogos_cadeado:
        jogo = _jogos_lideres.get(jogo_id)
        if jogo and time.time() - jogo["atualizado"] > QUIZ_VALIDADE:
            del _jogos_lideres[jogo_id]
            jogo = None
    if jogo is None:
        raise ErroLideres("Este jogo já não existe ou expirou. Começa um jogo novo.", 404)
    return jogo


# ---------------------------------------------------------------------------
# 6.5 Lógica do jogo: pistas, palpites e pontuação
# ---------------------------------------------------------------------------
def _iniciais(nome):
    partes = [p for p in nome.split() if p[:1].isupper()]
    return (partes[0][0] + partes[-1][0]) if len(partes) > 1 else nome[:2].upper()


def _imagem(lider):
    return url_for("static", filename=lider["imagem"]) if lider["imagem"] else None


def _valor_ronda(jogo, vistas=None):
    """Pontos de uma resposta certa: 10, 7, 4 ou 2 conforme as pistas vistas — ou metade
    (arredondada para cima) se o jogador pediu as 4 opções de escolha."""
    vistas = jogo["pistas_vistas"] if vistas is None else vistas
    valor = LIDERES_PONTOS_POR_PISTA[vistas - 1]
    return math.ceil(valor / 2) if jogo["opcoes"] else valor


def _opcoes_para(lider):
    """4 nomes à escolha: o certo e 3 outros, de preferência do mesmo país e da mesma dificuldade
    (assim a dica do país não chega, sozinha, para acertar)."""
    outros = [l for l in LIDERES if l is not lider]
    random.shuffle(outros)
    outros.sort(key=lambda l: (l["pais"] != lider["pais"], l["dificuldade"] != lider["dificuldade"]))
    nomes = [lider["nome"]] + [l["nome"] for l in outros[:3]]
    random.shuffle(nomes)
    return nomes


def _mapa_rondas(jogo):
    """Uma entrada por ronda para o painel: "certa", "falhada", "atual" ou "" (por jogar)."""
    mapa = []
    for indice in range(len(jogo["lideres"])):
        if indice < len(jogo["resultados"]):
            resultado = jogo["resultados"][indice]
            mapa.append({"numero": indice + 1, "pontos": resultado["pontos"],
                         "situacao": "certa" if resultado["certa"] else "falhada"})
        else:
            mapa.append({"numero": indice + 1, "pontos": 0,
                         "situacao": "atual" if indice == jogo["ronda"] else ""})
    return mapa


def _resumo_lideres(jogo):
    """Informação comum a todos os ecrãs do jogo (é o que alimenta o painel de pontuação)."""
    total = len(jogo["lideres"])
    return {
        "jogo": jogo["id"],
        "modo": "Misto" if jogo["modo"] == "misto" else LIDERES_DIFICULDADES[jogo["modo"]],
        "modo_valor": jogo["modo"],   # para o botão "Jogar outra vez" repetir a dificuldade
        "passo": jogo["passo"],
        "ronda": min(jogo["ronda"] + 1, total),
        "total_rondas": total,
        "pontuacao": jogo["pontos"],
        "maximo": total * LIDERES_PONTOS_POR_PISTA[0],
        "acertos": sum(r["certa"] for r in jogo["resultados"]),
        "historico": [{"certa": r["certa"], "pontos": r["pontos"]} for r in jogo["resultados"]],
        "mapa_rondas": _mapa_rondas(jogo),
        "pontos_por_pista": LIDERES_PONTOS_POR_PISTA,
    }


def estado_lideres(jogo):
    """Ronda atual — só com as pistas já desbloqueadas — ou, no fim, o resultado."""
    if jogo["ronda"] >= len(jogo["lideres"]):
        return resultado_lideres(jogo)
    lider = LIDERES_POR_ID[jogo["lideres"][jogo["ronda"]]]
    terminada = jogo["fim_ronda"] is not None
    vistas = jogo["pistas_vistas"]
    total_pistas = len(lider["pistas"])
    valor = _valor_ronda(jogo)
    escada = [_valor_ronda(jogo, n) for n in range(1, total_pistas + 1)]

    # Escada de pontos do painel: degraus já usados, o atual e (se acertou) o ganho.
    degraus = []
    for n, pontos in enumerate(escada, start=1):
        if terminada and jogo["fim_ronda"] == "certa" and n == vistas:
            situacao = "ganho"
        elif n < vistas or (terminada and n == vistas):
            situacao = "usado"
        else:
            situacao = "atual" if n == vistas else ""
        degraus.append({"pista": n, "pontos": pontos, "situacao": situacao})

    # As 4 opções (se pedidas): as que o jogador já tentou ficam riscadas.
    tentadas = {normalizar_nome(t) for t in jogo["tentativas"]}
    opcoes = None
    if jogo["opcoes"]:
        opcoes = [{"nome": nome, "tentada": normalizar_nome(nome) in tentadas} for nome in jogo["opcoes"]]

    estado = {
        **_resumo_lideres(jogo),
        "tipo": "ronda",
        "dificuldade": lider["dificuldade"],
        "dificuldade_nome": LIDERES_DIFICULDADES[lider["dificuldade"]],
        # Dica dada desde o início de cada ronda: o país do líder.
        "pais": lider["pais"],
        # A resposta nunca vai para a página antes do fim da ronda: só as pistas
        # desbloqueadas (e as 4 opções de escolha, se o jogador as pedir).
        "pistas": lider["pistas"] if terminada else lider["pistas"][:vistas],
        "pistas_vistas": vistas,
        "total_pistas": total_pistas,
        "pontos_ronda": 0 if terminada else valor,
        "escada": escada,
        "degraus": degraus,
        "custo_pista": (None if terminada or vistas >= total_pistas
                        else valor - _valor_ronda(jogo, vistas + 1)),
        "opcoes": opcoes,
        "custo_opcoes": None if terminada or jogo["opcoes"] else valor - math.ceil(valor / 2),
        "tentativas": jogo["tentativas"],
        "terminada": terminada,
        "ultima": jogo["ronda"] == len(jogo["lideres"]) - 1,
        "revelacao": None,
    }
    if terminada:
        ultimo = jogo["resultados"][-1]
        estado["revelacao"] = {
            "nome": lider["nome"], "pais": lider["pais"], "cargo": lider["cargo"], "epoca": lider["epoca"],
            "imagem": _imagem(lider), "iniciais": _iniciais(lider["nome"]),
            "certa": ultimo["certa"], "pontos": ultimo["pontos"],
        }
    return estado


def _ronda_em_jogo(jogo):
    """Devolve o líder da ronda atual ou dá erro se não houver ronda a decorrer."""
    if jogo["ronda"] >= len(jogo["lideres"]):
        raise ErroLideres("O jogo já terminou.", 409)
    if jogo["fim_ronda"] is not None:
        raise ErroLideres("Esta ronda já terminou: passa à seguinte.", 409)
    return LIDERES_POR_ID[jogo["lideres"][jogo["ronda"]]]


def _terminar_ronda(jogo, certa):
    pontos = _valor_ronda(jogo) if certa else 0
    jogo["fim_ronda"] = "certa" if certa else "falhada"
    jogo["pontos"] += pontos
    jogo["resultados"].append({"id": jogo["lideres"][jogo["ronda"]], "certa": certa, "pontos": pontos,
                               "pistas": jogo["pistas_vistas"], "opcoes": bool(jogo["opcoes"])})


def pedir_pista(jogo):
    """Desbloqueia a pista seguinte (a ronda passa a valer menos)."""
    with _jogos_cadeado:
        lider = _ronda_em_jogo(jogo)
        if jogo["pistas_vistas"] >= len(lider["pistas"]):
            raise ErroLideres("Já viste todas as pistas desta ronda.", 409)
        jogo["pistas_vistas"] += 1
        jogo["evento"] = {"tipo": "pista"}
        jogo["atualizado"] = time.time()
    return estado_lideres(jogo)


def mostrar_opcoes(jogo):
    """Ajuda: mostra 4 nomes à escolha (a partir daí, a ronda vale metade)."""
    with _jogos_cadeado:
        lider = _ronda_em_jogo(jogo)
        if not jogo["opcoes"]:
            jogo["opcoes"] = _opcoes_para(lider)
        jogo["evento"] = {"tipo": "opcoes"}
        jogo["atualizado"] = time.time()
    return estado_lideres(jogo)


def responder_lider(jogo, palpite):
    """Valida o palpite. Certo → pontos conforme as pistas vistas; errado → nova pista
    (ou fim da ronda, se já não houver mais); quase → aviso, sem penalização."""
    with _jogos_cadeado:
        lider = _ronda_em_jogo(jogo)
        avaliacao = avaliar_palpite(palpite, lider)
        evento = avaliacao
        if avaliacao == "certo":
            _terminar_ronda(jogo, True)
        elif avaliacao == "errado":
            jogo["tentativas"].append(palpite)
            if jogo["pistas_vistas"] < len(lider["pistas"]):
                jogo["pistas_vistas"] += 1
                evento = "errado_nova_pista"
            else:
                _terminar_ronda(jogo, False)
                evento = "errado_fim"
        jogo["evento"] = {"tipo": evento, "palpite": palpite}
        jogo["atualizado"] = time.time()
    return estado_lideres(jogo)


def desistir_ronda(jogo):
    """Revela o líder da ronda atual, sem pontos."""
    with _jogos_cadeado:
        _ronda_em_jogo(jogo)
        _terminar_ronda(jogo, False)
        jogo["evento"] = {"tipo": "desistiu"}
        jogo["atualizado"] = time.time()
    return estado_lideres(jogo)


def ronda_seguinte(jogo):
    """Passa à ronda seguinte (ou ao resultado final)."""
    with _jogos_cadeado:
        if jogo["ronda"] >= len(jogo["lideres"]):
            raise ErroLideres("O jogo já terminou.", 409)
        if jogo["fim_ronda"] is None:
            raise ErroLideres("Termina esta ronda antes de avançar.", 409)
        jogo.update(ronda=jogo["ronda"] + 1, pistas_vistas=1, tentativas=[], opcoes=None, fim_ronda=None,
                    evento=None, atualizado=time.time())
    return estado_lideres(jogo)


def resultado_lideres(jogo):
    """Pontuação final, classificação e resumo de cada ronda."""
    resumo = _resumo_lideres(jogo)
    percentagem = round(jogo["pontos"] / resumo["maximo"] * 100)
    titulo, mensagem = next((t, m) for minimo, t, m in LIDERES_CLASSIFICACOES if percentagem >= minimo)
    rondas = []
    for numero, resultado in enumerate(jogo["resultados"], start=1):
        lider = LIDERES_POR_ID[resultado["id"]]
        rondas.append({"ronda": numero, "nome": lider["nome"], "pais": lider["pais"],
                       "dificuldade_nome": LIDERES_DIFICULDADES[lider["dificuldade"]],
                       "iniciais": _iniciais(lider["nome"]), "imagem": _imagem(lider),
                       "certa": resultado["certa"], "pontos": resultado["pontos"],
                       "pistas": resultado["pistas"], "opcoes": resultado["opcoes"]})
    return {**resumo, "tipo": "resultado", "percentagem": percentagem, "titulo": titulo,
            "mensagem": mensagem, "rondas": rondas}


# Mensagem mostrada por baixo do palpite depois de cada jogada: (tipo, texto).
# O tipo escolhe a cor: certo (verde), errado (vermelho), quase (amarelo) ou info.
_MENSAGENS_LIDERES = {
    "certo": ("certo", "Certo! Ganhaste {ganhos} pontos."),
    "quase": ("quase", "Quase! «{palpite}» está muito perto: verifica a ortografia. Não perdeste pontos."),
    "errado_nova_pista": ("errado", "«{palpite}» não é a resposta certa. Desbloqueaste uma nova pista."),
    "errado_fim": ("errado", "«{palpite}» também não é. Já não há mais pistas nesta ronda."),
    "pista": ("info", "Nova pista desbloqueada. A ronda vale agora {valor} pontos."),
    "opcoes": ("info", "Escolhe uma das 4 opções (ou escreve o nome). A ronda vale agora {valor} pontos."),
    "desistiu": ("info", "Ronda terminada sem pontos."),
}


def mensagem_lideres(evento, estado):
    """Texto da última jogada, por exemplo ("errado", "«Gandhi» não é a resposta certa…")."""
    if not evento or not estado or estado["tipo"] != "ronda" or evento["tipo"] not in _MENSAGENS_LIDERES:
        return None
    tipo, texto = _MENSAGENS_LIDERES[evento["tipo"]]
    ganhos = estado["revelacao"]["pontos"] if estado["revelacao"] else 0
    return tipo, texto.format(palpite=evento.get("palpite", ""), ganhos=ganhos, valor=estado["pontos_ronda"])


# ---------------------------------------------------------------------------
# 6.6 Página do jogo (só HTML: cada botão é um formulário)
# ---------------------------------------------------------------------------
# Funciona como o quiz: cada botão envia um formulário (POST), o Python faz a
# jogada e redireciona para /lideres, que mostra o resultado (POST → redirect → GET).
#   GET  /lideres              → ecrã inicial, ronda atual ou resultado final
#   POST /lideres/novo         → dificuldade = "misto", 1, 2 ou 3 → começa um jogo
#   POST /lideres/responder    → resposta = nome escrito ou escolhido nas 4 opções
#   POST /lideres/pista        → desbloqueia a pista seguinte
#   POST /lideres/opcoes       → mostra 4 nomes à escolha (a ronda passa a valer metade)
#   POST /lideres/desistir     → revela o líder (0 pontos)
#   POST /lideres/seguinte     → ronda seguinte ou resultado final
#   POST /lideres/sair         → abandona o jogo e volta ao ecrã inicial
def _descricao_misto():
    """Ex.: [1, 1, 1, 2, 2] → "3 fáceis e 2 médios"."""
    nomes = {1: ("fácil", "fáceis"), 2: ("médio", "médios"), 3: ("difícil", "difíceis")}
    partes = [f"{LIDERES_MISTO.count(n)} {nomes[n][LIDERES_MISTO.count(n) > 1]}" for n in sorted(set(LIDERES_MISTO))]
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]


def _modos_lideres():
    modos = [{"valor": "misto", "nome": "Misto", "descricao": _descricao_misto()}]
    for nivel, nome in LIDERES_DIFICULDADES.items():
        total = sum(lider["dificuldade"] == nivel for lider in LIDERES)
        modos.append({"valor": nivel, "nome": nome, "descricao": f"{LIDERES_RONDAS} de {total} líderes"})
    return modos


@app.route("/lideres")
def lideres():
    """Mostra o ecrã certo para o jogo guardado no cookie de sessão."""
    estado = evento = None
    jogo_id = session.get("lideres_jogo")
    if jogo_id:
        jogo = obter_jogo_lideres(jogo_id)
        with _jogos_cadeado:
            evento, jogo["evento"] = jogo["evento"], None   # cada jogada só é anunciada uma vez
        estado = estado_lideres(jogo)
    return render_template(
        "lideres.html",
        estado=estado,
        evento=evento,
        mensagem=mensagem_lideres(evento, estado),
        modos=_modos_lideres(),
        pontos_por_pista=LIDERES_PONTOS_POR_PISTA,
        rondas=LIDERES_RONDAS,
        # Sugestões que aparecem ao escrever o palpite (ajudam na ortografia).
        nomes=sorted((lider["nome"] for lider in LIDERES), key=normalizar_nome),
    )


def _jogada_lideres(acao, *argumentos):
    """Faz uma jogada no jogo da sessão e volta à página do jogo.
    Cada formulário leva o n.º do passo em que foi mostrado: se já não for o passo
    atual (duplo clique ou formulário antigo), o envio é ignorado e não conta duas vezes."""
    jogo = obter_jogo_lideres(session.get("lideres_jogo"))
    with _jogos_cadeado:
        if request.form.get("passo", type=int) == jogo["passo"]:
            acao(jogo, *argumentos)
            jogo["passo"] += 1
    return redirect(url_for("lideres"))


@app.post("/lideres/novo")
def lideres_novo():
    modo = request.form.get("dificuldade", "misto")
    if modo != "misto":
        modo = int(modo) if modo.isdigit() else None
        if modo not in LIDERES_DIFICULDADES:
            raise ErroLideres("Escolhe uma dificuldade: Misto, Fácil, Médio ou Difícil.")
    session["lideres_jogo"] = criar_jogo_lideres(modo)["id"]
    return redirect(url_for("lideres"))


@app.post("/lideres/responder")
def lideres_responder():
    palpite = request.form.get("resposta", "").strip()
    if not palpite:
        raise ErroLideres("Escreve o nome de um líder antes de submeter (ou usa «Ver 4 opções»).")
    if len(palpite) > 80:
        raise ErroLideres("O palpite é demasiado longo (máximo de 80 caracteres).")
    return _jogada_lideres(responder_lider, palpite)


@app.post("/lideres/pista")
def lideres_pista():
    return _jogada_lideres(pedir_pista)


@app.post("/lideres/opcoes")
def lideres_opcoes():
    return _jogada_lideres(mostrar_opcoes)


@app.post("/lideres/desistir")
def lideres_desistir():
    return _jogada_lideres(desistir_ronda)


@app.post("/lideres/seguinte")
def lideres_seguinte():
    return _jogada_lideres(ronda_seguinte)


@app.post("/lideres/sair")
def lideres_sair():
    jogo_id = session.pop("lideres_jogo", None)
    with _jogos_cadeado:
        _jogos_lideres.pop(jogo_id, None)
    return redirect(url_for("lideres"))


if __name__ == "__main__":
    # A porta 5000 está ocupada no macOS pelo AirPlay, por isso usamos a 5050.
    porta = int(os.environ.get("PORT", 5050))
    app.run(host="127.0.0.1", port=porta, debug=True)
