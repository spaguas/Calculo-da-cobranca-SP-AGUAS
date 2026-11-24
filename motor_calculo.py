# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Motor de cálculo da cobrança pelo uso dos recursos hídricos (SP-ÁGUAS)
#
# Este módulo não depende do Streamlit: contém as regras das 21 bacias (PUBs e coeficientes
# ponderadores transcritos dos decretos vigentes), as fórmulas do Decreto nº 50.667/2006, os links
# oficiais das normas e as funções de leitura/formatação de números no padrão brasileiro.
#
# Fontes conferidas em 21/10/2026 no repositório de legislação da ALESP (links em LINKS). As tabelas
# de coeficientes publicadas como imagem estão em "decretos de bacias/anexos_oficiais/tabelas/imagens/", com
# transcrição dos coeficientes das 21 bacias (por bacia e consolidada em CSV) em "decretos de bacias/anexos_oficiais/tabelas/md/".
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import calendar
import copy
import datetime
import re

# UFESP 2026 (Comunicado DICAR nº 88/2025, DOE 18/12/2025). Atualizar todo mês de janeiro.
UFESP = 38.42
UFESP_ANO = 2026
# UFESP de cada ano, usada no lote de cobrança: incluir uma linha a cada janeiro.
UFESP_POR_ANO = {2026: 38.42}

# Art. 10, § 2º, do Decreto nº 50.667/2006: teto do PUF de captação = 0,001078 UFESP por m³.
TETO_PUF_CAP = 0.001078 * UFESP

# Art. 11 do Decreto nº 50.667/2006: lançamento limitado a 3 vezes (captação + consumo), desde que todos os
# lançamentos atendam aos padrões ambientais. Para a DBO, o padrão de emissão (Decreto Estadual nº 8.468/1976,
# art. 18) é de até 60 mg/L, ou acima disso com remoção de pelo menos 80% da carga.
TETO_LANC_MULTIPLO = 3.0
DBO_PADRAO_EMISSAO = 60.0
REMOCAO_PADRAO_EMISSAO = 80.0


def atende_padrao_dbo(dbo, remocao_pct):
    """True quando o efluente atende ao padrão de emissão de DBO: até 60 mg/L ou remoção ≥ 80%."""
    return dbo <= DBO_PADRAO_EMISSAO or remocao_pct >= REMOCAO_PADRAO_EMISSAO


# Carga lançada pela DBO do afluente (Pardo, Turvo/Grande, Médio Paranapanema e Aguapeí/Peixe). Os quatro decretos
# definem a carga como VCL = VLÇ × Cc × (1 − FTR × FER): Cc é a DBO do afluente (antes do tratamento), FTR o fator de
# tratamento e FER o fator de eficiência de remoção. O requisito do SisCob 2.0 ("Regra específica para cobrança de
# lançamento superficial", CBH-AP) usa essa carga quando a DBO do afluente é informada, com prioridade sobre a
# concentração remanescente, e cobra VCL × PUB, sem os coeficientes Y. O texto dos decretos cobra VCL × PUFCL, com
# PUFCL = PUB × (Y1 × Y2 × Y3 …). True segue o requisito do SisCob; False segue o texto dos decretos.
CARGA_AFLUENTE_SO_PUB = True

# DBO não declarada (SIMULAÇÃO LOCAL, 17/11/2026). Resolução Conjunta SERHS/SMA nº 1/2006, art. 6º, § 2º: "Para as
# atividades não licenciáveis pela CETESB em que haja lançamento de efluentes em corpos d'água, no caso de os Usuários
# não informarem os valores da concentração de DBO5,20, até o prazo estabelecido no Ato Convocatório, será adotado o
# valor de concentração para DBO5,20 igual a 300 mg/L." Sem DBO declarada não há remoção comprovada (a Nota Técnica da
# mesma resolução só admite Y3 < 1 com remoção acima de 80% comprovada): a remoção vai a 0% e o Y3 a 1,00. Nas bacias
# com carga_afluente, os 300 mg/L entram como a DBO do afluente, com FTR = FER = 0. Não vale para o resfriamento em
# circuito aberto, que tem regra própria, nem para a minuta rural. None desliga a simulação.
DBO_PRESUMIDA_MG_L = 300.0
FONTE_DBO_PRESUMIDA = "Resolução Conjunta SERHS/SMA nº 1/2006, art. 6º, § 2º"
_CC_LITERATURA = ("Carga lançada pela DBO do afluente: item {item} do Anexo do decreto. O decreto define Cc como a "
                  "concentração típica da DBO5,20, valor indicado em literatura.")
_CC_MEDIDA = ("Carga lançada pela DBO do afluente: item 5.3 do Anexo do decreto. Para Cc, o decreto manda usar os "
              "valores medidos (Resolução SERHS/SMA nº 1/2006) ou os indicados no licenciamento da CETESB (item 5.4).")

DIAS_ANO = 365


# ============================================================================================================================================================================================
# 1. NÚMEROS NO PADRÃO BRASILEIRO
# ============================================================================================================================================================================================
def fmt_num(valor, casas=2):
    """Formata número com ponto no milhar e vírgula na decimal: 1234.5 -> '1.234,50'."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_brl(valor, casas=2):
    """Formata valor monetário: 1234.5 -> 'R$ 1.234,50'."""
    sinal = "-" if valor < 0 else ""
    return f"{sinal}R$ {fmt_num(abs(valor), casas)}"


def fmt_coef(valor):
    """Coeficientes ponderadores com duas casas, como nos decretos: 1.1 -> '1,10'."""
    return fmt_num(valor, 2)


_RE_MILHAR_PONTO = re.compile(r"^\d{1,3}(\.\d{3})+$")


def ler_numero_br(texto):
    """
    Converte o texto digitado pelo usuário em número, aceitando o padrão brasileiro.

    - "1.500,75" -> 1500.75   (ponto = milhar, vírgula = decimal)
    - "1500,75"  -> 1500.75
    - "1.500"    -> 1500.0    (ponto seguido de grupos de 3 dígitos = milhar)
    - "12.5"     -> 12.5      (ponto isolado sem grupo de milhar = decimal)
    - ""         -> None      (campo vazio)
    Lança ValueError quando o texto não é um número válido.
    """
    if texto is None:
        return None
    t = str(texto).strip().replace(" ", "").replace("R$", "")
    if t == "":
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif _RE_MILHAR_PONTO.match(t):
        t = t.replace(".", "")
    valor = float(t)
    if valor != valor or valor in (float("inf"), float("-inf")):
        raise ValueError("número inválido")
    return valor


# Horas por dia: o operador escolhe digitar em hora e minuto (7:30) ou em hora decimal (7,5), o formato
# usado em muitos pareceres técnicos de vazão. O cálculo usa sempre a hora decimal (7:30 = 7,5 h).
FORMATO_HHMM = "Hora e minuto (hh:mm)"
FORMATO_DECIMAL = "Hora decimal (ex.: 7,5)"
FORMATOS_HORAS = [FORMATO_HHMM, FORMATO_DECIMAL]
_RE_HHMM = re.compile(r"^(\d{1,2})(?:\s*(?::|h)\s*(\d{1,2})?\s*(?:min)?)?$", re.IGNORECASE)


def ler_horas(texto, formato=FORMATO_HHMM):
    """
    Converte as horas por dia digitadas em hora decimal.

    - hh:mm:   "7:30" -> 7.5 · "07h30" -> 7.5 · "7h" -> 7.0 · "12" -> 12.0 (minutos de 0 a 59)
    - decimal: "7,5" -> 7.5 · "7.25" -> 7.25 · "12" -> 12.0
    - ""     -> None (campo vazio)
    Lança ValueError quando o texto não está no formato escolhido.
    """
    if texto is None or str(texto).strip() == "":
        return None
    t = str(texto).strip()
    if formato == FORMATO_DECIMAL:
        if ":" in t or "h" in t.lower():
            raise ValueError("no formato decimal, digite as horas com vírgula (ex.: 7,5)")
        return ler_numero_br(t)
    m = _RE_HHMM.match(t)
    if not m:
        raise ValueError("no formato hora e minuto, digite hh:mm (ex.: 7:30)")
    horas, minutos = int(m.group(1)), int(m.group(2) or 0)
    if minutos > 59:
        raise ValueError("os minutos vão de 0 a 59")
    return horas + minutos / 60


def fmt_hhmm(horas):
    """Hora decimal em hora e minuto, arredondada ao minuto: 7.5 -> '07:30'; 24 -> '24:00'."""
    minutos = round(horas * 60)
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def fmt_horas(horas, formato=FORMATO_HHMM):
    """Escreve as horas no formato escolhido: '07:30' ou '7,50'."""
    return fmt_hhmm(horas) if formato == FORMATO_HHMM else fmt_num(horas, 2)


# ============================================================================================================================================================================================
# 2. LINKS OFICIAIS DAS NORMAS
# ============================================================================================================================================================================================
# Todos os endereços abaixo foram verificados (HTTP 200) em 21/10/2026. linkar() troca as citações
# encontradas nos textos da calculadora por links Markdown, para que quem confere vá direto à norma.
_ALESP = "https://www.al.sp.gov.br/repositorio/legislacao"

LINK_LEI_12183 = f"{_ALESP}/lei/2005/lei-12183-29.12.2005.html"
LINK_LEI_7663 = f"{_ALESP}/lei/1991/lei-7663-30.12.1991.html"
LINK_DEC_50667 = f"{_ALESP}/decreto/2006/decreto-50667-30.03.2006.html"
LINK_DEC_10755 = f"{_ALESP}/decreto/1977/decreto-10755-22.11.1977.html"
LINK_SPAGUAS_LEGISLACAO = "https://www.spaguas.sp.gov.br/site/legislacaoderecursoshidricos/"


def _link_decreto(numero, data, ano=None):
    """Endereço do decreto no repositório da ALESP (decreto-58804-26.12.2012.html)."""
    ano = ano or data[-4:]
    return f"{_ALESP}/decreto/{ano}/decreto-{numero.replace('.', '')}-{data}.html"


def _link_decreto_2010(numero):
    """Os decretos de 09/12/2010 usam outro padrão de nome no repositório da ALESP."""
    return f"{_ALESP}/decreto/2010/decreto%20n.{numero},%20de%2009.12.2010.htm"


# (expressão regular da citação, endereço). A ordem importa: citações mais longas primeiro.
LINKS = [
    (r"Lei (?:Estadual )?nº 12\.183(?:/2005|, de 29 de dezembro de 2005)?", LINK_LEI_12183),
    (r"Lei (?:Estadual )?nº 7\.663(?:/1991|, de 30 de dezembro de 1991)?", LINK_LEI_7663),
    (r"Decreto(?: Estadual)? nº 50\.667(?:/2006|, de 30 de março de 2006)?", LINK_DEC_50667),
    (r"Decreto(?: Estadual)? nº 10\.755(?:/1977)?", LINK_DEC_10755),
    (r"Deliberação CBH-PS 05/2006", "https://www.ceivap.org.br/legisp/Decretos/Decreto-51450.pdf"),
    (r"Deliberação CBH-PS 011/2024",
     "https://sigrh.sp.gov.br/public/uploads/deliberation//CRH/29018/delib_crh_290_cobranca-cbh-ps_delib-cbh-ps-0112024_anexo.pdf"),
    (r"Deliberação CBH-SM 05/2026",
     "https://sigrh.sp.gov.br/public/uploads/deliberation//CBH-SM/32070/deliberacao-cbh-sm-05-2026-aprova-a-deliberacao-da-cobranca-ugrhi-01_v1_ass.pdf"),
    (r"Deliberação CRH 301/2025", "https://sigrh.sp.gov.br/pageitems/450/news/15501"),
    (r"Comunicado DICAR nº 88/2025", "https://legislacao.fazenda.sp.gov.br/Paginas/Comunicado-DICAR-88-de-2025.aspx"),
]


def _registrar_decreto(numero, link):
    """Inclui o decreto de uma bacia na lista de links (ex.: 'Decreto nº 58.804/2012')."""
    LINKS.insert(0, (rf"Decreto(?: Estadual)? nº {re.escape(numero)}(?:/\d{{4}}|, de \d{{2}}/\d{{2}}/\d{{4}}|, de \d{{1,2}}º? de \w+ de \d{{4}})?", link))


_RE_LINK_MD = re.compile(r"\[[^\]]*\]\([^)]*\)")


def _linkar_trecho(trecho):
    for padrao, url in LINKS:
        trecho = re.sub(rf"(?<!\[)({padrao})(?!\]\()", rf"[\1]({url})", trecho)
    return trecho


def linkar(texto):
    """Transforma as citações de normas conhecidas em links Markdown, sem mexer nos links que já existem."""
    partes, inicio = [], 0
    for link in _RE_LINK_MD.finditer(texto):
        partes.append(_linkar_trecho(texto[inicio:link.start()]))
        partes.append(link.group(0))
        inicio = link.end()
    partes.append(_linkar_trecho(texto[inicio:]))
    return "".join(partes)


# ============================================================================================================================================================================================
# 3. OPÇÕES E CAMPOS COMUNS
# ============================================================================================================================================================================================
NATUREZA = ["Superficial", "Subterrâneo"]
CLASSES = ["Classe 1", "Classe 2", "Classe 3", "Classe 4"]
CLASSES_RECEPTOR = ["Classe 2", "Classe 3", "Classe 4"]
FAIXAS_DISPONIBILIDADE = [
    "Muito alta (até 0,25)",
    "Alta (> 0,25 a 0,40)",
    "Média (> 0,40 a 0,50)",
    "Crítica (> 0,50 a 0,80)",
    "Muito crítica (> 0,80)",
]
DISPONIBILIDADE_2 = ["Crítica", "Média"]
FINALIDADES = ["Sistema público", "Solução alternativa", "Indústria"]
TRANSPOSICAO = ["Não existente", "Existente (para fora da UGRHI)"]

VALORES_Y3_FAIXAS = [0.80, 0.85, 0.90, 0.95, 1.00]  # > 95%; > 90 a 95%; > 85 a 90%; > 80 a 85%; até 80%

AJUDA_DISPONIBILIDADE = (
    "Relação entre a vazão total de demanda e a vazão de referência (Q7,10 + vazão potencial dos aquíferos) "
    "na sub-UGRHI da captação, ou na UGRHI quando ela não é subdividida (Deliberação CRH nº 90/2008). "
    "Vale para captação superficial e subterrânea: o índice já soma a vazão dos rios e a dos aquíferos. "
    "Essa informação consta do cadastro da SP Águas ou do Plano de Bacia."
)
AJUDA_FINALIDADE = (
    "**Sistema público:** abastecimento público por concessionária ou prefeitura. "
    "**Solução alternativa:** abastecimento próprio (condomínios, comércio, serviços). "
    "**Indústria:** uso em processo industrial."
)
AJUDA_CLASSE = "Enquadramento do corpo d'água no ponto de captação (Decreto Estadual nº 10.755/1977)."
# A classe (X2) é o enquadramento dos rios (Decreto nº 10.755/1977), que não classifica aquíferos. Nenhum decreto de
# bacia fixa X2 para a água subterrânea; o do Alto Tietê fixa 1,00. Adota-se 1,00, o valor de coeficiente não aplicável.
X2_SUBTERRANEA = 1.00
TEXTO_X2_SUBTERRANEA = (
    "Na captação subterrânea (poço), a classe não se aplica e X2 = 1,00. A classe é o enquadramento dos rios "
    "(Decreto Estadual nº 10.755/1977), que não classifica aquíferos, e nenhum decreto de bacia fixa outro valor para "
    "a água subterrânea; quando o coeficiente não se aplica, adota-se o valor 1,00. O poço continua pagando o X1 "
    "(natureza do corpo d'água) e os demais coeficientes da bacia."
)


def x2_nao_se_aplica(natureza_escolhida):
    """True quando a captação é subterrânea: a classe do rio (X2) não entra no preço."""
    return natureza_escolhida == "Subterrâneo"


def _valores_texto(opcoes, valores):
    partes = []
    for opcao, valor in zip(opcoes, valores):
        if isinstance(valor, dict):
            valor = " / ".join(f"{fmt_coef(v)} ({k.lower()})" for k, v in valor.items())
        else:
            valor = fmt_coef(valor)
        partes.append(f"{opcao} = {valor}")
    return "; ".join(partes) + "."


def _campo(coef, rotulo, opcoes, valores, ajuda=""):
    """Campo de seleção: cada opção vale um coeficiente (ou um dicionário por natureza do corpo d'água)."""
    texto = (ajuda + " " if ajuda else "") + _valores_texto(opcoes, valores)
    return {"coef": coef, "rotulo": rotulo, "opcoes": dict(zip(opcoes, valores)), "ajuda": texto}


def natureza(sup, sub):
    return _campo("X1", "Natureza do corpo d'água (X1)", NATUREZA, [sup, sub])


def classe(v1, v2, v3, v4):
    return _campo("X2", "Classe do corpo d'água (X2)", CLASSES, [v1, v2, v3, v4],
                  AJUDA_CLASSE + " Vale só para captação superficial; para a subterrânea, X2 = 1,00.")


def disponibilidade(valores, opcoes=FAIXAS_DISPONIBILIDADE):
    return _campo("X3", "Disponibilidade hídrica local (X3)", opcoes, valores, AJUDA_DISPONIBILIDADE)


def finalidade(v_pub, v_alt, v_ind, opcoes=FINALIDADES):
    return _campo("X7", "Finalidade do uso (X7)", opcoes, [v_pub, v_alt, v_ind], AJUDA_FINALIDADE)


def transposicao(existente):
    return _campo("X13", "Transposição de bacia (X13)", TRANSPOSICAO, [1.00, existente],
                  "Água levada para fora da UGRHI por meios artificiais.")


def receptor(v2, v3, v4):
    return _campo("Y1", "Classe do corpo receptor (Y1)", CLASSES_RECEPTOR, [v2, v3, v4])


def atividade(v_pub, v_alt, v_ind):
    return _campo("Y4", "Natureza da atividade (Y4)", FINALIDADES, [v_pub, v_alt, v_ind])


# ============================================================================================================================================================================================
# 4. REGRAS DAS BACIAS
# ============================================================================================================================================================================================
# Chaves de cada bacia:
#   campos_cap / campos_lanc  campos de seleção (coeficientes que o decreto faz variar)
#   fixos_cap                 coeficientes de captação fixos diferentes de 1,00 (ex.: X1 = 1,10)
#   consumo_coefs             {campo: {opção: valor}} coeficientes que também pesam no consumo
#   kout_kmed                 (KOUT, KMED) com medição; "medido" (só o medido) ou "outorga" (só a outorga)
#   x5                        None | {"modo": "formula"} | {"modo": "fixo", "sem": a, "com": b} | {"modo": "degraus"}
#   y3_modo / y3_valores      "faixas" (valores por faixa de remoção), "formula" ou "litoral_norte"
#   resfriamento              None | "pr100" (remoção de 100%) | "sem_carga" (carga e consumo desconsiderados)
#   mineracao                 None | "minimo_5" | "fixo_5" | "consumo_total" | "areia" (cálculo pelo volume de areia)
#   mineracao_r / _u_min      "areia": razão água/areia fixada no decreto (None = informada pelo usuário) e
#                             umidade mínima da areia (None = sem mínimo)
#   carga_afluente            True: o lançamento aceita a DBO do afluente (Cc) e o fator de tratamento (FTR), e a
#                             carga passa a VLÇ × Cc × (1 − FTR × FER) (ver CARGA_AFLUENTE_SO_PUB)
_PADRAO = {
    "campos_cap": {}, "campos_lanc": {}, "fixos_cap": {}, "consumo_coefs": {},
    "kout_kmed": (0.2, 0.8), "x5": None, "y3_modo": "faixas", "y3_valores": VALORES_Y3_FAIXAS,
    "resfriamento": None, "mineracao": None, "mineracao_r": None, "mineracao_u_min": None, "carga_afluente": False,
    "consumo_integral_opcoes": [],
    "valor_minimo": 0.0, "valor_minimo_texto": "", "insignificante_m3_dia": None,
    "insignificante_texto": "O decreto não fixa limite próprio; valem os critérios de uso insignificante da outorga.",
    "max_parcelas": 12, "revisao_pendente": None, "notas": [],
}

BACIAS = {}


def _bacia(nome, ugrhi, comite, numero, data, link, pubs, progressividade, resumo, **regras):
    regra = copy.deepcopy(_PADRAO)
    regra.update(
        ugrhi=ugrhi, comite=comite, decreto=f"Decreto nº {numero}/{data[-4:]}",
        decreto_extenso=f"Decreto Estadual nº {numero}, de {data.replace('.', '/')}", link_norma=link,
        pub_cap=pubs[0], pub_cons=pubs[1], pub_dbo=pubs[2], progressividade=progressividade, resumo=resumo,
    )
    regra.update(regras)
    BACIAS[nome] = regra
    _registrar_decreto(numero, link)


_PROG_CONCLUIDA = "Em 2026 aplica-se 100% dos PUBs."

# --- UGRHI 01 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Serra da Mantiqueira", "01", "CBH-SM", "58.804", "26.12.2012", _link_decreto("58.804", "26.12.2012"),
    (0.010, 0.020, 0.070),
    f"88% nos primeiros 12 meses, 94% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "Bacia de cabeceira com coeficientes mais rígidos: água subterrânea paga 20% a mais (X1 = 1,20), a indústria "
    "paga 30% a mais (X7 = 1,30) e a transposição dobra o preço da captação.",
    campos_cap={"natureza": natureza(1.00, 1.20), "classe": classe(1.00, 0.90, 0.80, 0.70),
                "disponibilidade": disponibilidade([1.00, 1.00, 1.00, 1.10, 1.20]),
                "finalidade": finalidade(1.00, 1.20, 1.30), "transposicao": transposicao(2.00)},
    campos_lanc={"natureza_atividade": atividade(1.00, 1.10, 1.10)},
    x5={"modo": "formula"}, resfriamento="pr100",
    valor_minimo=1.5 * UFESP, valor_minimo_ufesp=1.5,
    valor_minimo_texto=f"1,5 UFESP para emissão de boleto (item 4.2), ou {fmt_brl(1.5 * UFESP)} em {UFESP_ANO}.",
    insignificante_texto="Usos insignificantes conforme a Portaria DAEE nº 2.292/2006 e alterações (item 10).",
)
BACIAS["Serra da Mantiqueira"]["decreto_extenso"] += " (retificado no DOE de 27/12/2012)"

