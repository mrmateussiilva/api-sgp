from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Machine, MachineCreate, MachineUpdate, MachineDashboardData, MachineDashboardItem
from pedidos.schema import Pedido, Status
from pedidos.service import json_string_to_items

router = APIRouter(prefix="/maquinas", tags=["Máquinas"])


@router.get("/", response_model=list[Machine])
async def list_machines(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Machine))
    return result.all()


@router.get("/ativos", response_model=list[Machine])
async def list_active_machines(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Machine).where(Machine.active.is_(True)))
    return result.all()


@router.get("/{machine_id}", response_model=Machine)
async def get_machine(machine_id: int, session: AsyncSession = Depends(get_session)):
    machine = await session.get(Machine, machine_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Máquina não encontrada")
    return machine


@router.post("/", response_model=Machine, status_code=status.HTTP_201_CREATED)
async def create_machine(machine: MachineCreate, session: AsyncSession = Depends(get_session)):
    db_machine = Machine(**machine.model_dump())
    session.add(db_machine)
    await session.commit()
    await session.refresh(db_machine)
    return db_machine


@router.patch("/{machine_id}", response_model=Machine)
async def update_machine(
    machine_id: int,
    machine_update: MachineUpdate,
    session: AsyncSession = Depends(get_session),
):
    db_machine = await session.get(Machine, machine_id)
    if not db_machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Máquina não encontrada")

    update_data = machine_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_machine, field, value)

    session.add(db_machine)
    await session.commit()
    await session.refresh(db_machine)
    return db_machine


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine(machine_id: int, session: AsyncSession = Depends(get_session)):
    db_machine = await session.get(Machine, machine_id)
    if not db_machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Máquina não encontrada")

    await session.delete(db_machine)
    await session.commit()
    return None


@router.get("/dashboard/overview", response_model=list[MachineDashboardData])
async def get_machines_dashboard(session: AsyncSession = Depends(get_session)):
    """
    Retorna o dashboard de produção agrupado por máquina.
    Apenas pedidos pendentes ou em produção.
    """
    # 1. Buscar máquinas ativas
    machines = await session.exec(select(Machine).where(Machine.active.is_(True)))
    active_machines = machines.all()
    
    # Mapa para fácil acesso e resultado inicial
    machines_map = {
        m.id: MachineDashboardData(
            machine_id=m.id, 
            machine_name=m.name, 
            total_items=0, 
            total_area=0.0, 
            queue=[]
        ) 
        for m in active_machines
    }
    
    # Adicionar "Sem Máquina" (opcional, ID 0 ou None)
    # machines_map[0] = MachineDashboardData(machine_id=0, machine_name="Sem Máquina", total_items=0, total_area=0.0, queue=[])

    # 2. Buscar pedidos ativos
    query = select(Pedido).where(
        Pedido.status.in_([Status.PENDENTE, Status.EM_PRODUCAO])
    )
    result = await session.exec(query)
    pedidos = result.all()
    
    # 3. Processar itens
    for pedido in pedidos:
        if not pedido.items:
            continue
            
        items = json_string_to_items(pedido.items)
        
        for i, item in enumerate(items):
            # Ignorar itens já prontos (se houver flag no item, mas normalmente status é do pedido)
            # Vamos assumir que se o pedido está em produção, todos os itens contam, 
            # ou precisaríamos de status por item. Por enquanto, conta tudo.
            
            # Verificar machine_id
            machine_id = item.machine_id
            if machine_id is None:
                continue # Ou agrupar em "Sem Máquina"
                
            if machine_id not in machines_map:
                continue # Máquina inativa ou removida
                
            # Calcular área
            area = 0.0
            try:
                if item.metro_quadrado:
                    # Formato esperado: "10,50" ou "10.50"
                    val_str = str(item.metro_quadrado).replace(',', '.')
                    area = float(val_str)
            except:
                area = 0.0
                
            # Criar item do dashboard
            dashboard_item = MachineDashboardItem(
                order_id=pedido.id,
                order_number=pedido.numero,
                item_index=i,
                item_name=item.descricao or item.tipo_producao,
                dimensions=f"{item.largura}x{item.altura}",
                material=item.tecido,
                date_due=pedido.data_entrega,
                preview_url=item.imagem,
                status=pedido.status, # Status do item herda do pedido por enquanto
                priority=getattr(pedido, 'prioridade', 'NORMAL')
            )
            
            # Atualizar métricas da máquina
            machines_map[machine_id].queue.append(dashboard_item)
            machines_map[machine_id].total_items += 1
            machines_map[machine_id].total_area += area
            
    # Retornar lista ordenada por nome da máquina
    return sorted(list(machines_map.values()), key=lambda x: x.machine_name)
