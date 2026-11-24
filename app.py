# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 0. Paleta de cores SP-ÁGUAS
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ---------------------------------------------------------
# |      RGB       |     HEX     | Nome aproximado da cor |
# ---------------------------------------------------------
# | R0 G182 B95    | **#00B65F** | Verde esmeralda        |
# | R0 G62 B196    | **#003EC4** | Azul escuro            |
# | R1 G82 B255    | **#0152FF** | Azul intenso           |
# | R88 G141 B255  | **#588DFF** | Azul claro             |
# | R68 G114 B196  | **#4472C4** | Azul aço               |
# | R0 G117 B255   | **#0075FF** | Azul vibrante          |
# | R149 G183 B255 | **#95B7FF** | Azul pervinca          |
# | R0 G0 B0       | **#000000** | Preto                  |
# ---------------------------------------------------------

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  1. Bibliotecas
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import calendar
import datetime
import os
import re
from pathlib import Path

import pandas as pd     # Tabelas da memória de cálculo
import streamlit as st  # Aplicação web

from motor_calculo import (
    BACIAS, BASES_LOTE, DIAS_ANO, LINK_DEC_10755, LINK_DEC_50667, LINK_LEI_12183, LINK_SPAGUAS_LEGISLACAO, MESES,
    FORMATO_DECIMAL, FORMATO_HHMM, REMOCAO_PADRAO_EMISSAO, TETO_PUF_CAP, fmt_horas, ler_horas, TEXTO_X2_SUBTERRANEA, atende_padrao_dbo, UFESP, UFESP_ANO, UFESP_POR_ANO, calcular, x2_nao_se_aplica, cenarios_disponiveis, dias_por_ano, fmt_brl, fmt_coef,
    fmt_num, ler_numero_br, linkar, lote_mensal, modos_transicao, regra_bacia, volumes_mineracao,
    CAMADAS_RURAIS, CENARIO_RURAL_PADRAO, CENARIOS_RURAIS, COEFICIENTES_BACIA_RURAL, FINALIDADE_IRRIGACAO,
    FINALIDADES_RURAIS, ISENCAO_POR, MINUTA_RURAL, PREMISSAS_RURAIS, calcular_rural, equivalencias_m3_dia,
    origem_premissas, premissas_rurais, PARCELAMENTO_RURAL, parcelas_rurais, DIAS_DO_MES, volume_e_captacao_maxima,
    CARGA_AFLUENTE_SO_PUB, DBO_PRESUMIDA_MG_L, FONTE_DBO_PRESUMIDA,
)

PASTA = Path(__file__).parent
LOGO = PASTA / "SP-Águas---Colorido.png"
# Simulador do lote mensal do SisCob 2.0 (seção 7.1): desligado para o usuário geral; liga com SP_AGUAS_LOTE_SISCOB=1
MOSTRAR_LOTE_SISCOB = os.environ.get("SP_AGUAS_LOTE_SISCOB") == "1"
# Análise do modo rural (seção 5.3): chave "Comparar com a regra urbana da bacia", desligada até o usuário ligar. Para
# tirar a chave da tela, mude para False ou rode com SP_AGUAS_COMPARACAO_URBANA=0
MOSTRAR_COMPARACAO_URBANA = os.environ.get("SP_AGUAS_COMPARACAO_URBANA", "1") == "1"
# Edição só rural (fork para a apresentação na CT-COB): sem a escolha "Tipo de usuário", a tela fica sempre no modo rural,
# com a comparação urbana mantida. Liga quando a pasta do app tem o arquivo SOMENTE_RURAL.txt (o fork tem; a calculadora
# integrada não), para que este app.py seja o mesmo nas duas pastas. SP_AGUAS_SOMENTE_RURAL=1 ou 0 decide no lugar do arquivo.
SOMENTE_RURAL = os.environ.get("SP_AGUAS_SOMENTE_RURAL", "1" if (PASTA / "SOMENTE_RURAL.txt").exists() else "0") == "1"
# Parcelas do resultado rural (seção 7): em destaque, o valor anual em 8 parcelas mensais, de maio a dezembro, como num
# lote gerado por volta de maio; o total anual vem ao lado. Liga no modo rural da versão geral e na edição só rural
# (pedido de 24/11/2026); SP_AGUAS_PARCELAS_RURAIS=0 desliga.
MOSTRAR_PARCELAS_RURAIS = os.environ.get("SP_AGUAS_PARCELAS_RURAIS", "1") == "1"
# Texto alternativo do logotipo: o nome da instituição e a descrição da imagem, para quem não a vê.
LOGO_ALT = ("Logotipo da SP Águas, Agência de Águas do Estado de São Paulo: a sigla SP e a palavra Águas em letras "
            "pretas grandes; à direita da sigla, três faixas onduladas, em verde, azul-escuro e azul-claro, que lembram "
            "o movimento da água; embaixo, o nome Agência de Águas do Estado de São Paulo.")


def md(texto):
    """
    Prepara um texto para Markdown: liga as citações de leis e decretos ao texto oficial (ALESP) e escapa
    o cifrão de "R$" (dois "$" na mesma linha viram fórmula LaTeX). Só escapa o "R$" da moeda: o "$" que fecha
    uma fórmula logo depois de uma letra R (ex.: "0{,}16\\,PR$") é mantido.
    """
    return re.sub(r"(?<![A-Za-z0-9\\])R\$", r"R\\$", linkar(texto))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  2. Nome da página e Configurações Gerais
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title=f"Simulador SP Águas: cobrança pelo uso{' rural' if SOMENTE_RURAL else ''} da água",
    page_icon="💧",
    layout="wide",
)

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 3. ESTADO DA SESSÃO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Cada captação/lançamento é um cartão identificado por um número. Toda nova sessão começa com um
# cartão vazio de cada tipo: nenhum valor vem pré-preenchido.
st.session_state.setdefault("proximo_id", 1)


def _novo_id():
    rid = st.session_state["proximo_id"]
    st.session_state["proximo_id"] = rid + 1
    return rid


def _lista(tipo, slug):
    chave = f"linhas_{tipo}_{slug}"
    if chave not in st.session_state:
        # Mineração é um item opcional: começa sem cartão
        st.session_state[chave] = [] if tipo == "min" else [_novo_id()]
    return st.session_state[chave]


def _prefixo(tipo, slug, rid):
    return f"{tipo}_{slug}_{rid}_"


def _limpar_campos(tipo, slug, rid):
    prefixo = _prefixo(tipo, slug, rid)
    # O nome dado ao cartão fica: "Limpar" apaga os valores, não a identificação do cartão
    for chave in [k for k in st.session_state if str(k).startswith(prefixo) and k != prefixo + "nome"]:
        del st.session_state[chave]


def _remover_linha(tipo, slug, rid):
    _limpar_campos(tipo, slug, rid)
    st.session_state.pop(_prefixo(tipo, slug, rid) + "nome", None)
    st.session_state[f"linhas_{tipo}_{slug}"].remove(rid)


def _adicionar_linha(tipo, slug):
    st.session_state[f"linhas_{tipo}_{slug}"].append(_novo_id())


def _nova_simulacao():
    """
    Apaga os dados preenchidos e volta aos cartões vazios, na mesma bacia. Ficam só a bacia escolhida e o contador
    de cartões: apagar a bacia deixava o menu mostrando a bacia antiga com o app sem bacia, sem nenhum campo aberto, e
    escolher a mesma bacia de novo não mudava nada. O contador segue adiante para que os cartões novos ganhem chaves
    novas, que o navegador mostra vazias.
    """
    for chave in list(st.session_state.keys()):
        if chave not in ("bacia", "proximo_id"):
            del st.session_state[chave]


def _normalizar_numero(chave, casas):
    """Ao sair do campo, reescreve o número no padrão brasileiro (ex.: 1500.5 -> 1.500,50)."""
    try:
        valor = ler_numero_br(st.session_state.get(chave))
    except ValueError:
        return
    if valor is not None:
        st.session_state[chave] = fmt_num(valor, casas)


def _formato_horas(chave, chave_formato=None):
    """
    Formato do campo de horas: a chave "Hora decimal" ao lado do rótulo liga o decimal; desligada, hh:mm. A chave é a
    do próprio campo (chave + "_decimal") ou, na tabela da sazonalidade, uma só para os 12 meses (chave_formato).
    """
    return FORMATO_DECIMAL if st.session_state.get(chave_formato or chave + "_decimal") else FORMATO_HHMM


def _normalizar_horas(chave, chave_formato=None):
    """Ao sair do campo de horas, reescreve no formato escolhido (ex.: 7h30 -> 07:30; 7.5 -> 7,50)."""
    formato = _formato_horas(chave, chave_formato)
    try:
        valor = ler_horas(st.session_state.get(chave), formato)
    except ValueError:
        return
    if valor is not None and valor <= 24:
        st.session_state[chave] = fmt_horas(valor, formato)


def _converter_horas(chave, chave_formato=None):
    """Ao virar a chave de formato, converte o valor já digitado no campo (07:30 <-> 7,50)."""
    novo = _formato_horas(chave, chave_formato)
    antigo = FORMATO_DECIMAL if novo == FORMATO_HHMM else FORMATO_HHMM
    try:
        valor = ler_horas(st.session_state.get(chave), antigo)
    except ValueError:
        return   # texto inválido fica como está, com a mensagem de erro no cartão
    if valor is not None and valor <= 24:
        st.session_state[chave] = fmt_horas(valor, novo)


def _chave_mes(p, i, campo):
    """Chave de um campo da tabela da sazonalidade: mês i (0 = janeiro) do cartão de prefixo p."""
    return f"{p}m{i + 1:02d}_{campo}"


def _converter_horas_meses(p):
    """Ao virar a chave "Hora decimal" da tabela da sazonalidade, converte as horas já digitadas nos 12 meses."""
    for i in range(12):
        _converter_horas(_chave_mes(p, i, "horas"), p + "sazonal_decimal")


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 4. CABEÇALHO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Acessibilidade (A01): o Streamlit declara a página em inglês (lang="en"), e o leitor de tela lê o português com
# a voz e a pronúncia do inglês. Este script declara o português do Brasil e o mantém, caso o Streamlit volte a mudar.
st.html("""
<script>
(function () {
    const raiz = document.documentElement;
    const portugues = () => { if (raiz.lang !== "pt-BR") raiz.lang = "pt-BR"; };
    portugues();
    new MutationObserver(portugues).observe(raiz, { attributes: true, attributeFilter: ["lang"] });
})();
</script>
""", unsafe_allow_javascript=True)

# Em telas de celular, títulos menores e margens laterais mais estreitas
st.html("""
<style>
/* O botão "Fullscreen" do logotipo repetia a descrição inteira da imagem no leitor de tela e não tem uso aqui */
[data-testid="stElementContainer"]:has([data-testid="stImage"]) [data-testid="stElementToolbar"] { display: none; }
/* Resultado rural: os cartões dos preços percebidos por m³, abaixo da parcela e do total, com o valor menor */
.st-key-rural_precos [data-testid="stMetricValue"] { font-size: 1.6rem; }
@media (max-width: 640px) {
    h1 { font-size: 1.6rem !important; }
    h3 { font-size: 1.2rem !important; }
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
}
</style>
""")

with st.container(horizontal_alignment="center"):
    if LOGO.exists():
        st.image(str(LOGO), width=200, alt=LOGO_ALT)
    st.title(f"Simulador da cobrança pelo uso{' rural' if SOMENTE_RURAL else ''} da água", text_alignment="center")
    st.caption(
        md("[www.spaguas.sp.gov.br](https://www.spaguas.sp.gov.br) · Instrumento de gestão previsto na "
           "Lei Estadual nº 12.183/2005 e no Decreto nº 50.667/2006"),
        text_alignment="center",
    )

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 4.1. MENUS EXPLICATIVOS GERAIS
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
with st.container(horizontal=True, horizontal_alignment="center"):
    with st.popover("Como funciona a cobrança", icon=":material/menu_book:"):
        st.markdown(md("""
        #### Princípio da cobrança
        A cobrança pelo uso da água **não é imposto nem taxa**. É um **preço público** definido com a participação
        da sociedade nos Comitês de Bacias Hidrográficas (CBHs), e o dinheiro arrecadado é aplicado na própria bacia,
        por meio do FEHIDRO.

        #### Fórmula geral (valor anual)
        $$VT = VCC + VCCo + VCL$$

        - **Captação (VCC)** $= V_{CAP} \\times PUF_{CAP}$, com $PUF_{CAP} = PUB_{CAP} \\times X_1 \\times X_2 \\times \\dots \\times X_{13}$
        - **Consumo (VCCo)** $= FC \\times V_{CAP} \\times PUF_{CONS}$: parte da água captada que não volta ao rio
        - **Lançamento (VCL)** $= \\dfrac{DBO}{1.000} \\times V_{LANÇ} \\times PUF_{DBO}$, com $PUF_{DBO} = PUB_{DBO} \\times Y_1 \\times \\dots \\times Y_9$

        **Volume captado:** $V_{CAP} = K_{OUT} \\times V_{OUT} + K_{MED} \\times V_{MED}$
        - Sem medição: $K_{OUT} = 1$ e $K_{MED} = 0$ (paga-se sobre o volume outorgado).
        - Com medição: pesos definidos pelo decreto de cada bacia (em geral $K_{OUT} = 0{,}2$ e $K_{MED} = 0{,}8$,
          ou $0{,}3$ e $0{,}7$; algumas bacias usam só o volume medido ou só o outorgado).
        - Medição maior que a outorga: $K_{OUT} = 0$ e $K_{MED} = 1$ (o usuário deve pedir a retificação da outorga).

        **Fator de consumo:** $FC = \\dfrac{V_{CAPT} - V_{LANÇT}}{V_{CAPT}}$, entre 0 e 1.

        **Limites legais:** o PUF de captação não pode passar de 0,001078 UFESP/m³ (art. 10, § 2º, do
        Decreto nº 50.667/2006) e o valor do lançamento não pode passar de 3 vezes a soma de captação e consumo
        (art. 11). As regras gerais estão na Lei nº 12.183/2005.
        """))

    with st.popover("Período de uso e ano cheio", icon=":material/calendar_month:"):
        st.markdown(f"""
        #### Como preencher horas, dias e meses
        1. **Horas por dia (0 a 24):** tempo diário de bombeamento ou de lançamento previsto na outorga. Com a chave
           **"Hora decimal"** ao lado do campo desligada, digite em **hora e minuto** (`7:30`); ligada, em **hora
           decimal** (`7,5`, como em muitos pareceres técnicos). Ao virar a chave, o valor é convertido:
           7:30 = 7,5 h; 0,25 h = 15 min.
        2. **Dias por mês (1 a 31):** dias de uso em cada mês (ex.: 22 dias úteis, 30 dias contínuos).
        3. **Meses por ano (1 a 12):** meses de operação no ano (ex.: safra de 6 meses, uso o ano todo = 12).

        $$V_{{OUT}} = \\text{{vazão (m³/h)}} \\times \\text{{horas/dia}} \\times \\text{{dias de uso no ano}}$$

        #### Outorga de ano cheio (365 dias)
        - Marque **"Outorga de ano cheio"** para usar diretamente **{DIAS_ANO} dias**. Os campos de dias e meses
          ficam bloqueados.
        - Se preferir digitar, **30 ou 31 dias por mês** valem como **mês completo** ({fmt_num(DIAS_ANO / 12)} dias).
          Assim, **30 dias × 12 meses = {DIAS_ANO} dias**, e não 360.
        - Com menos de 30 dias por mês, o cálculo é dias × meses (ex.: 22 dias × 12 meses = 264 dias).

        #### Sazonalidade (modo rural)
        - Quando a outorga muda ao longo do ano (mais água na safra, nada na entressafra), ligue a chave
          **Sazonalidade**, ao lado da finalidade rural da captação. Ela abre os 12 meses: em cada mês com uso,
          informe a vazão, as horas por dia e os dias de uso; deixe em branco os meses sem captação.
        - O volume do ano é a soma dos meses. A captação máxima em m³/dia, que decide a isenção, é a do mês de maior
          vazão × horas.
        """)

    with st.popover("Números no padrão brasileiro", icon=":material/pin:"):
        st.markdown("""
        #### Como digitar números
        - Use **vírgula** para separar os decimais e **ponto** para o milhar: `1.500,75`.
        - Também é aceito sem o ponto de milhar: `1500,75`.
        - Depois de digitar, o campo é reescrito no padrão brasileiro e, logo abaixo, aparece o volume calculado
          para você conferir a ordem de grandeza.
        - Para apagar um valor, basta limpar o campo. Para apagar todo um cartão, use **Limpar campos**; para
          tirá-lo da simulação, use **Remover**.
        """)

    st.button("Nova simulação", icon=":material/restart_alt:", on_click=_nova_simulacao,
              help="Apaga todos os dados preenchidos e volta aos cartões vazios, na bacia já escolhida.")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 5. Seleção das bacias hidrográficas e tipo de cobrança
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
with st.container(horizontal=True, vertical_alignment="bottom"):
    if SOMENTE_RURAL:
        cobranca_selecionada = "Rural"   # edição só rural: sem a escolha do tipo de usuário
    else:
        cobranca_selecionada = st.segmented_control(
            "Tipo de usuário", ["Urbano/Industrial", "Rural"], default="Urbano/Industrial", required=True,
        )
    bacia_selecionada = st.selectbox(
        "Bacia hidrográfica", list(BACIAS), index=None, key="bacia", placeholder="Selecione a bacia hidrográfica",
        format_func=lambda b: f"{b} (UGRHI {BACIAS[b]['ugrhi'].replace('-', ' e ')})",
    )
# Acessibilidade (A13/A11): a explicação fica em texto visível, que o leitor de tela lê ao navegar, e não num botão
# de ajuda "Help for…", que dobrava as paradas de Tab e não tinha o texto lido ao ser ativado.
if SOMENTE_RURAL:
    st.caption("Este simulador aplica a minuta do decreto da cobrança rural, em discussão no Conselho Estadual de Recursos "
               "Hídricos, com as premissas do estudo da SP Águas: não é cobrança vigente. Hoje, a cobrança regulamentada "
               "no Estado alcança só os usuários urbanos e industriais. Há 21 bacias (22 UGRHIs); a ficha de cada uma "
               "mostra o que vem do decreto dela.")
else:
    st.caption("A cobrança regulamentada no Estado de São Paulo alcança os usuários urbanos e industriais. O modo rural "
               "simula a minuta do decreto da cobrança rural, em discussão no Conselho Estadual de Recursos Hídricos, com "
               "as premissas do estudo da SP Águas: não é cobrança vigente. Há 21 bacias (22 UGRHIs), cada uma com as "
               "regras do seu decreto.")

