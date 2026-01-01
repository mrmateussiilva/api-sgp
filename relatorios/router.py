"""
Router para endpoints de Templates de Relatórios.
"""

from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from base import get_session
from pedidos.router import require_admin
from .schema import (
    RelatorioTemplateData,
    RelatorioTemplateModel,
    RelatorioTemplateResponse,
    RelatorioTemplatesResponse,
    RelatorioTemplatesUpdate,
    RelatorioTemplateType,
    RelatorioTemplateTypeEnum,
)

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


# Templates padrão
DEFAULT_ENVIOS_TEMPLATE: RelatorioTemplateData = RelatorioTemplateData(
    title="Relatório de Envios",
    headerFields={
        "title": "Relatório de Envios",
        "subtitle": "",
        "periodoLabel": "Período:",
        "dataGeracaoLabel": "Gerado em:",
        "totalPedidosLabel": "Total de pedidos:",
    },
    styles={
        "fontFamily": "system-ui, -apple-system, sans-serif",
        "fontSize": 12,
        "titleSize": 20,
        "subtitleSize": 14,
        "textColor": "#0f172a",
        "headerColor": "#1e293b",
        "borderColor": "#cbd5e1",
        "backgroundColor": "#ffffff",
    },
    tableConfig={
        "showHeader": True,
        "headerStyle": {
            "backgroundColor": "#2563eb",
            "textColor": "#ffffff",
            "bold": True,
        },
        "alternatingRows": True,
        "cellPadding": 6,
    },
    pageConfig={
        "marginTop": 20,
        "marginBottom": 20,
        "marginLeft": 14,
        "marginRight": 14,
    },
)

DEFAULT_FECHAMENTOS_TEMPLATE: RelatorioTemplateData = RelatorioTemplateData(
    title="Relatório de Fechamentos",
    headerFields={
        "title": "Relatório de Fechamentos",
        "subtitle": "",
        "periodoLabel": "Período:",
        "dataGeracaoLabel": "Emitido em:",
        "statusLabel": "Status:",
    },
    styles={
        "fontFamily": "system-ui, -apple-system, sans-serif",
        "fontSize": 11,
        "titleSize": 18,
        "subtitleSize": 13,
        "textColor": "#0f172a",
        "headerColor": "#1e293b",
        "borderColor": "#cbd5e1",
        "backgroundColor": "#ffffff",
    },
    tableConfig={
        "showHeader": True,
        "headerStyle": {
            "backgroundColor": "#e2e8f0",
            "textColor": "#1e293b",
            "bold": True,
        },
        "alternatingRows": True,
        "cellPadding": 4,
    },
    pageConfig={
        "marginTop": 22,
        "marginBottom": 22,
        "marginLeft": 14,
        "marginRight": 14,
    },
)

DEFAULT_TEMPLATES: Dict[RelatorioTemplateType, RelatorioTemplateData] = {
    "envios": DEFAULT_ENVIOS_TEMPLATE,
    "fechamentos": DEFAULT_FECHAMENTOS_TEMPLATE,
}


def _build_template_response(
    template_type: RelatorioTemplateType,
    template: Optional[RelatorioTemplateModel],
) -> RelatorioTemplateResponse:
    """Constrói resposta do template."""
    if template:
        data = RelatorioTemplateData(
            title=template.title,
            headerFields=template.headerFields or {},
            styles=template.styles or {},
            tableConfig=template.tableConfig,
            pageConfig=template.pageConfig,
        )
        updated_at = template.updatedAt
    else:
        # Usar template padrão
        default_template = DEFAULT_TEMPLATES[template_type]
        data = RelatorioTemplateData(
            title=default_template.title,
            headerFields=default_template.headerFields,
            styles=default_template.styles,
            tableConfig=default_template.tableConfig,
            pageConfig=default_template.pageConfig,
        )
        updated_at = datetime.utcnow()

    return RelatorioTemplateResponse(
        **data.model_dump(),
        updatedAt=updated_at,
    )


async def _load_templates_response(
    session: AsyncSession,
) -> RelatorioTemplatesResponse:
    """Carrega templates do banco de dados."""
    result = await session.exec(select(RelatorioTemplateModel))
    templates = {tpl.template_type.value: tpl for tpl in result.all()}

    return RelatorioTemplatesResponse(
        envios=_build_template_response("envios", templates.get("envios")),
        fechamentos=_build_template_response("fechamentos", templates.get("fechamentos")),
    )


async def _upsert_template(
    template_type: RelatorioTemplateType,
    data: RelatorioTemplateData,
    session: AsyncSession,
) -> None:
    """Cria ou atualiza template no banco."""
    template_type_enum = RelatorioTemplateTypeEnum(template_type)

    statement = select(RelatorioTemplateModel).where(
        RelatorioTemplateModel.template_type == template_type_enum
    )
    result = await session.exec(statement)
    existing = result.first()

    if existing:
        existing.title = data.title
        existing.headerFields = data.headerFields or {}
        existing.styles = data.styles or {}
        existing.tableConfig = data.tableConfig
        existing.pageConfig = data.pageConfig
        existing.updatedAt = datetime.utcnow()
        session.add(existing)
    else:
        session.add(
            RelatorioTemplateModel(
                template_type=template_type_enum,
                title=data.title,
                headerFields=data.headerFields or {},
                styles=data.styles or {},
                tableConfig=data.tableConfig,
                pageConfig=data.pageConfig,
            )
        )


@router.get("/templates", response_model=RelatorioTemplatesResponse)
async def obter_templates(
    session: AsyncSession = Depends(get_session),
) -> RelatorioTemplatesResponse:
    """Obtém templates de relatórios."""
    try:
        return await _load_templates_response(session)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erro ao carregar templates: {exc}"
        ) from exc


@router.put("/templates", response_model=RelatorioTemplatesResponse)
async def salvar_templates(
    payload: RelatorioTemplatesUpdate,
    session: AsyncSession = Depends(get_session),
    _admin: bool = Depends(require_admin),
) -> RelatorioTemplatesResponse:
    """Salva templates de relatórios. Requer permissão de administrador."""
    try:
        await _upsert_template("envios", payload.envios, session)
        await _upsert_template("fechamentos", payload.fechamentos, session)
        await session.commit()
        return await _load_templates_response(session)
    except HTTPException:
        await session.rollback()
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail=f"Erro ao salvar templates: {exc}"
        ) from exc

