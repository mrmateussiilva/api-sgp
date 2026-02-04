#!/usr/bin/env python3
"""
Migracao segura de valores monetarios para centavos (SQLite).
Dry-run por padrao: DRY_RUN=1 so imprime, DRY_RUN=0 aplica.
"""

import csv
import json
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional, Tuple, List

from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///db/dev.db")
DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
CSV_PATH = os.getenv("CSV_PATH", "scripts/migracao_centavos_ambiguidade.csv")
CSV_INVALID_PATH = os.getenv("CSV_INVALID_PATH", "scripts/migracao_centavos_invalidos.csv")
ONLY_INVALID = os.getenv("ONLY_INVALID", "0") == "1"


def parse_money_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("R$", "").replace("$", "").strip()
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2:
            s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return Decimal(s)
    except Exception:
        return None


def to_centavos(dec: Decimal) -> int:
    return int((dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def infer_centavos(raw: Any, ref_centavos: Optional[int]) -> Tuple[Optional[int], str]:
    if raw is None or str(raw).strip() == "":
        return 0, "empty"
    s = str(raw).strip()
    has_sep = "," in s or "." in s
    dec = parse_money_decimal(s)
    if dec is None:
        return None, "invalid"
    if has_sep:
        return to_centavos(dec), "sep_decimal"
    as_centavos = int(dec)
    as_reais = to_centavos(dec)
    if not ref_centavos:
        return as_reais, "no_ref_assume_reais"
    if abs(as_centavos - ref_centavos) <= abs(as_reais - ref_centavos):
        return as_centavos, "no_sep_centavos"
    return as_reais, "no_sep_reais"


def _item_total_centavos(items: List[dict]) -> int:
    total = 0
    for item in items:
        qty = parse_money_decimal(item.get("quantity") or item.get("quantidade") or "1") or Decimal("1")
        unit = parse_money_decimal(item.get("unit_price") or item.get("valor_unitario") or "0") or Decimal("0")
        total += to_centavos(qty * unit)
    return total


def _load_items(items_json: Any) -> List[dict]:
    if not items_json:
        return []
    try:
        data = json.loads(items_json)
    except Exception:
        return []
    return [item for item in data if isinstance(item, dict)]


def _sqlite_add_column(conn, column_name: str, column_type: str) -> None:
    existing = conn.execute(text("PRAGMA table_info(pedidos)")).fetchall()
    if any(row[1] == column_name for row in existing):
        return
    conn.execute(text(f"ALTER TABLE pedidos ADD COLUMN {column_name} {column_type}"))


def main() -> None:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        _sqlite_add_column(conn, "valor_total_centavos", "BIGINT")
        _sqlite_add_column(conn, "valor_frete_centavos", "BIGINT")
        _sqlite_add_column(conn, "valor_itens_centavos", "BIGINT")

        rows = conn.execute(
            text("SELECT id, valor_total, valor_frete, valor_itens, items FROM pedidos")
        ).fetchall()

        csv_file = None
        csv_writer = None
        if not ONLY_INVALID:
            csv_file = open(CSV_PATH, "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)

        csv_invalid_file = open(CSV_INVALID_PATH, "w", newline="", encoding="utf-8")
        csv_invalid_writer = csv.writer(csv_invalid_file)
        header = [
            "pedido_id",
            "valor_total_raw",
            "valor_total_centavos",
            "valor_total_reason",
            "valor_frete_raw",
            "valor_frete_centavos",
            "valor_frete_reason",
            "valor_itens_raw",
            "valor_itens_centavos",
            "valor_itens_reason",
        ]
        if csv_writer:
            csv_writer.writerow(
                [
                    *header,
                ]
            )
        csv_invalid_writer.writerow([*header])

        reason_counts: dict[str, int] = {}
        ambig_rows = 0
        invalid_rows = 0

        for row in rows:
            pedido_id, vt, vf, vi, items_json = row
            items = _load_items(items_json)

            itens_cent = _item_total_centavos(items)
            frete_cent, frete_reason = infer_centavos(vf, None)
            if frete_cent is None:
                frete_cent = 0

            total_ref = itens_cent + frete_cent
            vt_cent, vt_reason = infer_centavos(vt, total_ref)
            vi_cent, vi_reason = infer_centavos(vi, itens_cent)

            row_data = [
                pedido_id,
                vt,
                vt_cent,
                vt_reason,
                vf,
                frete_cent,
                frete_reason,
                vi,
                vi_cent,
                vi_reason,
            ]
            reasons = {vt_reason, frete_reason, vi_reason}
            for reason in (vt_reason, frete_reason, vi_reason):
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if "invalid" in reasons:
                csv_invalid_writer.writerow(row_data)
                invalid_rows += 1
            elif reasons - {"sep_decimal", "empty"}:
                if csv_writer:
                    csv_writer.writerow(row_data)
                ambig_rows += 1

            if DRY_RUN:
                print(
                    pedido_id,
                    vt,
                    vt_cent,
                    vt_reason,
                    vf,
                    frete_cent,
                    frete_reason,
                    vi,
                    vi_cent,
                    vi_reason,
                )
                continue

            conn.execute(
                text(
                    "UPDATE pedidos "
                    "SET valor_total_centavos=:vt, valor_frete_centavos=:vf, valor_itens_centavos=:vi "
                    "WHERE id=:id"
                ),
                {"vt": vt_cent, "vf": frete_cent, "vi": vi_cent, "id": pedido_id},
            )

        summary_rows = [
            ["__summary__", "ambiguous_rows", ambig_rows, "", "", "", "", "", "", ""],
            ["__summary__", "invalid_rows", invalid_rows, "", "", "", "", "", "", ""],
        ]
        for reason, count in sorted(reason_counts.items()):
            summary_rows.append(["__summary__", f"reason:{reason}", count, "", "", "", "", "", "", ""])

        if csv_writer:
            csv_writer.writerow(["__summary__", "", "", "", "", "", "", "", "", ""])
            csv_writer.writerows(summary_rows)
            csv_file.close()

        csv_invalid_writer.writerow(["__summary__", "", "", "", "", "", "", "", "", ""])
        csv_invalid_writer.writerows(summary_rows)
        csv_invalid_file.close()

        print("Resumo da migracao:")
        print(f"- linhas_ambiguas: {ambig_rows}")
        print(f"- linhas_invalidas: {invalid_rows}")
        for reason, count in sorted(reason_counts.items()):
            print(f"- reason:{reason}: {count}")


if __name__ == "__main__":
    main()