if bacia_selecionada is None:
    if SOMENTE_RURAL:
        st.info("Escolha a bacia hidrográfica onde fica o empreendimento rural. Os preços e os coeficientes seguem as "
                "premissas do estudo da SP Águas, iguais em todas as bacias; do decreto da bacia vêm o PUB da DBO e os "
                "pesos do volume medido.", icon=":material/water:", title="Selecione a bacia")
    else:
        st.info(md("Escolha a bacia hidrográfica onde fica o empreendimento. Os campos e os coeficientes seguem o decreto "
                   "de cobrança de cada bacia, aprovado nos termos da Lei nº 12.183/2005 e do Decreto nº 50.667/2006."),
                icon=":material/water:", title="Selecione a bacia")
    st.stop()

slug = BACIAS[bacia_selecionada]["ugrhi"]
rural = cobranca_selecionada == "Rural"

# Cenário: "vigente" (decreto em vigor) ou "proposta" (revisão aprovada pelo comitê, sem decreto ainda).
# Os widgets que escolhem o cenário ficam na ficha da bacia; aqui lemos o valor da última interação.
# A revisão proposta é do decreto urbano: no modo rural ela não entra.
tem_proposta = "proposta" in cenarios_disponiveis(bacia_selecionada) and not rural
simular_proposta = tem_proposta and st.session_state.get(f"simular_proposta_{slug}", False)
ano_aplicacao = st.session_state.get(f"ano_aplicacao_{slug}") if simular_proposta else None
cenario = "proposta" if simular_proposta else "vigente"
modo_transicao = ("direto" if st.session_state.get(f"transicao_direta_{slug}") else "diferenca") \
    if simular_proposta else None
regra = regra_bacia(bacia_selecionada, cenario, ano_aplicacao, modo_transicao=modo_transicao)
regra_atual = regra_bacia(bacia_selecionada, "vigente")

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 5.1. FICHA DA BACIA E GUIA DE PREENCHIMENTO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
TODOS_X = {
    "X1": "natureza do corpo d'água", "X2": "classe do corpo d'água", "X3": "disponibilidade hídrica local",
    "X5": "volume captado e regime de variação (medição)", "X7": "finalidade do uso", "X13": "transposição de bacia",
}
TODOS_Y = {"Y1": "classe do corpo receptor", "Y3": "eficiência de remoção de DBO", "Y4": "natureza da atividade"}


def _faixas_y3(valores):
    rotulos = ["> 95%", "> 90 a 95%", "> 85 a 90%", "> 80 a 85%", "até 80%"]
    return "; ".join(f"{r} = {fmt_coef(v)}" for r, v in zip(rotulos, valores))


def guia_da_bacia(regra):
    """Texto do guia: explica cada campo da bacia, os coeficientes fixos e as regras especiais do decreto."""
    decreto = f"[{regra['decreto_extenso']}]({regra['link_norma']})"
    linhas = [f"#### Guia de preenchimento: {bacia_selecionada} (UGRHI {regra['ugrhi'].replace('-', ' e ')})",
              f"Base legal: **{decreto}**, nos termos da Lei nº 12.183/2005 e do Decreto nº 50.667/2006. "
              f"{regra['progressividade']}", "", "##### Captação: campos desta bacia"]
    usados_x = set(regra["fixos_cap"])
    for campo in regra["campos_cap"].values():
        usados_x.add(campo["coef"])
        linhas.append(f"- **{campo['rotulo']}:** {campo['ajuda']}")
    for coef, valor in regra["fixos_cap"].items():
        linhas.append(f"- **{coef} fixo em {fmt_coef(valor)}** para qualquer captação.")
    if any(campo["coef"] == "X2" for campo in regra["campos_cap"].values()):
        linhas.append(f"- **Captação subterrânea (poço):** {TEXTO_X2_SUBTERRANEA} Por isso, ao escolher "
                      "\"Subterrâneo\", o campo de classe fica travado.")
    x5 = regra["x5"]
    if x5:
        usados_x.add("X5")
        if x5["modo"] == "formula":
            linhas.append("- **X5 (medição):** calculado automaticamente. Se o volume medido for menor que 70% do "
                          "outorgado, $X_5 = 1 + \\dfrac{0{,}7\\,V_{OUT} - V_{MED}}{0{,}2\\,V_{OUT} + 0{,}8\\,V_{MED}}$; "
                          "caso contrário, $X_5 = 1{,}00$. Isso penaliza quem pede outorga muito acima do que usa.")
        elif x5["modo"] == "degraus":
            linhas.append("- **X5 (medição):** pela relação entre volume medido e outorgado: ≥ 70% = 1,00; 60 a 70% = "
                          "1,20; 50 a 60% = 1,40; abaixo de 50% = 1,80. Sem medição, 1,00.")
        else:
            linhas.append(f"- **X5 (medição):** sem medição = {fmt_coef(x5['sem'])}; com medição = "
                          f"{fmt_coef(x5['com'])}. Preencha o volume medido para aplicar o valor com medição.")
    fixos = [f"{c} ({TODOS_X[c]})" for c in TODOS_X if c not in usados_x]
    if fixos:
        linhas.append(f"- **Fixos em 1,00 nesta bacia:** {', '.join(fixos)}.")
    k = regra["kout_kmed"]
    if k == "medido":
        texto_k = "com medição, conta só o volume medido (KMED = 1)"
    elif k == "outorga":
        texto_k = "conta sempre o volume da outorga; o medido não altera o valor"
    else:
        texto_k = f"com medição, KOUT = {fmt_num(k[0], 1)} e KMED = {fmt_num(k[1], 1)}"
    linhas.append(f"- **Volume cobrado:** sem medição, o volume outorgado; {texto_k}. Se o medido passar do "
                  "outorgado, conta o medido e a outorga deve ser retificada.")
    linhas += ["", "##### Consumo"]
    if regra["consumo_coefs"]:
        for chave, mapa in regra["consumo_coefs"].items():
            campo = regra["campos_cap"][chave]
            valores = "; ".join(f"{o} = {fmt_coef(v)}" for o, v in mapa.items())
            linhas.append(f"- **{campo['coef']} no consumo:** {valores}. Os demais coeficientes valem 1,00.")
    else:
        linhas.append("- Todos os coeficientes de consumo valem 1,00: o preço é o próprio PUB de consumo.")
    for opcao in regra["consumo_integral_opcoes"]:
        linhas.append(f"- **{opcao}:** o consumo é igual a 100% do volume captado.")
    linhas += ["", "##### Lançamento: campos desta bacia"]
    usados_y = {"Y3"}
    for campo in regra["campos_lanc"].values():
        usados_y.add(campo["coef"])
        linhas.append(f"- **{campo['rotulo']}:** {campo['ajuda']}")
    if regra["y3_modo"] == "formula":
        linhas.append("- **Y3 (remoção de DBO, PR):** informe o percentual de remoção da ETE. PR ≤ 80%: Y3 = 1,00; "
                      "entre 80% e 95%: $Y_3 = (31 - 0{,}2\\,PR)/15$; a partir de 95%: $Y_3 = 16 - 0{,}16\\,PR$ "
                      "(ex.: 97% → 0,48; 100% → 0,00).")
    elif regra["y3_modo"] == "litoral_norte":
        linhas.append("- **Y3 (DBO e remoção):** com DBO do efluente até 60 mg/L, $Y_3 = 0{,}4 + 0{,}01 \\times DBO$; "
                      "acima de 60 mg/L e com remoção de pelo menos 80%, $Y_3 = 1{,}8 - 0{,}01 \\times TR$ (taxa de "
                      "remoção em %).")
    else:
        linhas.append(f"- **Y3 (remoção de DBO, PR):** informe o percentual de remoção da ETE; o valor é enquadrado "
                      f"nas faixas do decreto: {_faixas_y3(regra['y3_valores'])}.")
    if regra["resfriamento"] == "pr100":
        linhas.append("- **Resfriamento em circuito aberto**, sem acréscimo de DBO: conta como 100% de remoção.")
    elif regra["resfriamento"] == "sem_carga":
        linhas.append("- **Resfriamento em circuito aberto**, sem acréscimo de DBO: Y3 = 1,00 e carga de DBO igual a "
                      "zero; o lançamento não é cobrado.")
    fixos = [f"{c} ({TODOS_Y[c]})" for c in TODOS_Y if c not in usados_y]
    if fixos:
        linhas.append(f"- **Fixos em 1,00 nesta bacia:** {', '.join(fixos)}.")
    if regra["carga_afluente"]:
        valor = ("o valor é a carga × PUB, **sem os coeficientes Y**, como no requisito do SisCob 2.0 (o texto do "
                 "decreto multiplica a carga pelo PUF, PUB × Y)" if CARGA_AFLUENTE_SO_PUB
                 else "o valor é a carga × PUF (PUB × coeficientes Y), como no texto do decreto")
        linhas += [
            "- **Concentração remanescente de DBO (mg/L):** concentração média anual de DBO5,20 depois do tratamento. "
            "Sem a DBO do afluente, a carga é concentração ÷ 1.000 × volume lançado (kg/ano), cobrada pelo PUF da DBO "
            "(PUB × Y).",
            "- **Fator de eficiência de remoção, FER (%):** percentual de remoção de DBO da ETE. É sempre obrigatório: "
            "define o Y3 e, com a DBO do afluente, entra na fórmula da carga.",
            "- **DBO do afluente, Cc (mg/L), e fator de tratamento, FTR (%):** opcionais. Com a DBO do afluente "
            "(antes do tratamento), o FTR passa a ser obrigatório e a carga passa a "
            "VCL = volume lançado × Cc ÷ 1.000 × (1 − FTR × FER), em kg/ano, com prioridade sobre a "
            f"concentração remanescente; {valor}. Valores iguais a zero são aceitos: Cc = 0 zera a carga, e FTR = 0 "
            "ou FER = 0 cobram a carga sem desconto de tratamento.",
        ]
    else:
        linhas.append("- **DBO (mg/L):** concentração média anual de DBO5,20 no efluente final. A carga é "
                      "DBO ÷ 1.000 × volume lançado (kg/ano).")
    if DBO_PRESUMIDA_MG_L is not None:
        como = ("como DBO do afluente, sem tratamento (FTR = FER = 0)" if regra["carga_afluente"]
                else "com remoção de 0% (Y3 = 1,00)")
        linhas.append(f"- **DBO não declarada:** sem DBO no cartão (e fora do resfriamento), a simulação adota "
                      f"{fmt_num(DBO_PRESUMIDA_MG_L, 0)} mg/L, {como}, como manda a {FONTE_DBO_PRESUMIDA} para quem "
                      "não informa a DBO. O efluente fica fora do padrão de emissão, e o teto do lançamento não se "
                      "aplica.")
    linhas += ["", "##### Outras regras",
               f"- **Valor mínimo:** {regra['valor_minimo_texto']}",
               f"- **Uso insignificante:** {regra['insignificante_texto']}",
               "- **Volume medido:** informe apenas se houver hidrômetro aceito pelo órgão outorgante; senão, "
               "deixe em branco."]
    if regra["mineracao"]:
        linhas.append(f"- **Mineração de areia (item à parte):** {texto_mineracao(regra)}")
    for nota in regra["notas"]:
        linhas.append(f"- **Observação:** {nota}")
    return md("\n".join(linhas))


def texto_mineracao(regra):
    """Regra de mineração de areia do decreto da bacia, em linguagem simples."""
    modo = regra["mineracao"]
    if modo == "areia":
        r = (f"R = {fmt_num(regra['mineracao_r'], 0)} (cada m³ de areia corresponde a "
             f"{fmt_num(regra['mineracao_r'], 0)} m³ de água captada)" if regra["mineracao_r"] is not None
             else "R é a razão de mistura água/areia da polpa dragada, informada pelo usuário")
        u = (f", com mínimo de {fmt_num(regra['mineracao_u_min'] * 100, 0)}%" if regra["mineracao_u_min"] else "")
        return (f"captação = volume anual de areia × R e consumo = volume de areia × U, a umidade da areia{u}. "
                f"{r}. Não há cobrança de carga lançada.")
    return {
        "minimo_5": "captação pelo volume outorgado (e medido); consumo efetivo declarado, com mínimo de 5% do volume "
                    "outorgado. A carga lançada não é considerada.",
        "fixo_5": "captação pelo volume outorgado (e medido) e consumo de 5% do volume outorgado, sem carga lançada.",
        "consumo_total": "captação pela vazão máxima de bombeamento da draga e consumo igual ao volume captado.",
    }[modo]


def fontes_oficiais(regra):
    """Links para os textos oficiais usados no cálculo desta bacia."""
    itens = [
        f"- [{regra['decreto_extenso']}]({regra['link_norma']}): PUBs e coeficientes da bacia",
        f"- [Lei Estadual nº 12.183/2005]({LINK_LEI_12183}): lei da cobrança pelo uso da água",
        f"- [Decreto nº 50.667/2006]({LINK_DEC_50667}): fórmulas gerais, pesos KOUT/KMED e tetos",
        f"- [Decreto Estadual nº 10.755/1977]({LINK_DEC_10755}): enquadramento (classes) dos corpos d'água",
        f"- [Legislação de recursos hídricos na SP Águas]({LINK_SPAGUAS_LEGISLACAO})",
    ]
    return "\n".join(itens)


# Modo rural: a ficha da bacia, o guia e as fontes falam da minuta do decreto rural, e não do decreto urbano.
ART = MINUTA_RURAL["artigos"]


def fmt_enxuto(valor, casas=2):
    """Número no padrão brasileiro sem zeros finais, para o limiar: 300 → "300"; 12,50 → "12,5"; 3,4722 → "3,47"."""
    texto = fmt_num(valor, casas)
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


def texto_limiar(m3_dia):
    """Limiar de isenção nas três unidades: m³/dia (a da minuta), m³/h em 24 horas e L/s."""
    e = equivalencias_m3_dia(m3_dia)
    return (f"{fmt_enxuto(e['m3_dia'])} m³/dia, ou {fmt_enxuto(e['m3_h'])} m³/h em 24 horas, ou "
            f"{fmt_enxuto(e['l_s'])} L/s")


def _texto_kout_kmed(k):
    """Pesos KOUT/KMED do decreto urbano da bacia, em texto."""
    if k == "medido":
        return "com medição, conta só o volume medido"
    if k == "outorga":
        return "conta sempre o volume da outorga"
    return f"KOUT = {fmt_num(k[0], 1)} e KMED = {fmt_num(k[1], 1)}"


def texto_bacia_rural(regra):
    """O que a bacia muda na simulação rural."""
    return md(
        f"**Na simulação rural, os preços e os coeficientes vêm do cenário rural (premissas abaixo), iguais em todas as "
        f"bacias**, porque o estudo da SP Águas usa premissas estaduais. Do {regra['decreto']} vêm só o PUB da DBO "
        f"({fmt_brl(regra['pub_dbo'], 3)}/kg), os pesos com medição ({_texto_kout_kmed(regra['kout_kmed'])}) e, se "
        "você escolher coeficientes herdados, os coeficientes da bacia. Pela minuta, cada comitê vai propor os seus "
        f"PUBs e coeficientes ({MINUTA_RURAL['nome'].lower()}, art. 10, § 1º, e art. 12, § 2º)."
    )


def guia_rural():
    """Guia da simulação rural: fórmulas, fator de consumo, isenções, tetos e a origem de cada número."""
    teto_cap = MINUTA_RURAL["teto_puf_cap_ufesp"] * UFESP
    teto_cons = MINUTA_RURAL["teto_puf_cons_ufesp"] * UFESP
    limiar = equivalencias_m3_dia(MINUTA_RURAL["limiar_isencao_m3_dia"])
    estudo = CENARIOS_RURAIS[CENARIO_RURAL_PADRAO]["premissas"]
    camadas = "\n".join(f"- **{nome}:** {texto}." for nome, texto in CAMADAS_RURAIS.items())
    return md(
        "#### Guia da simulação rural\n"
        f"Base: {MINUTA_RURAL['nome'].lower()}, {MINUTA_RURAL['versao']} (quadro comparativo a partir da "
        f"{MINUTA_RURAL['base']}), em discussão na Câmara Técnica de Cobrança (CT-COB) do Conselho Estadual de "
        "Recursos Hídricos, com as premissas do estudo da SP Águas apresentado à CT-COB em 07/10/2026. "
        "**Não é cobrança vigente.**\n\n"
        "##### Fórmula (Anexo da minuta)\n"
        "$$VT = VCC + VCCo + VCL$$\n\n"
        "- **Captação:** $VCC = V_{CAP} \\times PUF_{CAP}$, com $PUF_{CAP} = PUB_{CAP} \\times X_1 \\times \\dots "
        "\\times X_{13}$\n"
        "- **Consumo:** $VCCo = FC \\times V_{CAP} \\times PUF_{CONS}$, com $PUF_{CONS} = PUB_{CONS} \\times X_1 "
        "\\times \\dots \\times X_{13}$\n"
        "- **Lançamento:** $VCL = \\dfrac{DBO}{1.000} \\times V_{LANÇ} \\times PUF_{DBO}$, com $PUF_{DBO} = "
        "PUB_{DBO} \\times Y_1 \\times \\dots \\times Y_9$. Nos dois primeiros anos, só a DBO é cobrada.\n"
        "- **Volume captado:** sem medição, o volume outorgado ($K_{OUT} = 1$); com medição, pesos definidos pelo "
        "comitê (Anexo, item 3).\n\n"
        "##### Fator de consumo (FC)\n"
        f"- **Irrigação:** FC = {fmt_num(MINUTA_RURAL['fc_irrigacao'] * 100, 0)}% ({ART['fc_irrigacao']}), "
        "alterável pelo comitê mediante estudo técnico.\n"
        "- **Dessedentação animal, aquicultura e outros usos rurais:** $FC = \\dfrac{V_{CAPT} - V_{LANÇT}}"
        "{V_{CAPT}}$, com os volumes de todo o empreendimento (Anexo, item 4).\n\n"
        "##### Isenções (art. 5º)\n"
        f"- **Por porte:** captação máxima outorgada de até {fmt_num(limiar['m3_dia'], 0)} m³/dia, ou "
        f"{fmt_num(limiar['m3_h'], 1)} m³/h em 24 horas, ou {fmt_num(limiar['l_s'], 2)} L/s. O comitê pode mudar "
        "o limiar.\n"
        "- **Agricultura familiar** inscrita no Cadastro Nacional da Agricultura Familiar (CAF).\n"
        "- A minuta não diz se o limiar vale para a soma das captações do usuário ou para cada outorga. A simulação "
        "faz as duas contas, com a escolha **Como aplicar o limiar de isenção**.\n"
        "- Os usos urbanos ou industriais do mesmo empreendimento continuam cobrados pelo Decreto nº 50.667/2006 "
        "(art. 5º, parágrafo único). A simulação rural ainda não separa esses usos.\n\n"
        "##### Limites\n"
        f"- **PUF de captação:** até 0,001078 UFESP/m³, ou {fmt_brl(teto_cap, 4)}/m³ em {UFESP_ANO} "
        f"({ART['teto_puf_cap']}).\n"
        f"- **PUF de consumo:** até 0,002156 UFESP/m³, ou {fmt_brl(teto_cons, 4)}/m³ em {UFESP_ANO} "
        f"({ART['teto_puf_cons']}).\n"
        f"- **Lançamento:** até 3 vezes a captação mais o consumo, se todos os lançamentos atendem aos padrões "
        f"({ART['teto_lancamento']}).\n"
        "- A minuta não fixa valor mínimo de boleto nem parcelamento.\n\n"
        "##### De onde vem cada número\n"
        f"{camadas}\n\n"
        f"Com as premissas do estudo, cada m³ captado na irrigação custa "
        f"{fmt_brl(CENARIOS_RURAIS[CENARIO_RURAL_PADRAO]['preco_percebido'], 4)}: "
        f"{fmt_num(estudo['pub_cap'], 2)} × {fmt_num(estudo['x7'], 3)} na captação, mais "
        f"{fmt_num(estudo['pub_cons'], 2)} × {fmt_num(estudo['fc_irrigacao'], 2)} × {fmt_num(estudo['x7'], 3)} "
        "no consumo."
    )


