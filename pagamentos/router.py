from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from .schema import Payments, PaymentsCreate, PaymentsUpdate

router = APIRouter(prefix="/tipos-pagamentos", tags=["Pagamentos"])


@router.get("/", response_model=list[Payments])
async def list_payments(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Payments))
    return result.all()


@router.get("/ativos", response_model=list[Payments])
async def list_active_payments(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Payments).where(Payments.ativo.is_(True)))
    return result.all()


@router.get("/{payment_id}", response_model=Payments)
async def get_payment(payment_id: int, session: AsyncSession = Depends(get_session)):
    payment = await session.get(Payments, payment_id)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de pagamento não encontrado")
    return payment


@router.post("/", response_model=Payments, status_code=status.HTTP_201_CREATED)
async def create_payment(payment: PaymentsCreate, session: AsyncSession = Depends(get_session)):
    db_payment = Payments(**payment.model_dump())
    session.add(db_payment)
    await session.commit()
    await session.refresh(db_payment)
    return db_payment


@router.patch("/{payment_id}", response_model=Payments)
async def update_payment(payment_id: int, payment_update: PaymentsUpdate, session: AsyncSession = Depends(get_session)):
    db_payment = await session.get(Payments, payment_id)
    if not db_payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de pagamento não encontrado")

    payment_data = payment_update.model_dump(exclude_unset=True)
    for field, value in payment_data.items():
        setattr(db_payment, field, value)

    session.add(db_payment)
    await session.commit()
    await session.refresh(db_payment)
    return db_payment


@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payment(payment_id: int, session: AsyncSession = Depends(get_session)):
    db_payment = await session.get(Payments, payment_id)
    if not db_payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tipo de pagamento não encontrado")

    await session.delete(db_payment)
    await session.commit()
    return None
