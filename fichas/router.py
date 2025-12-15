"""
Router para endpoints de Fichas.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from config import settings
from pedidos.router import require_admin
from .image_storage import (
    save_base64_image,
    delete_ficha_image,
    ImageStorageError,
    absolute_media_path,
)
from .schema import (
    Ficha,
    FichaCreate,
    FichaResponse,
    FichaTemplateData,
    FichaTemplateModel,
    FichaTemplateResponse,
    FichaTemplatesResponse,
    FichaTemplatesUpdate,
    FichaUpdate,
    TemplateFieldPayload,
    TemplateType,
    TemplateTypeEnum,
)

router = APIRouter(prefix="/fichas", tags=["Fichas"])


def _build_ficha_response(ficha: Ficha) -> FichaResponse:
    """Constrói FichaResponse com imagem_url calculada."""
    data = ficha.model_dump()
    if ficha.imagem_path:
        # Construir URL relativa ao endpoint de imagens (considerando prefixo da API)
        api_prefix = settings.API_V1_STR.rstrip("/") if settings.API_V1_STR else ""
        data["imagem_url"] = f"{api_prefix}/fichas/imagens/{ficha.id}"
    else:
        data["imagem_url"] = None
    return FichaResponse(**data)


def _clone_default_template(template: FichaTemplateData) -> FichaTemplateData:
    return FichaTemplateData.model_validate(template.model_dump())


DEFAULT_TEMPLATES: Dict[TemplateType, FichaTemplateData] = {
    "geral": FichaTemplateData(
        title="FICHA DE SERVIÇO - GERAL",
        width=210,
        height=297,
        marginTop=10,
        marginBottom=10,
        marginLeft=15,
        marginRight=15,
        fields=[
            TemplateFieldPayload(
                id="title_field",
                type="text",
                label="FICHA DE SERVIÇO",
                key="title",
                x=70,
                y=10,
                width=70,
                height=10,
                fontSize=16,
                bold=True,
            ),
            TemplateFieldPayload(
                id="numero_os_field",
                type="text",
                label="OS:",
                key="numero",
                x=10,
                y=25,
                width=30,
                height=6,
                fontSize=11,
            ),
            TemplateFieldPayload(
                id="cliente_field",
                type="text",
                label="Cliente:",
                key="cliente",
                x=10,
                y=35,
                width=80,
                height=6,
                fontSize=11,
            ),
            TemplateFieldPayload(
                id="descricao_field",
                type="text",
                label="Descrição:",
                key="item_name",
                x=10,
                y=50,
                width=90,
                height=8,
                fontSize=11,
            ),
        ],
    ),
    "resumo": FichaTemplateData(
        title="FICHA DE SERVIÇO - RESUMO PRODUÇÃO",
        width=70,
        height=99,
        marginTop=3,
        marginBottom=3,
        marginLeft=5,
        marginRight=5,
        fields=[
            TemplateFieldPayload(
                id="numero_os_resumo",
                type="text",
                label="OS:",
                key="numero",
                x=5,
                y=5,
                width=15,
                height=5,
                fontSize=10,
                bold=True,
            ),
            TemplateFieldPayload(
                id="descricao_resumo",
                type="text",
                label="Desc:",
                key="item_name",
                x=5,
                y=12,
                width=60,
                height=8,
                fontSize=9,
            ),
            TemplateFieldPayload(
                id="tamanho_resumo",
                type="text",
                label="Tam:",
                key="dimensoes",
                x=5,
                y=22,
                width=30,
                height=5,
                fontSize=8,
            ),
            TemplateFieldPayload(
                id="quantidade_resumo",
                type="number",
                label="Qtd:",
                key="quantity",
                x=5,
                y=30,
                width=15,
                height=5,
                fontSize=9,
            ),
            TemplateFieldPayload(
                id="tecido_resumo",
                type="text",
                label="Tecido:",
                key="tecido",
                x=5,
                y=38,
                width=30,
                height=5,
                fontSize=8,
            ),
        ],
    ),
}


def _ensure_field_defaults(field: TemplateFieldPayload) -> TemplateFieldPayload:
    data = field.model_dump()
    if data.get("fontSize") is None:
        data["fontSize"] = 11
    if data.get("visible") is None:
        data["visible"] = True
    if data.get("editable") is None:
        data["editable"] = True
    return TemplateFieldPayload(**data)


def _serialize_fields(fields: list[TemplateFieldPayload]) -> list[dict]:
    return [
        _ensure_field_defaults(field).model_dump()
        for field in fields
    ]


def _build_template_response(
    template_type: TemplateType,
    template: Optional[FichaTemplateModel],
) -> FichaTemplateResponse:
    if template:
        fields = [
            _ensure_field_defaults(TemplateFieldPayload.model_validate(field))
            for field in template.fields or []
        ]
        data = FichaTemplateData(
            title=template.title,
            width=template.width,
            height=template.height,
            marginTop=template.marginTop,
            marginBottom=template.marginBottom,
            marginLeft=template.marginLeft,
            marginRight=template.marginRight,
            fields=fields,
        )
        updated_at = template.updatedAt
    else:
        data = _clone_default_template(DEFAULT_TEMPLATES[template_type])
        updated_at = datetime.utcnow()

    return FichaTemplateResponse(
        templateType=template_type,
        updatedAt=updated_at,
        **data.model_dump(),
    )


async def _load_templates_response(
    session: AsyncSession,
) -> FichaTemplatesResponse:
    result = await session.exec(select(FichaTemplateModel))
    templates = {tpl.template_type.value: tpl for tpl in result.all()}

    return FichaTemplatesResponse(
        geral=_build_template_response("geral", templates.get("geral")),
        resumo=_build_template_response("resumo", templates.get("resumo")),
    )


async def _upsert_template(
    template_type: TemplateType,
    data: FichaTemplateData,
    session: AsyncSession,
) -> None:
    fields_payload = _serialize_fields(data.fields or [])
    template_type_enum = TemplateTypeEnum(template_type)

    statement = select(FichaTemplateModel).where(FichaTemplateModel.template_type == template_type_enum)
    result = await session.exec(statement)
    existing = result.first()

    if existing:
        existing.title = data.title
        existing.width = data.width
        existing.height = data.height
        existing.marginTop = data.marginTop
        existing.marginBottom = data.marginBottom
        existing.marginLeft = data.marginLeft
        existing.marginRight = data.marginRight
        existing.fields = fields_payload
        existing.updatedAt = datetime.utcnow()
        session.add(existing)
    else:
        session.add(
            FichaTemplateModel(
                template_type=template_type_enum,
                title=data.title,
                width=data.width,
                height=data.height,
                marginTop=data.marginTop,
                marginBottom=data.marginBottom,
                marginLeft=data.marginLeft,
                marginRight=data.marginRight,
                fields=fields_payload,
            )
        )


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
        
        return _build_ficha_response(db_ficha)
        
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
            # Deletar imagem antiga se existir
            if db_ficha.imagem_path:
                delete_ficha_image(db_ficha.imagem_path)
            
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
        
        return _build_ficha_response(db_ficha)
        
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
        
        return _build_ficha_response(ficha)
        
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
        
        return [_build_ficha_response(ficha) for ficha in fichas]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar fichas: {str(e)}")


@router.get("/templates", response_model=FichaTemplatesResponse)
async def obter_templates(
    session: AsyncSession = Depends(get_session),
) -> FichaTemplatesResponse:
    try:
        return await _load_templates_response(session)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar templates: {exc}") from exc


@router.put("/templates", response_model=FichaTemplatesResponse)
async def salvar_templates(
    payload: FichaTemplatesUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: bool = Depends(require_admin),
) -> FichaTemplatesResponse:
    try:
        await _upsert_template("geral", payload.geral, session)
        await _upsert_template("resumo", payload.resumo, session)
        await session.commit()
        return await _load_templates_response(session)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao salvar templates: {exc}") from exc


@router.delete("/{ficha_id}")
async def deletar_ficha(
    ficha_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: bool = Depends(require_admin),
):
    """
    Deleta uma ficha e sua imagem associada.
    Requer permissão de administrador.
    """
    try:
        db_ficha = await session.get(Ficha, ficha_id)
        if not db_ficha:
            raise HTTPException(status_code=404, detail="Ficha não encontrada")
        
        # Deletar imagem se existir
        if db_ficha.imagem_path:
            delete_ficha_image(db_ficha.imagem_path)
        
        # Deletar ficha do banco
        await session.delete(db_ficha)
        await session.commit()
        
        return {"message": f"Ficha {ficha_id} deletada com sucesso"}
        
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar ficha: {str(e)}")


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
        
        # Detectar tipo MIME baseado na extensão
        ext = absolute_path.suffix.lower()
        media_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
        }
        media_type = media_types.get(ext, 'image/png')
        
        return FileResponse(
            absolute_path,
            media_type=media_type,
            filename=Path(ficha.imagem_path).name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter imagem: {str(e)}")