def fontes_rurais(regra):
    """Fontes da simulação rural."""
    return md("\n".join([
        f"- {MINUTA_RURAL['nome']}, {MINUTA_RURAL['versao']}: quadro comparativo distribuído à CT-COB a partir da "
        f"{MINUTA_RURAL['base']} (documento de trabalho, ainda sem publicação oficial)",
        "- Apresentação da SP Águas à 154ª reunião da CT-COB, 07/10/2026: premissas do cenário (slide 12), "
        "sensibilidade ao limiar de isenção (slides 6 e 7) e perfil por finalidade (slide 15)",
        f"- [Lei Estadual nº 12.183/2005]({LINK_LEI_12183}): lei da cobrança pelo uso da água",
        f"- [Decreto nº 50.667/2006]({LINK_DEC_50667}): cobrança dos usos urbanos e industriais, que continua "
        "valendo para esses usos dentro do empreendimento rural",
        f"- [{regra['decreto_extenso']}]({regra['link_norma']}): PUB da DBO e pesos com medição usados como "
        "hipótese, e coeficientes da bacia na opção herdada",
        f"- [Legislação de recursos hídricos na SP Águas]({LINK_SPAGUAS_LEGISLACAO})",
    ]))


with st.container(border=True):
    with st.container(horizontal=True):
        st.badge(f"UGRHI {regra['ugrhi']} · {regra['comite']}", icon=":material/water:", color="blue")
        if rural:
            st.badge(f"Minuta rural · {MINUTA_RURAL['versao']}", icon=":material/agriculture:", color="orange")
        else:
            st.badge(regra["decreto"], icon=":material/gavel:", color="green")
        if simular_proposta:
            st.badge("Simulação da revisão proposta", icon=":material/science:", color="orange")
    if rural:
        st.markdown(texto_bacia_rural(regra))
    else:
        casas_pub = 4 if simular_proposta else 3
        st.markdown(md(
            f"**Preços unitários básicos (PUBs):** captação {fmt_brl(regra['pub_cap'], casas_pub)}/m³ · "
            f"consumo {fmt_brl(regra['pub_cons'], casas_pub)}/m³ · DBO {fmt_brl(regra['pub_dbo'], casas_pub)}/kg"
        ))
        if regra.get("percentual_transicao") is not None and regra["percentual_transicao"] < 1:
            atuais, finais = regra["pubs_atuais"], regra["pubs_finais"]
            pct = f"**{fmt_num(regra['percentual_transicao'] * 100, 0)}%**"
            conta = (f"PUB = PUB atual + {pct} × (PUB novo − PUB atual)" if regra["modo_transicao"] == "diferenca"
                     else f"PUB = {pct} × PUB novo")
            st.caption(md(
                f"Ano de transição: {conta}. Captação: {fmt_brl(atuais['pub_cap'], 4)} → {fmt_brl(finais['pub_cap'], 4)} · consumo: "
                f"{fmt_brl(atuais['pub_cons'], 4)} → {fmt_brl(finais['pub_cons'], 4)} · DBO: "
                f"{fmt_brl(atuais['pub_dbo'], 4)} → {fmt_brl(finais['pub_dbo'], 4)}."
            ))
        st.caption(md(f"{regra['resumo']} [Texto oficial do {regra['decreto']} (ALESP)]({regra['link_norma']})"))
        if regra_atual["revisao_pendente"]:
            st.warning(md(regra_atual["revisao_pendente"]), icon=":material/pending_actions:",
                       title="Revisão em andamento")
    if tem_proposta:
        # persist_state: a escolha volta quando o usuário passa pelo modo rural, que esconde estes controles
        with st.container(horizontal=True, vertical_alignment="center"):
            st.toggle("Simular como se o novo decreto já estivesse publicado", key=f"simular_proposta_{slug}",
                      persist_state="page",
                      help="Calcula com os PUBs e coeficientes da revisão aprovada pelo comitê e mostra a diferença "
                           "em relação ao decreto vigente. Os dados preenchidos são mantidos.")
            if simular_proposta:
                degraus = regra["degraus"]
                sufixo = "da diferença" if regra["modo_transicao"] == "diferenca" else "do PUB novo"
                st.segmented_control(
                    "Ano de aplicação", list(range(1, len(degraus) + 1)), default=len(degraus), required=True,
                    key=f"ano_aplicacao_{slug}", persist_state="page",
                    format_func=lambda a: f"{a}º ano ({fmt_num(degraus[a - 1] * 100, 0)}% {sufixo})",
                    help="A revisão é aplicada de forma progressiva, um degrau por exercício fiscal, até chegar ao "
                         "PUB novo (100%) no último ano.",
                )
        if simular_proposta and len(modos_transicao(bacia_selecionada)) > 1:
            st.toggle("Aplicar o percentual diretamente sobre o PUB novo (texto da deliberação)",
                      key=f"transicao_direta_{slug}", persist_state="page",
                      help="Desligado: conta dos estudos da revisão, PUB do ano = PUB atual + % × (PUB novo − PUB "
                           "atual). Ligado: conta do texto aprovado, PUB do ano = % × PUB novo. Enquanto o decreto "
                           "não define a leitura, as duas ficam disponíveis.")
    if rural:
        with st.expander("Guia da simulação rural", icon=":material/help:"):
            st.markdown(guia_rural())
        with st.expander("Fontes", icon=":material/gavel:"):
            st.markdown(fontes_rurais(regra))
    else:
        with st.expander("Guia de preenchimento desta bacia", icon=":material/help:"):
            st.markdown(guia_da_bacia(regra))
        with st.expander("Fontes oficiais", icon=":material/gavel:"):
            st.markdown(fontes_oficiais(regra))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 5.2. CENÁRIO RURAL (minuta em discussão)
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# As premissas ficam em chaves próprias da sessão ("rural_…"), iguais em todas as bacias, porque o estudo usa premissas
# estaduais. Os campos numéricos seguem o padrão brasileiro dos cartões; vazio = o valor do cenário (no PUB da DBO,
# o da bacia). persist_state="page" guarda as escolhas quando o usuário passa pelo modo urbano e volta.
CASAS_PREMISSA = {"pub_cap": 4, "pub_cons": 4, "pub_dbo": 4, "x7": 3, "x12": 2, "y9": 2, "fc_irrigacao": 1,
                  "limiar_isencao_m3_dia": 2}
EM_PERCENTUAL = {"fc_irrigacao"}    # na tela em %, como na minuta (88%); no motor, fração (0,88)


def _chave_rural(premissa):
    return f"rural_{premissa}"


def _rotulo_premissa(premissa):
    rotulo = PREMISSAS_RURAIS[premissa]["rotulo"]
    return f"{rotulo} (%)" if premissa in EM_PERCENTUAL else rotulo


def _texto_premissa(premissa, valor):
    if valor is None:
        return ""
    return fmt_num(valor * (100 if premissa in EM_PERCENTUAL else 1), CASAS_PREMISSA[premissa])


def _premissas_do_estudo():
    """Põe nos campos do painel as premissas do cenário do estudo (botão "Voltar às premissas do estudo")."""
    base = CENARIOS_RURAIS[CENARIO_RURAL_PADRAO]["premissas"]
    for premissa in CASAS_PREMISSA:
        st.session_state[_chave_rural(premissa)] = _texto_premissa(premissa, base[premissa])
    st.session_state[_chave_rural("isencao_por")] = base["isencao_por"]
    st.session_state[_chave_rural("coeficientes_bacia")] = base["coeficientes_bacia"]


def _ler_premissas():
    """Lê os campos do painel. Devolve (alterações para o motor, erros). Valor com erro: vale o do cenário."""
    alteracoes, erros = {}, []
    for premissa in CASAS_PREMISSA:
        rotulo = _rotulo_premissa(premissa)
        try:
            valor = ler_numero_br(st.session_state.get(_chave_rural(premissa)))
        except ValueError:
            erros.append(f"{rotulo}: número inválido. Use vírgula para os decimais (ex.: 0,214).")
            continue
        if valor is None:
            continue
        if valor < 0 or (premissa in EM_PERCENTUAL and valor > 100):
            erros.append(f"{rotulo}: o valor deve estar entre 0 e 100." if premissa in EM_PERCENTUAL
                         else f"{rotulo}: o valor deve ser maior ou igual a 0.")
            continue
        alteracoes[premissa] = valor / 100 if premissa in EM_PERCENTUAL else valor
    for premissa in ("isencao_por", "coeficientes_bacia"):
        if st.session_state.get(_chave_rural(premissa)):
            alteracoes[premissa] = st.session_state[_chave_rural(premissa)]
    return alteracoes, erros


def _valor_premissa(chave, p, regra):
    """Valor de uma premissa em texto, para as tabelas de premissas."""
    valor = p[chave]
    if chave == "pub_dbo":
        return (f"{fmt_brl(regra['pub_dbo'], 4)}/kg (da bacia)" if valor is None else f"{fmt_brl(valor, 4)}/kg")
    if chave in ("pub_cap", "pub_cons"):
        return f"{fmt_brl(valor, 4)}/m³"
    if chave in EM_PERCENTUAL:
        return f"{fmt_num(valor * 100, 1)}%"
    if chave == "limiar_isencao_m3_dia":
        return texto_limiar(valor)
    if chave == "isencao_por":
        return ISENCAO_POR[valor]
    if chave == "coeficientes_bacia":
        return COEFICIENTES_BACIA_RURAL[valor]
    if chave == "kout_kmed":
        return (f"{_texto_kout_kmed(regra['kout_kmed'])} (da bacia)" if valor is None
                else _texto_kout_kmed(valor))
    return fmt_num(valor, 3 if chave == "x7" else 2)


def tabela_premissas(p, regra):
    """Premissas em uso, com a origem de cada uma (Minuta, Estudo, Hipótese ou Sua escolha) e a fonte."""
    origem = origem_premissas(p)
    return pd.DataFrame([{
        "Premissa": info["rotulo"], "Valor": _valor_premissa(chave, p, regra), "Origem": origem[chave],
        "Fonte": info["fonte"],
    } for chave, info in PREMISSAS_RURAIS.items()])


def resumo_premissas(p):
    """Uma frase com o cenário em uso e o que o usuário mudou, sempre visível acima dos cartões."""
    mudadas = [PREMISSAS_RURAIS[k]["rotulo"] for k, camada in origem_premissas(p).items() if camada == "Sua escolha"]
    texto = (f"Cenário em uso: {p['cenario']}. PUBs de {fmt_brl(p['pub_cap'], 4)}/m³ na captação e "
             f"{fmt_brl(p['pub_cons'], 4)}/m³ no consumo, X7 = {fmt_num(p['x7'], 3)}, fator de consumo da irrigação "
             f"de {fmt_enxuto(p['fc_irrigacao'] * 100, 1)}%, limiar de isenção de "
             f"{texto_limiar(p['limiar_isencao_m3_dia'])}, coeficientes "
             f"{'herdados da bacia' if p['coeficientes_bacia'] == 'herdados' else 'neutros'}.")
    return texto + (f" Alterado por você: {'; '.join(mudadas)}." if mudadas else " Todas as premissas são as do estudo.")


def painel_rural():
    """
    Faixa de situação, escolha do limiar, CAF e premissas do cenário rural.
    Devolve (alterações das premissas para o motor, inscrito no CAF?, premissas completas).
    """
    if _chave_rural("pub_cap") not in st.session_state:
        _premissas_do_estudo()
    with st.container(border=True):
        st.warning(md(
            f"A cobrança do uso rural ainda não é vigente no Estado de São Paulo. Esta simulação segue a "
            f"{MINUTA_RURAL['nome'].lower()} ({MINUTA_RURAL['versao']}), em discussão na Câmara Técnica de Cobrança "
            "do Conselho Estadual de Recursos Hídricos, e as premissas do estudo da SP Águas apresentado em "
            "07/10/2026. Os valores são cenários para discussão, não cobrança."
        ), icon=":material/agriculture:", title="Minuta em discussão")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.segmented_control("Como aplicar o limiar de isenção", list(ISENCAO_POR), format_func=ISENCAO_POR.get,
                                 required=True, key=_chave_rural("isencao_por"), persist_state="page")
            st.checkbox("Agricultor familiar inscrito no CAF (Cadastro Nacional da Agricultura Familiar)",
                        key=_chave_rural("caf"), persist_state="page")
        with st.expander("Premissas do cenário rural: preços, coeficientes e limiar", icon=":material/tune:"):
            st.caption(md(
                "Os valores vêm da minuta e do estudo da SP Águas. Mude qualquer um para simular outro cenário: o que "
                "você mudar aparece como \"Sua escolha\" na tabela abaixo e na memória de cálculo. Campo vazio volta "
                "ao valor do estudo."
            ))
            linhas = (("pub_cap", "pub_cons", "pub_dbo"), ("x7", "x12", "y9"), ("fc_irrigacao", "limiar_isencao_m3_dia"))
            for linha in linhas:
                # Na linha dos coeficientes, os rótulos longos quebram em duas linhas: as caixas alinham pela base
                colunas = st.columns(3, vertical_alignment="bottom" if "x12" in linha else "top")
                for coluna, premissa in zip(colunas, linha):
                    chave = _chave_rural(premissa)
                    with coluna:
                        st.text_input(_rotulo_premissa(premissa), key=chave, persist_state="page",
                                      placeholder=(_texto_premissa(premissa, regra["pub_dbo"])
                                                   if premissa == "pub_dbo" else ""),
                                      on_change=_normalizar_numero, args=(chave, CASAS_PREMISSA[premissa]))
                        if premissa == "pub_dbo":
                            st.caption(md(f"Vazio = o da bacia ({fmt_brl(regra['pub_dbo'], 4)}/kg)."))
                if linha[-1] == "limiar_isencao_m3_dia":
                    with colunas[2]:
                        st.segmented_control("Coeficientes da bacia", list(COEFICIENTES_BACIA_RURAL),
                                             format_func=lambda c: "Neutros" if c == "neutros" else "Herdados",
                                             required=True, key=_chave_rural("coeficientes_bacia"),
                                             persist_state="page")
            st.caption("Coeficientes neutros: todos iguais a 1,00, menos X7, X12 e Y9, como no estudo. Herdados: os "
                       "coeficientes do decreto urbano da bacia, com o X7 trocado pelo X7 rural; os cartões passam a "
                       "pedir os campos da bacia.")
            st.button("Voltar às premissas do estudo", icon=":material/restart_alt:", on_click=_premissas_do_estudo)
        alteracoes, erros = _ler_premissas()
        if erros:
            st.error("Erro nas premissas do cenário rural (até corrigir, vale o valor do estudo):\n"
                     + "\n".join(f"- {e}" for e in erros))
        premissas = premissas_rurais(**alteracoes)
        st.caption(md(resumo_premissas(premissas)))
        with st.expander("Origem de cada premissa", icon=":material/source:"):
            st.dataframe(tabela_premissas(premissas, regra), hide_index=True,
                         alt="Premissas do cenário rural, com o valor, a origem e a fonte de cada uma")
            st.caption(md("Origem: " + "; ".join(f"**{nome}**, {texto}" for nome, texto in CAMADAS_RURAIS.items())
                          + "."))
    return alteracoes, bool(st.session_state.get(_chave_rural("caf"))), premissas


premissas_rural, caf_rural, cenario_rural = {}, False, None
if rural:
    premissas_rural, caf_rural, cenario_rural = painel_rural()
# Coeficientes herdados: os cartões do modo rural pedem os campos da bacia; neutros, não pedem
herdados = rural and cenario_rural["coeficientes_bacia"] == "herdados"

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 5.3. ANÁLISE: COMPARAÇÃO COM A REGRA URBANA DA BACIA
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Chave à parte, desligada até o usuário ligar (decisão D7 do plano da cobrança rural): calcula o mesmo uso pelo decreto
# urbano vigente da bacia, como se o usuário fosse urbano, num quadro abaixo do resultado rural. Não muda a simulação
# rural nem o resumo do resultado. Ligada, os cartões pedem os campos do decreto urbano que a simulação rural não usa,
# num bloco "só para a comparação"; o que faltar nele não tira o cartão da simulação rural.
# Para tirar a análise: MOSTRAR_COMPARACAO_URBANA = False (início do arquivo). Além desta seção, ela aparece em
# campos_de_selecao() (o bloco da comparação), em cartao() (PENDENTES_COMPARACAO) e no resultado rural (o cálculo
# urbano, a chamada de comparacao_urbana() e, na edição só rural, o cartão "Preço percebido pela regra urbana").
PENDENTES_COMPARACAO = []   # campos do decreto urbano que faltam nos cartões completos, para o quadro da comparação

comparar_urbano = False
if rural and MOSTRAR_COMPARACAO_URBANA:
    comparar_urbano = st.toggle("Comparar com a regra urbana da bacia", key="rural_comparar_urbano",
                                persist_state="page")
    st.caption(md(
        f"Análise: mostra, abaixo do resultado, quanto o mesmo uso pagaria pelo {regra['decreto']}, a cobrança urbana "
        "vigente na bacia. Ligada, os cartões pedem também os campos desse decreto, que não mudam a simulação rural."
    ))


