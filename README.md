# Cálculo da cobrança SP-ÁGUAS
Este projeto visa o desenvolvimento de uma calculadora/simulador da cobrança pelo uso da água no Estado de São Paulo. A cobrança pelo uso da água segue um decreto específico vigente para cada bacia hidrográfica. Os valores a serem cobrados, as ponderações, os coeficientes, o procedimento de cobrança, as fórmulas, entre outros aspectos, podem variar de acordo com o decreto vigente em cada Unidade de Gerenciamento de Recursos Hídricos (UGRHI). Dessa forma, cada Comitê de Bacia Hidrográfica (CBH) possui suas próprias especificidades de cálculo.

Nesse sentido, este projeto busca facilitar a visualização, pelo usuário, dos valores cobrados, sem que ele precise realizar a leitura minuciosa de cada decreto de seu interesse. Em outras palavras, trata-se de uma ferramenta destinada ao cidadão, que pode ser utilizada tanto por usuários que desejam conferir os valores cobrados pela agência em relação ao seu empreendimento quanto como simulador para pessoas físicas e jurídicas que ainda não possuem um empreendimento com uso outorgado, mas desejam avaliar previamente o impacto financeiro que ele poderá gerar.

Utilizamos a biblioteca streamlit para produzir uma página web acessível ao usuário. O simulador está disponível em https://calculadora-uso-das-aguas-spaguas.streamlit.app

## Estrutura

| Arquivo | Conteúdo |
| :--- | :--- |
| `app.py` | Interface em Streamlit: escolha da bacia e do tipo de usuário, cartões de captação e lançamento, guias de preenchimento, resultado e memória de cálculo. |
| `motor_calculo.py` | Regras de cada bacia (PUBs e coeficientes transcritos dos decretos), fórmulas do Decreto nº 50.667/2006 e formatação de números no padrão brasileiro. Não depende do Streamlit. |
| `requirements.txt` | Bibliotecas usadas pelo simulador. |
| `.streamlit/config.toml` | Tema: fonte Montserrat e cores da SP Águas. |
| `SP-Águas---Colorido.png` | Logotipo do cabeçalho. |
| `Execução_python_simulador.docx` | Passo a passo para rodar o simulador no VS Code. |

Os textos dos decretos, as transcrições dos anexos, os testes automatizados e os relatórios técnicos ficam no repositório de desenvolvimento e não fazem parte desta publicação.

## O que o simulador calcula

**Bacias:** as 21 bacias (22 UGRHIs) do Estado, cada uma com as regras do seu decreto de cobrança e o link para o texto oficial na ALESP. Paraíba do Sul e Serra da Mantiqueira também têm a simulação das revisões aprovadas pelos comitês e ainda sem decreto, com a transição progressiva entre o PUB atual e o novo. Nas bacias cujo decreto tem regra própria para a mineração de areia, ela é lançada em um item à parte.

**Captação subterrânea (poço):** a classe do corpo d'água (X2) não se aplica e vale 1,00, com a explicação logo abaixo do campo. A classe é o enquadramento dos rios (Decreto Estadual nº 10.755/1977), que não classifica aquíferos. O poço continua pagando o X1 (natureza) e os demais coeficientes da bacia, e o lançamento continua pela classe do rio receptor (Y1).

**Teto do lançamento:** o limite de 3 vezes captação + consumo (art. 11 do Decreto nº 50.667/2006) só é aplicado quando todos os lançamentos atendem ao padrão de DBO: até 60 mg/L, ou remoção de pelo menos 80%. Fora do padrão, o lançamento é cobrado integralmente.

**DBO do afluente:** em Pardo, Turvo/Grande, Médio Paranapanema e Aguapeí/Peixe, o cartão de lançamento segue o requisito do SisCob 2.0 para o lançamento superficial. Pede a concentração remanescente de DBO e o fator de eficiência de remoção (FER); a DBO do afluente (Cc) e o fator de tratamento (FTR) são opcionais. Com a DBO do afluente, a carga é volume lançado × Cc × (1 − FTR × FER), como nos decretos dessas bacias, e o valor é a carga × PUB, sem os coeficientes Y, como no requisito. Para seguir o texto dos decretos, que multiplicam a carga pelo PUF com os Y, mude `CARGA_AFLUENTE_SO_PUB` para `False` em `motor_calculo.py`.