# --- UGRHI 02 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Paraíba do Sul", "02", "CBH-PS", "51.450", "29.12.2006", _link_decreto("51.450", "29.12.2006"),
    (0.010, 0.020, 0.070),
    f"88% no 1º ano (2007), 94% no 2º ano e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "Cobrança estadual desde 2007. O Y3 é calculado por fórmula contínua a partir do percentual de remoção de DBO, "
    "e a transposição para fora da bacia dobra o preço da captação e do consumo (X13 = 2,00).",
    campos_cap={"natureza": natureza(1.00, 1.10), "classe": classe(1.00, 0.90, 0.90, 0.70),
                "disponibilidade": disponibilidade([1.00, 1.00, 1.00, 1.10, 1.20]),
                "finalidade": finalidade(1.00, 1.20, 1.10), "transposicao": transposicao(2.00)},
    consumo_coefs={"transposicao": {TRANSPOSICAO[0]: 1.00, TRANSPOSICAO[1]: 2.00}},
    campos_lanc={"natureza_atividade": atividade(1.00, 1.20, 1.10)},
    x5={"modo": "formula"}, y3_modo="formula", resfriamento="pr100",
    mineracao="areia", mineracao_u_min=0.05,  # art. 3º da Del. CBH-PS 05/2006; U ≥ 5% (Del. CBH-PS 07/2006)
    valor_minimo=20.00, valor_minimo_texto="R$ 20,00 (art. 5º, § 2º, da Deliberação CBH-PS 05/2006).",
)
BACIAS["Paraíba do Sul"]["decreto_extenso"] += " (Deliberações CBH-PS 05/2006 e 07/2006)"

# --- UGRHI 03 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Litoral Norte", "03", "CBH-LN", "64.292", "18.06.2019", _link_decreto("64.292", "18.06.2019"),
    (0.011, 0.025, 0.077),
    f"80% nos primeiros 12 meses, 90% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "O Y3 depende da concentração de DBO lançada (até 60 mg/L) ou da taxa de remoção (acima de 60 mg/L). "
    "Indústria e mineração pagam 20% a mais na captação e no lançamento.",
    campos_cap={"natureza": natureza(1.00, 1.10),
                "disponibilidade": disponibilidade([1.00, 1.00, 1.00, 1.10, 1.20]),
                "finalidade": finalidade(1.00, 1.00, 1.20, FINALIDADES)},
    campos_lanc={"natureza_atividade": atividade(1.00, 1.00, 1.20)},
    x5={"modo": "formula"}, y3_modo="litoral_norte", mineracao="consumo_total",
    valor_minimo=40.00, valor_minimo_texto="R$ 40,00. Valores menores são acumulados até atingir o mínimo (item 4.2).",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações e extrações de até 5 m³/dia, isoladas ou em conjunto, são isentas (item 11).",
    notas=["Mineração (X7 e Y4 = 1,20) equivale, nesta calculadora, à opção Indústria. A mineração de areia tem item "
           "próprio: informe a vazão máxima nominal de bombeamento da draga; o consumo é igual à captação (item 3)."],
)

# --- UGRHI 04 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Pardo", "04", "CBH-Pardo", "58.771", "20.12.2012", _link_decreto("58.771", "20.12.2012"),
    (0.010, 0.020, 0.100),
    f"60% no 1º exercício fiscal, 75% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "Captação superficial tem desconto (X1 = 0,95) e a subterrânea paga 15% a mais (X1 = 1,15), para proteger o "
    "Aquífero Guarani.",
    campos_cap={"natureza": natureza(0.95, 1.15), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "disponibilidade": disponibilidade([0.90, 0.95, 1.00, 1.05, 1.10])},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    resfriamento="pr100", mineracao="fixo_5", carga_afluente=True,
    valor_minimo=30.00, valor_minimo_texto="R$ 30,00. Valores menores são acumulados até atingir o mínimo (item 4.2).",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos inferiores a 5 m³/dia, isolados ou em conjunto (item 3).",
    notas=[_CC_LITERATURA.format(item="5")],
)

# --- UGRHI 05 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Piracicaba/Capivari/Jundiaí", "05", "CBH-PCJ", "61.430", "17.08.2015", _link_decreto("61.430", "17.08.2015"),
    (0.0127, 0.0255, 0.1274),
    "R$ 0,0118 / 0,0235 / 0,1175 até 31/12/2015 e os valores atuais a partir de 01/01/2016.",
    "Maiores PUBs de captação do Estado. A transposição reduz o preço do consumo (X13 = 0,25), porque a água "
    "transposta já é cobrada na captação.",
    campos_cap={"natureza": natureza(1.00, 1.15), "classe": classe(1.00, 0.90, 0.90, 0.70),
                "transposicao": transposicao(1.00)},
    consumo_coefs={"transposicao": {TRANSPOSICAO[0]: 1.00, TRANSPOSICAO[1]: 0.25}},
    x5={"modo": "formula"}, y3_modo="formula", resfriamento="pr100",
    valor_minimo=20.00, valor_minimo_texto="R$ 20,00 (item 2.2).",
    revisao_pendente=(
        "O CRH referendou a revisão dos mecanismos e valores da cobrança do CBH-PCJ (Deliberação CRH 301/2025, "
        "13/11/2025). A minuta de decreto está em análise; até a publicação, vale o Decreto nº 61.430/2015, usado aqui."
    ),
)

# --- UGRHI 06 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_X7_ALTO_TIETE = {
    "Abastecimento urbano sem Plano Diretor de Perdas": {"Superficial": 1.00, "Subterrâneo": 1.00},
    "Abastecimento urbano com Plano Diretor de Perdas": {"Superficial": 0.80, "Subterrâneo": 1.00},
    "Indústria sem programa de uso racional": {"Superficial": 1.00, "Subterrâneo": 1.00},
    "Indústria com programa de uso racional": {"Superficial": 0.80, "Subterrâneo": 1.00},
    "Solução alternativa: condomínios (com rede pública disponível)": {"Superficial": 1.00, "Subterrâneo": 1.20},
    "Solução alternativa: condomínios (sem rede pública)": {"Superficial": 1.00, "Subterrâneo": 1.00},
    "Solução alternativa: transporte de água (caminhão-pipa)": {"Superficial": 1.00, "Subterrâneo": 1.50},
}
_bacia(
    "Alto Tietê", "06", "CBH-AT", "56.503", "09.12.2010", _link_decreto_2010("56.503"),
    (0.010, 0.020, 0.100),
    f"60% nos primeiros 12 meses (2011), 80% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "A classe do rio só reduz o preço da captação superficial. A finalidade dá desconto de 20% a quem tem Plano "
    "Diretor de Perdas ou programa de uso racional, e encarece poços de solução alternativa.",
    campos_cap={
        "natureza": natureza(1.00, 1.00),
        "classe": _campo("X2", "Classe do corpo d'água (X2)", CLASSES,
                         [{"Superficial": 1.00, "Subterrâneo": 1.00}, {"Superficial": 0.90, "Subterrâneo": 1.00},
                          {"Superficial": 0.80, "Subterrâneo": 1.00}, {"Superficial": 0.70, "Subterrâneo": 1.00}],
                         AJUDA_CLASSE + " Vale só para captação superficial; para a subterrânea, X2 = 1,00."),
        "finalidade": _campo("X7", "Finalidade do uso (X7)", list(_X7_ALTO_TIETE), list(_X7_ALTO_TIETE.values()),
                             "Plano de perdas e programa de uso racional exigem comprovação junto à FABHAT."),
    },
    campos_lanc={"classe_receptor": receptor(1.00, 0.90, 0.90)},
    consumo_integral_opcoes=["Solução alternativa: transporte de água (caminhão-pipa)"],
    y3_modo="formula", resfriamento="pr100",
    valor_minimo=100.00, valor_minimo_texto="R$ 100,00, cobrados em boleto único quando o total for menor (item 4.2).",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações de um mesmo usuário inferiores a 5 m³/dia, isoladas ou em conjunto (item 11).",
    notas=["Transporte de água por caminhão-pipa: o consumo é igual a 100% do volume captado (Anexo II, item 6)."],
)