def _percentual(fracao):
    return f"{fmt_num(fracao * 100, 1)}%"


def _preco_por_m3(res):
    """(Captação + consumo) ÷ volume captado. No rural, o preço da minuta, sem a isenção."""
    if res.get("rural"):
        return res["preco_percebido"]
    return (res["captacao"] + res["consumo"]) / res["VCAPT"] if res["VCAPT"] > 0 else 0.0


def frase_da_comparacao(res, urbano):
    """Uma frase com a diferença entre a minuta rural e a regra urbana."""
    rural_total, urbano_total = res["total"], urbano["total"]
    if res["isencao"]["isento"]:
        return (f"A minuta isenta este uso ({res['isencao']['artigo']}). Pela regra urbana, ele pagaria "
                f"{fmt_brl(urbano_total)} por ano.")
    diferenca = urbano_total - rural_total
    if abs(diferenca) < 0.005:
        return "Os dois valores são iguais."
    texto = (f"Pela regra urbana, este uso pagaria {fmt_brl(abs(diferenca))} "
             f"{'a mais' if diferenca > 0 else 'a menos'} por ano")
    if rural_total > 0:
        texto += f", {fmt_num(urbano_total / rural_total, 1)} vezes o valor da minuta rural"
    texto += "."
    if res["isencao"]["parcial"]:
        texto += f" Sem a isenção parcial da minuta, o valor rural seria de {fmt_brl(res['valor_sem_isencao'])}."
    return texto


def tabela_da_comparacao(res, urbano):
    """Os mesmos dados pelas duas regras, parcela a parcela."""
    isencao = res["isencao"]
    linhas = [
        ("Volume captado (m³/ano)", fmt_num(res["VCAPT"]), fmt_num(urbano["VCAPT"])),
        ("Fator de consumo médio", _percentual(res["FC"]), _percentual(urbano["FC"])),
        ("Captação (VCC)", fmt_brl(res["captacao"]), fmt_brl(urbano["captacao"])),
        ("Consumo (VCCo)", fmt_brl(res["consumo"]), fmt_brl(urbano["consumo"])),
        ("Lançamento (VCL)", fmt_brl(res["lancamento"]), fmt_brl(urbano["lancamento"])),
        ("Isenção", "Isento" if isencao["isento"] else "Parcial, por outorga" if isencao["parcial"]
         else "Não, acima do limiar", "Não prevista"),
        ("Valor total anual", fmt_brl(res["total"]), fmt_brl(urbano["total"])),
        ("Preço percebido por m³ captado, sem isenção", fmt_brl(_preco_por_m3(res), 4),
         fmt_brl(_preco_por_m3(urbano), 4)),
    ]
    return pd.DataFrame(linhas, columns=["Item", "Minuta rural", "Regra urbana da bacia"])


def diferencas_das_regras(res, urbano):
    """O que muda de uma regra para a outra, com os números desta simulação."""
    p = res["premissas"]
    pub_r, pub_u = res["pubs_aplicados"], urbano["pubs_aplicados"]
    x7_urbanos = "; ".join(f"{d['item']}: {fmt_num(d['coefs']['X7'], 2)}" for d in urbano["detalhes_cap"])
    demais = "herdados da bacia" if p["coeficientes_bacia"] == "herdados" else "neutros (1,00)"
    x12 = f" e X12 = {fmt_num(p['x12'], 2)}" if p["x12"] != 1 else ""
    if (round(pub_r["cap"], 6), round(pub_r["cons"], 6)) == (round(pub_u["cap"], 6), round(pub_u["cons"], 6)):
        pubs = (f"os mesmos nas duas regras, {fmt_brl(pub_r['cap'], 4)}/m³ na captação e "
                f"{fmt_brl(pub_r['cons'], 4)}/m³ no consumo.")
    else:
        pubs = (f"captação de {fmt_brl(pub_r['cap'], 4)}/m³ na minuta e {fmt_brl(pub_u['cap'], 4)}/m³ na regra "
                f"urbana; consumo de {fmt_brl(pub_r['cons'], 4)}/m³ e {fmt_brl(pub_u['cons'], 4)}/m³.")
    linhas = [
        f"**Preços básicos (PUB):** {pubs}",
        f"**Coeficientes:** na minuta, X7 = {fmt_num(p['x7'], 3)}{x12} e os demais {demais}; na regra urbana, os do "
        f"{regra['decreto']}" + (f", com o X7 da finalidade urbana escolhida ({x7_urbanos})." if x7_urbanos else "."),
        f"**Fator de consumo:** {_percentual(res['FC'])} em média na minuta, com "
        f"{fmt_enxuto(p['fc_irrigacao'] * 100, 1)}% fixos na irrigação; {_percentual(urbano['FC'])} na regra urbana, "
        "pela fórmula (volume captado − volume lançado) ÷ volume captado.",
        f"**Isenção:** a minuta isenta quem capta até {texto_limiar(p['limiar_isencao_m3_dia'])}, aplicado "
        f"{APLICACAO_DO_LIMIAR[p['isencao_por']]}, e o agricultor familiar inscrito no CAF. A regra urbana não tem essa "
        f"isenção. {regra['insignificante_texto']}",
    ]
    if res["detalhes_lanc"]:
        linhas.append(f"**Lançamento:** PUB da DBO de {fmt_brl(pub_r['dbo'], 4)}/kg na minuta, com "
                      f"Y9 = {fmt_num(p['y9'], 2)} e os demais Y {demais}, e de {fmt_brl(pub_u['dbo'], 4)}/kg na regra "
                      "urbana, com os coeficientes Y do decreto.")
    return linhas


def comparacao_urbana(res, urbano):
    """
    Quadro da análise: os mesmos dados pela minuta rural e pela regra urbana vigente da bacia. urbano é o cálculo
    pela regra urbana (None enquanto faltarem campos do decreto nos cartões).
    """
    with st.container(border=True):
        st.subheader("Comparação com a regra urbana da bacia")
        st.caption(md(
            f"Análise: os mesmos dados calculados pelo [{regra['decreto_extenso']}]({regra['link_norma']}), a cobrança "
            "urbana vigente na bacia, como se o uso fosse urbano. Serve para comparar; a cobrança rural seguirá o "
            "decreto rural."
        ))
        if PENDENTES_COMPARACAO:
            st.info(md("Para comparar, preencha nos cartões os campos da regra urbana. "
                       + " ".join(PENDENTES_COMPARACAO)), icon=":material/compare_arrows:")
            return
        col_rural, col_urbano = st.columns(2)
        col_rural.metric("Pela minuta rural", fmt_brl(res["total"]), border=True)
        col_urbano.metric(f"Pela regra urbana ({regra['decreto']})", fmt_brl(urbano["total"]), border=True)
        st.markdown(md(frase_da_comparacao(res, urbano)))
        st.dataframe(tabela_da_comparacao(res, urbano), hide_index=True,
                     alt="Comparação, parcela a parcela, do valor pela minuta rural e pela regra urbana da bacia")
        st.markdown(md("**O que muda de uma regra para a outra**\n\n"
                       + "\n".join(f"- {linha}" for linha in diferencas_das_regras(res, urbano))))
        for aviso in urbano["avisos"]:
            st.caption(md(f"Regra urbana: {aviso}"))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 6. CARTÕES DE CAPTAÇÃO E LANÇAMENTO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Acessibilidade nos cartões (lotes 3 a 5 do plano):
# - A14: cada rótulo diz a qual cartão pertence ("Vazão outorgada da captação 1 (m³/h)"), porque quem navega por Tab
#   ouve só o rótulo do campo, e os campos se repetem em todos os cartões.
# - A13/A11: os cartões não têm botões de ajuda "Help for…". As explicações estão no "Guia de preenchimento desta
#   bacia" e no menu "Período de uso e ano cheio"; o que é essencial para preencher fica em texto visível no cartão.
# - A04/A15: os erros de um cartão saem numa só mensagem st.error ("Erro na captação 1: …"), que é alerta e é anunciada
#   assim que o usuário sai do campo. O que falta preencher fica em texto no cartão, sem alerta, para não interromper
#   quem ainda está preenchendo; a contagem de cartões pendentes vai para o resumo do resultado (região viva educada).
def com_contexto(rotulo, contexto):
    """Põe o contexto do cartão antes dos parênteses finais: "Vazão outorgada (m³/h)" -> "Vazão outorgada da captação 1 (m³/h)"."""
    m = re.match(r"^(.*?)((?:\s*\([^()]*\))*)$", rotulo)
    return f"{m.group(1)} {contexto}{m.group(2)}"


def campo_numero(rotulo, chave, contexto, minimo=0.0, maximo=None, casas=2, inteiro=False, desabilitado=False,
                 nota=None, oculto=False):
    """
    Campo numérico em texto, lido no padrão brasileiro. O rótulo leva o contexto do cartão; a mensagem de erro usa o
    rótulo curto, porque sai dentro do aviso do próprio cartão. Devolve (valor ou None, mensagem de erro ou None).
    oculto: rótulo recolhido (o leitor de tela continua a lê-lo), para as linhas da tabela da sazonalidade, que têm
    os títulos das colunas em texto visível.
    """
    st.text_input(com_contexto(rotulo, contexto), key=chave, placeholder="0" if inteiro else "0,00",
                  disabled=desabilitado, on_change=_normalizar_numero, args=(chave, 0 if inteiro else casas),
                  persist_state="page", label_visibility="collapsed" if oculto else "visible")
    if nota:
        st.caption(nota)
    if desabilitado:
        return None, None
    try:
        valor = ler_numero_br(st.session_state.get(chave))
    except ValueError:
        return None, f"{rotulo}: número inválido. Use vírgula para os decimais (ex.: 1.500,75)."
    if valor is None:
        return None, None
    if inteiro and valor != int(valor):
        return None, f"{rotulo}: use um número inteiro."
    if valor < minimo or (maximo is not None and valor > maximo):
        faixa = f"entre {fmt_num(minimo, 0)} e {fmt_num(maximo, 0)}" if maximo is not None else "maior ou igual a 0"
        return None, f"{rotulo}: o valor deve estar {faixa}."
    return valor, None


def campo_horas(chave, contexto):
    """
    Horas por dia com a chave "Hora decimal" ao lado do rótulo: desligada, hora e minuto (7:30); ligada, hora
    decimal (7,5). Devolve (horas em decimal ou None, mensagem de erro ou None) e mostra a equivalência no
    outro formato.
    """
    formato = _formato_horas(chave)
    if formato == FORMATO_HHMM:
        exemplo, outro, como = "00:00", FORMATO_DECIMAL, "em hora e minuto"
    else:
        exemplo, outro, como = "0,00", FORMATO_HHMM, "em hora decimal"
    with st.container(gap=None):   # rótulo, chave e caixa juntos, alinhados aos campos vizinhos
        # Linha do rótulo: "Horas por dia", a chave e o texto "Hora decimal". Os nomes completos, com o cartão, ficam
        # nos rótulos recolhidos da chave e da caixa, que são os lidos pelo leitor de tela.
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.markdown("<span style='font-size:0.875rem'>Horas por dia</span>", unsafe_allow_html=True,
                        width="content")   # mesmo tamanho dos rótulos dos outros campos
            st.toggle(f"Hora decimal nas horas por dia {contexto}", key=chave + "_decimal", label_visibility="collapsed",
                      on_change=_converter_horas, args=(chave,), width="content", persist_state="page")
            st.markdown("<span style='font-size:0.875rem'>Hora decimal</span>", unsafe_allow_html=True,
                        width="content")
        st.text_input(f"Horas por dia {contexto}, {como}", key=chave, placeholder=exemplo,
                      label_visibility="collapsed", on_change=_normalizar_horas, args=(chave,), persist_state="page")
    try:
        valor = ler_horas(st.session_state.get(chave), formato)
    except ValueError as erro:
        return None, f"Horas por dia: {erro}, ou vire a chave \"Hora decimal\" ao lado do campo."
    if valor is None:
        return None, None
    if valor > 24:
        return None, "Horas por dia: o valor deve estar entre 0 e 24 horas."
    if formato == FORMATO_HHMM:
        st.caption(f"= {fmt_horas(valor, outro)} h em hora decimal")
    else:
        st.caption(f"= {fmt_horas(valor, outro)} em hora e minuto")
    return valor, None


def campo_opcao(campo, chave, contexto):
    return st.selectbox(com_contexto(campo["rotulo"], contexto), list(campo["opcoes"]), index=None, key=chave,
                        placeholder="Selecione…", persist_state="page")


def campos_de_selecao(campos, p, dados, pendencias, captacao, contexto, faltam_comparacao=None):
    """
    Desenha os campos de coeficientes da bacia e grava a opção escolhida em dados.
    Na captação subterrânea a classe do rio (X2) fica travada em 1,00, com a explicação em texto logo abaixo.
    No modo rural com coeficientes neutros, os campos da bacia não entram na conta e ficam escondidos (os valores
    escolhidos no modo urbano são guardados pelo persist_state); com coeficientes herdados, só o X7 fica de fora,
    porque vale o X7 rural.
    Com a comparação com a regra urbana ligada (seção 5.3), os campos que a simulação rural não usa aparecem num
    bloco à parte, com as mesmas chaves do modo urbano: o que faltar nele vai para faltam_comparacao, e não para as
    pendências do cartão. Devolve as chaves desse bloco.
    """
    if not rural:
        _desenhar_campos(campos, p, dados, pendencias, captacao, contexto)
        return set()
    na_simulacao = {k: c for k, c in campos.items() if herdados and c["coef"] != "X7"}
    _desenhar_campos(na_simulacao, p, dados, pendencias, captacao, contexto)
    so_comparacao = {k: c for k, c in campos.items() if k not in na_simulacao} if comparar_urbano else {}
    if so_comparacao:
        st.caption("Só para a comparação com a regra urbana (não mudam a simulação rural):")
        _desenhar_campos(so_comparacao, p, dados, faltam_comparacao, captacao, contexto)
    return set(so_comparacao)


def _desenhar_campos(visiveis, p, dados, pendencias, captacao, contexto):
    """Campos de seleção em até 3 colunas; o que ficar sem escolha vai para pendencias."""
    if not visiveis:
        return
    colunas = st.columns(min(3, len(visiveis)))
    for i, (chave, campo) in enumerate(visiveis.items()):
        with colunas[i % len(colunas)]:
            if captacao and campo["coef"] == "X2" and x2_nao_se_aplica(dados.get("natureza")):
                st.selectbox(com_contexto(campo["rotulo"], contexto), ["Não se aplica a poço: X2 = 1,00"],
                             key=p + chave + "_subterranea", disabled=True)
                st.caption("Captação subterrânea: a classe do rio não entra na conta, porque o enquadramento não "
                           "classifica aquíferos (veja o Guia de preenchimento desta bacia).")
                dados[chave] = None
                continue
            dados[chave] = campo_opcao(campo, p + chave, contexto)
            if dados[chave] is None:
                pendencias.append(campo["rotulo"])


NOMES_CARTAO = {"cap": ("Captação", "a"), "lanc": ("Lançamento", "o"), "min": ("Mineração de areia", "a")}


def nomes_do_cartao(tipo, numero, nome=None):
    """
    Nomes de um cartão para rótulos e mensagens. Com o nome padrão: título "Captação 1", "da captação 1",
    "na captação 1" e "captação 1". Com um nome dado pelo usuário: "Poço Norte", "de Poço Norte", "em Poço Norte".
    """
    titulo, artigo = NOMES_CARTAO[tipo]
    padrao = f"{titulo} {numero}"
    if nome and nome != padrao:
        return {"titulo": nome, "de": f"de {nome}", "em": f"em {nome}", "curto": nome, "padrao": padrao}
    curto = ("mineração" if tipo == "min" else titulo.lower()) + f" {numero}"
    return {"titulo": padrao, "de": f"d{artigo} {curto}", "em": f"n{artigo} {curto}", "curto": curto,
            "padrao": padrao}


# Nome dos cartões: o usuário pode trocar "Captação 1" por um nome próprio (ex.: "Poço Norte"), que passa a valer no
# título do cartão, nos rótulos dos campos, no resumo do resultado e nas tabelas da memória de cálculo.
NOMES_EM_USO = []        # nomes já usados nesta execução, para não haver dois cartões com o mesmo nome
NOME_DOS_CARTOES = {}    # (tipo, rid) -> nome curto, para o resumo dos cartões pendentes
CARACTERES_DE_MARCACAO = re.compile(r"[*_`$\\[\]#~|<>]")


def nome_escolhido(tipo, rid, numero):
    """
    Lê o nome dado ao cartão, sem os caracteres que o Markdown interpretaria. Vazio, ou no padrão com outro número
    (o cartão "Captação 3" que virou o 2º depois de remover um), volta ao nome padrão.
    """
    chave = _prefixo(tipo, slug, rid) + "nome"
    titulo = NOMES_CARTAO[tipo][0]
    atual = " ".join(CARACTERES_DE_MARCACAO.sub("", str(st.session_state.get(chave) or "")).split())
    if not atual or re.fullmatch(rf"{re.escape(titulo)} \d+", atual):
        atual = f"{titulo} {numero}"
    st.session_state[chave] = atual
    return atual


def identificar_cartao(tipo, rid, numero):
    """Nome do cartão e campo para editá-lo. Devolve os nomes do cartão (ver nomes_do_cartao)."""
    nome = nome_escolhido(tipo, rid, numero)
    padrao = nomes_do_cartao(tipo, numero)
    repetido = nome.casefold() in NOMES_EM_USO
    nomes = nomes_do_cartao(tipo, numero, f"{nome} ({padrao['titulo']})" if repetido else nome)
    NOMES_EM_USO.append(nomes["titulo"].casefold())
    NOME_DOS_CARTOES[(tipo, rid)] = nomes["curto"]
    return nomes, repetido


def campo_do_nome(tipo, rid, nomes, repetido):
    """Campo editável com o nome do cartão; o rótulo usa sempre o nome padrão, que diz a posição do cartão."""
    padrao = nomes_do_cartao(tipo, int(nomes["padrao"].rsplit(" ", 1)[1]))
    colunas = st.columns(3)
    with colunas[0]:
        st.text_input(f"Nome {padrao['de']}", key=_prefixo(tipo, slug, rid) + "nome", max_chars=40,
                      persist_state="page")
    if repetido:
        nome = nomes["titulo"].rsplit(" (", 1)[0]
        st.warning(f"Atenção: o nome “{nome}” já está em uso em outro cartão. Para diferenciá-los, este aparece como "
                   f"“{nomes['titulo']}”. Escolha um nome diferente.")


