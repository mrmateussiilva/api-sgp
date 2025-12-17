import os
from datetime import datetime, timedelta
from pathlib import Path

from media_cleanup import cleanup_empty_dirs


def _touch_dir(path: Path, days_ago: int = 10) -> None:
    path.mkdir(parents=True, exist_ok=True)
    past = datetime.utcnow() - timedelta(days=days_ago)
    ts = past.timestamp()
    os.utime(path, (ts, ts))


def test_cleanup_empty_dirs_remove_antigos(tmp_path):
    """
    Diretórios vazios antigos em media/pedidos e media/fichas devem ser removidos.
    """
    media_root = tmp_path / "media"
    pedidos = media_root / "pedidos"
    fichas = media_root / "fichas"

    # dirs vazios "antigos"
    old_pedido_dir = pedidos / "1"
    old_ficha_dir = fichas / "10"
    _touch_dir(old_pedido_dir, days_ago=30)
    _touch_dir(old_ficha_dir, days_ago=30)

    # dir vazio porém "recente" não deve ser removido
    recent_dir = pedidos / "recent"
    _touch_dir(recent_dir, days_ago=1)

    report = cleanup_empty_dirs(media_root=media_root, older_than_days=7)

    # antigos removidos
    assert not old_pedido_dir.exists()
    assert not old_ficha_dir.exists()

    # recente permanece
    assert recent_dir.exists()

    assert report.removed_dirs >= 2


def test_cleanup_empty_dirs_ignora_dirs_com_arquivos(tmp_path):
    """
    Diretórios que possuem arquivos não devem ser removidos.
    """
    media_root = tmp_path / "media"
    pedidos = media_root / "pedidos"
    non_empty_dir = pedidos / "2"
    non_empty_dir.mkdir(parents=True, exist_ok=True)

    # criar um arquivo para impedir remoção
    f = non_empty_dir / "arquivo.txt"
    f.write_text("conteudo")

    report = cleanup_empty_dirs(media_root=media_root, older_than_days=0)

    assert non_empty_dir.exists()
    assert f.exists()
    # Nenhum diretório removido
    assert report.removed_dirs == 0


