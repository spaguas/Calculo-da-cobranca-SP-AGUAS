import os
import streamlit as st
import pandas as pd
import numpy as np

# Nome da página
st.set_page_config(
    page_title="Calculadora SP-ÁGUAS",
    page_icon="SP-Águas---Colorido.png",
    layout="wide",
)

# ----------------------------------------------------
# ESTILO
# A fonte (Montserrat) e o tamanho base do texto são definidos nativamente pelo Streamlit, no arquivo .streamlit/config.toml
# ----------------------------------------------------
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
            
    [data-testid="stSelectbox"] [role="group"] {
        background-color: #D0D8E4 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# CABEÇALHO
# ----------------------------------------------------
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
#st.write('Selecione a Bacia Hidrográfica:')

# Seleção das bacias hidrográficas


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

#################################################################################################
# Preenchimento Captação
#################################################################################################

# Altura de cada linha da tabela (usada tanto no row_height quanto no cálculo da altura total, pra manter os dois em sincronia).
ALTURA_LINHA = 25
LINHAS_VISIVEIS_SEM_SCROLL = 6
ALTURA_TABELA = ALTURA_LINHA * (LINHAS_VISIVEIS_SEM_SCROLL + 1) + 22

st.write("Preencha os dados para os usos de **captação** do empreendimento (se houver):")

tabela_uso_padrao_1 = pd.DataFrame({
    "Tipo de uso": pd.Series(dtype="str"),
    "Vazão (m³/h)": pd.Series(dtype="float"),
    "Horas": pd.Series(dtype="float"),
    "Dias": pd.Series(dtype="int"),
    "Medição": pd.Series(dtype="str"),
    "Natureza": pd.Series(dtype="str"),
    "Classe de uso": pd.Series(dtype="str"),
})


# Altura total da tabela, calculada dinamicamente para caber todas as linhas sem precisar de barra de rolagem interna.
#if "altura_tabela_uso_1" not in st.session_state:
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
        "Tipo de uso": st.column_config.SelectboxColumn(
            "Tipo de uso",
            help="Tipo de uso: captação superficial ou subterrânea",
            options=["Captação Superficial", "Captação Subterrânea"],
            required=True,
            width="small",
        ),
        "Vazão (m³/h)": st.column_config.NumberColumn(
            "Vazão (m³/h)",
            help="Vazão de captação outorgada em m³/h",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            required=True,
            width="small",
        ),
        "Horas": st.column_config.NumberColumn(
            "Horas",
            help="Quantidade de horas de uso de captação outorgada ao longo do dia",
            min_value=0,
            step=0.01,
            required=True,
            width="small",
        ),
        "Dias": st.column_config.NumberColumn(
            "Dias",
            help="Quantidade de dias de uso de captação outorgada ao longo do mês",
            min_value=0,
            step=1,
            required=True,
            width="small",
        ),
        "Medição": st.column_config.SelectboxColumn(
            "Medição",
            help="Existência de medição de volume captado, extraído ou derivado",
            options=["Existe", "Não existe"],
            required=True,
            width="small",
        ),
        "Natureza": st.column_config.SelectboxColumn(
            "Natureza",
            help="Natureza do corpo d'água",
            options=["Superficial", "Subterrâneo"],
            required=True,
            width="medium",
        ),
        "Classe de uso": st.column_config.SelectboxColumn(
            "Classe de uso",
            help="Classe de uso preponderante em que estiver enquadrado o corpo d'água no local do uso ou da derivação",
            options=["Classe 1", "Classe 2", "Classe 3", "Classe 4"],
            required=True,
            width="small",
        ),
    },
)

# Atualiza a altura salva com base na quantidade atual de linhas — assim, ao adicionar ou remover uma linha, a tabela já nasce no tamanho certo na interação seguinte.
st.session_state.altura_tabela_uso_1 = ALTURA_LINHA * \
    (len(tabela_uso_1) + 3) + 46


#################################################################################################
# Preenchimento Lançamento
#################################################################################################


st.write("Preencha os dados para os usos de **lançamento** do empreendimento (se houver):")

tabela_uso_padrao_2 = pd.DataFrame({
    "Vazão (m³/h)": pd.Series(dtype="float"),
    "Horas": pd.Series(dtype="float"),
    "Dias": pd.Series(dtype="int"),
    "Classe de uso": pd.Series(dtype="str"),
    "Taxa de remoção (%)": pd.Series(dtype="str"),
    "DBO (mg/L)": pd.Series(dtype="float")
})