def cabecalho_do_cartao(tipo, rid, nomes):
    """Título do cartão e botões com o nome do cartão, para não haver vários "Remover" iguais na página."""
    p = _prefixo(tipo, slug, rid)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown(f"**{nomes['titulo']}**")
        st.space("stretch")
        st.button(f"Limpar {nomes['curto']}", key=p + "btn_limpar", icon=":material/ink_eraser:", type="tertiary",
                  on_click=_limpar_campos, args=(tipo, slug, rid))
        st.button(f"Remover {nomes['curto']}", key=p + "btn_remover", icon=":material/delete:", type="tertiary",
                  on_click=_remover_linha, args=(tipo, slug, rid))


def avisos_do_cartao(nomes, erros, pendencias):
    """Erros numa só mensagem de alerta; o que falta preencher em texto, sem alerta."""
    if erros:
        if len(erros) == 1:
            st.error(f"Erro {nomes['em']}: {erros[0]}")
        else:
            st.error(f"Erros {nomes['em']}:\n" + "\n".join(f"- {e}" for e in erros))
    if pendencias:
        st.caption(f":orange[Falta preencher {nomes['em']}: {', '.join(pendencias)}. Este cartão ainda não entra no "
                   "cálculo.]")


NOTA_VOLUME_MEDIDO = "Deixe em branco se não houver hidrômetro aceito pelo órgão outorgante."


def texto_fc_rural(finalidade):
    """Fator de consumo da finalidade rural, em texto visível no cartão de captação."""
    fc = fmt_enxuto(cenario_rural["fc_irrigacao"] * 100, 1)
    if finalidade is None:
        return (f"A finalidade define o fator de consumo: {fc}% na irrigação; nas demais finalidades, pela fórmula "
                "do Anexo, item 4, da minuta.")
    if finalidade == FINALIDADE_IRRIGACAO:
        return f"Fator de consumo de {fc}% na irrigação ({ART['fc_irrigacao']}, da minuta)."
    return ("Fator de consumo pela fórmula do Anexo, item 4, da minuta: (volume captado − volume lançado) ÷ volume "
            "captado, com os volumes do empreendimento todo.")


def campo_finalidade_rural(p, ctx, dados, pendencias):
    """
    Finalidade rural da captação, com a chave da sazonalidade ao lado e, embaixo, o fator de consumo que a finalidade
    implica. Devolve True se a sazonalidade (outorga mês a mês) está ligada.
    """
    esquerda, direita = st.columns(2, vertical_alignment="bottom")
    with esquerda:
        dados["finalidade_rural"] = st.selectbox(
            com_contexto("Finalidade rural", ctx), FINALIDADES_RURAIS, index=None, key=p + "finalidade_rural",
            placeholder="Selecione…", persist_state="page")
    with direita:
        sazonal = st.toggle(com_contexto("Sazonalidade (outorga mês a mês)", ctx), key=p + "sazonal",
                            persist_state="page")
    st.caption(md(texto_fc_rural(dados["finalidade_rural"])))
    if dados["finalidade_rural"] is None:
        pendencias.append("finalidade rural")
    return sazonal


def campos_sazonais(p, ctx, erros, pendencias):
    """
    Sazonalidade (modo rural): a outorga mês a mês, com vazão, horas por dia e dias de uso em cada mês; mês em branco é
    mês sem captação. Os títulos das colunas são texto visível; cada campo tem o nome completo no rótulo recolhido
    ("Vazão em março da captação 1 (m³/h)"), que é o lido pelo leitor de tela. Devolve (12 posições, cada uma None ou
    (vazão, horas, dias), algum campo preenchido?).
    """
    chave_formato = p + "sazonal_decimal"
    formato = _formato_horas(None, chave_formato)
    como = "em hora e minuto" if formato == FORMATO_HHMM else "em hora decimal"
    st.caption("Outorga mês a mês: preencha a vazão, as horas por dia e os dias de uso de cada mês com captação e "
               "deixe em branco os meses sem uso. O volume do ano é a soma dos meses; a captação máxima em m³/dia, que "
               "decide a isenção, é a do mês de maior vazão × horas.")
    cabecalho = st.columns(4, vertical_alignment="center")
    cabecalho[0].markdown("**Mês**")
    cabecalho[1].markdown("**Vazão (m³/h)**")
    with cabecalho[2]:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.markdown("**Horas por dia**", width="content")
            st.toggle(f"Hora decimal nas horas por dia dos meses {ctx}", key=chave_formato,
                      label_visibility="collapsed", on_change=_converter_horas_meses, args=(p,), width="content",
                      persist_state="page")
            st.markdown("<span style='font-size:0.875rem'>Hora decimal</span>", unsafe_allow_html=True,
                        width="content")
    cabecalho[3].markdown("**Dias de uso**")

    meses, preenchido = [], False
    for i, nome_mes in enumerate(MESES):
        mes = nome_mes.lower()
        chaves = [_chave_mes(p, i, c) for c in ("vazao", "horas", "dias")]
        linha = st.columns(4, vertical_alignment="center")
        linha[0].markdown(nome_mes)
        with linha[1]:
            vazao, e_vazao = campo_numero(f"Vazão em {mes} (m³/h)", chaves[0], ctx, oculto=True)
        with linha[2]:
            st.text_input(f"Horas por dia em {mes} {ctx}, {como}", key=chaves[1],
                          placeholder="00:00" if formato == FORMATO_HHMM else "0,00", label_visibility="collapsed",
                          on_change=_normalizar_horas, args=(chaves[1], chave_formato), persist_state="page")
            horas, e_horas = None, None
            try:
                horas = ler_horas(st.session_state.get(chaves[1]), formato)
            except ValueError as erro:
                e_horas = f"Horas por dia em {mes}: {erro}, ou vire a chave \"Hora decimal\" acima da coluna."
            if horas is not None and horas > 24:
                horas, e_horas = None, f"Horas por dia em {mes}: o valor deve estar entre 0 e 24 horas."
        with linha[3]:
            dias, e_dias = campo_numero(f"Dias de uso em {mes}", chaves[2], ctx, minimo=1, maximo=DIAS_DO_MES[i],
                                        inteiro=True, oculto=True)
        erros_da_linha = [e for e in (e_vazao, e_horas, e_dias) if e]
        erros += erros_da_linha
        digitados = any(str(st.session_state.get(k) or "").strip() for k in chaves)
        preenchido = preenchido or digitados
        valores = (vazao, horas, dias)
        if all(v is not None for v in valores):
            meses.append((vazao, horas, int(dias)))
            continue
        meses.append(None)
        if digitados and not erros_da_linha:
            faltam = [n for n, v in zip(("vazão", "horas por dia", "dias de uso"), valores) if v is None]
            faltam = faltam[0] if len(faltam) == 1 else ", ".join(faltam[:-1]) + " e " + faltam[-1]
            pendencias.append(f"{faltam} de {mes}")
    if not any(meses) and not preenchido:
        pendencias.append("vazão, horas por dia e dias de uso de ao menos um mês")
    return meses, preenchido


def aviso_padrao_dbo(nomes, dbo, pr, resfriamento, afluente=False):
    """
    Alerta quando a remoção fica abaixo de 80%: diz se o efluente ainda atende ao padrão de emissão de DBO (até 60 mg/L
    ou remoção de pelo menos 80%, Decreto Estadual nº 8.468/1976, art. 18), de que depende o teto do lançamento.
    afluente: dbo e pr são a DBO que chega ao rio, Cc × (1 − FTR × FER), e a remoção total, FTR × FER.
    """
    if pr is None or dbo is None or pr >= REMOCAO_PADRAO_EMISSAO or resfriamento:
        return   # sem DBO declarada, o cartão explica a DBO presumida (texto_dbo_presumida)
    if afluente:
        situacao = (f"a DBO que chega ao rio, de {fmt_num(dbo)} mg/L, atende ao padrão de emissão."
                    if atende_padrao_dbo(dbo, pr) else
                    f"com {fmt_num(dbo)} mg/L de DBO chegando ao rio, o efluente não atende ao padrão de emissão, e o "
                    "teto do lançamento não se aplica.")
        st.warning(f"Atenção {nomes['em']}: remoção total (FTR × FER) de {fmt_num(pr, 1)}%, abaixo de 80%; {situacao}")
        return
    if dbo is not None and not atende_padrao_dbo(dbo, pr):
        st.warning(f"Atenção {nomes['em']}: DBO acima de 60 mg/L e remoção abaixo de 80%. O efluente "
                   "não atende ao padrão de emissão: Y3 = 1,00 e o teto do lançamento não se aplica.")
    else:
        y3 = "" if regra["y3_modo"] == "litoral_norte" else " Y3 = 1,00."
        st.warning(f"Atenção {nomes['em']}: remoção abaixo de 80%, mas, com DBO de até 60 mg/L, o "
                   f"efluente atende ao padrão de emissão.{y3}")


def texto_dbo_presumida(remocao_digitada):
    """
    Texto do cartão de lançamento sem DBO declarada (simulação local): a DBO presumida de 300 mg/L, sem remoção, e o
    que isso muda na conta. Nas bacias com carga pela DBO do afluente, os 300 mg/L entram como Cc, com FTR = FER = 0.
    """
    dbo = fmt_num(DBO_PRESUMIDA_MG_L, 0)
    if regra["carga_afluente"]:
        valor = "pelo PUB, sem os coeficientes Y" if CARGA_AFLUENTE_SO_PUB else "pelo PUB × coeficientes Y"
        conta = (f"DBO do afluente de {dbo} mg/L, sem tratamento (FTR = FER = 0): a carga é o volume lançado × "
                 f"{fmt_num(DBO_PRESUMIDA_MG_L / 1000, 1)} kg/m³, cobrada {valor}")
    else:
        conta = f"{dbo} mg/L e remoção de 0%, como efluente sem tratamento comprovado: Y3 = 1,00"
    remocao = " A remoção informada só vale com a DBO declarada." if remocao_digitada else ""
    return (f":material/info: DBO não declarada: a simulação adota {conta} ({FONTE_DBO_PRESUMIDA}). O efluente fica "
            f"fora do padrão de emissão, e o teto do lançamento não se aplica.{remocao} Informe a DBO medida para "
            "chegar ao valor real.")


def campos_carga_afluente(p, ctx, dados, erros):
    """
    Segunda linha do lançamento nas bacias com carga pela DBO do afluente (Pardo, Turvo/Grande, Médio Paranapanema e
    Aguapeí/Peixe), como no SisCob 2.0: DBO do afluente (Cc) e fator de tratamento (FTR). É opcional; com a DBO do
    afluente, a carga passa a VLÇ × Cc × (1 − FTR × FER), com prioridade sobre a concentração remanescente, e o FTR
    passa a ser obrigatório. Com o resfriamento em circuito aberto vale a regra do resfriamento, e a linha fica travada.
    Devolve (Cc, FTR), cada um None se vazio.
    """
    valor = ("o valor é a carga × PUB, sem os coeficientes Y (requisito do SisCob 2.0)" if CARGA_AFLUENTE_SO_PUB
             else "o valor é a carga × PUB × coeficientes Y")
    st.caption(f"Opcional: com a DBO do afluente (antes do tratamento) e o fator de tratamento, a carga passa a volume "
               f"lançado × Cc × (1 − FTR × FER), com prioridade sobre a concentração remanescente, e {valor}.")
    travado = dados["resfriamento"]
    colunas = st.columns(3, vertical_alignment="bottom")   # rótulos de alturas diferentes: caixas alinhadas
    with colunas[0]:
        cc, e = campo_numero("DBO do afluente (Cc) (mg/L)", p + "dbo_afluente", ctx, desabilitado=travado)
        if e:
            erros.append(e)
    with colunas[1]:
        ftr, e = campo_numero("Fator de tratamento (FTR) (%)", p + "ftr_pct", ctx, maximo=100.0, casas=1,
                              desabilitado=travado)
        if e:
            erros.append(e)
    dados["dbo_afluente"], dados["ftr_pct"] = cc, ftr
    return cc, ftr


def cartao(tipo, rid, numero):
    """
    Desenha um cartão de captação ('cap') ou lançamento ('lanc').
    Devolve (dados para o cálculo ou None, lista de pendências, cartão vazio?).
    """
    p = _prefixo(tipo, slug, rid)
    nomes, repetido = identificar_cartao(tipo, rid, numero)
    ctx = nomes["de"]
    campos = regra["campos_cap"] if tipo == "cap" else regra["campos_lanc"]
    dados, pendencias, erros = {}, [], []
    faltam_comparacao = []   # campos só da comparação com a regra urbana (seção 5.3): não tiram o cartão do cálculo

    with st.container(border=True):
        cabecalho_do_cartao(tipo, rid, nomes)
        campo_do_nome(tipo, rid, nomes, repetido)

        # Modo rural: a finalidade rural de cada captação decide o fator de consumo (88% na irrigação); ao lado, a chave
        # da sazonalidade troca a vazão e o período por uma tabela mês a mês
        sazonal = False
        if rural and tipo == "cap":
            sazonal = campo_finalidade_rural(p, ctx, dados, pendencias)
        # Características que definem os coeficientes (variam por bacia)
        so_comparacao = campos_de_selecao(campos, p, dados, pendencias, captacao=tipo == "cap", contexto=ctx,
                                          faltam_comparacao=faltam_comparacao)

        # Lançamento: eficiência e DBO. Nas bacias com carga pela DBO do afluente (Pardo, Turvo/Grande, Médio
        # Paranapanema e Aguapeí/Peixe), os campos seguem os nomes do SisCob 2.0 e há uma segunda linha, opcional,
        # com a DBO do afluente (Cc) e o fator de tratamento (FTR); a minuta rural tem fórmula própria e não a usa.
        if tipo == "lanc":
            afluente = regra["carga_afluente"] and not rural
            colunas = st.columns(3)
            with colunas[0]:
                dbo, e = campo_numero("Concentração remanescente de DBO (mg/L)" if afluente else "DBO do efluente (mg/L)",
                                      p + "dbo", ctx)
                erros += [e] if e else []
                dados["dbo"] = dbo
            dados["resfriamento"] = False
            # Com os coeficientes neutros do modo rural, o decreto da bacia (e o seu resfriamento) não entra
            if regra["resfriamento"] and not (rural and not herdados):
                with colunas[2]:
                    st.checkbox(com_contexto("Resfriamento em circuito aberto", ctx), key=p + "resfriamento",
                                persist_state="page")
                dados["resfriamento"] = st.session_state.get(p + "resfriamento", False)
            with colunas[1]:
                pr, e = campo_numero("Fator de eficiência de remoção (FER) (%)" if afluente
                                     else "Remoção de DBO na ETE (%) (Y3)", p + "remocao_pct", ctx, maximo=100.0,
                                     casas=1, desabilitado=dados["resfriamento"])
                erros += [e] if e else []
                dados["remocao_pct"] = 100.0 if dados["resfriamento"] else pr
                if not afluente:   # aviso logo depois de sair do campo; com a DBO do afluente, depois da 2ª linha
                    aviso_padrao_dbo(nomes, dbo, pr, dados["resfriamento"])
            if afluente:
                cc, ftr = campos_carga_afluente(p, ctx, dados, erros)
                if cc is not None and ftr is not None and pr is not None:
                    remocao = ftr * pr / 100.0
                    aviso_padrao_dbo(nomes, cc * (1 - remocao / 100.0), remocao, dados["resfriamento"], afluente=True)
                elif cc is None:
                    aviso_padrao_dbo(nomes, dbo, pr, dados["resfriamento"])

        # Vazão e período: com a sazonalidade (modo rural), a tabela mês a mês; sem ela, vazão × horas × dias no ano
        ano_cheio = not sazonal and st.session_state.get(p + "ano_cheio", False)
        vazao = horas = dias_mes = meses = None
        meses_sazonais = None
        if sazonal:
            meses_sazonais, _ = campos_sazonais(p, ctx, erros, pendencias)
            colunas = st.columns(3)
            with colunas[0]:
                v_med, e = campo_numero("Volume medido no ano (m³)", p + "v_med", ctx, nota=NOTA_VOLUME_MEDIDO)
                erros += [e] if e else []
        else:
            colunas = st.columns(3)
            with colunas[0]:
                vazao, e = campo_numero("Vazão outorgada (m³/h)", p + "vazao", ctx)
                erros += [e] if e else []
            with colunas[1]:
                horas, e = campo_horas(p + "horas", ctx)
                erros += [e] if e else []
            with colunas[2]:
                v_med, e = campo_numero("Volume medido no ano (m³)", p + "v_med", ctx, nota=NOTA_VOLUME_MEDIDO)
                erros += [e] if e else []
            colunas = st.columns(3, vertical_alignment="bottom")
            with colunas[0]:
                dias_mes, e = campo_numero("Dias por mês", p + "dias_mes", ctx, minimo=1, maximo=31, inteiro=True,
                                           desabilitado=ano_cheio)
                erros += [e] if e else []
            with colunas[1]:
                meses, e = campo_numero("Meses por ano", p + "meses", ctx, minimo=1, maximo=12, inteiro=True,
                                        desabilitado=ano_cheio)
                erros += [e] if e else []
            with colunas[2]:
                st.checkbox(com_contexto("Outorga de ano cheio (365 dias)", ctx), key=p + "ano_cheio",
                            persist_state="page")

        numericos = [vazao, horas, v_med, dias_mes, meses, dados.get("dbo"), dados.get("remocao_pct"),
                     dados.get("dbo_afluente"), dados.get("ftr_pct")]
        vazio = (all(v is None for v in numericos) and not erros and not ano_cheio and not sazonal
                 and all(dados.get(k) is None for k in campos if k not in so_comparacao)
                 and not dados.get("resfriamento") and dados.get("finalidade_rural") is None)
        if vazio:
            return None, [], True

        if not sazonal:   # com a sazonalidade, o que falta em cada mês já entrou nas pendências
            if vazao is None:
                pendencias.append("vazão")
            if horas is None:
                pendencias.append("horas por dia")
            if not ano_cheio and (dias_mes is None or meses is None):
                pendencias.append("dias por mês e meses por ano (ou marque ano cheio)")
        dbo_presumida = False
        if tipo == "lanc":
            # com a DBO do afluente, a concentração remanescente é dispensada e o FTR passa a ser obrigatório; sem
            # nenhuma DBO (e fora do resfriamento e do modo rural), a simulação presume DBO_PRESUMIDA_MG_L sem remoção
            com_afluente = dados.get("dbo_afluente") is not None
            sem_dbo = dados.get("dbo") is None and not com_afluente
            dbo_presumida = (sem_dbo and DBO_PRESUMIDA_MG_L is not None and not rural
                             and not dados.get("resfriamento"))
            if sem_dbo and not dbo_presumida:
                pendencias.append("concentração remanescente de DBO (ou a DBO do afluente)" if afluente else "DBO")
            if dados.get("remocao_pct") is None and not dbo_presumida:
                pendencias.append("fator de eficiência de remoção (FER)" if afluente else "remoção de DBO (%)")
            if com_afluente and dados.get("ftr_pct") is None:
                pendencias.append("fator de tratamento (FTR), obrigatório quando a DBO do afluente é informada")

        if erros or pendencias:
            avisos_do_cartao(nomes, erros, pendencias)
            return None, pendencias, False

        if sazonal:
            # vazão, horas e dias no ano ficam como resumo (o mês de maior captação e a soma dos dias); o motor usa
            # os meses para o volume e para a captação máxima
            usados = [m for m in meses_sazonais if m]
            maior = max(usados, key=lambda m: m[0] * m[1])
            dias_ano = float(sum(m[2] for m in usados))
            dados.update(nome=nomes["titulo"], vazao=maior[0], horas_dia=maior[1], dias_ano=dias_ano,
                         v_med=v_med or 0.0, dias_mes=None, meses_ano=len(usados), meses=meses_sazonais)
        else:
            dias_ano = dias_por_ano(dias_mes or 0, meses or 0, ano_cheio)
            dados.update(nome=nomes["titulo"], vazao=vazao, horas_dia=horas, dias_ano=dias_ano, v_med=v_med or 0.0,
                         dias_mes=None if ano_cheio else dias_mes, meses_ano=12 if ano_cheio else int(meses))
        v_out, m3_dia = volume_e_captacao_maxima(dados)
        if sazonal:
            n = len(usados)
            st.caption(f":material/check_circle: captação máxima de {fmt_num(m3_dia)} m³/dia · {fmt_num(dias_ano, 0)} "
                       f"dias de uso em {n} {'mês' if n == 1 else 'meses'} · volume outorgado de "
                       f"**{fmt_num(v_out)} m³/ano**")
        else:
            carga = (" · carga pela DBO do afluente" if tipo == "lanc" and dados.get("dbo_afluente") is not None
                     else "")
            st.caption(f":material/check_circle: {fmt_num(m3_dia)} m³/dia · {fmt_num(dias_ano, 1)} dias de uso · "
                       f"volume outorgado de **{fmt_num(v_out)} m³/ano**{carga}")
        if dbo_presumida:
            st.caption(texto_dbo_presumida(bool(dados.get("remocao_pct"))))
        if faltam_comparacao:
            em = nomes["em"]
            PENDENTES_COMPARACAO.append(f"{em[0].upper()}{em[1:]}: {', '.join(faltam_comparacao)}.")
        if rural and tipo == "cap" and cenario_rural["isencao_por"] == "outorga" and not caf_rural:
            limiar = cenario_rural["limiar_isencao_m3_dia"]
            st.caption(f"Até o limiar de isenção de {fmt_enxuto(limiar)} m³/dia: isenta na leitura por outorga."
                       if m3_dia <= limiar else
                       f"Acima do limiar de isenção de {fmt_enxuto(limiar)} m³/dia: cobrada na leitura por outorga.")
        return dados, [], False