# --- UGRHI 07 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Baixada Santista", "07", "CBH-BS", "56.501", "09.12.2010", _link_decreto_2010("56.501"),
    (0.010, 0.020, 0.100),
    "Sem progressividade: 100% dos PUBs desde 2011.",
    "Única bacia em que a captação superficial paga mais que a subterrânea (X1 = 1,05). Remoção de DBO acima de "
    "95% reduz o preço do lançamento à metade (Y3 = 0,50).",
    campos_cap={"natureza": natureza(1.05, 1.00), "classe": classe(1.15, 1.05, 0.95, 0.90),
                "disponibilidade": disponibilidade([0.80, 0.90, 1.00, 1.05, 1.10])},
    campos_lanc={"classe_receptor": receptor(1.20, 1.00, 0.90)},
    kout_kmed=(0.3, 0.7), x5={"modo": "fixo", "sem": 1.00, "com": 0.90},
    y3_valores=[0.50, 0.85, 0.90, 0.95, 1.00], resfriamento="sem_carga",
    valor_minimo=20.00, valor_minimo_texto="R$ 20,00 (item 4.2).",
)

# --- UGRHI 08 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Sapucaí-Mirim/Grande", "08", "CBH-SMG", "58.772", "20.12.2012", _link_decreto("58.772", "20.12.2012"),
    (0.010, 0.020, 0.100),
    f"60% no 1º exercício fiscal, 75% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "Quem mede o volume captado tem desconto de 10% (X5 = 0,90) e a medição pesa 70% no volume cobrado.",
    campos_cap={"natureza": natureza(1.00, 1.00), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "disponibilidade": disponibilidade([0.90, 0.95, 1.00, 1.05, 1.10])},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    kout_kmed=(0.3, 0.7), x5={"modo": "fixo", "sem": 1.00, "com": 0.90}, resfriamento="sem_carga", mineracao="fixo_5",
    valor_minimo=50.00, valor_minimo_texto="R$ 50,00 para parcelamento e emissão de boleto.",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos de até 5 m³/dia, isolados ou em conjunto.",
)

# --- UGRHI 09 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Mogi-Guaçu", "09", "CBH-MOGI", "58.791", "21.12.2012", _link_decreto("58.791", "21.12.2012"),
    (0.010, 0.020, 0.100),
    f"50% no 1º exercício fiscal, 75% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "Só duas faixas de disponibilidade (crítica e média) e desconto de 10% para quem mede o volume captado.",
    campos_cap={"natureza": natureza(1.00, 1.10), "classe": classe(1.10, 1.00, 0.90, 0.80),
                "disponibilidade": disponibilidade([1.00, 0.90], DISPONIBILIDADE_2)},
    kout_kmed=(0.3, 0.7), x5={"modo": "fixo", "sem": 1.00, "com": 0.90}, y3_modo="formula", resfriamento="pr100",
    mineracao="fixo_5",
    valor_minimo=50.00, valor_minimo_texto="R$ 50,00.",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos de até 5 m³/dia, isolados ou em conjunto.",
    notas=["A tabela publicada traz o Y3 como “(31 − 0,2·PR):1”. Foi adotada a divisão por 15, como nos demais "
           "decretos: com “:1” o Y3 passaria de 13 para 90% de remoção, o que não faz sentido. Convém confirmar no DOE."],
)

# --- UGRHI 10 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Sorocaba/Médio Tietê", "10", "CBH-SMT", "55.008", "10.11.2009", _link_decreto("55.008", "10.11.2009"),
    (0.011, 0.029, 0.130),
    f"60% nos primeiros 12 meses, 80% do 13º ao 24º mês e 100% a partir do 25º mês, para quem se cadastrou no "
    f"ato convocatório. {_PROG_CONCLUIDA}",
    "PUBs de consumo e de DBO entre os mais altos do Estado. Captação superficial tem desconto (X1 = 0,90) e a "
    "transposição custa 50% a mais (X13 = 1,50).",
    campos_cap={"natureza": natureza(0.90, 1.00), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "disponibilidade": disponibilidade([1.00, 0.95], DISPONIBILIDADE_2),
                "transposicao": transposicao(1.50)},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    kout_kmed="medido", x5={"modo": "fixo", "sem": 1.00, "com": 0.90}, y3_modo="formula",
    mineracao="fixo_5",
    valor_minimo=50.00, valor_minimo_texto="R$ 50,00. Valores menores são acumulados para os anos seguintes (Anexo II, item 8).",
    insignificante_texto="Todas as derivações, captações e lançamentos que dependem de outorga são considerados "
                         "significantes (Anexo I, item 2).",
    notas=["O decreto não fixa pesos KOUT/KMED: os volumes são os da outorga ou os medidos. Com medição, a "
           "calculadora usa o volume medido (KMED = 1).",
           "Os PUBs estão no Anexo III do decreto, publicado como imagem no Diário Oficial; os valores usados aqui "
           "foram transcritos dessa imagem."],
)

# --- UGRHI 11 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Ribeira de Iguape/Litoral Sul", "11", "CBH-RB", "58.814", "27.12.2012", _link_decreto("58.814", "27.12.2012"),
    (0.010, 0.020, 0.110),
    f"80% nos primeiros 12 meses, 90% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "Transposição custa 70% a mais (X13 = 1,70) e lançar em rios mais limpos (classes 1 e 2) encarece a carga "
    "(Y1 = 1,20 e 1,10).",
    campos_cap={"natureza": natureza(1.00, 1.20), "classe": classe(1.00, 0.90, 0.90, 0.70),
                "disponibilidade": disponibilidade([1.00, 1.00, 1.00, 1.10, 1.20]),
                "transposicao": transposicao(1.70)},
    campos_lanc={"classe_receptor": _campo("Y1", "Classe do corpo receptor (Y1)", CLASSES, [1.20, 1.10, 1.00, 1.00],
                                           "Classe 1 conforme Decreto Estadual nº 43.594/1998.")},
    x5={"modo": "formula"}, y3_modo="formula", mineracao="areia", mineracao_r=3.0, mineracao_u_min=0.05,
    valor_minimo=30.00, valor_minimo_texto="R$ 30,00 (item 5.2).",
    notas=["Mineração de areia (item próprio): Qcap = Qareia × 3 (75% de água e 25% de areia na polpa) e "
           "Qcons = Qareia × U, com umidade U de no mínimo 5% (item 3)."],
)

# --- UGRHI 12 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Baixo Pardo/Grande", "12", "CBH-BPG", "58.813", "27.12.2012", _link_decreto("58.813", "27.12.2012"),
    (0.010, 0.020, 0.100),
    f"60% no 1º exercício fiscal, 80% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "Coeficientes elevados: X1 = 1,10 para qualquer captação, rios limpos pagam até 20% a mais e quem mede menos "
    "de 70% do outorgado paga até 80% a mais (X5 = 1,80).",
    campos_cap={"natureza": natureza(1.10, 1.10), "classe": classe(1.20, 1.15, 1.10, 1.00),
                "disponibilidade": disponibilidade([0.90, 0.95, 1.00, 1.05, 1.10]),
                "finalidade": finalidade(1.00, 1.10, 1.00), "transposicao": transposicao(1.50)},
    campos_lanc={"classe_receptor": receptor(1.20, 1.15, 1.00), "natureza_atividade": atividade(1.00, 1.10, 1.00)},
    kout_kmed="medido", x5={"modo": "degraus"}, resfriamento="pr100", mineracao="fixo_5",
    valor_minimo=30.00, valor_minimo_texto="R$ 30,00 ou duas vezes o custo de emissão do boleto, o que for maior.",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos inferiores a 5 m³/dia, isolados ou em conjunto.",
    notas=["Coeficientes de captação conforme a retificação publicada no DOE de 28/12/2012 e republicada em 12/12/2013.",
           "Com medição, o volume cobrado é o medido (KMED = 1), salvo se o usuário declarar o volume outorgado."],
)

# --- UGRHI 13 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Tietê/Jacaré", "13", "CBH-TJ", "56.505", "09.12.2010", _link_decreto_2010("56.505"),
    (0.011, 0.021, 0.110),
    f"70% nos primeiros 12 meses, 85% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "PUBs acima do padrão estadual e Y3 por fórmula contínua, que premia remoção de DBO acima de 80%.",
    campos_cap={"natureza": natureza(1.00, 1.10), "classe": classe(1.10, 1.00, 0.95, 0.90)},
    x5={"modo": "formula"}, y3_modo="formula", resfriamento="pr100",
    valor_minimo=20.00, valor_minimo_texto="R$ 20,00.",
    insignificante_texto="Captações ou extrações subterrâneas inferiores a 5 m³/dia que independem de outorga (item 9).",
)

# --- UGRHI 14 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Alto Paranapanema", "14", "CBH-ALPA", "63.263", "09.03.2018", _link_decreto("63.263", "09.03.2018"),
    (0.009, 0.020, 0.090),
    f"60% em 2018, 75% em 2019 e 100% a partir de 2020. {_PROG_CONCLUIDA}",
    "PUBs de captação e de DBO 10% menores que os da maioria das bacias. Só a natureza e a classe do corpo d'água "
    "(X1, X2) e a classe do receptor e a eficiência da ETE (Y1, Y3) alteram o preço.",
    campos_cap={"natureza": natureza(1.00, 1.05), "classe": classe(1.00, 1.00, 0.95, 0.90)},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    mineracao="minimo_5",
    valor_minimo=30.00, valor_minimo_texto="R$ 30,00. Valores menores são acumulados até atingir o mínimo (item 4.2).",
    insignificante_m3_dia=5.0,
    insignificante_texto="Usos de até 5 m³/dia, isoladamente ou em conjunto, são insignificantes e não pagam (item 3).",
)

# --- UGRHI 15 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Turvo/Grande", "15", "CBH-TG", "61.346", "06.07.2015", _link_decreto("61.346", "06.07.2015"),
    (0.010, 0.020, 0.100),
    f"60% no 1º exercício fiscal, 75% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "Só a classe do rio e a disponibilidade hídrica alteram a captação; a medição pesa 70% no volume cobrado.",
    campos_cap={"natureza": natureza(1.00, 1.00), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "disponibilidade": disponibilidade([0.90, 0.95, 1.00, 1.05, 1.10])},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    kout_kmed=(0.3, 0.7), resfriamento="sem_carga", mineracao="fixo_5", carga_afluente=True,
    valor_minimo=30.00, valor_minimo_texto="R$ 30,00 para parcelamento e emissão de boleto.",
    insignificante_texto="Usos insignificantes conforme o artigo 3º da Portaria DAEE nº 2.292/2006.",
    notas=[_CC_LITERATURA.format(item="6")],
)

# --- UGRHI 16 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Tietê/Batalha", "16", "CBH-TB", "56.502", "09.12.2010", _link_decreto_2010("56.502"),
    (0.010, 0.020, 0.090),
    f"70% nos primeiros 12 meses, 85% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "PUB de DBO menor que o padrão. Solução alternativa paga 10% a mais na captação e no lançamento.",
    campos_cap={"natureza": natureza(1.00, 1.10), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "finalidade": finalidade(1.00, 1.10, 1.00)},
    campos_lanc={"natureza_atividade": atividade(1.00, 1.10, 1.00)},
    x5={"modo": "formula"}, y3_modo="formula", resfriamento="pr100",
    valor_minimo=20.00, valor_minimo_texto="R$ 20,00.",
)

# --- UGRHI 17 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Médio Paranapanema", "17", "CBH-MP", "61.386", "23.07.2015", _link_decreto("61.386", "23.07.2015"),
    (0.009, 0.020, 0.090),
    f"50% do 1º ao 12º mês, 75% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "Menor PUB de captação do Estado. Quem não mede paga 10% a mais (X5 = 1,10) e a remoção de DBO acima de 95% "
    "reduz o lançamento em 30% (Y3 = 0,70).",
    campos_cap={"natureza": natureza(1.00, 1.05), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "disponibilidade": disponibilidade([0.90, 0.95, 1.00, 1.05, 1.10]),
                "finalidade": finalidade(1.00, 1.10, 1.00)},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    kout_kmed=(0.3, 0.7), x5={"modo": "fixo", "sem": 1.10, "com": 1.00},
    y3_valores=[0.70, 0.80, 0.90, 0.95, 1.00], resfriamento="pr100", carga_afluente=True,
    valor_minimo=50.00, valor_minimo_texto="R$ 50,00. Valores menores são acumulados até atingir o mínimo.",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos de até 5 m³/dia, isolados ou em conjunto.",
    notas=[_CC_MEDIDA],
)

# --- UGRHI 18 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "São José dos Dourados", "18", "CBH-SJD", "64.305", "28.06.2019", _link_decreto("64.305", "28.06.2019"),
    (0.010, 0.020, 0.100),
    f"60% no 1º exercício fiscal, 75% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "A captação é cobrada só pelo volume da outorga, sem ponderar a medição. Captação superficial tem desconto "
    "(X1 = 0,95).",
    campos_cap={"natureza": natureza(0.95, 1.05), "classe": classe(1.10, 1.00, 0.95, 0.90),
                "disponibilidade": disponibilidade([0.90, 0.95, 1.00, 1.05, 1.10])},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    kout_kmed="outorga",
    valor_minimo=45.00, valor_minimo_texto="R$ 45,00. Valores menores são acumulados até atingir o mínimo (item 4.2).",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações e extrações de até 5 m³/dia, isoladas ou em conjunto, são isentas (item 3).",
    notas=["QCAP = volume constante da Portaria de Outorga ou do Ato Declaratório (item 5.1): o volume medido não "
           "altera a cobrança nesta bacia."],
)

# --- UGRHI 19 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Baixo Tietê", "19", "CBH-BT", "56.504", "09.12.2010", _link_decreto_2010("56.504"),
    (0.012, 0.024, 0.120),
    f"70% no 1º ano, 85% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "PUBs 20% acima do padrão estadual; só a natureza do corpo d'água e a medição alteram a captação.",
    campos_cap={"natureza": natureza(1.00, 1.10)},
    x5={"modo": "formula"}, y3_modo="formula", resfriamento="pr100",
    valor_minimo=20.00, valor_minimo_texto="R$ 20,00.",
)

# --- UGRHIs 20 e 21 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Aguapeí/Peixe", "20-21", "CBH-AP", "61.347", "06.07.2015", _link_decreto("61.347", "06.07.2015"),
    (0.010, 0.020, 0.100),
    f"60% do 1º ao 12º mês, 80% do 13º ao 24º mês e 100% a partir do 25º mês. {_PROG_CONCLUIDA}",
    "Quem não mede paga 10% a mais (X5 = 1,10) e quem mede tem 10% de desconto (X5 = 0,90). Bacia declarada "
    "crítica pelo comitê paga 20% a mais.",
    campos_cap={"natureza": natureza(1.00, 1.00), "classe": classe(1.10, 1.00, 0.90, 0.80),
                "disponibilidade": disponibilidade([1.20, 1.00], ["Bacia declarada crítica pelo CBH", "Bacia não crítica"]),
                "finalidade": finalidade(1.00, 1.10, 1.00)},
    campos_lanc={"classe_receptor": receptor(1.00, 0.95, 0.90)},
    kout_kmed=(0.3, 0.7), x5={"modo": "fixo", "sem": 1.10, "com": 0.90},
    y3_valores=[0.70, 0.80, 0.90, 0.95, 1.00], resfriamento="pr100", carga_afluente=True,
    valor_minimo=50.00, valor_minimo_texto="R$ 50,00. Valores menores são acumulados até atingir o mínimo.",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos de até 5 m³/dia, isolados ou em conjunto (item 3).",
    notas=[_CC_MEDIDA],
)
BACIAS["Aguapeí/Peixe"]["decreto_extenso"] = "Decreto Estadual nº 61.347, de 06/07/2015 (UGRHIs 20 e 21)"

