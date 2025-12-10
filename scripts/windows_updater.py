#!/usr/bin/env python3
"""
Atualizador automático para ambientes Windows.

Fluxo:
1. Consulta um manifesto JSON que descreve a última versão disponível.
2. Compara com a versão instalada localmente (armazenada em um arquivo).
3. Caso exista uma versão mais nova, baixa o instalador MSI e executa a instalação
   silenciosa automaticamente.

O manifesto deve seguir o formato:
{
  "version": "1.0.1",
  "notes": "Correções gerais.",
  "pub_date": "2025-01-01T00:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "url": "https://.../SGP_1.0.1_x64.msi"
    }
  }
}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

DEFAULT_MANIFEST_URL = os.environ.get(
    "SGP_UPDATE_MANIFEST", "https://sgp.finderbit.com.br/update/releases/latest.json"
)
DEFAULT_PLATFORM = os.environ.get("SGP_UPDATE_PLATFORM", "windows-x86_64")
DEFAULT_VERSION_FILE = Path(
    os.environ.get("PROGRAMDATA", r"C:\ProgramData")
) / "SGP" / "version.json"


class UpdateError(RuntimeError):
    """Erro alto nível durante o processo de atualização."""


def ensure_windows() -> None:
    if os.name != "nt":
        raise UpdateError("Este script foi projetado para ser executado no Windows.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Atualizador automático do SGP.")
    parser.add_argument(
        "--manifest-url",
        default=DEFAULT_MANIFEST_URL,
        help="URL do manifesto JSON com informações da release.",
    )
    parser.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        help="Identificador da plataforma no manifesto (ex.: windows-x86_64).",
    )
    parser.add_argument(
        "--version-file",
        type=Path,
        default=DEFAULT_VERSION_FILE,
        help="Arquivo local que guarda a versão instalada.",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "sgp_updater",
        help="Diretório temporário para armazenar o MSI baixado.",
    )
    parser.add_argument(
        "--msi-args",
        default="/qn",
        help="Argumentos passados ao msiexec (default: /qn para modo silencioso).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força a reinstalação mesmo se a versão local for igual.",
    )
    return parser.parse_args()


def load_manifest(url: str) -> Dict[str, Any]:
    try:
        with urlopen(url, timeout=30) as response:
            if response.status != 200:
                raise UpdateError(f"Manifesto respondeu com status HTTP {response.status}.")
            return json.load(response)
    except URLError as exc:
        raise UpdateError(f"Falha ao baixar manifesto: {exc}") from exc


def load_local_version(version_file: Path) -> Optional[str]:
    if not version_file.exists():
        return None
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        return data.get("version")
    except json.JSONDecodeError as exc:
        raise UpdateError(f"Arquivo de versão corrompido: {version_file}") from exc


def write_local_version(version_file: Path, version: str) -> None:
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(json.dumps({"version": version}, indent=2), encoding="utf-8")


def normalize_version(value: str) -> list[int]:
    parts = []
    for segment in value.replace("-", ".").split("."):
        if not segment:
            continue
        try:
            parts.append(int(segment))
        except ValueError:
            # Garante comparação determinística mesmo com sufixos como beta/rc.
            parts.append(
                sum(ord(char) for char in segment)
            )
    return parts


def is_newer(remote: str, local: Optional[str]) -> bool:
    if local is None:
        return True
    return normalize_version(remote) > normalize_version(local)


def download_file(url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_name = Path(urlsplit(url).path).name or "installer.msi"
    target = destination / file_name
    try:
        with urlopen(url, timeout=60) as response, open(target, "wb") as handler:
            chunk = response.read(8192)
            while chunk:
                handler.write(chunk)
                chunk = response.read(8192)
    except URLError as exc:
        raise UpdateError(f"Falha ao baixar installer: {exc}") from exc
    return target


def install_msi(installer: Path, additional_args: str) -> None:
    cmd = [
        "msiexec.exe",
        "/i",
        str(installer),
    ]
    if additional_args:
        cmd.extend(additional_args.split())
    print(f"[updater] Executando: {' '.join(cmd)}")
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise UpdateError(f"Instalação retornou código {proc.returncode}.")


def main() -> None:
    args = parse_args()
    ensure_windows()

    print(f"[updater] Lendo manifesto: {args.manifest_url}")
    manifest = load_manifest(args.manifest_url)
    platform_info = manifest.get("platforms", {}).get(args.platform)
    if not platform_info:
        raise UpdateError(f"Manifesto não contém dados para a plataforma {args.platform}.")

    remote_version = manifest.get("version")
    if not remote_version:
        raise UpdateError("Manifesto não define o campo 'version'.")

    local_version = load_local_version(args.version_file)
    print(f"[updater] Versão local: {local_version or 'desconhecida'}")
    print(f"[updater] Versão remota: {remote_version}")

    if not args.force and not is_newer(remote_version, local_version):
        print("[updater] Nenhuma atualização necessária.")
        return

    download_dir = args.download_dir
    installer_path = download_file(platform_info["url"], download_dir)
    print(f"[updater] Arquivo baixado para {installer_path}")

    install_msi(installer_path, args.msi_args)
    write_local_version(args.version_file, remote_version)
    print("[updater] Atualização concluída com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except UpdateError as exc:
        print(f"[updater] Erro: {exc}", file=sys.stderr)
        sys.exit(1)