def cartao_mineracao(rid, numero):
    """
    Desenha um cartão de mineração de areia, cobrado à parte pela regra do decreto da bacia.
    Devolve (dados para o cálculo ou None, lista de pendências, cartão vazio?).
    """
    p = _prefixo("min", slug, rid)
    nomes, repetido = identificar_cartao("min", rid, numero)
    ctx = nomes["de"]
    modo = regra["mineracao"]
    dados, pendencias, erros, numericos = {}, [], [], []

    with st.container(border=True):
        cabecalho_do_cartao("min", rid, nomes)
        campo_do_nome("min", rid, nomes, repetido)
        st.caption(md(f"Regra do {regra['decreto']}: {texto_mineracao(regra)}"))

        campos_de_selecao(regra["campos_cap"], p, dados, pendencias, captacao=True, contexto=ctx)

        ano_cheio = False
        if modo == "areia":
            # Umidade da areia (U): sem medição, fica travada no mínimo do decreto (5%); com laudo de medição, o
            # usuário informa o valor medido, que nunca fica abaixo do mínimo. A chave vem antes dos campos, para
            # que quem navega por Tab encontre o controle antes do campo que ele libera. Sem mínimo no decreto
            # (revisão do Paraíba do Sul), a umidade é sempre informada. A razão R já fica travada onde o decreto
            # a fixa; onde não fixa (Paraíba do Sul), o decreto manda o usuário informá-la.
            minimo = regra["mineracao_u_min"]
            u_medida = True
            if minimo:
                u_medida = st.checkbox(com_contexto("Há medição da umidade da areia (laudo)", ctx), key=p + "u_medida",
                                       persist_state="page")
            colunas = st.columns(3)
            with colunas[0]:
                q_areia, e = campo_numero("Volume de areia produzido no ano (m³)", p + "q_areia", ctx)
                erros += [e] if e else []
            r = regra["mineracao_r"]
            with colunas[1]:
                if r is None:
                    r, e = campo_numero("Razão de mistura água/areia (R)", p + "r", ctx,
                                        nota="Metros cúbicos de água por metro cúbico de areia na polpa dragada, "
                                             "conforme o projeto da lavra.")
                    erros += [e] if e else []
                    numericos.append(r)
                else:
                    st.text_input(com_contexto("Razão de mistura água/areia (R)", ctx), value=fmt_num(r, 2),
                                  key=p + "r_fixo", disabled=True)
                    st.caption("Fixada pelo decreto da bacia.")
            with colunas[2]:
                if u_medida:
                    u_pct, e = campo_numero("Umidade da areia (U, %)", p + "u_pct", ctx, maximo=100.0, casas=1,
                                            nota=(f"O decreto adota no mínimo {fmt_num(minimo * 100, 0)}%." if minimo
                                                  else None))
                    erros += [e] if e else []
                    numericos.append(u_pct)
                else:
                    u_pct = minimo * 100
                    st.text_input(com_contexto("Umidade da areia (U, %)", ctx), value=fmt_num(u_pct, 1),
                                  key=p + "u_fixo", disabled=True)
                    st.caption(f"Sem medição, vale o mínimo do decreto: {fmt_num(u_pct, 0)}%. Com laudo, marque a "
                               "medição acima.")
            numericos.append(q_areia)
            for valor, rotulo in ((q_areia, "volume de areia"), (r, "R"), (u_pct, "umidade")):
                if valor is None:
                    pendencias.append(rotulo)
            dados.update(q_areia=q_areia, r=r, u_pct=u_pct)
        else:
            ano_cheio = st.session_state.get(p + "ano_cheio", False)
            rotulo_vazao = ("Vazão máxima de bombeamento da draga (m³/h)" if modo == "consumo_total"
                            else "Vazão outorgada (m³/h)")
            colunas = st.columns(3)
            with colunas[0]:
                vazao, e = campo_numero(rotulo_vazao, p + "vazao", ctx)
                erros += [e] if e else []
            with colunas[1]:
                horas, e = campo_horas(p + "horas", ctx)
                erros += [e] if e else []
            v_med = declarado = None
            with colunas[2]:
                if modo != "consumo_total":
                    v_med, e = campo_numero("Volume medido no ano (m³)", p + "v_med", ctx, nota=NOTA_VOLUME_MEDIDO)
                    erros += [e] if e else []
            colunas = st.columns(3, vertical_alignment="bottom")
            with colunas[0]:
                dias_mes, e = campo_numero("Dias por mês", p + "dias_mes", ctx, minimo=1, maximo=31, inteiro=True,
                                           desabilitado=ano_cheio)
                erros += [e] if e else []
            with colunas[1]:
                meses, e = campo_numero("Meses por ano", p + "meses", ctx, minimo=1, maximo=12, inteiro=True,
                                        desabilitado=ano_cheio)
                erros += [e] if e else []
            with colunas[2]:
                st.checkbox(com_contexto("Outorga de ano cheio (365 dias)", ctx), key=p + "ano_cheio",
                            persist_state="page")
            if modo == "minimo_5":
                declarado, e = campo_numero("Consumo efetivo declarado (m³/ano)", p + "consumo_declarado", ctx,
                                            nota="Abaixo de 5% do volume outorgado, o decreto adota 5%.")
                erros += [e] if e else []
            numericos += [vazao, horas, v_med, dias_mes, meses, declarado]
            if vazao is None:
                pendencias.append("vazão")
            if horas is None:
                pendencias.append("horas por dia")
            if not ano_cheio and (dias_mes is None or meses is None):
                pendencias.append("dias por mês e meses por ano (ou marque ano cheio)")
            if vazao is not None and horas is not None and (ano_cheio or (dias_mes and meses)):
                dados.update(vazao=vazao, horas_dia=horas, dias_ano=dias_por_ano(dias_mes or 0, meses or 0, ano_cheio),
                             v_med=v_med or 0.0, consumo_declarado=declarado or 0.0,
                             dias_mes=None if ano_cheio else dias_mes, meses_ano=12 if ano_cheio else int(meses))

        vazio = (all(v is None for v in numericos) and not erros and not ano_cheio
                 and all(dados.get(k) is None for k in regra["campos_cap"]))
        if vazio:
            return None, [], True
        if erros or pendencias:
            avisos_do_cartao(nomes, erros, pendencias)
            return None, pendencias, False

        dados["nome"] = nomes["titulo"]
        v_out, _, _, _, v_cap, v_cons, memoria = volumes_mineracao(regra, dados)
        st.caption(f":material/check_circle: Captação de **{fmt_num(v_cap)} m³/ano** · consumo de "
                   f"**{fmt_num(v_cons)} m³/ano** ({memoria}).")
        return dados, [], False


ROTULOS_ADICIONAR = {"cap": "Adicionar captação", "lanc": "Adicionar lançamento", "min": "Adicionar mineração de areia"}


def secao(tipo, titulo, descricao):
    """Desenha os cartões de um tipo. Devolve (dados dos cartões completos, nomes dos cartões a completar ou corrigir)."""
    st.subheader(titulo)
    guia = "o Guia da simulação rural" if rural else "o Guia de preenchimento desta bacia"
    st.caption(md(descricao + " Cada cartão pode ganhar um nome próprio no campo Nome, que aparece no resultado e "
                  f"na memória de cálculo. Dúvidas sobre um campo: veja {guia}, acima, e o menu "
                  "Período de uso e ano cheio."))
    validos, pendentes = [], []
    ids = list(_lista(tipo, slug))
    for numero, rid in enumerate(ids, start=1):
        dados, pend, vazio = cartao_mineracao(rid, numero) if tipo == "min" else cartao(tipo, rid, numero)
        if dados:
            validos.append(dados)
        elif not vazio:
            pendentes.append(NOME_DOS_CARTOES[(tipo, rid)])
    st.button(ROTULOS_ADICIONAR[tipo], key=f"add_{tipo}_{slug}", icon=":material/add:", on_click=_adicionar_linha,
              args=(tipo, slug))
    return validos, pendentes


captacoes, pend_cap = secao(
    "cap", "Captação, extração ou derivação",
    (f"Informe cada ponto de captação do empreendimento rural na bacia {bacia_selecionada} e a sua finalidade: é a "
     "finalidade que define o fator de consumo. A vazão e as horas por dia dão a captação máxima outorgada em m³/dia, "
     "que decide a isenção. Se a outorga muda ao longo do ano, ligue a chave Sazonalidade, ao lado da finalidade, e "
     "informe cada mês: vale o mês de maior vazão × horas." if rural else
     f"Informe cada ponto de captação do empreendimento na bacia {bacia_selecionada}. Os campos mudam conforme "
     "os coeficientes previstos no decreto da bacia."),
)
lancamentos, pend_lanc = secao(
    "lanc", "Lançamento de efluentes",
    ("Informe cada ponto de lançamento em corpo d'água, como a saída de tanques de aquicultura. Se o empreendimento "
     "não lança efluentes, deixe o cartão em branco ou remova-o." if rural else
     "Informe cada ponto de lançamento em corpo d'água. Se o empreendimento não lança efluentes, deixe o cartão "
     "em branco ou remova-o."),
)

# Mineração de areia: regra própria dos decretos urbanos; fica fora da simulação rural
mineracoes, pend_min = [], []
if regra["mineracao"] and not rural:
    mineracoes, pend_min = secao(
        "min", "Mineração de areia",
        f"Item cobrado à parte pela regra própria do {regra['decreto']}. Não entra no fator de consumo das captações "
        "e não tem carga lançada. Use apenas se o empreendimento extrai areia em leito de rio ou cava.",
    )

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 7. RESULTADO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
st.divider()

# Acessibilidade (A03): o resumo do resultado fica sempre neste mesmo lugar, logo abaixo da linha. O st.info e o
# st.success saem com role="status" (região viva): como o elemento já existe na tela, o leitor de tela anuncia cada
# mudança do valor sem tirar o foco do campo que o usuário está preenchendo. Nada condicional pode vir antes dele,
# senão o Streamlit recria o elemento e o anúncio se perde.
aviso_resultado = st.empty()

# Acessibilidade (A15): os cartões a completar ou corrigir entram no próprio resumo, que é região viva educada (não
# interrompe a leitura), e não mais num st.warning à parte, que é alerta e falava a cada mudança, cedo demais.
pendentes = pend_cap + pend_lanc + pend_min


def _juntar(itens):
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def frase_dos_pendentes():
    if not pendentes:
        return ""
    if len(pendentes) == 1:
        return f" Fora do cálculo, a completar ou corrigir: {pendentes[0]}."
    return f" Fora do cálculo, {len(pendentes)} cartões a completar ou corrigir: {_juntar(pendentes)}."


def mostrar_resumo(texto):
    """Cálculo completo em verde (st.success); com cartões pendentes, em azul (st.info). Os dois são role="status"."""
    if pendentes:
        if "valor total" in texto:   # há valor, mas sem os cartões pendentes
            texto = texto.replace("Resultado", "Resultado parcial", 1)
        aviso_resultado.info(md(texto + frase_dos_pendentes()))
    else:
        aviso_resultado.success(md(texto))


if not captacoes and not lancamentos and not mineracoes:
    if pendentes:
        mostrar_resumo("Resultado: ainda sem valor.")
    else:
        itens = ("uma captação ou um lançamento" if rural
                 else "uma captação, um lançamento ou uma mineração de areia")
        aviso_resultado.info(f"Resultado: calculadora vazia. Preencha ao menos {itens} para ver o valor da cobrança.")
    st.stop()

def parcelas_mensais(res):
    """Parcelas mensais do valor anual rural, só quando a tela as mostra (MOSTRAR_PARCELAS_RURAIS) e há valor a pagar."""
    return parcelas_rurais(res["total"], **PARCELAMENTO_RURAL) if MOSTRAR_PARCELAS_RURAIS else []


def resumo_rural(res):
    """Frase única do resultado rural, para a região viva (A03): a isenção ou o valor primeiro, depois as parcelas."""
    isencao = res["isencao"]
    sem = fmt_brl(res["valor_sem_isencao"])
    if isencao["isento"]:
        return f"Resultado: isento pela minuta ({isencao['artigo']}). Sem a isenção, o valor total anual seria de {sem}."
    parcelas = (f"captação {fmt_brl(res['captacao'])}, consumo {fmt_brl(res['consumo'])} e "
                f"lançamento {fmt_brl(res['lancamento'])}")
    mensais = parcelas_mensais(res)
    if mensais:   # as parcelas mensais primeiro, como na tela
        texto = (f"Resultado: {len(mensais)} parcelas mensais de {fmt_brl(mensais[0][1])}, de {mensais[0][0].lower()} "
                 f"a {mensais[-1][0].lower()}, e valor total anual de {fmt_brl(res['total'])} ({parcelas})")
    else:
        texto = f"Resultado: valor total anual de {fmt_brl(res['total'])} ({parcelas})"
    if isencao["parcial"]:
        return texto + f", com isenção parcial por outorga. Sem a isenção, seria de {sem}."
    return texto + f". Preço percebido por m³ captado: {fmt_brl(res['preco_percebido'], 4)}."


APLICACAO_DO_LIMIAR = {"usuario": "à soma das captações do usuário", "outorga": "a cada outorga de captação"}