# --- UGRHI 22 ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
_bacia(
    "Pontal do Paranapanema", "22", "CBH-PP", "61.415", "07.08.2015", _link_decreto("61.415", "07.08.2015"),
    (0.010, 0.020, 0.090),
    f"80% no 1º exercício fiscal, 90% no 2º e 100% a partir do 3º. {_PROG_CONCLUIDA}",
    "Modelo mais simples do Estado: todos os coeficientes de captação e consumo valem 1,00. Só a eficiência da ETE "
    "(Y3) altera o lançamento.",
    kout_kmed=(0.3, 0.7), resfriamento="sem_carga", mineracao="minimo_5",
    valor_minimo=50.00, valor_minimo_texto="R$ 50,00.",
    insignificante_m3_dia=5.0,
    insignificante_texto="Captações, extrações e lançamentos de até 5 m³/dia, isolados ou em conjunto (item 3).",
)

# Ordem de exibição: alfabética, como no seletor da calculadora.
def _chave_alfabetica(item):
    import unicodedata
    return unicodedata.normalize("NFKD", item[0]).encode("ascii", "ignore").decode().lower()


BACIAS = dict(sorted(BACIAS.items(), key=_chave_alfabetica))


# ============================================================================================================================================================================================
# 4.1. REVISÕES APROVADAS PELOS COMITÊS, À ESPERA DE DECRETO
# ============================================================================================================================================================================================
# Cada revisão guarda só o que muda em relação à regra vigente (BACIAS). Enquanto "decreto" e
# "data_publicacao" estiverem vazios, ela aparece apenas como simulação ("proposta"). Quando o decreto
# sair, basta preencher esses dois campos (e, se for o caso, "primeiro_exercicio"): a partir da data
# de publicação a revisão passa a ser o cálculo base, com a progressividade contada por ano fiscal.
# Se o decreto publicado alterar algum valor da deliberação, ajuste-o aqui em "alteracoes".

REVISOES = {
    "Paraíba do Sul": {
        "deliberacao": "Deliberação CBH-PS 011/2024",
        "situacao": "Aprovada pelo CBH-PS em 06/11/2024 e referendada pelo CRH em 13/11/2025. Aguarda decreto do Governador.",
        "decreto": None,             # ex.: "Decreto nº 70.000/2026"
        "data_publicacao": None,     # ex.: datetime.date(2026, 12, 15)
        "link_norma": None,          # link do decreto na ALESP, quando publicado
        "primeiro_exercicio": None,  # ano fiscal do 1º degrau; se vazio, o ano da publicação (art. 15, § 2º)
        "progressividade": [0.40, 0.60, 0.80, 1.00],
        "modo_transicao": None,      # "diferenca" ou "direto" quando definido; vazio = os dois na simulação
        "alteracoes": {
            "pub_cap": 0.0276,
            "pub_cons": 0.0552,
            "pub_dbo": 0.1932,
            "consumo_coefs": {},  # na revisão, o X13 do consumo passa a 1,00
            "mineracao_u_min": None,  # o art. 3º da Del. CBH-PS 011/2024 não fixa umidade mínima
            "max_parcelas": 8,
            "valor_minimo": 50.00,
            "valor_minimo_texto": "R$ 50,00, em parcela única ou em até 8 parcelas (art. 5º da Deliberação CBH-PS 011/2024).",
            "insignificante_m3_dia": 5.0,
            "insignificante_texto": "Captações e extrações de até 5 m³/dia, isoladas ou em conjunto, ficam isentas (art. 10).",
        },
    },
    "Serra da Mantiqueira": {
        "deliberacao": "Deliberação CBH-SM 05/2026",
        "situacao": "Aprovada pelo CBH-SM em 26/05/2026 (DOE de 28/05/2026). Aguarda referendo do CRH e decreto do Governador.",
        "decreto": None,
        "data_publicacao": None,
        "link_norma": None,
        "primeiro_exercicio": None,
        "progressividade": [0.40, 0.70, 1.00],
        "modo_transicao": None,
        "alteracoes": {
            "pub_cap": 0.0203,
            "pub_cons": 0.0405,
            "pub_dbo": 0.1418,
            "campos_cap": {
                # Valores como publicados na deliberação (classe 3 = 0,95 e classe 4 = 0,90): conferir no decreto.
                "classe": classe(1.00, 0.90, 0.95, 0.90),
            },
            "campos_lanc": {"natureza_atividade": atividade(1.00, 1.20, 1.30)},
            "y3_modo": "formula",  # art. 9º: mesma fórmula contínua do Paraíba do Sul
            "mineracao": "areia",
            "mineracao_r": 4.0,       # art. 3º: R = 4,0 (80% água / 20% areia)
            "mineracao_u_min": 0.05,  # art. 3º: U não pode ser inferior a 5%
            "insignificante_texto": "Usos insignificantes conforme a Portaria DAEE nº 1.631/2017 e normas que a sucederem (art. 10).",
        },
        "observacao": "Depois do 1º exercício, os PUBs serão corrigidos todo ano pela variação da UFESP (art. 2º, § 2º).",
    },
}


def revisao_publicada(revisao, hoje=None):
    """A revisão vale como regra base quando o decreto foi publicado e a data já chegou."""
    hoje = hoje or datetime.date.today()
    return bool(revisao.get("decreto")) and revisao.get("data_publicacao") is not None \
        and revisao["data_publicacao"] <= hoje


def _degraus_texto(progressividade):
    return ", ".join(f"{fmt_num(p * 100, 0)}% no {i}º ano" for i, p in enumerate(progressividade, start=1))


_PUBS = ("pub_cap", "pub_cons", "pub_dbo")

# Duas leituras da progressividade das revisões:
# - "diferenca": a dos estudos da revisão, com o percentual sobre a diferença entre o PUB atual e o novo;
# - "direto": a do texto das deliberações, com o percentual aplicado diretamente sobre o PUB novo.
# Enquanto "modo_transicao" da revisão estiver vazio, a simulação oferece as duas; definido, só vale ele.
MODOS_TRANSICAO = {
    "diferenca": "percentual sobre a diferença entre o PUB atual e o novo (estudos da revisão)",
    "direto": "percentual aplicado diretamente sobre o PUB novo (texto da deliberação)",
}
MODO_TRANSICAO_PADRAO = "diferenca"


def modos_transicao(bacia):
    """Modos de progressividade disponíveis para a revisão da bacia ([] se não houver revisão)."""
    revisao = REVISOES.get(bacia)
    if revisao is None:
        return []
    return [revisao["modo_transicao"]] if revisao.get("modo_transicao") else list(MODOS_TRANSICAO)


def _transicao(base, nova, percentual, modo):
    """
    PUB do ano no modo "diferenca": PUB atual + percentual × (PUB novo − PUB atual).
    PUB do ano no modo "direto": percentual × PUB novo.
    Nos dois casos chega-se ao PUB novo (100%) no último ano.
    """
    nova["pubs_atuais"] = {k: base[k] for k in _PUBS}
    nova["pubs_finais"] = {k: nova[k] for k in _PUBS}
    for k in _PUBS:
        nova[k] = (base[k] + percentual * (nova[k] - base[k]) if modo == "diferenca" else percentual * nova[k])
    nova["percentual_transicao"] = percentual
    nova["modo_transicao"] = modo


def _texto_transicao(degraus, modo):
    if modo == "direto":
        return (f"Os novos PUBs são aplicados de forma progressiva: {_degraus_texto(degraus)} do PUB novo "
                "(PUB do ano = percentual × PUB novo).")
    return (f"Os PUBs passam do valor atual ao novo de forma progressiva: {_degraus_texto(degraus)} da diferença "
            "entre o PUB atual e o novo (PUB do ano = PUB atual + percentual × (PUB novo − PUB atual)).")


def _sufixo_percentual(modo):
    return "da diferença" if modo == "diferenca" else "do PUB novo"


def _aplicar_revisao(base, revisao):
    regra = copy.deepcopy(base)
    for chave, valor in revisao["alteracoes"].items():
        if chave in ("campos_cap", "campos_lanc"):
            regra[chave].update(copy.deepcopy(valor))
        else:
            regra[chave] = copy.deepcopy(valor)
    return regra


def cenarios_disponiveis(bacia, hoje=None):
    """'vigente' sempre; 'proposta' enquanto houver revisão aprovada sem decreto publicado."""
    revisao = REVISOES.get(bacia)
    if revisao and not revisao_publicada(revisao, hoje):
        return ["vigente", "proposta"]
    return ["vigente"]


def regra_bacia(bacia, cenario="vigente", ano_aplicacao=None, hoje=None, modo_transicao=None):
    """
    Regra de cálculo da bacia no cenário pedido.

    - "vigente": o decreto em vigor hoje. Se a revisão já tiver decreto publicado, ela é a vigente,
      com o percentual de progressividade do ano fiscal corrente.
    - "proposta": a revisão ainda sem decreto, no ano de aplicação escolhido (1 = primeiro degrau;
      vazio = 100%). Devolve None se não houver revisão pendente.
    - modo_transicao: "diferenca" ou "direto" (ver MODOS_TRANSICAO). Só é usado enquanto a revisão não tiver
      o modo definido em REVISOES; vazio = MODO_TRANSICAO_PADRAO.
    """
    hoje = hoje or datetime.date.today()
    base = copy.deepcopy(BACIAS[bacia])
    base.update(fator_pub=1.0, cenario="vigente", ano_aplicacao=None)
    revisao = REVISOES.get(bacia)
    if revisao is None:
        return base if cenario == "vigente" else None

    nova = _aplicar_revisao(base, revisao)
    degraus = revisao["progressividade"]
    observacao = f" {revisao['observacao']}" if revisao.get("observacao") else ""
    modo = revisao.get("modo_transicao") or modo_transicao or MODO_TRANSICAO_PADRAO

    if revisao_publicada(revisao, hoje):
        if cenario != "vigente":
            return None
        inicio = revisao.get("primeiro_exercicio") or revisao["data_publicacao"].year
        ano = min(len(degraus), max(1, hoje.year - inicio + 1))
        _transicao(base, nova, degraus[ano - 1], modo)
        nova.update(
            fator_pub=1.0, cenario="vigente", ano_aplicacao=ano,
            decreto=revisao["decreto"],
            decreto_extenso=f"{revisao['decreto']}, publicado em {revisao['data_publicacao']:%d/%m/%Y} "
                            f"({revisao['deliberacao']})",
            link_norma=revisao.get("link_norma") or base["link_norma"],
            progressividade=f"{_texto_transicao(degraus, modo)} Em {hoje.year} aplica-se "
                            f"{fmt_num(degraus[ano - 1] * 100, 0)}% {_sufixo_percentual(modo)}.{observacao}",
            revisao_pendente=None,
        )
        return nova

    pubs = (f"captação {fmt_brl(nova['pub_cap'], 4)}/m³, consumo {fmt_brl(nova['pub_cons'], 4)}/m³ e "
            f"DBO {fmt_brl(nova['pub_dbo'], 4)}/kg")
    if cenario == "vigente":
        if revisao.get("modo_transicao"):
            como = f"{_degraus_texto(degraus)} {_sufixo_percentual(revisao['modo_transicao'])}"
        else:
            como = (f"{_degraus_texto(degraus)}. O texto da deliberação aplica o percentual diretamente sobre o PUB "
                    "novo; os estudos da revisão o aplicam sobre a diferença em relação ao PUB atual. A simulação "
                    "permite as duas contas")
        base["revisao_pendente"] = (
            f"A {revisao['deliberacao']} propõe novos PUBs ({pubs}), alcançados de forma progressiva: {como}. "
            f"{revisao['situacao']} Até a publicação, vale o {base['decreto']}, usado no cálculo base."
        )
        return base

    ano = min(len(degraus), max(1, ano_aplicacao or len(degraus)))
    _transicao(base, nova, degraus[ano - 1], modo)
    nova.update(
        fator_pub=1.0, cenario="proposta", ano_aplicacao=ano,
        decreto=f"{revisao['deliberacao']} (proposta)",
        decreto_extenso=f"{revisao['deliberacao']}, simulada como se o decreto já estivesse publicado",
        progressividade=f"{_texto_transicao(degraus, modo)} Simulação no {ano}º ano: "
                        f"{fmt_num(degraus[ano - 1] * 100, 0)}% {_sufixo_percentual(modo)}.{observacao}",
        revisao_pendente=None,
        degraus=degraus,
    )
    return nova


# ============================================================================================================================================================================================
# 5. FÓRMULAS
# ============================================================================================================================================================================================
def dias_por_ano(dias_mes, meses_ano, ano_cheio=False):
    """
    Dias de uso no ano.

    - "Outorga de ano cheio" marcada: 365 dias.
    - Dias/mês igual ou maior que 30: o mês é considerado completo (365/12 dias), de modo que
      30 dias × 12 meses = 365 dias, e não 360.
    - Nos demais casos: dias/mês × meses/ano.
    """
    if ano_cheio:
        return float(DIAS_ANO)
    dias_mes = min(31, max(0, int(dias_mes)))
    meses_ano = min(12, max(0, int(meses_ano)))
    if dias_mes >= 30:
        return meses_ano * DIAS_ANO / 12
    return float(dias_mes * meses_ano)


def volume_anual(vazao_m3h, horas_dia, dias_ano):
    """Volume anual (m³) = vazão (m³/h) × horas/dia × dias/ano."""
    return vazao_m3h * min(24.0, max(0.0, horas_dia)) * dias_ano


# Sazonalidade (modo rural): a outorga mês a mês. Fevereiro aceita 29 dias, para a outorga de ano bissexto.
DIAS_DO_MES = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _meses_usados(item):
    meses = item.get("meses")
    if meses is None:
        return None
    if len(meses) != 12:
        raise ValueError(f"{item.get('nome') or 'Captação'}: a sazonalidade precisa dos 12 meses, de janeiro a dezembro.")
    return [(i, m) for i, m in enumerate(meses) if m]


def volume_e_captacao_maxima(item):
    """
    Volume outorgado no ano (m³) e captação máxima outorgada (m³/dia) de um item. Com sazonalidade, o item traz
    "meses": 12 posições, de janeiro a dezembro, cada uma None (sem uso no mês) ou (vazão m³/h, horas/dia, dias de
    uso). O volume é a soma dos meses, e a captação máxima, o maior vazão × horas entre eles. Sem "meses", vale
    vazão × horas × dias no ano.
    """
    usados = _meses_usados(item)
    if usados is None:
        return (volume_anual(item["vazao"], item["horas_dia"], item["dias_ano"]),
                item["vazao"] * min(24.0, max(0.0, item["horas_dia"])))
    v_out = sum(volume_anual(v, h, d) for _, (v, h, d) in usados)
    maxima = max((v * min(24.0, max(0.0, h)) for _, (v, h, _d) in usados), default=0.0)
    return v_out, maxima


def meses_da_outorga(item):
    """Detalhe mês a mês de um item com sazonalidade (para a memória de cálculo); lista vazia sem sazonalidade."""
    return [{"mes": MESES[i], "vazao": v, "horas_dia": h, "dias": d, "m3_dia": v * min(24.0, max(0.0, h)),
             "volume": volume_anual(v, h, d)} for i, (v, h, d) in (_meses_usados(item) or [])]


def pesos_kout_kmed(v_out, v_med, modo=(0.2, 0.8)):
    """
    Pesos KOUT/KMED (item 3 do Anexo do Decreto nº 50.667/2006 e decretos das bacias).
    Sem medição: KOUT = 1. Medição acima da outorga: KMED = 1. Com medição: os pesos da bacia;
    "medido" usa só o volume medido e "outorga" ignora a medição.
    """
    if v_med <= 0 or modo == "outorga":
        return 1.0, 0.0
    if modo == "medido" or (v_out > 0 and v_med / v_out > 1.0):
        return 0.0, 1.0
    return modo


