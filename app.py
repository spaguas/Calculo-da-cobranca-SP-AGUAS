# Paleta de cores SP-ÁGUAS
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
# --------------------------------------------------------


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  Bibliotecas
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import streamlit as st  # Aplicação web
import pandas as pd     # Maniplação de dados
import numpy as np      # Cálulos matemáticos
import os               # Miscelâneos

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Nome da página
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Simulador SP-ÁGUAS",
    page_icon="SP-Águas---Colorido.png",
    layout="wide",
)

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ESTILO
# A fonte (Montserrat) e o tamanho base do texto são definidos nativamente pelo Streamlit, no arquivo .streamlit/config.toml
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Montserrat', Montserrat !important;
    }

    .block-container {
        padding-top: 2.9rem;
        padding-bottom: 1rem;
        padding-left: 4rem;
        padding-right: 4rem;
        max-width: 12350px;
    }

    h1 {
        font-weight: 700 !important;
    }

    p, li, label, .stMarkdown, .stCaption {
        font-size: 16px !important;
    }
    
    [data-testid="stVerticalBlock"] {
        gap: 0.4rem !important;
    }
            
    [data-testid="stSelectbox"] [role="group"] {
        background-color: #D0D8E4 !important;
    }


    [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
        background-color: rgba(255, 43, 43, 0.4) !important;
        border: 1px solid rgba(255, 43, 43, 1) !important;
    }

    </style>