def resultado_rural(res, urbano=None):
    """
    Resultado da simulação rural: valor, valor sem a isenção, preço percebido por m³, isenção e parcelas cobradas.
    urbano: o mesmo uso pela regra urbana da bacia (análise da seção 5.3), quando a comparação está ligada e completa.
    """
    isencao = res["isencao"]
    st.subheader("Resultado da simulação rural (minuta em discussão)")
    mensais = parcelas_mensais(res)
    preco = fmt_brl(res["preco_percebido"], 4)
    tem_isencao = isencao["isento"] or isencao["parcial"]
    if mensais:   # a parcela mensal e o total anual em destaque; embaixo, os preços percebidos
        n, primeira, ultima = len(mensais), mensais[0][1], mensais[-1][1]
        de, ate = mensais[0][0].lower(), mensais[-1][0].lower()
        colunas = st.columns(3 if tem_isencao else 2)
        colunas[0].metric("Parcela mensal", md(f"{n}x – {fmt_brl(primeira)} :small[({de} a {ate})]"), border=True)
        colunas[1].metric("Valor total anual", fmt_brl(res["total"]), border=True)
        if tem_isencao:
            colunas[2].metric("Valor anual sem a isenção", fmt_brl(res["valor_sem_isencao"]), border=True)
        acerto = f" A última parcela, de {fmt_brl(ultima)}, acerta os centavos." if ultima != primeira else ""
        st.caption(md(
            f"Simulação do lote do ano, gerado por volta de {de}: o valor anual dividido em {n} parcelas mensais iguais, "
            f"de {de} a {ate}.{acerto} É uma hipótese desta simulação, e não regra da minuta. O valor total anual é "
            f"{fmt_brl(res['total'])}."
        ))
        # Cartões menores (o valor em fonte menor vem do CSS do cabeçalho): o preço percebido rural e, ao lado, o da
        # regra urbana, que sai da análise da comparação (seção 5.3)
        with st.container(key="rural_precos"):
            colunas = st.columns(3)
            colunas[0].metric("Preço percebido por m³ captado", preco, border=True)
            if MOSTRAR_COMPARACAO_URBANA:
                colunas[1].metric("Preço percebido pela regra urbana",
                                  fmt_brl(_preco_por_m3(urbano), 4) if urbano else None, border=True)
    else:
        colunas = st.columns(3 if tem_isencao else 2)
        colunas[0].metric("Valor total anual", fmt_brl(res["total"]), border=True)
        if tem_isencao:
            colunas[1].metric("Valor anual sem a isenção", fmt_brl(res["valor_sem_isencao"]), border=True)
        colunas[-1].metric("Preço percebido por m³ captado", preco, border=True)
    texto = ("Preço percebido por m³ captado = (captação + consumo, sem a isenção) ÷ volume captado. Referência do "
             f"estudo da SP Águas para a irrigação: {fmt_brl(res['preco_percebido_estudo'], 4)}/m³ "
             f"({fmt_num(res['preco_percebido_estudo'], 7)}, slide 12).")
    if mensais and MOSTRAR_COMPARACAO_URBANA:
        if urbano:
            texto += (f" Pela regra urbana, a mesma conta com o {regra['decreto']}, a cobrança urbana vigente na "
                      "bacia, como se o uso fosse urbano.")
        elif comparar_urbano:
            texto += f" Para ver o preço pela regra urbana, preencha nos cartões os campos do {regra['decreto']}."
        else:
            texto += (" Para ver o preço pela regra urbana, ligue a chave \"Comparar com a regra urbana da bacia\", "
                      "acima dos cartões.")
    st.caption(md(texto))

    icone = (":material/verified:" if isencao["isento"] else ":material/rule:" if isencao["parcial"]
             else ":material/payments:")
    with st.container(border=True):
        st.markdown(md(f"{icone} **Isenção:** {isencao['texto']}"))
        st.caption(md(
            f"Limiar de isenção de {texto_limiar(isencao['limiar_m3_dia'])}, aplicado "
            f"{APLICACAO_DO_LIMIAR[isencao['modo']]}. A isenção olha a vazão de captação máxima outorgada, e não o "
            "volume do ano."
        ))

    col_vcc, col_vcco = st.columns(2)
    col_vcl, col_fc = st.columns(2)
    col_vcc.metric("Captação (VCC)", fmt_brl(res["captacao"]), border=True)
    col_vcco.metric("Consumo (VCCo)", fmt_brl(res["consumo"]), border=True)
    col_vcl.metric("Lançamento (VCL)", fmt_brl(res["lancamento"]), border=True)
    col_fc.metric("Fator de consumo médio (FC)", fmt_num(res["FC"], 4), border=True)
    fcs = "; ".join(f"{f['item']}, {fmt_num(f['fc'] * 100, 1)}% ({f['finalidade_rural'].lower()}, {f['origem']})"
                    for f in res["fc_por_item"])
    st.caption(md("Parcelas cobradas, já depois da isenção."
                  + (f" Fator de consumo de cada captação: {fcs}. O fator médio pondera pelo volume captado."
                     if fcs else "")))
    for aviso in res["avisos"]:
        st.warning(md(aviso), icon=":material/report:")
    st.caption(md(
        f"Fundamentação: {MINUTA_RURAL['nome'].lower()} ({MINUTA_RURAL['versao']}), em discussão na CT-COB do "
        f"Conselho Estadual de Recursos Hídricos, e premissas do cenário \"{res['cenario']}\" ({res['cenario_fonte']}). "
        "A minuta não fixa valor mínimo de boleto nem parcelamento. Simulação para discussão, sem valor de cobrança."
    ))


def resumo_do_resultado(res, atual=None):
    """Frase única do resultado, para a região viva (A03): o valor total primeiro, depois as parcelas."""
    parcelas = (f"captação {fmt_brl(res['captacao'])}, consumo {fmt_brl(res['consumo'])} e "
                f"lançamento {fmt_brl(res['lancamento'])}")
    if atual is None:
        return f"Resultado: valor total anual de {fmt_brl(res['total'])} ({parcelas})."
    dif = res["total"] - atual["total"]
    sentido = "a mais" if dif > 0 else "a menos" if dif < 0 else "de diferença"
    return (f"Resultado com a revisão proposta: valor total anual de {fmt_brl(res['total'])} ({parcelas}). "
            f"Hoje: {fmt_brl(atual['total'])}, ou seja, {fmt_brl(abs(dif))} {sentido}.")


if rural:
    try:
        resultado = calcular_rural(bacia_selecionada, captacoes, lancamentos, premissas=premissas_rural,
                                   caf=caf_rural)
    except ValueError as erro:
        aviso_resultado.error(f"Erro no cálculo rural: {erro}")
        st.stop()
    # Análise da seção 5.3: o mesmo uso pela regra urbana, para o quadro da comparação e o preço percebido urbano
    urbano = (calcular(bacia_selecionada, captacoes, lancamentos)
              if comparar_urbano and not PENDENTES_COMPARACAO else None)
    mostrar_resumo(resumo_rural(resultado))
    resultado_rural(resultado, urbano)
    if comparar_urbano:   # análise da seção 5.3
        comparacao_urbana(resultado, urbano)
else:
    resultado = calcular(bacia_selecionada, captacoes, lancamentos, mineracoes=mineracoes, cenario=cenario,
                         ano_aplicacao=ano_aplicacao, modo_transicao=modo_transicao)
    if simular_proposta:
        # O decreto vigente pode não ter regra de mineração (ex.: Serra da Mantiqueira): o item fica fora da comparação
        min_atual = mineracoes if regra_atual["mineracao"] == regra["mineracao"] else []
        if mineracoes and not min_atual:
            st.info(md(f"O {regra_atual['decreto']} não tem a mesma regra de mineração de areia da revisão: na comparação "
                       "com o valor de hoje, os itens de mineração não foram incluídos."), icon=":material/info:")
        atual = calcular(bacia_selecionada, captacoes, lancamentos, mineracoes=min_atual)
        diferenca = resultado["total"] - atual["total"]
        variacao = f" ({'+' if diferenca >= 0 else '−'}{fmt_num(abs(diferenca) / atual['total'] * 100, 1)}%)" \
            if atual["total"] > 0 else ""
        mostrar_resumo(resumo_do_resultado(resultado, atual))
        st.subheader(f"Resultado com a revisão proposta · {regra['ano_aplicacao']}º ano de aplicação")
        col_novo, col_hoje = st.columns(2)
        col_novo.metric(
            "Valor total anual com a revisão", fmt_brl(resultado["total"]), border=True,
            delta=f"{'+' if diferenca >= 0 else '−'}{fmt_brl(abs(diferenca))}{variacao} em relação a hoje",
            delta_color="inverse", help="Simulação: só vale depois da publicação do decreto do Governador.",
        )
        col_hoje.metric(f"Valor total anual hoje ({regra_atual['decreto']})", fmt_brl(atual["total"]), border=True,
                        help="Mesmos dados, calculados com o decreto em vigor.")
    else:
        mostrar_resumo(resumo_do_resultado(resultado))
        st.subheader("Resultado da simulação anual")
        st.metric("Valor total anual", fmt_brl(resultado["total"]), border=True,
                  help="Soma das parcelas de captação, consumo e lançamento.")
    col_vcc, col_vcco = st.columns(2)
    col_vcl, col_fc = st.columns(2)
    col_vcc.metric("Captação (VCC)", fmt_brl(resultado["captacao"]), border=True,
                   help="Volume captado × preço unitário final de captação.")
    col_vcco.metric("Consumo (VCCo)", fmt_brl(resultado["consumo"]), border=True,
                    help="Fator de consumo × volume captado × preço unitário final de consumo.")
    col_vcl.metric("Lançamento (VCL)", fmt_brl(resultado["lancamento"]), border=True,
                   help="Carga de DBO lançada × preço unitário final de lançamento.")
    col_fc.metric("Fator de consumo (FC)", fmt_num(resultado["FC"], 4), border=True,
                  help="(Volume captado total − volume lançado total) ÷ volume captado total.")
    if resultado["detalhes_min"]:
        st.caption(md(f"Captação e consumo incluem {fmt_brl(resultado['mineracao'])} da mineração de areia, cobrada à "
                      "parte e fora do fator de consumo."))

    if resultado["total"] > 0:
        parcelas = regra.get("max_parcelas", 12)
        st.caption(md(f"Pagamento em parcela única ou em até {parcelas} parcelas mensais, sem parcela abaixo do valor "
                      f"mínimo de cobrança da bacia: {regra['valor_minimo_texto']} As faturas seguem os dias de uso de "
                      "cada mês" + (": veja o lote de cobrança mensal abaixo." if MOSTRAR_LOTE_SISCOB else ".")))
    for aviso in resultado["avisos"]:
        st.warning(md(aviso), icon=":material/report:")
    st.caption(md(f"Fundamentação: [{regra['decreto_extenso']}]({regra['link_norma']}), Lei nº 12.183/2005 e "
                  "Decreto nº 50.667/2006. Simulação sem valor de boleto; a cobrança oficial é feita pela SP Águas com "
                  "os dados da outorga."))

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 7.1. LOTE DE COBRANÇA MENSAL (SisCob 2.0)
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
NOMES_ITEM = {"cap": "Captação", "lanc": "Lançamento", "min": "Mineração"}


def _rotulo_mes(mes):
    return MESES[mes - 1]


def _csv(linhas):
    """Tabela em CSV no padrão brasileiro (ponto e vírgula, com BOM para o Excel abrir os acentos)."""
    return pd.DataFrame(linhas).to_csv(sep=";", index=False).encode("utf-8-sig")


def ajustes_do_lote(tipo, itens):
    """Meses de uso e vigência de cada outorga no lote. Devolve os itens com os campos do lote."""
    ajustados = []
    for i, item in enumerate(itens, start=1):
        k = f"lote_{slug}_{tipo}_{i}_"
        meses_ano = int(item.get("meses_ano") or 12)
        with st.container(border=True):
            nomes = nomes_do_cartao(tipo, i, item.get("nome"))
            st.markdown(f"**{nomes['titulo']}**")
            colunas = st.columns([2, 1, 1])
            # A14: o nome de cada campo diz a qual outorga pertence; A13: as ajudas viram texto visível (abaixo)
            meses_uso = colunas[0].multiselect(
                f"Meses de uso {nomes['de']}", list(range(1, 13)), default=list(range(1, meses_ano + 1)),
                format_func=_rotulo_mes, key=k + "meses")
            inicio = colunas[1].date_input(f"Início da vigência {nomes['de']}", value=None, key=k + "inicio",
                                           format="DD/MM/YYYY")
            fim = colunas[2].date_input(f"Fim da vigência {nomes['de']}", value=None, key=k + "fim",
                                        format="DD/MM/YYYY")
            st.caption("Só os dias dos meses marcados entram no lote. Deixe a vigência em branco se a outorga vale "
                       "do início ao fim do lote.")
            # A04: avisos com papel de alerta e o texto começando por "Atenção" ou "Erro"
            if len(meses_uso) != meses_ano:
                st.warning(f"Atenção {nomes['em']}: o cartão informa {meses_ano} meses de uso no ano e aqui há "
                           f"{len(meses_uso)} marcados. O lote cobra os dias dos meses marcados.")
            if inicio and fim and fim < inicio:
                st.error(f"Erro {nomes['em']}: o fim da vigência é anterior ao início, e a outorga fica sem cobrança "
                         "no lote.")
        ajustados.append({**item, "meses_uso": sorted(meses_uso), "vigencia_inicio": inicio, "vigencia_fim": fim})
    return ajustados


# Simulador do lote mensal do SisCob 2.0: escondido do usuário geral por enquanto (decisão de 06/11/2026). O código
# fica pronto; para mostrar de novo, rode com a variável de ambiente SP_AGUAS_LOTE_SISCOB=1 (ou mude o padrão de
# MOSTRAR_LOTE_SISCOB, no início do arquivo). Os testes do lote ligam a variável.
def simulador_lote_siscob():
    with st.expander("Lote de cobrança mensal (SisCob 2.0)", icon=":material/receipt_long:"):
        st.markdown(md(
            "Simula como o SisCob 2.0 divide a cobrança nas faturas do lote anual, **outorga por outorga**: cada mês é "
            "cobrado pelos dias de uso (valor anual ÷ dias de uso no ano × dias de uso no mês), do mês de geração do lote "
            "até dezembro ou até o fim da vigência da outorga. Fevereiro tem 29 dias nos anos bissextos (366 dias no ano)."
        ))
        anos_lote = list(range(UFESP_ANO, UFESP_ANO + 5))
        hoje = datetime.date.today()
        with st.container(horizontal=True, vertical_alignment="bottom"):
            ano_lote = st.selectbox("Ano do lote", anos_lote, key=f"lote_ano_{slug}",
                                    index=anos_lote.index(hoje.year) if hoje.year in anos_lote else 0)
            mes_lote = st.selectbox("Mês de geração do lote", list(range(1, 13)), format_func=_rotulo_mes,
                                    key=f"lote_mes_{slug}", help="O lote cobra do 1º dia deste mês até dezembro.")
            base_lote = st.segmented_control(
                "Regras da bacia aplicadas sobre", list(BASES_LOTE), default="ano", required=True, key=f"lote_base_{slug}",
                format_func={"ano": "Valor anual", "periodo": "Período do lote"}.get,
                help=f"Valor anual: {BASES_LOTE['ano']}. Período do lote: {BASES_LOTE['periodo']}. A escolha muda o "
                     "teto do lançamento (3 × captação + consumo), o fator de consumo e a comparação com o valor mínimo.")
        parcelar_igual = st.toggle(
            "Parcelar igualmente em todos os meses do lote", key=f"lote_igual_{slug}",
            help="Para uso sazonal ou cobranças altas: divide o valor do lote em parcelas iguais nos meses de vigência do "
                 "lote, respeitando o limite de parcelas do decreto e o valor mínimo da bacia.")
        ufesp_lote = None
        if ano_lote not in UFESP_POR_ANO:
            ufesp_lote, erro = campo_numero(
                "UFESP (R$)", f"lote_ufesp_{slug}", f"de {ano_lote}", minimo=0.01,
                nota=md(f"Usada no teto do PUF de captação e nos mínimos fixados em UFESP. Em branco, vale a de "
                        f"{UFESP_ANO} ({fmt_brl(UFESP)})."))
            if erro:
                st.error(f"Erro: {erro}")

        st.markdown("**Meses de uso e vigência de cada outorga**")
        itens_lote = {tipo: ajustes_do_lote(tipo, itens)
                      for tipo, itens in (("cap", captacoes), ("lanc", lancamentos), ("min", mineracoes))}
        lote = lote_mensal(bacia_selecionada, itens_lote["cap"], itens_lote["lanc"], itens_lote["min"], ano=ano_lote,
                           mes_inicio=mes_lote, base=base_lote, parcelar_igual=parcelar_igual, ufesp=ufesp_lote,
                           cenario=cenario, ano_aplicacao=ano_aplicacao,
                           modo_transicao=modo_transicao)

        periodo_lote = f"{_rotulo_mes(mes_lote).lower()} a dezembro de {ano_lote}"
        col_lote, col_boletos, col_anual = st.columns(3)
        col_lote.metric(f"Valor do lote ({periodo_lote})", fmt_brl(lote["total"]), border=True,
                        help="Soma dos boletos de todas as outorgas no período do lote.")
        col_boletos.metric("Boletos no lote", lote["boletos"], border=True,
                           help="Total de faturas emitidas, somando todas as outorgas.")
        col_anual.metric("Valor anual de referência", fmt_brl(sum(o["valor_anual"] for o in lote["outorgas"])),
                         border=True, help="Valor anual das outorgas, calculado com as regras da bacia.")
        if lote["bissexto"]:
            st.caption(f"{ano_lote} é bissexto: fevereiro tem 29 dias e a outorga de ano cheio é cobrada por 366 dias.")
        for aviso in lote["avisos"]:
            st.warning(md(aviso), icon=":material/report:")

        st.markdown("##### Uso cobrado mês a mês")
        linhas_mes = []
        for m in lote["meses_lote"]:
            linha = {"Mês": f"{_rotulo_mes(m)}/{ano_lote}", "Dias do mês": calendar.monthrange(ano_lote, m)[1]}
            for o in lote["outorgas"]:
                linha[f"{o['item']} (dias)"] = o["meses"][m]["dias"]
                linha[o["item"]] = fmt_brl(o["meses"][m]["valor"])
            linha["Total do mês"] = fmt_brl(sum(o["meses"][m]["valor"] for o in lote["outorgas"]))
            linhas_mes.append(linha)
        st.dataframe(pd.DataFrame(linhas_mes), hide_index=True, alt="Uso cobrado em cada mês do lote, por outorga")
        referencia = "valor anual" if base_lote == "ano" else "valor no período do lote"
        for o in lote["outorgas"]:
            st.caption(md(
                f"**{o['item']}:** {referencia} de {fmt_brl(o['valor_base'])} ÷ {fmt_num(o['dias_base'], 1)} dias de uso = "
                f"{fmt_brl(o['diario'], 4)} por dia × {o['dias_lote']} dias de uso no lote = "
                f"{fmt_brl(sum(v['valor'] for v in o['meses'].values()))}."
            ))

        st.markdown("##### Boletos")
        linhas_boleto = [{
            "Outorga": o["item"], "Boleto": f"{n} de {len(o['parcelas'])}",
            "Mês de referência": f"{_rotulo_mes(p['mes'])}/{ano_lote}", "Valor": fmt_brl(p["valor"]),
        } for o in lote["outorgas"] for n, p in enumerate(o["parcelas"], start=1)]
        if linhas_boleto:
            st.dataframe(pd.DataFrame(linhas_boleto), hide_index=True, alt="Boletos do lote, por outorga")
        else:
            st.caption("Nenhum boleto no período do lote.")
        for o in lote["outorgas"]:
            st.caption(md(f"**{o['item']}:** {o['regra_parcelas']}"))
        st.caption(md(
            f"Valor mínimo da bacia em {ano_lote}: {fmt_brl(lote['minimo'])} · até {lote['max_parcelas']} parcelas "
            f"({regra['decreto']}). Simulação sem valor de boleto: o lote oficial é gerado pela SP Águas no SisCob 2.0."
        ))
        with st.container(horizontal=True):
            st.download_button("Baixar uso mês a mês (CSV)", _csv(linhas_mes), file_name=f"lote_{slug}_{ano_lote}_meses.csv",
                               mime="text/csv", icon=":material/download:", key=f"lote_csv_meses_{slug}")
            st.download_button("Baixar boletos (CSV)", _csv(linhas_boleto or [{}]),
                               file_name=f"lote_{slug}_{ano_lote}_boletos.csv", mime="text/csv",
                               icon=":material/download:", key=f"lote_csv_boletos_{slug}")


if MOSTRAR_LOTE_SISCOB and not rural:   # o lote do SisCob 2.0 é da cobrança vigente (urbana)
    simulador_lote_siscob()

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 7.2. MEMÓRIA DE CÁLCULO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _coef_rural(valor):
    """Coeficiente com duas casas, ou três quando a premissa tem três (X7 = 0,214)."""
    return fmt_num(valor, 3) if round(valor, 2) != round(valor, 3) else fmt_coef(valor)