def coef_x5(v_out, v_med):
    """X5 por fórmula: 1 + (0,7·Vout − Vmed) / (0,2·Vout + 0,8·Vmed), se Vmed/Vout < 0,7."""
    if v_med > 0 and v_out > 0 and v_med / v_out < 0.7:
        return 1.0 + (0.7 * v_out - v_med) / (0.2 * v_out + 0.8 * v_med)
    return 1.0


def coef_x5_degraus(v_out, v_med):
    """X5 do Baixo Pardo/Grande: ≥ 70% = 1,00; 60 a 70% = 1,20; 50 a 60% = 1,40; < 50% = 1,80 (Vmed/Vout)."""
    if v_med <= 0 or v_out <= 0:
        return 1.0
    razao = v_med / v_out * 100
    for limite, valor in ((70, 1.00), (60, 1.20), (50, 1.40)):
        if razao >= limite:
            return valor
    return 1.80


def coef_x5_regra(regra, v_out, v_med):
    x5 = regra["x5"]
    if not x5:
        return 1.0
    if x5["modo"] == "formula":
        return coef_x5(v_out, v_med)
    if x5["modo"] == "degraus":
        return coef_x5_degraus(v_out, v_med)
    return x5["com"] if v_med > 0 else x5["sem"]


def coef_y3_formula(pr):
    """
    Y3 por fórmula contínua (Paraíba do Sul, PCJ, Alto Tietê, Mogi-Guaçu, Sorocaba, Ribeira, Tietês):
    PR ≤ 80%: 1,00; 80% < PR < 95%: (31 − 0,2·PR) / 15; PR ≥ 95%: 16 − 0,16·PR.
    """
    if pr <= 80:
        return 1.0
    if pr < 95:
        return (31 - 0.2 * pr) / 15
    return max(0.0, 16 - 0.16 * pr)


coef_y3_paraiba = coef_y3_formula


def coef_y3_faixas(pr, valores=VALORES_Y3_FAIXAS):
    """Y3 por faixas de 5% de remoção: > 95%; > 90 a 95%; > 85 a 90%; > 80 a 85%; até 80%."""
    for limite, valor in zip((95, 90, 85, 80), valores):
        if pr > limite:
            return valor
    return valores[-1]


def coef_y3_litoral_norte(dbo, pr):
    """
    Y3 do Litoral Norte (item 8 do Decreto nº 64.292/2019):
    DBO ≤ 60 mg/L: Y3 = 0,4 + 0,01·DBO; DBO > 60 mg/L e remoção ≥ 80%: Y3 = 1,8 − 0,01·TR.
    Fora dessas condições o efluente não atende ao padrão; adota-se 1,00.
    """
    if dbo <= 60:
        return 0.4 + 0.01 * dbo
    if pr >= 80:
        return 1.8 - 0.01 * pr
    return 1.0


def _valor_opcao(campo, opcao, nat):
    valor = campo["opcoes"][opcao]
    return valor[nat] if isinstance(valor, dict) else valor


# ============================================================================================================================================================================================
# 6. CÁLCULO COMPLETO
# ============================================================================================================================================================================================
def _coefs_captacao(regra, c, v_out, v_med, x7_rural, x12_rural):
    """Coeficientes X de uma captação (ou de um item de mineração) conforme os campos escolhidos."""
    nat = c.get("natureza") or "Superficial"
    coefs = {"X1": 1.0, "X2": 1.0, "X3": 1.0, "X5": 1.0, "X7": 1.0, "X12": 1.0, "X13": 1.0}
    coefs.update(regra["fixos_cap"])
    for chave, campo in regra["campos_cap"].items():
        if campo["coef"] == "X2" and x2_nao_se_aplica(nat):
            coefs["X2"] = X2_SUBTERRANEA  # a classe do rio não vale para poço (TEXTO_X2_SUBTERRANEA)
            continue
        coefs[campo["coef"]] = _valor_opcao(campo, nat if chave == "natureza" else c[chave], nat)
    coefs["X5"] = coef_x5_regra(regra, v_out, v_med)
    if x7_rural is not None:
        coefs["X7"] = x7_rural
    if x12_rural is not None:
        coefs["X12"] = x12_rural
    coefs_cons = {}
    for chave, mapa in regra["consumo_coefs"].items():
        coef = regra["campos_cap"][chave]["coef"]
        coefs_cons[coef] = X2_SUBTERRANEA if coef == "X2" and x2_nao_se_aplica(nat) else mapa[c[chave]]
    return coefs, coefs_cons


def _produto(valores):
    total = 1.0
    for valor in valores:
        total *= valor
    return total


def volumes_mineracao(regra, m):
    """
    Volumes anuais de captação e consumo de um item de mineração de areia, conforme a regra do decreto:
    - "areia": captação = Qareia × R e consumo = Qareia × U (U com o mínimo do decreto, quando houver);
    - "consumo_total": captação = vazão máxima de bombeamento da draga e consumo igual à captação;
    - "fixo_5": captação pelo volume outorgado (e medido) e consumo = 5% do volume outorgado;
    - "minimo_5": captação pelo volume outorgado (e medido) e consumo efetivo de no mínimo 5% do outorgado.
    Devolve (v_out, v_med, kout, kmed, v_cap, v_cons, memória em texto).
    """
    modo = regra["mineracao"]
    if modo == "areia":
        r = regra["mineracao_r"] if regra["mineracao_r"] is not None else m["r"]
        u = m["u_pct"] / 100.0
        if regra["mineracao_u_min"] is not None:
            u = max(u, regra["mineracao_u_min"])
        v_cap = m["q_areia"] * r
        v_cons = m["q_areia"] * u
        memoria = (f"Qcap = {fmt_num(m['q_areia'])} m³ de areia × R {fmt_num(r, 2)}; "
                   f"Qcons = {fmt_num(m['q_areia'])} × U {fmt_num(u * 100, 1)}%")
        return v_cap, 0.0, 1.0, 0.0, v_cap, v_cons, memoria
    v_out = volume_anual(m["vazao"], m["horas_dia"], m["dias_ano"])
    v_med = m.get("v_med", 0.0)
    if modo == "consumo_total":
        return v_out, 0.0, 1.0, 0.0, v_out, v_out, "Consumo igual à captação (vazão máxima da draga)"
    kout, kmed = pesos_kout_kmed(v_out, v_med, regra["kout_kmed"])
    v_cap = kout * v_out + kmed * v_med
    if modo == "fixo_5":
        return v_out, v_med, kout, kmed, v_cap, 0.05 * v_out, "Consumo = 5% do volume outorgado"
    declarado = m.get("consumo_declarado") or 0.0
    v_cons = max(declarado, 0.05 * v_out)
    memoria = ("Consumo efetivo declarado" if declarado >= 0.05 * v_out
               else "Consumo efetivo abaixo de 5% do outorgado: adotado 5%")
    return v_out, v_med, kout, kmed, v_cap, v_cons, memoria


def _detalhe_lancamento(regra, l, i, pub_dbo, y_extra=None, permitir_afluente=True, presumir_dbo=True):
    """
    Volumes, coeficientes Y, carga de DBO e valor de um lançamento, pela regra da bacia (ou pela regra rural neutra).
    y_extra: coeficientes Y adicionais, multiplicados no PUF da DBO (o Y9 do modo rural).
    permitir_afluente: False desliga a carga pela DBO do afluente (a minuta rural tem fórmula própria).
    presumir_dbo: com "dbo" vazia (None), sem DBO do afluente e fora do resfriamento, adota DBO_PRESUMIDA_MG_L com
    remoção de 0%; False exige a DBO (minuta rural).

    Nas bacias com carga_afluente, quando "dbo_afluente" (Cc, mg/L) vem preenchida, a carga é
    VLÇ × Cc ÷ 1.000 × (1 − FTR × FER), com FTR = "ftr_pct" e FER = "remocao_pct", e tem prioridade sobre a
    concentração remanescente ("dbo"). O padrão de emissão é conferido pela DBO que chega ao rio, Cc × (1 − FTR × FER),
    e pela remoção total, FTR × FER. Com CARGA_AFLUENTE_SO_PUB, o valor é carga × PUB, sem os coeficientes Y.
    """
    v_out = volume_anual(l["vazao"], l["horas_dia"], l["dias_ano"])
    v_med = l.get("v_med", 0.0)
    v_lanc = v_med if v_med > 0 else v_out
    dbo = l.get("dbo", 0.0)
    resfriamento = bool(l.get("resfriamento")) and regra["resfriamento"] is not None
    pr = 100.0 if resfriamento else l.get("remocao_pct", 80.0)
    cc = l.get("dbo_afluente")
    ftr = l.get("ftr_pct")
    afluente_na_bacia = permitir_afluente and regra["carga_afluente"]
    # DBO não declarada: 300 mg/L, sem remoção (nas bacias com carga pela DBO do afluente, Cc = 300 e FTR = FER = 0)
    presumida = (presumir_dbo and DBO_PRESUMIDA_MG_L is not None and dbo is None and cc is None and not resfriamento)
    if presumida:
        pr = 0.0
        if afluente_na_bacia:
            cc, ftr = DBO_PRESUMIDA_MG_L, 0.0
        else:
            dbo = DBO_PRESUMIDA_MG_L
    pela_afluente = afluente_na_bacia and cc is not None and not resfriamento
    if pela_afluente:
        if ftr is None:
            raise ValueError(f"{l.get('nome') or f'Lançamento {i}'}: com a DBO do afluente, informe o fator de "
                             "tratamento (FTR).")
        remocao_total = ftr / 100.0 * pr / 100.0
        dbo = cc * (1.0 - remocao_total)   # DBO que chega ao rio
    elif dbo is None:
        raise ValueError(f"{l.get('nome') or f'Lançamento {i}'}: informe a DBO do efluente.")

    coefs = {"Y1": 1.0, "Y3": 1.0, "Y4": 1.0}
    for chave, campo in regra["campos_lanc"].items():
        coefs[campo["coef"]] = campo["opcoes"][l[chave]]
    if resfriamento and regra["resfriamento"] == "sem_carga":
        coefs["Y3"] = 1.0
    elif regra["y3_modo"] == "neutro":
        coefs["Y3"] = 1.0  # modo rural com coeficientes neutros (premissa do estudo: demais coeficientes = 1)
    elif regra["y3_modo"] == "formula":
        coefs["Y3"] = coef_y3_formula(pr)
    elif regra["y3_modo"] == "litoral_norte":
        coefs["Y3"] = coef_y3_litoral_norte(dbo, pr)
    else:
        coefs["Y3"] = coef_y3_faixas(pr, regra["y3_valores"])

    puf_dbo = pub_dbo * coefs["Y1"] * coefs["Y3"] * coefs["Y4"]
    for coef, valor in (y_extra or {}).items():
        coefs[coef] = valor
        puf_dbo *= valor
    coefs_aplicados = not (pela_afluente and CARGA_AFLUENTE_SO_PUB)
    if not coefs_aplicados:
        puf_dbo = pub_dbo   # requisito do SisCob 2.0: VCL × PUB
    # DBO em mg/L equivale a g/m³; dividir por 1.000 converte para kg/m³.
    if pela_afluente:
        carga_kg = cc / 1000.0 * v_lanc * (1.0 - remocao_total)
    else:
        carga_kg = 0.0 if resfriamento and regra["resfriamento"] == "sem_carga" else dbo / 1000.0 * v_lanc
    remocao_padrao = remocao_total * 100.0 if pela_afluente else pr
    return {
        "item": l.get("nome") or f"Lançamento {i}", "v_out": v_out, "v_med": v_med, "v_lanc": v_lanc, "dbo": dbo,
        "carga_kg": carga_kg, "coefs": coefs, "puf_dbo": puf_dbo, "vcl": carga_kg * puf_dbo,
        "remocao_pct": remocao_padrao, "atende_padrao": atende_padrao_dbo(dbo, remocao_padrao),
        "vazao_dia": l["vazao"] * min(24.0, max(0.0, l["horas_dia"])),
        # carga pela DBO do afluente: Cc, FTR e FER informados; coefs_aplicados = False quando o valor é VCL × PUB
        "pela_afluente": pela_afluente, "dbo_afluente": cc if pela_afluente else None,
        "ftr_pct": ftr if pela_afluente else None, "fer_pct": pr if pela_afluente else None,
        "coefs_aplicados": coefs_aplicados,
        "dbo_presumida": presumida,   # DBO não declarada: DBO_PRESUMIDA_MG_L e remoção de 0%
    }


def _teto_lancamento(vcc, vcco, det_lanc, norma="art. 11 do Decreto nº 50.667/2006"):
    """
    Teto do lançamento: 3 vezes (captação + consumo), só quando todos os lançamentos atendem ao padrão de DBO.
    norma: o artigo citado nos avisos (o do decreto urbano ou o da minuta do decreto rural, com o mesmo teto).
    """
    vcl_bruto = sum(d["vcl"] for d in det_lanc)
    teto = TETO_LANC_MULTIPLO * (vcc + vcco)
    fora_do_padrao = [d for d in det_lanc if not d["atende_padrao"]]
    excedido = vcl_bruto > 0 and vcc + vcco > 0 and vcl_bruto > teto
    limitado = excedido and not fora_do_padrao
    aviso = None
    if limitado:
        aviso = (f"O valor do lançamento ({fmt_brl(vcl_bruto)}) passou do teto de 3 vezes a captação + consumo "
                 f"({norma}) e foi limitado a {fmt_brl(teto)}. O teto vale porque "
                 "todos os lançamentos atendem ao padrão de DBO (até 60 mg/L ou remoção de pelo menos 80%); "
                 "na cobrança real, os demais parâmetros de emissão também precisam ser atendidos.")
    elif excedido:
        itens = "; ".join(f"{d['item']}: DBO de {fmt_num(d['dbo'])} mg/L e remoção de {fmt_num(d['remocao_pct'], 1)}%"
                          for d in fora_do_padrao)
        aviso = (f"O valor do lançamento ({fmt_brl(vcl_bruto)}) passou do teto de 3 vezes a captação + consumo "
                 f"({fmt_brl(teto)}), mas o teto não se aplica e o lançamento é cobrado integralmente. "
                 f"Há lançamento fora do padrão de emissão de DBO ({itens}): o Decreto Estadual nº 8.468/1976 "
                 f"(art. 18) exige até 60 mg/L ou remoção de pelo menos 80%, e o {norma} "
                 "só admite o teto quando todos os lançamentos atendem aos padrões.")
    return {"vcl_bruto": vcl_bruto, "vcl": teto if limitado else vcl_bruto, "teto": teto, "excedido": excedido,
            "limitado": limitado, "fora_do_padrao": fora_do_padrao, "aviso": aviso}