""", unsafe_allow_html=True)

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# CABEÇALHO
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
col_esq, col_logo, col_dir = st.columns([2, 0.6, 2])

with col_logo:
    if os.path.exists("SP-Águas---Colorido.png"):
        st.image("SP-Águas---Colorido.png", use_container_width=True)
    else:
        st.write("💧")  # placeholder até o arquivo do logo ser adicionado

# st.markdown(
#    "<h1 style='text-align: center;'>SP ÁGUAS - Agência de Águas do Estado de São Paulo</h1>",
#   unsafe_allow_html=True,
# )

st.markdown(
    "<p style='text-align: center;'>🔗 <a href='https://www.spaguas.sp.gov.br' target='_blank' rel='noopener noreferrer'>www.spaguas.sp.gov.br</a></p>",
    unsafe_allow_html=True,
)

st.markdown(
    "<p style='text-align: center;'>💧 Cálculo da cobrança pelo uso da água no Estado de São Paulo</p>",
    unsafe_allow_html=True,
)

# st.write("Preencha os dados abaixo para simular o valor da sua conta de água.")
# st.write('Selecione a Bacia Hidrográfica:')

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Seleção das bacias hidrográficas
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

bacias_hidrograficas = ["Aguapeí/Peixe",
                        "Alto Paranapanema",
                        "Alto Tietê",
                        "Bacia Hidrográfica da Baixada Santista",
                        "Baixo Pardo/Grande",
                        "Baixo Tietê",
                        "Litoral Norte",
                        "Médio Paranapanema",
                        "Mogi-Guaçu",
                        "Paraíba do Sul",
                        "Pardo",
                        "Piracicaba/Capivari/Jundiaí",
                        "Pontal do Paranapanema",
                        "Ribeira de Iguape/Litoral Sul",
                        "São José dos Dourados",
                        "Sapucaí-Mirim/Grande",
                        "Serra da Mantiqueira",
                        "Sorocaba/Médio Tietê",
                        "Tietê/Batalha",
                        "Tietê/Jacaré",
                        "Turvo/Grande",]

bacia_selecionada = st.selectbox(
    "Bacia Hidrográfica",
    bacias_hidrograficas,
    index=None,
    placeholder="Selecione a Bacia Hidrográfica",
    label_visibility="collapsed",
)

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Preenchimento da tabela de Captação
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


# Altura de cada linha da tabela (usada tanto no row_height quanto no cálculo da altura total, pra manter os dois em sincronia).
ALTURA_LINHA = 25
LINHAS_VISIVEIS_SEM_SCROLL = 6
ALTURA_TABELA = ALTURA_LINHA * (LINHAS_VISIVEIS_SEM_SCROLL + 1) + 22

st.write("Preencha os dados para os usos de **captação**/**consumo** do empreendimento (se houver):")

tabela_uso_padrao_1 = pd.DataFrame({
    "Natureza": pd.Series(dtype="str"),
    "Classe de uso": pd.Series(dtype="str"),
    "Vazão outorgada (m³/h)": pd.Series(dtype="float"),
    "Horas/Dia": pd.Series(dtype="float"),
    "Dias/Ano": pd.Series(dtype="int"),
    "Volume anual medido (m³)": pd.Series(dtype="float"),
})


# Altura total da tabela, calculada dinamicamente para caber todas as linhas sem precisar de barra de rolagem interna.
# if "altura_tabela_uso_1" not in st.session_state:
#    st.session_state.altura_tabela_uso_1 = ALTURA_LINHA * \
#        (len(tabela_uso_padrao_1) + 3) + 46

tabela_uso_1 = st.data_editor(
    tabela_uso_padrao_1,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    height=ALTURA_TABELA,
    row_height=ALTURA_LINHA,
    key="tabela_uso_agua_1",
    column_config={
        "Natureza": st.column_config.SelectboxColumn(
            "Natureza",
            help="Natureza do corpo d'água: Superficial ou Subterrâneo",
            options=["Superficial", "Subterrâneo"],
            required=True,
            width="small",
        ),
        "Classe de uso": st.column_config.SelectboxColumn(
            "Classe de uso",
            help="A classe de uso preponderante em que estiver enquadrado o corpo d'água no local do uso ou da derivação: Classe 1, Classe 2, Classe 3 ou Classe 4 - Decreto Estadual nº 10.755/77",
            options=["Classe 1", "Classe 2", "Classe 3", "Classe 4"],
            required=True,
            width="small",
        ),
        "Vazão outorgada (m³/h)": st.column_config.NumberColumn(
            "Vazão outorgada (m³/h)",
            help="Vazão de captação outorgada em m³/h",
            min_value=0.0,
            step=0.01,
            format="%.2f",  # Número de casas decimais (2) exibidas na tabela
            required=True,
            width="small",
        ),
        "Horas/Dia": st.column_config.NumberColumn(
            "Horas/Dia",
            help="Quantidade de horas de uso de captação outorgada ao longo do dia (entre 0 e 24 horas)",
            min_value=0,
            step=0.01,
            required=True,
            width="small",
        ),
        "Dias/Ano": st.column_config.NumberColumn(
            "Dias/Ano",
            help="Quantidade de dias de uso de captação outorgada ao longo do ano (entre 0 e 365)",
            min_value=0,
            step=1,
            required=True,
            width="small",
        ),
        "Volume anual medido (m³)": st.column_config.NumberColumn(
            "Volume anual medido (m³)",
            help="Volume anual medido em m³ no ano anterior à cobrança, caso haja medição do uso de captação/consumo",
            min_value=0.0,
            step=0.01,
            format="%.2f",  # Número de casas decimais (2) exibidas na tabela
            required=True,
            width="small",
        ),
    },
)

# Atualiza a altura salva com base na quantidade atual de linhas — assim, ao adicionar ou remover uma linha, a tabela já nasce no tamanho certo na interação seguinte.
st.session_state.altura_tabela_uso_1 = ALTURA_LINHA * \
    (len(tabela_uso_1) + 3) + 46


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Preenchimento da tabela de Lançamento
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


st.write("Preencha os dados para os usos de **lançamento** do empreendimento (se houver):")

tabela_uso_padrao_2 = pd.DataFrame({
    "Classe de uso": pd.Series(dtype="str"),
    "Taxa de remoção (%)": pd.Series(dtype="str"),
    "DBO (mg/L)": pd.Series(dtype="float"),
    "Vazão outorgada (m³/h)": pd.Series(dtype="float"),
    "Horas/Dia": pd.Series(dtype="float"),
    "Dias/Ano": pd.Series(dtype="int"),
    "Volume anual medido (m³)": pd.Series(dtype="float")
})


# Altura total da tabela, calculada dinamicamente para caber todas as linhas sem precisar de barra de rolagem interna.
# if "altura_tabela_uso_2" not in st.session_state:
#    st.session_state.altura_tabela_uso_2 = ALTURA_LINHA * \
#        (len(tabela_uso_padrao_2) + 3) + 46

tabela_uso_2 = st.data_editor(
    tabela_uso_padrao_2,
    num_rows="dynamic",
    hide_index=True,
    use_container_width=True,
    height=ALTURA_TABELA,
    row_height=ALTURA_LINHA,
    key="tabela_uso_agua_2",
    column_config={
        "Classe de uso": st.column_config.SelectboxColumn(
            "Classe de uso",
            help="Classe de uso preponderante do corpo d'água receptor: Classe 2, Classe 3 ou Classe 4",
            options=["Classe 2", "Classe 3", "Classe 4"],
            required=True,
            width="small",
        ),
        "Taxa de remoção (%)": st.column_config.SelectboxColumn(
            "Taxa de remoção (%)",
            help="A carga lançada e seu regime de variação, atendido o padrão de emissão requerido para o local (entre 0% e 100%)",
            options=["> 95% de remoção", "> 90% e ≤ 95% de remoção",
                     "> 85% e ≤ 90% de remoção", "> 80% e ≤ 85% de remoção", "≤ 80% de remoção"],
            required=True,
            width="medium",
        ),
        "DBO (mg/L)": st.column_config.NumberColumn(
            "DBO (mg/L)",
            help="Concentração de DBO em mg/L",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            required=True,
            width="small",
        ),
        "Vazão outorgada (m³/h)": st.column_config.NumberColumn(
            "Vazão outorgada (m³/h)",
            help="Vazão de lançamento outorgada em m³/h",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            required=True,
            width="medium",
        ),
        "Horas/Dia": st.column_config.NumberColumn(
            "Horas/Dia",
            help="Quantidade de horas de uso de lançamento outorgada ao longo do dia (entre 0 e 24 horas)",
            min_value=0,
            step=0.01,
            required=True,
            width="small",
        ),
        "Dias/Ano": st.column_config.NumberColumn(
            "Dias/Ano",
            help="Quantidade de dias de uso de lançamento outorgado ao longo do ano (entre 0 e 365)",
            min_value=0,
            step=1,
            required=True,
            width="small",
        ),
        "Volume anual medido (m³)": st.column_config.NumberColumn(
            "Volume anual medido (m³)",
            help="Volume anual medido em m³ no ano anterior à cobrança, caso haja medição do uso de lançamento",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            required=True,
            width="medium",
        ),
    },
)


# Atualiza a altura salva com base na quantidade atual de linhas — assim, ao adicionar ou remover uma linha, a tabela já nasce no tamanho certo na interação seguinte.
st.session_state.altura_tabela_uso_2 = ALTURA_LINHA * \
    (len(tabela_uso_2) + 3) + 46


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#
# A seção abaixo faz as considerações sobre os coeficientes de cada bacia hidrográfica. Como existe uma particularidade do cálculo da cobrança para cada bacia, uma vez que cada uma possui
# seu respectivo decreto, é necessário considerar uma função específica para cada CBH. Ademais, é necessário considerar que as colunas das tabelas para consumo e lançamento sejam diferentes
# para cada bacia.
#
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


####################################################################################################
#                                    Coeficientes Aguapeí/Peixe                                    #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |      X2, X3, X5, X7       |          X1, X13          |       X4, X6, X8-X12      |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |          Y1, Y3           |            Y4             |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                  Coeficientes Alto Paranapanema                                  #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |            X1, X2 	      |       X3, X5, X7, X13     |       X4, X6, X8-X12      |#
# Consumo	  |                 	      |      X1-X3, X5-X7, X13    |         X4, X8-X12        |#
# Lançamento  |            Y1, Y3         |             Y4	          |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#

def calcular_alto_paranapanema(tabela_captacao, tabela_lancamento):
    ################################################################################################
    # Parâmetros constantes/fixos
    ################################################################################################
    PUBCAP_ALPA = 0.009    # R$ por m³ captado
    PUBCONS_ALPA = 0.020    # R$ por m³ consumido
    PUBDBO_ALPA = 0.090     # R$ por kg de DBO lançada

    # Captação
    X3_CAP = 1.000
    X5_CAP = 1.000
    X7_CAP = 1.000
    X13_CAP = 1.000

    # Consumo
    X1_CONS = 1.000
    X2_CONS = 1.000
    X3_CONS = 1.000
    X5_CONS = 1.000
    X6_CONS = 1.000
    X7_CONS = 1.000
    X13_CONS = 1.000

    # Lançamento
    Y4_LANC = 1.000

    ################################################################################################
    # Parâmetros variáveis
    ################################################################################################
    # X1: natureza do corpo d'água

    def obter_x1(natureza):
        if natureza == "Superficial":
            return 1.000
        else:  # Subterrâneo
            return 1.050

    # X2: classe de uso do corpo d'água na captação
    def obter_x2(classe_de_uso):
        if classe_de_uso in ("Classe 1", "Classe 2"):
            return 1.000
        elif classe_de_uso == "Classe 3":
            return 0.950
        else:  # Classe 4
            return 0.900

    # Y1: classe de uso do corpo d'água receptor no lançamento
    def obter_y1(classe_de_uso):
        if classe_de_uso == "Classe 2":
            return 1.000
        elif classe_de_uso == "Classe 3":
            return 0.950
        else:  # Classe 4
            return 0.900

    # Y3: taxa de remoção da carga lançada
    def obter_y3(taxa_remocao):
        valores = {
            "> 95% de remoção": 0.800,
            "> 90% e ≤ 95% de remoção": 0.850,
            "> 85% e ≤ 90% de remoção": 0.900,
            "> 80% e ≤ 85% de remoção": 0.950,
            "≤ 80% de remoção": 1.000,
        }
        return valores[taxa_remocao]

    ################################################################################################
    # Cálculo do KOUT e do KMED
    ################################################################################################
    def obter_kout_kmed(volume_outorgado, volume_medido):
        if volume_medido <= 0:
            kout, kmed = 1, 0  # sem medição
        elif volume_outorgado > 0 and (volume_medido / volume_outorgado) > 1:
            kout, kmed = 0, 1  # volume medido excede o outorgado
        else:
            kout, kmed = 0.2, 0.8  # existe medição, dentro do limite outorgado

        return kout, kmed

    ################################################################################################
    # Calcular o PUF para captação, consumo e lançamento
    ################################################################################################
    # Captação
    def calcular_puf_cap(natureza, classe_de_uso, PUBCAP_ALPA, x3_cap, x5_cap, x7_cap, x13_cap):
        x1 = obter_x1(natureza)
        x2 = obter_x2(classe_de_uso)
        PUF_CAP = PUBCAP_ALPA * x1 * x2 * x3_cap * x5_cap * x7_cap * x13_cap
        return PUF_CAP

    # Consumo
    def calcular_puf_cons(PUBCONS_ALPA, x1_cons, x2_cons, x3_cons, x5_cons, x6_cons, x7_cons, x13_cons):
        PUF_CONS = PUBCONS_ALPA * x1_cons * x2_cons * \
            x3_cons * x5_cons * x6_cons * x7_cons * x13_cons
        return PUF_CONS

    # Lançamento
    def calcular_puf_lanc(classe_de_uso, taxa_remocao, PUBDBO_ALPA, y4_lanc):
        y1 = obter_y1(classe_de_uso)
        y3 = obter_y3(taxa_remocao)
        PUF_DBO = PUBDBO_ALPA * y1 * y3 * y4_lanc
        return PUF_DBO

    ################################################################################################
    # Calcular o Volume Captado de cada uso V_CAP
    ################################################################################################
    def calcular_v_cap(volume_outorgado, volume_medido):
        kout, kmed = obter_kout_kmed(volume_outorgado, volume_medido)
        V_CAP = volume_outorgado * kout + volume_medido * kmed
        return V_CAP

    ################################################################################################
    # Calcular o Volume Lançado de cada uso V_LANC
    ################################################################################################
    def calcular_v_lanc(volume_outorgado, volume_medido):
        if volume_medido > 0:
            V_LANC = volume_medido
        else:
            V_LANC = volume_outorgado
        return V_LANC

    ################################################################################################
    # Cálculo do pagamento anual pelo lançamento de carga poluidora VCL
    ################################################################################################
    def calcular_vcl(concentracao_dbo, v_lanc, puf_dbo):
        q_dbo = concentracao_dbo / 1000  # mg/L -> kg/m³
        VCL = q_dbo * v_lanc * puf_dbo
        return VCL

    ################################################################################################
    # Cálculo do valor do volume de captação total do empreendimento VCAPT  (e do valor a ser pago)
    ################################################################################################
    VCAPT = 0.0
    valor_captacao_total = 0.0

    for _, linha in tabela_captacao.iterrows():
        volume_outorgado = linha["Vazão outorgada (m³/h)"] * linha["Horas/Dia"] * linha["Dias/Ano"]
        volume_medido = linha["Volume anual medido (m³)"]

        v_cap = calcular_v_cap(volume_outorgado, volume_medido)
        VCAPT += v_cap

        puf_cap = calcular_puf_cap(
            linha["Natureza"], linha["Classe de uso"], PUBCAP_ALPA, X3_CAP, X5_CAP, X7_CAP, X13_CAP,)
        valor_captacao_total += v_cap * puf_cap

    ################################################################################################
    # Cálculo do valor do volume de lançamento total do empreendimento VLANCT (e do valor a ser pago)
    ################################################################################################
    V_LANCT = 0.0
    valor_lancamento_total = 0.0

    for _, linha in tabela_lancamento.iterrows():
        volume_outorgado = linha["Vazão outorgada (m³/h)"] * linha["Horas/Dia"] * linha["Dias/Ano"]
        volume_medido = linha["Volume anual medido (m³)"]

        v_lanc = calcular_v_lanc(volume_outorgado, volume_medido)
        V_LANCT += v_lanc

        puf_dbo = calcular_puf_lanc(
            linha["Classe de uso"], linha["Taxa de remoção (%)"], PUBDBO_ALPA, Y4_LANC,)
        vcl = calcular_vcl(linha["DBO (mg/L)"], v_lanc, puf_dbo)
        valor_lancamento_total += vcl

    ################################################################################################
    # Cálculo do fator de consumo FC
    ################################################################################################
    def calcular_fc(VCAPT, V_LANCT):
        if VCAPT <= 0:
            return 0.0  # sem captação declarada, não há base para calcular consumo
        FC = (VCAPT - V_LANCT) / VCAPT
        # evita fator negativo se o lançamento superar a captação
        return max(0.0, FC)

    return {
        "captacao": valor_captacao_total,
        "consumo": valor_consumo_total,
        "lancamento": valor_lancamento_total,
        "total": valor_captacao_total + valor_consumo_total + valor_lancamento_total,
    }


    ################################################################################################
    # Cálculo do volume consumido de cada uso V_CONS
    ################################################################################################
    def calcular_v_cons(FC, v_cap):
        """VCONS: volume consumido de um uso específico (item 5.2 do decreto)."""
        V_CONS = FC * v_cap
        return V_CONS

####################################################################################################
#                                      Coeficientes Alto Tietê                                     #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |                   	      |                   	      |                   	      |#
# Consumo	  |                 	      |                 	      |                 	      |#
# Lançamento  |                 	      |                 	      |                 	      |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                  Coeficientes Baixada Santista                                   #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |         X1-X3, X5         |        X6, X7, X13        |         X4, X8-X12        |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |          Y1, Y3           |            Y4             |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                 Coeficientes Baixo Pardo/Grande                                  #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |    X2, X3, X5, X7, X13    |             X1            |       X4, X6, X8-X12      |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |         Y1, Y3, Y4        |                 	      |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                     Coeficientes Baixo Tietê                                     #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |                   	      |                   	      |                   	      |#
# Consumo	  |                 	      |                 	      |                 	      |#
# Lançamento  |                 	      |                 	      |                 	      |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                    Coeficientes Litoral Norte                                    #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |                   	      |                   	      |                   	      |#
# Consumo	  |                 	      |                 	      |                 	      |#
# Lançamento  |                 	      |                 	      |                 	      |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                 Coeficientes Médio Paranapanema                                  #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |       X1-X3, X5, X7       |            X13            |                   	      |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |           Y1, Y3          |             Y4            |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                      Coeficientes Mogi-Guaçu                                     #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |         X1-X3, X5         |          X7, X13          |        X4, X8-X12         |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |             Y3            |           Y1, Y4          |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                    Coeficientes Paraíba do Sul                                   #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |     X1-X3, X5, X7, X13    |             X6            |         X4, X8-X12        |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |           Y3, Y4          |             Y2            |         Y1, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                        Coeficientes Pardo                                        #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |           X1-X3           |        X5, X7, X13        |       X4, X6, X8-X12      |#
# Consumo	  |                 	      |     X1-X3, X5, X7, X13    |         X4, X7-X12        |#
# Lançamento  |           Y1, Y3          |             Y4            |         Y1, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                             Coeficientes Piracicaba/Capivari/Jundiaí                             #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |        X1, X2, X5         |        X6, X7, X13        |         X4, X8-X12        |#
# Consumo	  |            X13            |        X1-X3, X5-X7       |         X4, X7-X12        |#
# Lançamento  |            Y3             |           Y1, Y4          |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                               Coeficientes Pontal do Paranapanema                                #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |                   	      |     X1-X3, X5, X7, X13    |       X4, X6, X8-X12      |#
# Consumo	  |                   	      |     X1-X3, X5, X6, X13    |       X4, X7, X8-X12      |#
# Lançamento  |            Y3             |           Y1, Y4          |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                            Coeficientes Ribeira de Iguape/Litoral Sul                            #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |      X1-X3, X5, X13       |          X6, X7           |         X4, X8-X12        |#
# Consumo	  |                 	      |   X1-X3, X5, X6, X7, X13  |         X4, X8-X12        |#
# Lançamento  |          Y1, Y3           |            Y4             |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                Coeficientes São José dos Dourados                                #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |           X1-X3           |        X5, X7, X13        |       X4, X6, X8-X12      |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |        X4, X8-X12         |#
# Lançamento  |           Y1, Y3          |             Y4            |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                 Coeficientes Sapucaí-Mirim/Grande                                #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |         X2, X3, X5        |        X1, X7, X13        |      X4, X6, X8-X12       |#
# Consumo	  |                 	      |   X1-X3, X5, X6, X7, X13  |        X4, X8-X12         |#
# Lançamento  |          Y1, Y3           |             Y4            |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                Coeficientes Serra da Mantiqueira                                 #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |     X1-X3, X5, X7, X13    |                   	      |      X4, X6, X8-X12       |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |        X4, X8-X12         |#
# Lançamento  |          Y3, Y4           |             Y1            |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#

####################################################################################################
#                                Coeficientes Sorocaba/Médio Tietê                                 #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |      X1-X3, X5, X13       |          X6, X7           |         X4, X8-X12        |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |           Y1, Y3          |            Y4             |           Y5-Y9           |#
# -------------------------------------------------------------------------------------------------#


####################################################################################################
#                                    Coeficientes Tietê/Batalha                                    #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |      X1, X2, X5, X7       |          X3, X13          |      X4, X6, X8-X12       |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |        X4, X8-X12         |#
# Lançamento  |          Y3, Y4           |            Y1             |                 	      |#
# -------------------------------------------------------------------------------------------------#
####################################################################################################
#                                     Coeficientes Tietê/Jacaré                                    #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |         X1, X2, X5        |      X3, X6, X7, X13      |         X4, X8-X12        |#
# Consumo	  |                           |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |             Y3            |          Y1, Y4           |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#
####################################################################################################
#                                     Coeficientes Turvo/Grande                                    #
####################################################################################################
#             -------------------------------------------------------------------------------------#
#             |  Coeficientes que variam  |     Coeficientes Fixos    |  Coeficientes não usados  |#
# -------------------------------------------------------------------------------------------------#
# Captação	  |          X2, X3           |      X1, X5, X7, X13      |      X4, X6, X8-X12       |#
# Consumo	  |                 	      |     X1-X3, X5-X7, X13     |         X4, X8-X12        |#
# Lançamento  |          Y1, Y3           |            Y4             |         Y2, Y5-Y9         |#
# -------------------------------------------------------------------------------------------------#
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Seleção da função de cálculo de acordo com a bacia hidrográfica selecionada.
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
CALCULADORAS_POR_BACIA = {
    # "Aguapeí/Peixe": calcular_aguapei_peixe,
    "Alto Paranapanema": calcular_alto_paranapanema,
    # "Alto Tietê": calcular_alto_tiete,
    # "Bacia Hidrográfica da Baixada Santista": calcular_bacia_hidrografica_da_baixada_santista,
    # "Baixo Pardo/Grande": calcular_baixo_pardo_grande,
    # "Baixo Tietê": calcular_baixo_tiete,
    # "Litoral Norte": calcular_litoral_norte,
    # "Médio Paranapanema": calcular_medio_paranapanema,
    # "Mogi-Guaçu": calcular_mogi_guacu,
    # "Paraíba do Sul": calcular_paraiba_do_sul,
    # "Pardo": calcular_pardo,
    # "Piracicaba/Capivari/Jundiaí": calcular_piracicaba_capivari_jundiai,
    # "Pontal do Paranapanema": calcular_pontal_do_paranapanema,
    # "Ribeira de Iguape/Litoral Sul": calcular_ribeira_de_iguape_litoral_sul,
    # "São José dos Dourados": calcular_sao_jose_dos_dourados,
    # "Sapucaí-Mirim/Grande": calcular_sapucai_mirim_grande,
    # "Serra da Mantiqueira": calcular_serra_da_mantiqueira,
    # "Sorocaba/Médio Tietê": calcular_sorocaba_medio_tiete,
    # "Tietê/Batalha": calcular_tiete_batalha,
    # "Tietê/Jacaré": calcular_tiete_jacare,
    # "Turvo/Grande": calcular_turvo_grande,
}


# Botão "Calcular" que dispara a função de cálculo da bacia selecionada, caso ela esteja implementada.

# Usamos duas abordagens: A primeira mostra os dados calculados no final da página, enquanto que a segunda mostra uma nova janela com os dados calculados.

###############################################################
# 1ª ABORDAGEM: Dados calculados mostrados no final da página #
###############################################################

col_esq, col_botao, col_dir = st.columns([3, 1, 3])
with col_botao:
    calcular = st.button("Calcular", type="primary",
                         icon="🧮", use_container_width=True)

if calcular:
    calculadora = CALCULADORAS_POR_BACIA.get(bacia_selecionada)
    if calculadora is None:
        if bacia_selecionada is None:
            st.error("Selecione a Bacia Hidrográfica antes de calcular.")
        else:
            st.error(
                f"Ainda não temos os coeficientes de '{bacia_selecionada}' implementados.")
    else:
        resultado = calculadora(tabela_uso_1, tabela_uso_2)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Captação", f"R$ {resultado['captacao']:,.2f}")
        col2.metric("Consumo", f"R$ {resultado['consumo']:,.2f}")
        col3.metric("Lançamento", f"R$ {resultado['lancamento']:,.2f}")
        col4.metric("Total", f"R$ {resultado['total']:,.2f}")


###############################################################
# 2ª ABORDAGEM: Dados calculados mostrados em uma nova janela #
###############################################################

# @st.dialog("Resultado do cálculo", width="medium")
# def mostrar_resultado():
#     if bacia_selecionada is None:
#         st.error("Selecione a Bacia Hidrográfica antes de calcular.")
#         return

#     calculadora = CALCULADORAS_POR_BACIA.get(bacia_selecionada)
#     if calculadora is None:
#         st.error(f"Ainda não temos os coeficientes de '{bacia_selecionada}' implementados.")
#     else:
#         resultado = calculadora(tabela_uso_1, tabela_uso_2)
#         col1, col2, col3, col4 = st.columns(4)
#         col1.metric("Captação", f"R$ {resultado['captacao']:,.2f}")
#         col2.metric("Consumo", f"R$ {resultado['consumo']:,.2f}")
#         col3.metric("Lançamento", f"R$ {resultado['lancamento']:,.2f}")
#         col4.metric("Total", f"R$ {resultado['total']:,.2f}")

# col_esq, col_botao, col_dir = st.columns([3, 1, 3])
# with col_botao:
#     if st.button("Calcular", type="primary", icon="🧮", use_container_width=True):
#         mostrar_resultado()

# # O trecho abaixo serve para centralizar a janela modal que aparece quando o botão "Calcular" é clicado.
# # Além disso, ele também altera a fonte do texto para Montserrat, que é uma fonte mais moderna e legível.
# st.markdown("""
#     <style>
#     @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap');

#     html, body, [data-testid="stAppViewContainer"] {
#         font-family: 'Montserrat', Montserrat !important;
#     }

#     .block-container {
#         padding-top: 2.9rem;
#         padding-bottom: 1rem;
#         padding-left: 4rem;
#         padding-right: 4rem;
#         max-width: 12350px;
#     }

#     h1 {
#         font-weight: 700 !important;
#     }

#     p, li, label, .stMarkdown, .stCaption {
#         font-size: 16px !important;
#     }

#     [data-testid="stSelectbox"] [role="group"] {
#         background-color: #D0D8E4 !important;
#     }

#     [data-testid="stDialog"] {
#         align-items: center !important;
#     }
#     </style>
# """, unsafe_allow_html=True)
