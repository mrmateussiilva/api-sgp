from datetime import date
from typing import List

from pedidos.schema import FichaPedido, Prioridade
from pagamentos.schema import Payments
from clientes.schema import Cliente
from envios.schema import Envio

# ajuste conforme seu projeto

# Simulando um banco de dados em memória
pedidos_fake: List[FichaPedido] = [
    FichaPedido(
        numero="001",
        cliente="Mateus José da Silva",
        telefone="27999999999",
        cidade="Colatina",
        data_entrada=str(date.today().strftime("%d/%m/%Y")),
        data_entrega=str(date.today().strftime("%d/%m/%Y")),
        status="pendente",
        prioridade=Prioridade.ALTA,
        financeiro=False,
        sublimação=False,
        costura=False,
        expedicao=False,
        observacao="Urgente",
        tipo_pagamento="PIX",
        obs_pagamento="Pago antecipado",
        valor_total="150.00",
        valor_frete="20.00",
        items=[]
    ),
    FichaPedido(
        numero="002",
        cliente="Carlos Souza",
        telefone="27988888888",
        cidade="Vitória",
        data_entrada=str(date.today().strftime("%d/%m/%Y")),
        data_entrega=str(date.today().strftime("%d/%m/%Y")),
        status="pronto",
        prioridade=Prioridade.NORMAL,
        financeiro=True,
        sublimação=True,
        costura=True,
        expedicao=True,
        observacao="Entrega no balcão",
        tipo_pagamento="Dinheiro",
        obs_pagamento="A receber",
        valor_total="200.00",
        valor_frete="30.00",
        items=[]
    ),
]


clientes: List[Cliente] = [
    Cliente(
        id=0,
        nome="Mateus",
        cep="29701340",
        cidade="colatina",
        estado="es",
        telefone="27 995900071"
    ),
    Cliente(
        id=1,
        nome="Breno Polezi",
        cep="29701340",
        cidade="linhares",
        estado="es",
        telefone="27 000900071"
    ),
]


tiposPagamentos: List[Payments] = [
    Payments(id=1, name="PIX"),
    Payments(id=2, name="Link Cartão"),
    Payments(id=3, name="Boleto"),
    Payments(id=4, name="Dinheiro"),
]


Transportadoras: List[Ellipsis] = [
    Envio(id=1, name="Correios", value=40.00),
    Envio(id=2, name="Viação Aguia Branca", value=40.00),
    Envio(id=3, name="Viação Pretti", value=50.00),
    Envio(id=4, name="Flex",),
    Envio(id=5, name="Retirada"),
]