**Lançamento sem DBO declarada:** a calculadora adota 300 mg/L de DBO e remoção de 0%, como manda a Resolução Conjunta SERHS/SMA nº 1/2006 (art. 6º, § 2º) para quem não informa a DBO. O Y3 fica em 1,00, e o teto do lançamento não se aplica. A regra não vale para o resfriamento em circuito aberto nem para o modo rural. Para desligá-la, mude `DBO_PRESUMIDA_MG_L` para `None` em `motor_calculo.py`.

**Horas por dia:** podem ser digitadas em hora e minuto (`7:30`) ou em hora decimal (`7,5`), como em muitos pareceres técnicos. O formato se escolhe na chave "Hora decimal", ao lado do rótulo de cada campo de horas, e o cálculo usa sempre a hora decimal.

**Modo rural:** simula a cobrança pelo uso rural segundo a minuta de decreto em discussão na CT-COB (versão preliminar de 31/08/2026). A cobrança rural ainda não está vigente, e o resultado é um cenário. A simulação parte das premissas do estudo da SP Águas apresentado em 07/10/2026, que o usuário pode alterar no painel "Premissas do cenário rural": PUBs, coeficientes X7, X12 e Y9, fator de consumo da irrigação (88%) e limiar de isenção de 300 m³/dia. O agricultor familiar inscrito no CAF é isento. A chave "Sazonalidade" abre a outorga mês a mês, e a chave "Comparar com a regra urbana da bacia" mostra quanto o mesmo uso pagaria pelo decreto urbano.

## Chaves de configuração

| Chave | Efeito |
| :--- | :--- |
| `SP_AGUAS_LOTE_SISCOB=1` | Mostra a seção "Lote de cobrança mensal (SisCob 2.0)", que divide o valor anual nas faturas do lote, outorga por outorga. Desligada na versão pública. |
| `SP_AGUAS_COMPARACAO_URBANA=0` | Tira do modo rural a chave de comparação com a regra urbana. |
| `SP_AGUAS_SOMENTE_RURAL=1` | Edição só rural, usada na apresentação à CT-COB: some a escolha do tipo de usuário. Também liga com um arquivo `SOMENTE_RURAL.txt` na pasta do app. |

## Como rodar

No terminal do VS Code, na pasta do projeto (o mesmo passo a passo de `Execução_python_simulador.docx`, com a instalação das bibliotecas):

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Manutenção anual

Todo mês de janeiro, atualize `UFESP` e `UFESP_ANO` em `motor_calculo.py` (Comunicado DICAR da Sefaz-SP) e inclua o ano novo em `UFESP_POR_ANO`, usada no lote de cobrança. A UFESP define o teto do preço de captação e o valor mínimo de cobrança da Serra da Mantiqueira.

## Histórico e créditos

- **Versão original (julho a setembro de 2026): Igor Correia** ([@Economistico](https://github.com/Economistico)). Criou o projeto e a primeira versão do simulador em Streamlit, com a identidade visual da SP Águas (paleta, fonte Montserrat e logotipo), a lista das 21 bacias, a escolha entre cobrança urbana/industrial e rural, as tabelas de captação/consumo e lançamento e o cálculo do Alto Paranapanema, com os coeficientes X7 e X12 para simular o uso rural. O histórico dessa construção está nos commits de 16/07/2026 a 01/09/2026.
- **Versão 2 (novembro de 2026): Gregório Sanches** ([@Gregsanches](https://github.com/Gregsanches)). Partiu da versão original e separou as regras num motor de cálculo próprio (`motor_calculo.py`), estendeu o cálculo às 21 bacias, conferidas com os decretos na ALESP, e trocou as tabelas por cartões de captação e lançamento com memória de cálculo. Incluiu ainda o modo rural pela minuta da CT-COB, a DBO do afluente nas quatro bacias que a preveem, a DBO presumida de 300 mg/L e o simulador do lote mensal do SisCob 2.0.