def memoria_rural(res):
    """Memória de cálculo da simulação rural: premissas, captação, consumo por finalidade, lançamento e isenção."""
    p = res["premissas"]
    herdado = p["coeficientes_bacia"] == "herdados"
    if herdado:
        coefs_cap = sorted({c["coef"] for c in regra["campos_cap"].values()} | set(regra["fixos_cap"])
                           | ({"X5"} if regra["x5"] else set()) | {"X7", "X12"}, key=lambda c: int(c[1:]))
        coefs_lanc = sorted({c["coef"] for c in regra["campos_lanc"].values()} | {"Y3", "Y9"},
                            key=lambda c: int(c[1:]))
    else:
        coefs_cap, coefs_lanc = ["X7", "X12"], ["Y9"]
    tetos, isencao, sem = res["tetos"], res["isencao"], res["sem_isencao"]
    estudo = CENARIOS_RURAIS[CENARIO_RURAL_PADRAO]["premissas"]

    with st.expander("Memória de cálculo passo a passo", icon=":material/fact_check:"):
        st.markdown("##### 0. Premissas do cenário rural")
        st.dataframe(tabela_premissas(p, regra), hide_index=True,
                     alt="Premissas do cenário rural usadas no cálculo, com a origem de cada uma")
        st.caption(md(f"Cenário: {res['cenario']} ({res['cenario_fonte']})."
                      + ("" if herdado else " Coeficientes neutros: os X e Y que não aparecem nas tabelas valem 1,00.")))

        st.markdown(md(f"##### 1. Captação · PUB aplicado = {fmt_brl(res['pubs_aplicados']['cap'], 5)}/m³"))
        if res["detalhes_cap"]:
            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "Finalidade": d["finalidade_rural"],
                "Captação máxima (m³/dia)": fmt_num(d["vazao_dia"]),
                "Isenção": "isenta" if d["isento"] else "cobrada",
                "Vol. outorgado (m³/ano)": fmt_num(d["v_out"]),
                "Vol. medido (m³/ano)": fmt_num(d["v_med"]),
                "KOUT / KMED": f"{fmt_num(d['kout'], 1)} / {fmt_num(d['kmed'], 1)}",
                "V_CAP (m³/ano)": fmt_num(d["v_cap"]),
                **{c: _coef_rural(d["coefs"][c]) for c in coefs_cap},
                "PUF (R$/m³)": fmt_brl(d["puf_cap"], 5) + (" (teto)" if d["puf_limitado"] else ""),
                "VCC calculado": fmt_brl(d["vcc"]),
                "VCC cobrado": fmt_brl(d["valor_cobrado"]),
            } for d in res["detalhes_cap"]]), hide_index=True, alt="Memória de cálculo da captação rural")
            st.caption(md(f"Teto do PUF de captação ({ART['teto_puf_cap']}, da minuta): 0,001078 × UFESP "
                          f"({fmt_brl(tetos['ufesp'])}) = {fmt_brl(tetos['puf_cap'], 5)}/m³. X7: finalidade do uso "
                          "(rural); X12: práticas de conservação do solo e da água."))
            for d in res["detalhes_cap"]:   # sazonalidade: a outorga mês a mês de cada captação
                if d.get("meses"):
                    st.caption(md(f"Sazonalidade de {d['item']}: volume outorgado = soma dos meses = "
                                  f"{fmt_num(d['v_out'])} m³/ano; captação máxima = a do mês de maior vazão × horas, "
                                  f"{fmt_num(d['vazao_dia'])} m³/dia."))
                    st.dataframe(pd.DataFrame([{
                        "Mês": m["mes"],
                        "Vazão (m³/h)": fmt_num(m["vazao"]),
                        "Horas por dia": fmt_num(m["horas_dia"]),
                        "Dias de uso": fmt_num(m["dias"], 0),
                        "Captação (m³/dia)": fmt_num(m["m3_dia"]),
                        "Volume (m³)": fmt_num(m["volume"]),
                    } for m in d["meses"]]), hide_index=True, alt=f"Sazonalidade de {d['item']}: a outorga mês a mês")
        else:
            st.caption("Nenhuma captação informada.")

        st.markdown(md(f"##### 2. Consumo · PUB aplicado = {fmt_brl(res['pubs_aplicados']['cons'], 5)}/m³"))
        st.markdown(
            f"- Volume captado total: **{fmt_num(res['VCAPT'])} m³/ano**\n"
            f"- Volume lançado total: **{fmt_num(res['V_LANCT'])} m³/ano**\n"
            f"- Irrigação: FC = **{fmt_num(res['fc_irrigacao'] * 100, 1)}%** ({ART['fc_irrigacao']}, da minuta)\n"
            f"- Demais finalidades: FC = ({fmt_num(res['VCAPT'])} − {fmt_num(res['V_LANCT'])}) ÷ "
            f"{fmt_num(res['VCAPT'])} = **{fmt_num(res['fc_formula'], 4)}** ({ART['fc_formula']}, da minuta)"
        )
        if res["detalhes_cons"]:
            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "Finalidade": d["finalidade_rural"],
                "FC": f"{fmt_num(d['fc'] * 100, 1)}%",
                "V_CONS (m³/ano)": fmt_num(d["v_cons"]),
                **{f"{c} (consumo)": _coef_rural(v) for c, v in d["coefs"].items()},
                "X7": _coef_rural(p["x7"]),
                "X12": _coef_rural(p["x12"]),
                "PUF (R$/m³)": fmt_brl(d["puf_cons"], 5) + (" (teto)" if d["puf_limitado"] else ""),
                "VCCo calculado": fmt_brl(d["vcco"]),
                "VCCo cobrado": fmt_brl(d["valor_cobrado"]),
            } for d in res["detalhes_cons"]]), hide_index=True, alt="Memória de cálculo do consumo rural")
            st.caption(md(f"Teto do PUF de consumo ({ART['teto_puf_cons']}, da minuta): 0,002156 × UFESP "
                          f"({fmt_brl(tetos['ufesp'])}) = {fmt_brl(tetos['puf_cons'], 5)}/m³."))

        st.markdown(md(f"##### 3. Lançamento de carga orgânica · PUB aplicado = "
                       f"{fmt_brl(res['pubs_aplicados']['dbo'], 5)}/kg de DBO"))
        if res["detalhes_lanc"]:
            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "Vol. lançado (m³/ano)": fmt_num(d["v_lanc"]),
                "DBO (mg/L)": fmt_num(d["dbo"]),
                "Carga (kg/ano)": fmt_num(d["carga_kg"]),
                **{c: _coef_rural(d["coefs"][c]) for c in coefs_lanc},
                "PUF (R$/kg)": fmt_brl(d["puf_dbo"], 5),
                "VCL calculado": fmt_brl(d["vcl"]),
                "VCL cobrado": fmt_brl(d["valor_cobrado"]),
                "Padrão de DBO": "atende" if d["atende_padrao"] else "não atende",
            } for d in res["detalhes_lanc"]]), hide_index=True, alt="Memória de cálculo do lançamento rural")
            st.caption(f"Carga (kg/ano) = DBO (mg/L) ÷ 1.000 × volume lançado (m³/ano) ({ART['carga']}, da minuta). "
                       "Nos dois primeiros anos, só a DBO é cobrada. Y9: práticas de conservação do solo e da água.")
            teto = (f"Teto do {ART['teto_lancamento']} da minuta = 3 × (captação + consumo de todos os usos do "
                    f"empreendimento) = {fmt_brl(res['teto_lancamento'])}; lançamento calculado = "
                    f"{fmt_brl(res['lancamento_bruto'])}.")
            if res["lancamento_limitado"]:
                st.caption(md(teto + " Todos os lançamentos atendem ao padrão de DBO, então vale o teto."))
            elif res["teto_lancamento_excedido"]:
                st.caption(md(teto + f" O teto não se aplica, porque {', '.join(res['lancamentos_fora_do_padrao'])} "
                                     "não atende ao padrão de DBO: o lançamento é cobrado integralmente."))
        else:
            st.caption("Nenhum lançamento informado.")

        st.markdown("##### 4. Isenção e preço percebido por m³ captado")
        st.markdown(md(
            f"- {isencao['texto']}\n"
            f"- Sem a isenção: captação {fmt_brl(sem['captacao'])} + consumo {fmt_brl(sem['consumo'])} + lançamento "
            f"{fmt_brl(sem['lancamento'])} = **{fmt_brl(sem['total'])}**\n"
            f"- Valor cobrado, depois da isenção: **{fmt_brl(res['total'])}**\n"
            f"- Preço percebido por m³ captado = ({fmt_brl(sem['captacao'])} + {fmt_brl(sem['consumo'])}) ÷ "
            f"{fmt_num(res['VCAPT'])} m³ = **{fmt_brl(res['preco_percebido'], 7)}/m³**. Referência do estudo: "
            f"{fmt_brl(res['preco_percebido_estudo'], 7)}/m³ ({fmt_num(estudo['pub_cap'], 2)} × "
            f"{fmt_num(estudo['x7'], 3)} + {fmt_num(estudo['pub_cons'], 2)} × {fmt_num(estudo['fc_irrigacao'], 2)} × "
            f"{fmt_num(estudo['x7'], 3)}, slide 12)."
        ))

        st.info(
            "1. **Agricultura familiar:** quem está inscrito no CAF fica isento (art. 5º, II, da minuta).\n"
            "2. **Outorga ajustada ao uso:** a isenção por porte olha a vazão de captação máxima outorgada. Uma outorga "
            "muito acima do uso real pode tirar o usuário da faixa de isenção.\n"
            "3. **Boas práticas:** conservação do solo e uso eficiente da água podem dar desconto pelos coeficientes "
            "X12 e Y9, quando o comitê definir os critérios (art. 12, § 5º, da minuta).\n"
            "4. **Devolução de água:** fora da irrigação, quanto mais água volta ao rio, menor o fator de consumo.",
            icon=":material/lightbulb:", title="O que pode reduzir o valor na proposta rural",
        )


if rural:
    memoria_rural(resultado)
else:
    coefs_cap = sorted({c["coef"] for c in regra["campos_cap"].values()}
                       | set(regra["fixos_cap"]) | ({"X5"} if regra["x5"] else set()),
                       key=lambda c: int(c[1:]))
    coefs_lanc = sorted({c["coef"] for c in regra["campos_lanc"].values()} | {"Y3"}, key=lambda c: int(c[1:]))

    with st.expander("Memória de cálculo passo a passo", icon=":material/fact_check:"):
        st.markdown(md(f"##### 1. Captação · PUB aplicado = {fmt_brl(resultado['pubs_aplicados']['cap'], 5)}/m³"))
        if resultado["detalhes_cap"]:
            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "Vol. outorgado (m³/ano)": fmt_num(d["v_out"]),
                "Vol. medido (m³/ano)": fmt_num(d["v_med"]),
                "KOUT / KMED": f"{fmt_num(d['kout'], 1)} / {fmt_num(d['kmed'], 1)}",
                "V_CAP (m³/ano)": fmt_num(d["v_cap"]),
                **{c: fmt_coef(d["coefs"][c]) for c in coefs_cap},
                "PUF (R$/m³)": fmt_brl(d["puf_cap"], 5) + (" (teto)" if d["puf_limitado"] else ""),
                "VCC": fmt_brl(d["vcc"]),
            } for d in resultado["detalhes_cap"]]), hide_index=True, alt="Memória de cálculo da captação")
            st.caption(md(f"Teto do PUF de captação em {UFESP_ANO}: 0,001078 × UFESP ({fmt_brl(UFESP)}) = "
                          f"{fmt_brl(TETO_PUF_CAP, 5)}/m³."))
            pocos = [d["item"] for d in resultado["detalhes_cap"] if d.get("x2_nao_se_aplica")]
            if pocos:
                st.caption(md(f":material/info: {', '.join(pocos)}: captação subterrânea, X2 = 1,00. "
                              f"{TEXTO_X2_SUBTERRANEA}"))
        else:
            st.caption("Nenhuma captação informada.")

        st.markdown(md(f"##### 2. Consumo · PUB aplicado = {fmt_brl(resultado['pubs_aplicados']['cons'], 5)}/m³"))
        st.markdown(
            f"- Volume captado total: **{fmt_num(resultado['VCAPT'])} m³/ano**\n"
            f"- Volume lançado total: **{fmt_num(resultado['V_LANCT'])} m³/ano**\n"
            f"- FC = ({fmt_num(resultado['VCAPT'])} − {fmt_num(resultado['V_LANCT'])}) ÷ {fmt_num(resultado['VCAPT'])} "
            f"= **{fmt_num(resultado['FC'], 4)}**"
        )
        if resultado["detalhes_cons"]:
            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "V_CONS (m³/ano)": fmt_num(d["v_cons"]),
                **{f"{c} (consumo)": fmt_coef(v) for c, v in d["coefs"].items()},
                "PUF (R$/m³)": fmt_brl(d["puf_cons"], 5),
                "VCCo": fmt_brl(d["vcco"]),
            } for d in resultado["detalhes_cons"]]), hide_index=True, alt="Memória de cálculo do consumo")

        st.markdown(md(f"##### 3. Lançamento de carga orgânica · PUB aplicado = {fmt_brl(resultado['pubs_aplicados']['dbo'], 5)}/kg de DBO"))
        if resultado["detalhes_lanc"]:
            pela_afluente = any(d["pela_afluente"] for d in resultado["detalhes_lanc"])

            def _colunas_afluente(d):
                """Colunas da carga pela DBO do afluente (só aparecem quando algum lançamento a usa)."""
                if not pela_afluente:
                    return {}
                if not d["pela_afluente"]:
                    return {"Carga por": "concentração remanescente", "Cc (mg/L)": "—", "FTR × FER": "—"}
                return {"Carga por": "DBO do afluente", "Cc (mg/L)": fmt_num(d["dbo_afluente"])
                        + (" (presumida)" if d["dbo_presumida"] else ""),
                        "FTR × FER": f"{fmt_num(d['ftr_pct'], 1)}% × {fmt_num(d['fer_pct'], 1)}% = "
                                     f"{fmt_num(d['remocao_pct'], 1)}%"}

            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "Vol. lançado (m³/ano)": fmt_num(d["v_lanc"]),
                **_colunas_afluente(d),
                "DBO (mg/L)": fmt_num(d["dbo"]) + (" (presumida)" if d["dbo_presumida"] else ""),
                "Carga (kg/ano)": fmt_num(d["carga_kg"]),
                **{c: fmt_coef(d["coefs"][c]) if d["coefs_aplicados"] else "não se aplica" for c in coefs_lanc},
                "PUF (R$/kg)": fmt_brl(d["puf_dbo"], 5),
                "VCL": fmt_brl(d["vcl"]),
                "Padrão de DBO": "atende" if d["atende_padrao"] else "não atende",
            } for d in resultado["detalhes_lanc"]]), hide_index=True, alt="Memória de cálculo do lançamento")
            st.caption("Carga (kg/ano) = DBO (mg/L) ÷ 1.000 × volume lançado (m³/ano), pois 1 mg/L = 1 g/m³. "
                       "Padrão de DBO (Decreto Estadual nº 8.468/1976, art. 18): até 60 mg/L, ou remoção de pelo menos 80%.")
            if pela_afluente:
                valor = ("PUF = PUB, sem os coeficientes Y, como no requisito do SisCob 2.0; o texto do decreto "
                         "multiplica a carga pelo PUB × Y" if CARGA_AFLUENTE_SO_PUB else "PUF = PUB × coeficientes Y")
                st.caption(f"Carga pela DBO do afluente: carga = Cc ÷ 1.000 × volume lançado × (1 − FTR × FER) e {valor}. "
                           "A coluna DBO mostra a DBO que chega ao rio, Cc × (1 − FTR × FER), usada no padrão de "
                           "emissão com a remoção total FTR × FER.")
            presumidas = [d["item"] for d in resultado["detalhes_lanc"] if d["dbo_presumida"]]
            if presumidas:
                st.caption(f"DBO presumida em {', '.join(presumidas)}: sem DBO declarada, a simulação adota "
                           f"{fmt_num(DBO_PRESUMIDA_MG_L, 0)} mg/L ({FONTE_DBO_PRESUMIDA}) e remoção de 0%.")
            teto = (f"Teto do art. 11 = 3 × (captação + consumo) = {fmt_brl(resultado['teto_lancamento'])}; "
                    f"lançamento calculado = {fmt_brl(resultado['lancamento_bruto'])}.")
            if resultado["lancamento_limitado"]:
                st.caption(md(teto + " Todos os lançamentos atendem ao padrão de DBO, então vale o teto."))
            elif resultado["teto_lancamento_excedido"]:
                st.caption(md(teto + f" O teto não se aplica, porque {', '.join(resultado['lancamentos_fora_do_padrao'])} "
                                     "não atende ao padrão de DBO: o lançamento é cobrado integralmente."))
        else:
            st.caption("Nenhum lançamento informado.")

        if resultado["detalhes_min"]:
            st.markdown(md(f"##### 4. Mineração de areia (item à parte) · {texto_mineracao(regra)}"))
            st.dataframe(pd.DataFrame([{
                "Item": d["item"],
                "Q captação (m³/ano)": fmt_num(d["v_cap"]),
                "Q consumo (m³/ano)": fmt_num(d["v_cons"]),
                "Como foi calculado": d["memoria"],
                **{c: fmt_coef(d["coefs"][c]) for c in coefs_cap},
                "PUF cap. (R$/m³)": fmt_brl(d["puf_cap"], 5) + (" (teto)" if d["puf_limitado"] else ""),
                "VCC": fmt_brl(d["vcc"]),
                "PUF cons. (R$/m³)": fmt_brl(d["puf_cons"], 5),
                "VCCo": fmt_brl(d["vcco"]),
            } for d in resultado["detalhes_min"]]), hide_index=True, alt="Memória de cálculo da mineração de areia")

        st.info(
            "1. **Instale hidrômetro aceito pelo órgão outorgante:** na maioria das bacias, com medição paga-se 20% ou "
            "30% sobre o volume outorgado e o restante sobre o medido, em vez de 100% do outorgado.\n"
            "2. **Ajuste a outorga ao uso real:** nas bacias com X5, medir menos de 70% do outorgado aumenta o preço.\n"
            "3. **Melhore a ETE:** remoção de DBO acima de 95% reduz o preço do lançamento em 20% ou mais.\n"
            "4. **Reúso e devolução:** quanto mais água tratada volta ao rio, menor o fator de consumo.",
            icon=":material/lightbulb:", title="Como reduzir o valor da cobrança",
        )