def calcular(bacia, captacoes, lancamentos, x7_rural=None, x12_rural=None, mineracoes=None,
             cenario="vigente", ano_aplicacao=None, hoje=None, modo_transicao=None, ufesp=None):
    """
    Calcula a cobrança anual de um empreendimento.

    captacoes:   lista de dicts com vazao, horas_dia, dias_ano, v_med e os rótulos escolhidos
                 nos campos da bacia (natureza, classe, disponibilidade, finalidade, transposicao).
    lancamentos: lista de dicts com vazao, horas_dia, dias_ano, v_med, dbo, remocao_pct, resfriamento
                 e os campos da bacia (classe_receptor, natureza_atividade).
    x7_rural / x12_rural: coeficientes hipotéticos do modo rural (substituem o X7 da bacia).
    mineracoes:  itens de mineração de areia, cobrados à parte pela regra do decreto (ver volumes_mineracao):
                 campos da bacia + q_areia, r, u_pct ("areia") ou vazao, horas_dia, dias_ano, v_med e
                 consumo_declarado (demais regras). Não entram no fator de consumo do empreendimento e não
                 têm carga lançada cobrada.
    Todo item aceita "nome" (o nome dado pelo usuário ao cartão), usado na memória de cálculo e nos avisos;
    sem ele, o item se chama "Captação 1", "Lançamento 1", "Mineração 1"…
    cenario / ano_aplicacao / modo_transicao: "vigente" ou "proposta" (revisão sem decreto), ver regra_bacia().
    ufesp: UFESP do ano de cobrança (teto do PUF de captação e mínimos em UFESP); vazio = UFESP vigente.
    """
    regra = regra_bacia(bacia, cenario, ano_aplicacao, hoje, modo_transicao)
    if regra is None:
        raise ValueError(f"Não há cenário '{cenario}' para a bacia {bacia}.")
    teto_puf = 0.001078 * ufesp if ufesp else TETO_PUF_CAP
    fator = regra["fator_pub"]
    pub_cap, pub_cons, pub_dbo = regra["pub_cap"] * fator, regra["pub_cons"] * fator, regra["pub_dbo"] * fator
    mineracoes = mineracoes or []
    if mineracoes and not regra["mineracao"]:
        raise ValueError(f"O decreto da bacia {bacia} não tem regra de mineração de areia.")
    avisos = []

    # ---------- Captação ----------
    det_cap = []
    for i, c in enumerate(captacoes, start=1):
        v_out, vazao_dia = volume_e_captacao_maxima(c)   # com sazonalidade, a soma dos meses
        v_med = c.get("v_med", 0.0)
        kout, kmed = pesos_kout_kmed(v_out, v_med, regra["kout_kmed"])
        v_cap = kout * v_out + kmed * v_med
        coefs, coefs_cons = _coefs_captacao(regra, c, v_out, v_med, x7_rural, x12_rural)
        puf_cap = pub_cap * _produto(coefs.values())
        nome = c.get("nome") or f"Captação {i}"
        limitado = puf_cap > teto_puf
        if limitado:
            puf_cap = teto_puf
            avisos.append(f"{nome}: o PUF passou do teto legal de {fmt_brl(teto_puf, 4)}/m³ "
                          f"(0,001078 UFESP, art. 10, § 2º, do Decreto nº 50.667/2006) e foi limitado a esse valor.")

        det_cap.append({
            "item": nome, "v_out": v_out, "v_med": v_med, "kout": kout, "kmed": kmed,
            "v_cap": v_cap, "coefs": coefs, "puf_cap": puf_cap, "puf_limitado": limitado,
            "vcc": v_cap * puf_cap, "coefs_cons": coefs_cons,
            "x2_nao_se_aplica": x2_nao_se_aplica(c.get("natureza"))
                                and any(campo["coef"] == "X2" for campo in regra["campos_cap"].values()),
            "consumo_integral": c.get("finalidade") in regra["consumo_integral_opcoes"],
            "vazao_dia": vazao_dia,
        })

    # ---------- Lançamento ----------
    det_lanc = [_detalhe_lancamento(regra, l, i, pub_dbo) for i, l in enumerate(lancamentos, start=1)]

    # ---------- Consumo ----------
    VCAPT = sum(d["v_cap"] for d in det_cap)
    V_LANCT = sum(d["v_lanc"] for d in det_lanc)
    FC = min(1.0, max(0.0, (VCAPT - V_LANCT) / VCAPT)) if VCAPT > 0 else 0.0

    det_cons = []
    for d in det_cap:
        v_cons = d["v_cap"] if d["consumo_integral"] else FC * d["v_cap"]
        x7 = x7_rural if x7_rural is not None else 1.0
        x12 = x12_rural if x12_rural is not None else 1.0
        produto_cons = 1.0
        for valor in d["coefs_cons"].values():
            produto_cons *= valor
        puf_cons = pub_cons * produto_cons * x7 * x12
        det_cons.append({"item": d["item"], "v_cons": v_cons, "coefs": d["coefs_cons"], "puf_cons": puf_cons,
                         "vcco": v_cons * puf_cons})

    # ---------- Mineração de areia (item à parte) ----------
    det_min = []
    for i, m in enumerate(mineracoes, start=1):
        v_out, v_med, kout, kmed, v_cap, v_cons, memoria = volumes_mineracao(regra, m)
        coefs, coefs_cons = _coefs_captacao(regra, m, v_out, v_med, x7_rural, x12_rural)
        if regra["mineracao"] == "areia":
            coefs["X5"] = 1.0  # sem outorga de vazão a comparar com medição
        puf_cap = pub_cap * _produto(coefs.values())
        nome = m.get("nome") or f"Mineração {i}"
        limitado = puf_cap > teto_puf
        if limitado:
            puf_cap = teto_puf
            avisos.append(f"{nome}: o PUF passou do teto legal de {fmt_brl(teto_puf, 4)}/m³ e foi limitado.")
        x7 = x7_rural if x7_rural is not None else 1.0
        x12 = x12_rural if x12_rural is not None else 1.0
        puf_cons = pub_cons * _produto(coefs_cons.values()) * x7 * x12
        det_min.append({
            "item": nome, "v_out": v_out, "v_med": v_med, "kout": kout, "kmed": kmed,
            "v_cap": v_cap, "v_cons": v_cons, "coefs": coefs, "coefs_cons": coefs_cons,
            "puf_cap": puf_cap, "puf_limitado": limitado, "puf_cons": puf_cons,
            "vcc": v_cap * puf_cap, "vcco": v_cons * puf_cons, "memoria": memoria,
        })

    vcc = sum(d["vcc"] for d in det_cap) + sum(d["vcc"] for d in det_min)
    vcco = sum(d["vcco"] for d in det_cons) + sum(d["vcco"] for d in det_min)
    teto = _teto_lancamento(vcc, vcco, det_lanc)
    vcl_bruto, vcl = teto["vcl_bruto"], teto["vcl"]
    teto_lanc, lanc_limitado, teto_excedido = teto["teto"], teto["limitado"], teto["excedido"]
    fora_do_padrao = teto["fora_do_padrao"]
    if teto["aviso"]:
        avisos.append(teto["aviso"])

    total = vcc + vcco + vcl

    if regra["insignificante_m3_dia"]:
        limite = regra["insignificante_m3_dia"]
        volume_dia = sum(d["vazao_dia"] for d in det_cap) + sum(d["vazao_dia"] for d in det_lanc)
        if 0 < volume_dia <= limite:
            avisos.append(f"Os usos somam {fmt_num(volume_dia)} m³/dia, abaixo de {fmt_num(limite, 0)} m³/dia: "
                          "podem ser considerados insignificantes e isentos de cobrança. " + regra["insignificante_texto"])

    if 0 < total < valor_minimo_do_ano(regra, ufesp):
        avisos.append(f"O total ficou abaixo do valor mínimo de cobrança da bacia: {regra['valor_minimo_texto']}")

    return {
        "bacia": bacia,
        "regra": regra,
        "pubs_aplicados": {"cap": pub_cap, "cons": pub_cons, "dbo": pub_dbo},
        "FC": FC,
        "VCAPT": VCAPT,
        "V_LANCT": V_LANCT,
        "captacao": vcc,
        "consumo": vcco,
        "lancamento": vcl,
        "lancamento_bruto": vcl_bruto,
        "lancamento_limitado": lanc_limitado,
        "teto_lancamento": teto_lanc,
        "teto_lancamento_excedido": teto_excedido,
        "lancamentos_fora_do_padrao": [d["item"] for d in fora_do_padrao],
        "total": total,
        "detalhes_cap": det_cap,
        "detalhes_cons": det_cons,
        "detalhes_lanc": det_lanc,
        "detalhes_min": det_min,
        "mineracao": sum(d["vcc"] + d["vcco"] for d in det_min),
        "avisos": avisos,
    }


# ============================================================================================================================================================================================
# 7. LOTE DE COBRANÇA MENSAL (SisCob 2.0)
# ============================================================================================================================================================================================
# O SisCob 2.0 gera um lote anual por outorga, dividido em faturas mensais pelos dias de cada mês:
# - valor diário = valor anual ÷ dias de uso no ano (365 no ano cheio); mês = diário × dias de uso no mês, com
#   29 dias em fevereiro nos anos bissextos (366 dias cobrados no ano);
# - o lote vai do mês de geração até dezembro, ou até o fim da vigência da outorga;
# - abaixo do valor mínimo da bacia: boleto único (o valor também pode ser acumulado para o lote seguinte);
# - uso de algum mês abaixo do mínimo: o valor do lote é dividido em parcelas iguais, no maior número que deixa
#   cada parcela acima do mínimo, sem passar do limite de parcelas do decreto (ex.: 8 na revisão do PS);
# - uso sazonal: cobram-se só os meses de uso; opcionalmente, o valor é parcelado igualmente nos meses do lote;
# - base "ano": regras da bacia (teto do lançamento, valor mínimo) sobre o valor anual, depois rateado; base
#   "periodo": cálculo refeito com os volumes do período do lote, com as regras sobre esse período.
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro",
         "Novembro", "Dezembro"]
BASES_LOTE = {
    "ano": "regras da bacia aplicadas ao valor anual, depois rateado pelos dias de uso do período do lote",
    "periodo": "cálculo refeito com os volumes do período do lote, com as regras da bacia sobre esse período",
}


def ufesp_do_ano(ano, informada=None):
    """UFESP do ano: a informada pelo usuário, a da tabela UFESP_POR_ANO ou, na falta, a vigente."""
    return informada or UFESP_POR_ANO.get(ano, UFESP)


def valor_minimo_do_ano(regra, ufesp=None):
    """Valor mínimo de cobrança da bacia, atualizado pela UFESP do ano quando o decreto o fixa em UFESP."""
    if regra.get("valor_minimo_ufesp") and ufesp:
        return regra["valor_minimo_ufesp"] * ufesp
    return regra["valor_minimo"]


def dias_de_uso(item, ano, mes, mes_inicio=1):
    """
    Dias de uso de uma outorga num mês do lote: zero antes do mês de geração, fora da vigência da outorga e nos
    meses sem uso; com menos de 30 dias de uso por mês, no máximo esse número de dias.
    """
    meses_uso = item.get("meses_uso")
    if mes < mes_inicio or (meses_uso is not None and mes not in meses_uso):
        return 0
    inicio = datetime.date(ano, mes, 1)
    fim = datetime.date(ano, mes, calendar.monthrange(ano, mes)[1])
    if item.get("vigencia_inicio"):
        inicio = max(inicio, item["vigencia_inicio"])
    if item.get("vigencia_fim"):
        fim = min(fim, item["vigencia_fim"])
    if fim < inicio:
        return 0
    dias = (fim - inicio).days + 1
    dias_mes = item.get("dias_mes")
    return min(int(dias_mes), dias) if dias_mes and dias_mes < 30 else dias


def _dias_base(item):
    """Dias de uso no ano do cálculo anual (365 para a areia, informada pelo volume anual)."""
    return item.get("dias_ano") or DIAS_ANO


def _no_periodo(item, dias):
    """Cópia da outorga com os volumes do período do lote (dias de uso, medição, consumo declarado e areia)."""
    fator = dias / _dias_base(item)
    novo = dict(item)
    if "dias_ano" in item:
        novo["dias_ano"] = dias
    for chave in ("v_med", "consumo_declarado", "q_areia"):
        if novo.get(chave):
            novo[chave] = novo[chave] * fator
    return novo


def _valores_por_outorga(res):
    """Valor de cada outorga: captação (com o seu consumo), lançamento (depois do teto) e mineração."""
    fator_lanc = res["lancamento"] / res["lancamento_bruto"] if res["lancamento_bruto"] else 1.0
    valores = [{"captacao": c["vcc"], "consumo": co["vcco"], "lancamento": 0.0}
               for c, co in zip(res["detalhes_cap"], res["detalhes_cons"])]
    valores += [{"captacao": 0.0, "consumo": 0.0, "lancamento": l["vcl"] * fator_lanc} for l in res["detalhes_lanc"]]
    valores += [{"captacao": m["vcc"], "consumo": m["vcco"], "lancamento": 0.0} for m in res["detalhes_min"]]
    return valores


def _dividir(total, n):
    """Divide o total em n parcelas iguais, em centavos; a diferença de arredondamento fica na última."""
    parcela = round(total / n, 2)
    return [parcela] * (n - 1) + [round(total - parcela * (n - 1), 2)]


