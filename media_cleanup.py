"""
Rotinas de manutenção para diretórios de mídia (pedidos e fichas).

Pensado para ser executado periodicamente (via cron ou script) e também
testável em unidade.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List

from config import settings


@dataclass
class CleanupReport:
    scanned_dirs: int
    removed_dirs: int
    removed_files: int


def _default_media_root() -> Path:
    root = Path(settings.MEDIA_ROOT)
    if not root.is_absolute():
        # raiz do projeto (este arquivo está na raiz do repo)
        project_root = Path(__file__).resolve().parent
        root = (project_root / root).resolve()
    return root


def _iter_target_dirs(media_root: Path) -> Iterable[Path]:
    """Retorna diretórios de mídia relevantes (pedidos e fichas) se existirem."""
    for name in ("pedidos", "fichas"):
        candidate = media_root / name
        if candidate.exists() and candidate.is_dir():
            yield candidate


def cleanup_empty_dirs(
    media_root: Path | None = None,
    older_than_days: int = 7,
) -> CleanupReport:
    """
    Remove diretórios vazios (sem arquivos) em `media/pedidos` e `media/fichas`.

    - `older_than_days` evita apagar diretórios recém-criados (margem de segurança).
    - Não apaga arquivos; apenas diretórios vazios em árvore.
    """
    base = media_root or _default_media_root()
    now = datetime.utcnow()
    min_age = timedelta(days=older_than_days)

    scanned = 0
    removed_dirs = 0
    removed_files = 0

    for root_dir in _iter_target_dirs(base):
        # Caminhar de baixo para cima (post-order) para facilitar remoção
        for path in sorted(root_dir.rglob("*"), reverse=True):
            if not path.is_dir():
                continue
            scanned += 1

            try:
                # Se tiver arquivos, ignorar
                has_files = any(p.is_file() for p in path.iterdir())
                if has_files:
                    continue

                # Verificar "idade" do diretório (ctime/mtime)
                stat = path.stat()
                mtime = datetime.utcfromtimestamp(stat.st_mtime)
                if now - mtime < min_age:
                    continue

                path.rmdir()
                removed_dirs += 1
            except OSError:
                # diretório em uso ou permissão negada – ignorar silenciosamente
                continue

    return CleanupReport(
        scanned_dirs=scanned,
        removed_dirs=removed_dirs,
        removed_files=removed_files,
    )


__all__: List[str] = ["CleanupReport", "cleanup_empty_dirs"]