# Altura total da tabela, calculada dinamicamente para caber todas as linhas sem precisar de barra de rolagem interna.
#if "altura_tabela_uso_2" not in st.session_state:
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
        "Vazão (m³/h)": st.column_config.NumberColumn(
            "Vazão (m³/h)",
            help="Vazão de lançamento outorgada em m³/h",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            required=True,
            width="small",
        ),
        "Horas": st.column_config.NumberColumn(
            "Horas",
            help="Quantidade de horas de uso de lançamento outorgada ao longo do dia",
            min_value=0,
            step=0.01,
            required=True,
            width="small",
        ),
        "Dias": st.column_config.NumberColumn(
            "Dias",
            help="Quantidade de dias de uso de lançamento outorgada ao longo do mês",
            min_value=0,
            step=1,
            required=True,
            width="small",
        ),
        "Classe de uso": st.column_config.SelectboxColumn(
            "Classe de uso",
            help="Classe de uso preponderante do corpo d'água recepor",
            options=["Classe 2", "Classe 3", "Classe 4"],
            required=True,
            width="small",
        ),
        "Taxa de remoção (%)": st.column_config.SelectboxColumn(
            "Taxa de remoção (%)",
            help="A carga lançada e seu regime de variação, atendido o padrão de emissão requerido para o local",
            options=["> 95% de remoção", "> 90% e ≤ 95% de remoção",
                     "> 85% e ≤ 90% de remoção", "> 80% e ≤ 85% de remoção", "≤ 80% de remoção"],
            required=True,
            width="small",
        ),
        "DBO (mg/L)": st.column_config.NumberColumn(
            "DBO (mg/L)",
            help="Concentração de DBO em mg/L",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            required=True,
            width="small",
        )
    },
)


# Atualiza a altura salva com base na quantidade atual de linhas — assim, ao adicionar ou remover uma linha, a tabela já nasce no tamanho certo na interação seguinte.
st.session_state.altura_tabela_uso_2 = ALTURA_LINHA * \
    (len(tabela_uso_2) + 3) + 46


# Coeficientes Aguapeí/Peixe

##################################################
# Coeficientes Alto Paranapanema
##################################################
# PUB: Preços Unitários Básicos
# PUBCAP_ALPA = 0.009 # Captação
# PUBCONS_ALPA = 0.02 # Consumo
# PUBDBO_ALPA = 0.09  # Lançamento

# KOUT: Peso atribuído ao volume de captação outorgado
# KMED: Peso atribuído ao volume de captação medido
# if VCAPMED/VCAPOUT > 1:
#     KOUT = 0
#     KMED = 1
# else:
#     if medicao == 'Existe medição':
#        KOUT = 0.2
#        KMED = 0.8
#    elif medicao == 'Não existe medição':
#        KOUT = 1
#        KMED = 0

# X1: A natureza do corpo d'água
# if natureza == 'Superficial':
#    X1_ALPA = 1
# elif natureza == 'Subterrâneo':
#    X1_ALPA = 1.05

# X2: A classe de uso em que estiver enquadrado o corpo d'água no local do uso ou da derivação
# if classe == 'Classe 1':
#    X2_ALPA = 1
# elif classe == 'Classe 2':
#    X2_ALPA = 1
# elif classe == 'Classe 3':
#    X2_ALPA = 0.95
# elif classe == 'Classe 4':
#    X2_ALPA = 0.90

# X3: A disponibilidade hídrica local
# X3_ALPA = 1

# X5: O volume captado, extraído ou derivado e seu regime de variação
# X5_ALPA = 1

# X7: A finalidade de uso
# X7_ALPA = 1

# X13: Transposição
# X13_ALPA = 1

# Y1: Classe de uso preponderante do corpo d'água receptor
# if classe == 'Classe 2':
#    Y1_ALPA = 1
# elif classe == 'Classe 3':
#    Y1_ALPA = 0.95
# elif classe == 'Classe 4':
#    Y1_ALPA = 0.90

# Y3: A carga lançada e seu regime de  variação, atendido o padrão de emissão requerido para o local
# if classe == 'Maior que 95% de remoção':
#    Y3_ALPA = 0.80
# elif classe == 'Maior que 90% e menor que 95% de remoção':
#    Y3_ALPA = 0.85
# elif classe == 'Maior que 85% e menor que 90% de remoção':
#    Y3_ALPA = 0.90
# elif classe == 'Maior que 80% e menor que 85% de remoção':
#    Y3_ALPA = 0.95
# elif classe == 'Igual a 80% de remoção':
#    Y3_ALPA = 1

# Y4: A natureza da atividade
# Y4_ALPA = 1


# Coeficientes Alto Tietê
# Coeficientes Bacia Hidrográfica da Baixada Santista
# Coeficientes Baixo Pardo/Grande
# Coeficientes Baixo Tietê
# Coeficientes Litoral Norte
# Coeficientes Médio Paranapanema
# Coeficientes Mogi-Guaçu
# Coeficientes Paraíba do Sul
# Coeficientes Pardo
# Coeficientes Piracicaba/Capivari/Jundiaí
# Coeficientes Pontal do Paranapanema
# Coeficientes Ribeira de Iguape/Litoral Sul
# Coeficientes São José dos Dourados
# Coeficientes Sapucaí-Mirim/Grande
# Coeficientes Serra da Mantiqueira
# Coeficientes Sorocaba/Médio Tietê
# Coeficientes Tietê/Batalha
# Coeficientes Tietê/Jacaré
# Coeficientes Turvo/Grande