def parcelas_do_lote(valores_mes, minimo, max_parcelas, meses_vigentes, abaixo_minimo, parcelar_igual=False):
    """
    Boletos de uma outorga no lote. valores_mes = {mês: valor do uso no mês}; meses_vigentes = meses do lote em
    que a outorga está vigente (para o parcelamento igual). Devolve ([(mês, valor), ...], regra aplicada).
    """
    total = round(sum(valores_mes.values()), 2)
    cobrados = [m for m, v in valores_mes.items() if v > 0]
    if total <= 0:
        return [], "Sem uso cobrado no período do lote."
    if abaixo_minimo:
        return [(cobrados[0], total)], (f"Boleto único: o valor fica abaixo do mínimo da bacia ({fmt_brl(minimo)}). "
                                         "O valor também pode ser acumulado para o lote do ano seguinte.")
    mensal_ok = all(round(valores_mes[m], 2) >= minimo for m in cobrados)
    if not parcelar_igual and len(cobrados) <= max_parcelas and mensal_ok:
        valores = [round(valores_mes[m], 2) for m in cobrados]
        valores[-1] = round(total - sum(valores[:-1]), 2)
        return list(zip(cobrados, valores)), "Um boleto por mês, pelo uso de cada mês (dias de uso × valor diário)."
    meses = meses_vigentes if parcelar_igual else cobrados
    limite = min(len(meses), max_parcelas)
    n = max(1, min(limite, int(total // minimo) if minimo > 0 else limite))
    motivos = []
    if parcelar_igual:
        motivos.append(f"parcelamento igual nos {len(meses)} meses do lote")
    elif not mensal_ok:
        motivos.append(f"o uso de algum mês fica abaixo do mínimo da bacia ({fmt_brl(minimo)})")
    if len(meses) > max_parcelas:
        motivos.append(f"o decreto permite no máximo {max_parcelas} parcelas")
    if n < limite:
        motivos.append(f"{n} é o maior número de parcelas que fica acima do mínimo ({fmt_brl(minimo)})")
    inicio = f"Valor do lote dividido em {n} parcelas iguais" if n > 1 else "Boleto único"
    return list(zip(meses[:n], _dividir(total, n))), f"{inicio}: {'; '.join(motivos)}."


# Parcelamento da edição só rural (apresentação na CT-COB): hipótese da simulação, e não regra da minuta, que não fixa
# parcelamento nem valor mínimo de boleto. O lote do ano sai por volta de maio, e o valor anual é pago em 8 parcelas
# mensais iguais, de maio a dezembro.
PARCELAMENTO_RURAL = {"parcelas": 8, "mes_inicio": 5}


def parcelas_rurais(total, parcelas=8, mes_inicio=5):
    """
    Valor anual em parcelas mensais iguais, de mes_inicio em diante: [(nome do mês, valor), ...]. A diferença de
    centavos fica na última parcela. Sem valor a cobrar, devolve a lista vazia.
    """
    if parcelas < 1 or not 1 <= mes_inicio <= 12 or mes_inicio + parcelas - 1 > 12:
        raise ValueError("As parcelas precisam caber no ano, do mês de início até dezembro.")
    total = round(total, 2)
    if total <= 0:
        return []
    return list(zip(MESES[mes_inicio - 1:mes_inicio - 1 + parcelas], _dividir(total, parcelas)))


def lote_mensal(bacia, captacoes, lancamentos, mineracoes=None, ano=None, mes_inicio=1, base="ano",
                parcelar_igual=False, ufesp=None, **kw):
    """
    Simula o lote de cobrança do SisCob 2.0 para o ano e o mês de geração escolhidos, outorga por outorga.

    captacoes / lancamentos / mineracoes: os itens de calcular(), com os campos opcionais do lote:
        meses_uso (meses de 1 a 12; None = todos), dias_mes (dias de uso por mês; vazio ou 30 e 31 = mês inteiro),
        vigencia_inicio e vigencia_fim (datetime.date).
    base: "ano" ou "periodo" (ver BASES_LOTE). parcelar_igual: divide o valor igualmente nos meses do lote.
    ufesp: UFESP do ano do lote (vazio = tabela UFESP_POR_ANO ou a vigente). kw: demais parâmetros de calcular().
    """
    ano = ano or datetime.date.today().year
    mineracoes = mineracoes or []
    informada = ufesp
    ufesp = ufesp_do_ano(ano, informada)
    hoje = kw.pop("hoje", None) or datetime.date(ano, mes_inicio, 1)
    itens = list(captacoes) + list(lancamentos) + list(mineracoes)
    meses_lote = list(range(mes_inicio, 13))
    dias = [{m: dias_de_uso(it, ano, m, mes_inicio) for m in meses_lote} for it in itens]

    anual = calcular(bacia, captacoes, lancamentos, mineracoes=mineracoes, hoje=hoje, ufesp=ufesp, **kw)
    if base == "periodo":
        n_cap, n_lanc = len(captacoes), len(lancamentos)
        periodo = [_no_periodo(it, sum(d.values())) for it, d in zip(itens, dias)]
        res = calcular(bacia, periodo[:n_cap], periodo[n_cap:n_cap + n_lanc], mineracoes=periodo[n_cap + n_lanc:],
                       hoje=hoje, ufesp=ufesp, **kw)
        bases = [sum(d.values()) for d in dias]
    else:
        res = anual
        bases = [_dias_base(it) for it in itens]

    regra = res["regra"]
    minimo = valor_minimo_do_ano(regra, ufesp)
    max_parcelas = regra.get("max_parcelas", 12)
    nomes = [d["item"] for d in res["detalhes_cap"] + res["detalhes_lanc"] + res["detalhes_min"]]
    outorgas = []
    for nome, it, d, b, val, val_anual in zip(nomes, itens, dias, bases, _valores_por_outorga(res),
                                              _valores_por_outorga(anual)):
        meses = {}
        for m in meses_lote:
            partes = {k: (v / b * d[m] if b else 0.0) for k, v in val.items()}
            meses[m] = {"dias": d[m], **partes, "valor": sum(partes.values())}
        valor_base = sum(val.values())
        vigentes = [m for m in meses_lote if dias_de_uso({**it, "meses_uso": None, "dias_mes": None}, ano, m, mes_inicio)]
        parcelas, texto = parcelas_do_lote({m: meses[m]["valor"] for m in meses_lote}, minimo, max_parcelas,
                                           vigentes, 0 < valor_base < minimo, parcelar_igual)
        outorgas.append({
            "item": nome, "valor_anual": sum(val_anual.values()), "valor_base": valor_base, "dias_base": b,
            "dias_lote": sum(d.values()), "diario": valor_base / b if b else 0.0, "meses": meses,
            "total": sum(v for _, v in parcelas), "parcelas": [{"mes": m, "valor": v} for m, v in parcelas],
            "regra_parcelas": texto, "abaixo_minimo": 0 < valor_base < minimo,
        })

    avisos = []
    if informada is None and ano not in UFESP_POR_ANO:
        avisos.append(f"A UFESP de {ano} ainda não está na tabela da calculadora: foi usada a de {UFESP_ANO} "
                      f"({fmt_brl(UFESP)}). Informe a UFESP do ano para atualizar o teto do PUF e os mínimos em UFESP.")
    if base == "periodo":
        avisos += [f"No período do lote: {a}" for a in res["avisos"]]
    return {
        "ano": ano, "mes_inicio": mes_inicio, "meses_lote": meses_lote, "bissexto": calendar.isleap(ano),
        "base": base, "parcelar_igual": parcelar_igual, "ufesp": ufesp, "minimo": minimo,
        "max_parcelas": max_parcelas, "resultado": res, "resultado_anual": anual, "outorgas": outorgas,
        "total": sum(o["total"] for o in outorgas), "boletos": sum(len(o["parcelas"]) for o in outorgas),
        "avisos": avisos,
    }


# ============================================================================================================================================================================================
# 8. COBRANÇA RURAL (MINUTA EM DISCUSSÃO)
# ============================================================================================================================================================================================
# A cobrança do uso rural ainda não é vigente no Estado de São Paulo. Esta seção simula a minuta de decreto que
# substitui a Deliberação CRH nº 101/2009 (versão preliminar de 31/08/2026, quadro comparativo distribuído à CT-COB),
# com as premissas do estudo da SP Águas apresentado na 154ª reunião da CT-COB (07/10/2026). Cada premissa tem uma
# origem (CAMADAS_RURAIS), para que a tela mostre o que é regra, o que é premissa do estudo e o que é hipótese.
# Decupagem do material e plano: relatorios/rural/01_DECUPAGEM_E_PLANO_COBRANCA_RURAL_2026-11-07.md.
#
# Leituras adotadas onde a minuta não é explícita (registradas no plano, a confirmar com a SP Águas):
# - limiar de isenção: pela soma das captações do usuário ("em cuja atividade", art. 5º, I) ou outorga por outorga,
#   à escolha (premissa "isencao_por"). Na leitura por outorga, os lançamentos continuam cobrados, porque o limiar
#   olha só a vazão de captação;
# - teto do lançamento: 3 vezes a captação e o consumo de todos os usos do empreendimento, inclusive os isentos
#   (art. 11, § 1º);
# - FC das finalidades que não são irrigação: VCAPT e VLANÇT de todo o empreendimento, inclusive a irrigação
#   (Anexo, item 4, ao pé da letra), com aviso quando há mistura;
# - PUB da DBO e pesos KOUT/KMED com medição: os do decreto urbano da bacia (a minuta deixa ao CBH e o estudo não fixa).
_DA_MINUTA = "da minuta do decreto rural"

MINUTA_RURAL = {
    "nome": "Minuta do decreto da cobrança rural",
    "versao": "versão preliminar de 31/08/2026",
    "base": "Deliberação CRH nº 101/2009",
    "situacao": "Minuta em discussão na CT-COB do CRH. Não é cobrança vigente.",
    "limiar_isencao_m3_dia": 300.0,             # art. 5º, I
    "fc_irrigacao": 0.88,                       # art. 10, § 7º, e Anexo, item 4
    "teto_puf_cap_ufesp": 0.001078,             # art. 10, § 3º
    "teto_puf_cons_ufesp": 0.002156,            # art. 10, § 4º
    "teto_lanc_multiplo": TETO_LANC_MULTIPLO,   # art. 11
    "parametros_lancamento": ("DBO",),          # só a DBO nos dois primeiros anos
    "artigos": {
        "isencao_porte": "art. 5º, I",
        "isencao_caf": "art. 5º, II",
        "usos_multiplos": "art. 5º, parágrafo único",
        "teto_puf_cap": "art. 10, § 3º",
        "teto_puf_cons": "art. 10, § 4º",
        "fc_irrigacao": "art. 10, § 7º, e Anexo, item 4",
        "fc_formula": "Anexo, item 4",
        "teto_lancamento": "art. 11",
        "desconto": "art. 12, § 5º",
        "kout_kmed": "Anexo, item 3",
        "carga": "Anexo, item 5",
    },
}

# Categorias das outorgas rurais usadas no estudo (slide 15). É a finalidade que decide o fator de consumo.
FINALIDADES_RURAIS = ["Irrigação", "Dessedentação animal", "Aquicultura", "Outro uso rural"]
FINALIDADE_IRRIGACAO = "Irrigação"
FINALIDADE_RURAL_PADRAO = FINALIDADE_IRRIGACAO  # 97% da vazão rural outorgada (slide 15)

ISENCAO_POR = {
    "usuario": "Somatório das captações do usuário",
    "outorga": "Cada outorga de captação",
}
COEFICIENTES_BACIA_RURAL = {
    "neutros": "Neutros: todos iguais a 1,00, como no estudo",
    "herdados": "Herdados do decreto urbano da bacia",
}
CAMADAS_RURAIS = {
    "Minuta": "regra da minuta do decreto rural",
    "Estudo": "premissa de simulação do estudo da SP Águas",
    "Hipótese": "suposição da calculadora onde a minuta e o estudo não fixam valor",
    "Sua escolha": "valor alterado por você",
}

# Premissas de um cenário rural: rótulo para a tela, camada de origem e fonte.
_SLIDE_12 = "Apresentação da SP Águas à CT-COB, 07/10/2026, slide 12"
PREMISSAS_RURAIS = {
    "pub_cap": {"rotulo": "PUB de captação (R$/m³)", "camada": "Estudo",
                "fonte": f"{_SLIDE_12}. Os PUBs de cada bacia serão propostos pelo CBH (art. 10, § 1º)"},
    "pub_cons": {"rotulo": "PUB de consumo (R$/m³)", "camada": "Estudo", "fonte": _SLIDE_12},
    "pub_dbo": {"rotulo": "PUB da DBO (R$/kg)", "camada": "Hipótese",
                "fonte": "O estudo não fixa. Vazio = o PUB da DBO do decreto urbano da bacia"},
    "x7": {"rotulo": "X7: finalidade do uso (rural)", "camada": "Estudo", "fonte": _SLIDE_12},
    "x12": {"rotulo": "X12: práticas de conservação do solo e da água", "camada": "Minuta",
            "fonte": "Art. 12, § 5º: desconto a definir pelo CBH. 1,00 = sem desconto"},
    "y9": {"rotulo": "Y9: práticas de conservação do solo e da água (lançamento)", "camada": "Minuta",
           "fonte": "Art. 12, § 5º: desconto a definir pelo CBH. 1,00 = sem desconto"},
    "fc_irrigacao": {"rotulo": "Fator de consumo da irrigação", "camada": "Minuta",
                     "fonte": "Art. 10, § 7º: 88%, alterável pelo CBH mediante estudo técnico"},
    "limiar_isencao_m3_dia": {"rotulo": "Limiar de isenção (m³/dia de captação)", "camada": "Minuta",
                              "fonte": "Art. 5º, I: até 300 m³/dia de captação máxima outorgada, alterável pelo CBH"},
    "isencao_por": {"rotulo": "Limiar aplicado ao", "camada": "Hipótese",
                    "fonte": "O art. 5º, I, fala na vazão captada \"em cuja atividade\": a calculadora soma as "
                             "captações do usuário. A alternativa aplica o limiar a cada outorga"},
    "coeficientes_bacia": {"rotulo": "Coeficientes da bacia", "camada": "Estudo",
                           "fonte": f"{_SLIDE_12}: demais coeficientes iguais a 1"},
    "kout_kmed": {"rotulo": "Pesos KOUT e KMED com medição", "camada": "Hipótese",
                  "fonte": "Anexo, item 3: definidos pelo CBH (sem medição, KOUT = 1). Vazio = os pesos do decreto "
                           "urbano da bacia"},
}

# Cenários rurais. Cada estudo novo entra como um cenário, e os anteriores ficam para comparação.
CENARIOS_RURAIS = {
    "Estudo SP Águas, out/2026": {
        "data": "07/10/2026",
        "fonte": f"{_SLIDE_12}, e minuta de 31/08/2026",
        "premissas": {
            "pub_cap": 0.01, "pub_cons": 0.02, "pub_dbo": None, "x7": 0.214, "x12": 1.0, "y9": 1.0,
            "fc_irrigacao": 0.88, "limiar_isencao_m3_dia": 300.0, "isencao_por": "usuario",
            "coeficientes_bacia": "neutros", "kout_kmed": None,
        },
        # Preço unitário final percebido do slide 12, por m³ captado: 0,01 × 0,214 + 0,02 × 0,88 × 0,214.
        "preco_percebido": 0.0059064,
    },
}
CENARIO_RURAL_PADRAO = "Estudo SP Águas, out/2026"


def equivalencias_m3_dia(m3_dia):
    """Vazão diária nas três unidades da tela: m³/dia (a da minuta), m³/h em 24 horas e L/s."""
    return {"m3_dia": m3_dia, "m3_h": m3_dia / 24.0, "l_s": m3_dia * 1000.0 / 86400.0}


def _fmt_enxuto(valor, casas=2):
    """Número no padrão brasileiro sem zeros finais: 300 → "300"; 86,40 → "86,4"."""
    texto = fmt_num(valor, casas)
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


def _numero(valor):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _validar_premissas(p):
    erros = []
    for chave in ("pub_cap", "pub_cons", "x7", "x12", "y9", "fc_irrigacao", "limiar_isencao_m3_dia"):
        if not _numero(p[chave]) or p[chave] < 0:
            erros.append(f"{PREMISSAS_RURAIS[chave]['rotulo']}: informe um número maior ou igual a zero.")
    if p["pub_dbo"] is not None and (not _numero(p["pub_dbo"]) or p["pub_dbo"] < 0):
        erros.append("PUB da DBO: informe um número maior ou igual a zero, ou deixe vazio para usar o da bacia.")
    if _numero(p["fc_irrigacao"]) and p["fc_irrigacao"] > 1:
        erros.append("Fator de consumo da irrigação: informe um valor entre 0 e 1 (88% = 0,88).")
    if p["isencao_por"] not in ISENCAO_POR:
        erros.append(f"Limiar aplicado ao: use {' ou '.join(ISENCAO_POR)}.")
    if p["coeficientes_bacia"] not in COEFICIENTES_BACIA_RURAL:
        erros.append(f"Coeficientes da bacia: use {' ou '.join(COEFICIENTES_BACIA_RURAL)}.")
    if p["kout_kmed"] is not None:
        pesos = tuple(p["kout_kmed"])
        if len(pesos) != 2 or not all(_numero(v) and v >= 0 for v in pesos) or abs(sum(pesos) - 1.0) > 1e-9:
            erros.append("Pesos KOUT e KMED: informe dois pesos maiores ou iguais a zero que somem 1 (Anexo, item 3).")
    if erros:
        raise ValueError(" ".join(erros))


def premissas_rurais(cenario=CENARIO_RURAL_PADRAO, **alteracoes):
    """
    Premissas do cenário rural com as alterações do usuário por cima (chaves de PREMISSAS_RURAIS).
    Devolve um dict com "cenario" e todas as premissas. Chave ou valor inválido levanta ValueError.
    """
    if cenario not in CENARIOS_RURAIS:
        raise ValueError(f"Cenário rural desconhecido: {cenario}.")
    desconhecidas = sorted(set(alteracoes) - set(PREMISSAS_RURAIS))
    if desconhecidas:
        raise ValueError(f"Premissa rural desconhecida: {', '.join(desconhecidas)}.")
    premissas = {**CENARIOS_RURAIS[cenario]["premissas"], **alteracoes}
    _validar_premissas(premissas)
    return {"cenario": cenario, **premissas}


def _mesmo_valor(a, b):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_mesmo_valor(x, y) for x, y in zip(a, b))
    if _numero(a) and _numero(b):
        return abs(a - b) <= 1e-12
    return a == b


def origem_premissas(premissas):
    """{premissa: camada}: "Sua escolha" quando o valor difere do cenário; senão, a camada de origem."""
    base = CENARIOS_RURAIS[premissas["cenario"]]["premissas"]
    return {chave: info["camada"] if _mesmo_valor(premissas[chave], base[chave]) else "Sua escolha"
            for chave, info in PREMISSAS_RURAIS.items()}


def _regra_rural_neutra(regra):
    """Regra da bacia sem os coeficientes do decreto urbano: todos os X e Y valem 1,00 (premissa do estudo)."""
    neutra = dict(regra)
    neutra.update(campos_cap={}, fixos_cap={}, consumo_coefs={}, x5=None, campos_lanc={}, y3_modo="neutro",
                  resfriamento=None)
    return neutra


def _isencao_rural(det_cap, det_lanc, premissas, caf):
    """
    Isenção do art. 5º da minuta: marca "isento" em cada captação e devolve (dados da isenção, lançamentos isentos?).
    """
    limiar = premissas["limiar_isencao_m3_dia"]
    modo = premissas["isencao_por"]
    soma = sum(d["vazao_dia"] for d in det_cap)
    if caf:
        lanc_isento = True
        for d in det_cap:
            d["isento"] = True
    elif modo == "usuario":
        lanc_isento = soma <= limiar
        for d in det_cap:
            d["isento"] = lanc_isento
    else:
        lanc_isento = False
        for d in det_cap:
            d["isento"] = d["vazao_dia"] <= limiar
    isentas = [d for d in det_cap if d["isento"]]
    cobradas = [d for d in det_cap if not d["isento"]]
    lanc_cobrados = bool(det_lanc) and not lanc_isento
    isento = bool(det_cap or det_lanc) and not cobradas and not lanc_cobrados
    parcial = bool(isentas) and not isento

    lim = _fmt_enxuto(limiar)
    artigo = MINUTA_RURAL["artigos"]["isencao_caf" if caf else "isencao_porte"]
    if caf:
        texto = (f"Isento pela minuta ({artigo}): agricultor familiar inscrito no Cadastro Nacional da Agricultura "
                 "Familiar (CAF).")
    elif modo == "usuario":
        texto = (f"Isento pela minuta ({artigo}): a captação máxima outorgada soma {_fmt_enxuto(soma)} m³/dia, "
                 f"dentro do limiar de {lim} m³/dia." if isento else
                 f"Cobrado: a captação máxima outorgada soma {_fmt_enxuto(soma)} m³/dia, acima do limiar de isenção "
                 f"de {lim} m³/dia ({artigo}, {_DA_MINUTA}).")
    else:
        def lista(itens):
            return "; ".join(f"{d['item']} ({_fmt_enxuto(d['vazao_dia'])} m³/dia)" for d in itens)
        if not det_cap:
            texto = "Não há captação informada. Na leitura por outorga, o limiar olha só a vazão de captação."
        elif isento:
            texto = f"Isento pela minuta ({artigo}), outorga por outorga: nenhuma captação passa de {lim} m³/dia."
        elif not isentas:
            texto = f"Cobrado: todas as captações passam de {lim} m³/dia ({artigo}, {_DA_MINUTA}, outorga por outorga)."
        else:
            texto = (f"Isenção parcial, outorga por outorga ({artigo}, {_DA_MINUTA}). Isentas, com até {lim} m³/dia: "
                     f"{lista(isentas)}. Cobradas: {lista(cobradas) or 'nenhuma captação'}.")
        if lanc_cobrados:
            texto += " Os lançamentos continuam cobrados, porque o limiar olha só a vazão de captação."

    return {
        "modo": modo, "modo_texto": ISENCAO_POR[modo], "caf": caf,
        "limiar_m3_dia": limiar, "limiar_unidades": equivalencias_m3_dia(limiar),
        "captacao_m3_dia": soma, "captacao_unidades": equivalencias_m3_dia(soma),
        "isento": isento, "parcial": parcial,
        "motivo": "caf" if caf else ("porte" if isento or parcial else None),
        "artigo": artigo,
        "itens": [{"item": d["item"], "m3_dia": d["vazao_dia"], "isento": d["isento"]} for d in det_cap],
        "texto": texto,
    }, lanc_isento


def calcular_rural(bacia, captacoes, lancamentos, premissas=None, caf=False, ufesp=None):
    """
    Simula a cobrança rural de um empreendimento pela minuta do decreto rural, com as premissas do cenário.

    captacoes:   dicts com vazao, horas_dia, dias_ano, v_med, nome e finalidade_rural (uma de FINALIDADES_RURAIS;
                 vazio = Irrigação). Com os coeficientes "herdados", também os campos da bacia (natureza, classe…).
    lancamentos: dicts como os de calcular() (vazao, horas_dia, dias_ano, v_med, dbo, remocao_pct e campos da bacia).
    premissas:   alterações sobre o cenário (chaves de PREMISSAS_RURAIS); "cenario" escolhe o cenário (padrão: o
                 do estudo). "isencao_por" é a chave do limiar: "usuario" (somatório) ou "outorga" (cada outorga).
    caf:         agricultor familiar inscrito no CAF (isento, art. 5º, II).
    ufesp:       UFESP do ano, para os tetos dos PUFs; vazio = a vigente.

    Devolve o formato de calcular(), com captacao, consumo, lancamento e total já depois da isenção, e acrescenta:
    rural, minuta, cenario, premissas, origem_premissas, isencao, sem_isencao, valor_sem_isencao, preco_percebido
    (R$ por m³ captado, sem a isenção), preco_percebido_estudo, fc_formula, fc_irrigacao, fc_por_item e tetos.
    Cada item de detalhes_cap, detalhes_cons e detalhes_lanc traz "isento" e "valor_cobrado".
    """
    if bacia not in BACIAS:
        raise ValueError(f"Bacia desconhecida: {bacia}.")
    regra = regra_bacia(bacia)
    p = premissas_rurais(**(premissas or {}))
    herdados = p["coeficientes_bacia"] == "herdados"
    regra_coefs = regra if herdados else _regra_rural_neutra(regra)
    kout_kmed = tuple(p["kout_kmed"]) if p["kout_kmed"] is not None else regra["kout_kmed"]
    u = ufesp or UFESP
    teto_cap = MINUTA_RURAL["teto_puf_cap_ufesp"] * u
    teto_cons = MINUTA_RURAL["teto_puf_cons_ufesp"] * u
    pub_cap, pub_cons = p["pub_cap"], p["pub_cons"]
    pub_dbo = p["pub_dbo"] if p["pub_dbo"] is not None else regra["pub_dbo"] * regra["fator_pub"]
    arts = MINUTA_RURAL["artigos"]
    avisos = []

    # ---------- Captação ----------
    det_cap = []
    for i, c in enumerate(captacoes, start=1):
        nome = c.get("nome") or f"Captação {i}"
        finalidade = c.get("finalidade_rural") or FINALIDADE_RURAL_PADRAO
        if finalidade not in FINALIDADES_RURAIS:
            raise ValueError(f"{nome}: finalidade rural desconhecida ({finalidade}). "
                             f"Use {', '.join(FINALIDADES_RURAIS)}.")
        if herdados:
            c = dict(c)
            if "finalidade" in regra["campos_cap"]:
                c.setdefault("finalidade", list(regra["campos_cap"]["finalidade"]["opcoes"])[0])  # vale o X7 rural
            faltam = [regra["campos_cap"][k]["rotulo"] for k in regra["campos_cap"] if k != "natureza" and k not in c]
            if faltam:
                raise ValueError(f"{nome}: com os coeficientes herdados da bacia, informe {', '.join(faltam)}.")
        v_out, vazao_dia = volume_e_captacao_maxima(c)   # com sazonalidade, a soma dos meses e o maior mês
        v_med = c.get("v_med", 0.0)
        kout, kmed = pesos_kout_kmed(v_out, v_med, kout_kmed)
        v_cap = kout * v_out + kmed * v_med
        coefs, coefs_cons = _coefs_captacao(regra_coefs, c, v_out, v_med, p["x7"], p["x12"])
        puf_cap = pub_cap * _produto(coefs.values())
        limitado = puf_cap > teto_cap
        if limitado:
            puf_cap = teto_cap
            avisos.append(f"{nome}: o PUF de captação passou do teto de {fmt_brl(teto_cap, 4)}/m³ (0,001078 UFESP, "
                          f"{arts['teto_puf_cap']}, {_DA_MINUTA}) e foi limitado a esse valor.")
        det_cap.append({
            "item": nome, "finalidade_rural": finalidade, "v_out": v_out, "v_med": v_med, "kout": kout, "kmed": kmed,
            "v_cap": v_cap, "coefs": coefs, "puf_cap": puf_cap, "puf_limitado": limitado,
            "vcc": v_cap * puf_cap, "coefs_cons": coefs_cons,
            "x2_nao_se_aplica": herdados and x2_nao_se_aplica(c.get("natureza"))
                                and any(campo["coef"] == "X2" for campo in regra["campos_cap"].values()),
            "consumo_integral": False,
            "vazao_dia": vazao_dia,
            "meses": meses_da_outorga(c),   # sazonalidade: o detalhe mês a mês; vazio sem ela
        })

    # ---------- Lançamento (só DBO; Y9 = desconto por práticas de conservação) ----------
    det_lanc = [_detalhe_lancamento(regra_coefs, l, i, pub_dbo, {"Y9": p["y9"]}, permitir_afluente=False,
                                    presumir_dbo=False)
                for i, l in enumerate(lancamentos, start=1)]

    # ---------- Consumo (Anexo, item 4): irrigação com FC fixo; demais finalidades pela fórmula ----------
    VCAPT = sum(d["v_cap"] for d in det_cap)
    V_LANCT = sum(d["v_lanc"] for d in det_lanc)
    fc_formula = min(1.0, max(0.0, (VCAPT - V_LANCT) / VCAPT)) if VCAPT > 0 else 0.0
    det_cons = []
    for d in det_cap:
        irrigacao = d["finalidade_rural"] == FINALIDADE_IRRIGACAO
        fc = p["fc_irrigacao"] if irrigacao else fc_formula
        v_cons = fc * d["v_cap"]
        puf_cons = pub_cons * _produto(d["coefs_cons"].values()) * p["x7"] * p["x12"]
        limitado = puf_cons > teto_cons
        if limitado:
            puf_cons = teto_cons
            avisos.append(f"{d['item']}: o PUF de consumo passou do teto de {fmt_brl(teto_cons, 4)}/m³ (0,002156 "
                          f"UFESP, {arts['teto_puf_cons']}, {_DA_MINUTA}) e foi limitado a esse valor.")
        det_cons.append({
            "item": d["item"], "finalidade_rural": d["finalidade_rural"], "fc": fc,
            "fc_origem": arts["fc_irrigacao"] if irrigacao else arts["fc_formula"],
            "v_cons": v_cons, "coefs": d["coefs_cons"], "puf_cons": puf_cons, "puf_limitado": limitado,
            "vcco": v_cons * puf_cons,
        })

    irrigacoes = [d for d in det_cap if d["finalidade_rural"] == FINALIDADE_IRRIGACAO]
    outras = [d for d in det_cap if d["finalidade_rural"] != FINALIDADE_IRRIGACAO]
    if irrigacoes and outras and V_LANCT > 0:
        v_outras = sum(d["v_cap"] for d in outras)
        fc_sem = min(1.0, max(0.0, (v_outras - V_LANCT) / v_outras)) if v_outras > 0 else 0.0
        avisos.append(f"O fator de consumo das captações que não são de irrigação ({fmt_num(fc_formula * 100, 1)}%) "
                      "foi calculado com todo o volume captado e lançado no empreendimento, inclusive o da irrigação, "
                      f"como diz o {arts['fc_formula']}, {_DA_MINUTA}. Sem o volume da irrigação, seria "
                      f"{fmt_num(fc_sem * 100, 1)}%. Essa leitura ainda precisa ser confirmada com a SP Águas.")

    # ---------- Isenção (art. 5º) e teto do lançamento (art. 11) ----------
    isencao, lanc_isento = _isencao_rural(det_cap, det_lanc, p, caf)
    vcc_total = sum(d["vcc"] for d in det_cap)
    vcco_total = sum(d["vcco"] for d in det_cons)
    teto = _teto_lancamento(vcc_total, vcco_total, det_lanc, norma=f"{arts['teto_lancamento']} {_DA_MINUTA}")
    if teto["aviso"] and not lanc_isento:
        avisos.append(teto["aviso"])
    fator_lanc = 0.0 if lanc_isento else (teto["vcl"] / teto["vcl_bruto"] if teto["vcl_bruto"] else 1.0)
    for d, dc in zip(det_cap, det_cons):
        dc["isento"] = d["isento"]
        d["valor_cobrado"] = 0.0 if d["isento"] else d["vcc"]
        dc["valor_cobrado"] = 0.0 if d["isento"] else dc["vcco"]
    for d in det_lanc:
        d["isento"] = lanc_isento
        d["valor_cobrado"] = d["vcl"] * fator_lanc

    vcc = sum(d["valor_cobrado"] for d in det_cap)
    vcco = sum(d["valor_cobrado"] for d in det_cons)
    vcl = 0.0 if lanc_isento else teto["vcl"]
    sem_isencao = {"captacao": vcc_total, "consumo": vcco_total, "lancamento": teto["vcl"],
                   "total": vcc_total + vcco_total + teto["vcl"]}
    cenario = CENARIOS_RURAIS[p["cenario"]]
    return {
        "bacia": bacia,
        "regra": regra,
        "rural": True,
        "minuta": MINUTA_RURAL,
        "cenario": p["cenario"],
        "cenario_fonte": cenario["fonte"],
        "premissas": p,
        "origem_premissas": origem_premissas(p),
        "pubs_aplicados": {"cap": pub_cap, "cons": pub_cons, "dbo": pub_dbo},
        "FC": sum(d["v_cons"] for d in det_cons) / VCAPT if VCAPT > 0 else 0.0,
        "fc_formula": fc_formula,
        "fc_irrigacao": p["fc_irrigacao"],
        "fc_por_item": [{"item": d["item"], "finalidade_rural": d["finalidade_rural"], "fc": d["fc"],
                         "origem": d["fc_origem"]} for d in det_cons],
        "VCAPT": VCAPT,
        "V_LANCT": V_LANCT,
        "captacao": vcc,
        "consumo": vcco,
        "lancamento": vcl,
        "lancamento_bruto": teto["vcl_bruto"],
        "lancamento_limitado": teto["limitado"] and not lanc_isento,
        "teto_lancamento": teto["teto"],
        "teto_lancamento_excedido": teto["excedido"] and not lanc_isento,
        "lancamentos_fora_do_padrao": [d["item"] for d in teto["fora_do_padrao"]],
        "total": vcc + vcco + vcl,
        "detalhes_cap": det_cap,
        "detalhes_cons": det_cons,
        "detalhes_lanc": det_lanc,
        "detalhes_min": [],
        "mineracao": 0.0,
        "avisos": avisos,
        "isencao": isencao,
        "sem_isencao": sem_isencao,
        "valor_sem_isencao": sem_isencao["total"],
        "preco_percebido": (vcc_total + vcco_total) / VCAPT if VCAPT > 0 else 0.0,
        "preco_percebido_estudo": cenario["preco_percebido"],
        "tetos": {"ufesp": u, "puf_cap": teto_cap, "puf_cons": teto_cons},
    }
