"""
Router para endpoints de Fichas.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime

from fastapi.responses import FileResponse
from pathlib import Path

from base import get_session
from .schema import Ficha, FichaCreate, FichaUpdate, FichaResponse
from .image_storage import save_base64_image, ImageStorageError, absolute_media_path

router = APIRouter(prefix="/fichas", tags=["Fichas"])


@router.post("/", response_model=FichaResponse)
async def criar_ficha(
    ficha: FichaCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Cria uma nova ficha com todos os dados fornecidos.
    Se imagem_base64 for fornecida, salva a imagem e armazena o caminho.
    """
    try:
        # Preparar dados da ficha (sem imagem_base64)
        ficha_data = ficha.model_dump(exclude_unset=True, exclude={"imagem_base64"})
        imagem_base64 = ficha.imagem_base64
        
        # Criar ficha no banco
        db_ficha = Ficha(
            **ficha_data,
            data_criacao=datetime.utcnow(),
            ultima_atualizacao=datetime.utcnow()
        )
        
        session.add(db_ficha)
        await session.flush()  # Para obter o ID
        
        # Processar imagem se fornecida
        if imagem_base64:
            try:
                imagem_path = save_base64_image(imagem_base64, db_ficha.id)
                db_ficha.imagem_path = imagem_path
                session.add(db_ficha)
            except ImageStorageError as exc:
                await session.rollback()
                raise HTTPException(status_code=400, detail=f"Erro ao salvar imagem: {str(exc)}")
        
        await session.commit()
        await session.refresh(db_ficha)
        
        return FichaResponse(**db_ficha.model_dump())
        
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao criar ficha: {str(e)}")


@router.patch("/{ficha_id}", response_model=FichaResponse)
async def atualizar_ficha(
    ficha_id: int,
    ficha_update: FichaUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Atualiza uma ficha existente.
    Se imagem_base64 for fornecida, salva a nova imagem e atualiza o caminho.
    """
    try:
        db_ficha = await session.get(Ficha, ficha_id)
        if not db_ficha:
            raise HTTPException(status_code=404, detail="Ficha não encontrada")
        
        # Preparar dados de atualização (sem imagem_base64)
        update_data = ficha_update.model_dump(exclude_unset=True, exclude={"imagem_base64"})
        imagem_base64 = ficha_update.imagem_base64
        
        # Processar nova imagem se fornecida
        if imagem_base64 is not None:
            try:
                imagem_path = save_base64_image(imagem_base64, ficha_id)
                update_data["imagem_path"] = imagem_path
            except ImageStorageError as exc:
                raise HTTPException(status_code=400, detail=f"Erro ao salvar imagem: {str(exc)}")
        
        # Atualizar timestamp
        update_data["ultima_atualizacao"] = datetime.utcnow()
        
        # Aplicar atualizações
        for field, value in update_data.items():
            setattr(db_ficha, field, value)
        
        session.add(db_ficha)
        await session.commit()
        await session.refresh(db_ficha)
        
        return FichaResponse(**db_ficha.model_dump())
        
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao atualizar ficha: {str(e)}")


@router.get("/{ficha_id}", response_model=FichaResponse)
async def obter_ficha(
    ficha_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Obtém uma ficha específica por ID."""
    try:
        ficha = await session.get(Ficha, ficha_id)
        if not ficha:
            raise HTTPException(status_code=404, detail="Ficha não encontrada")
        
        return FichaResponse(**ficha.model_dump())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter ficha: {str(e)}")


@router.get("/", response_model=list[FichaResponse])
async def listar_fichas(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100
):
    """Lista todas as fichas."""
    try:
        from sqlmodel import select
        
        statement = select(Ficha).offset(skip).limit(limit).order_by(Ficha.data_criacao.desc())
        result = await session.exec(statement)
        fichas = result.all()
        
        return [FichaResponse(**ficha.model_dump()) for ficha in fichas]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar fichas: {str(e)}")


@router.get("/imagens/{ficha_id}")
async def obter_imagem_ficha(
    ficha_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Retorna a imagem de uma ficha específica.
    """
    try:
        ficha = await session.get(Ficha, ficha_id)
        if not ficha:
            raise HTTPException(status_code=404, detail="Ficha não encontrada")
        
        if not ficha.imagem_path:
            raise HTTPException(status_code=404, detail="Ficha não possui imagem")
        
        try:
            absolute_path = absolute_media_path(ficha.imagem_path)
        except ImageStorageError:
            raise HTTPException(status_code=404, detail="Caminho de imagem inválido")
        
        if not absolute_path.exists():
            raise HTTPException(status_code=404, detail="Arquivo de imagem não encontrado")
        
        return FileResponse(
            absolute_path,
            media_type="image/png",
            filename=Path(ficha.imagem_path).name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter imagem: {str(e)}")

