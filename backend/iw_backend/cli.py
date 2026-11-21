"""CLI backendu.

    python -m iw_backend.cli init              # schemat bazy + dane demo + rejestr (IW_REGISTRY_SOURCES)
    python -m iw_backend.cli crawl             # jednorazowy przebieg wszystkich kolektorów (bez kolejki)
    python -m iw_backend.cli reanalyze         # ponowna analiza wszystkich dokumentów
    python -m iw_backend.cli registry-knf      # import Rejestru Firm Inwestycyjnych KNF
    python -m iw_backend.cli evaluate          # precyzja / pełność na zbiorze walidacyjnym
"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import select


def evaluate() -> dict:
    from .db import Document, Finding, get_thresholds, session_scope

    out = {}
    with session_scope() as s:
        th = get_thresholds(s)
        docs = list(s.scalars(select(Document).where(Document.duplicate_of.is_(None))))
        for m in (1, 2, 3):
            tp = fp = fn = tn = 0
            print(f"\n=== Moduł {m} (próg {th[m]}) ===")
            for d in docs:
                gt = (d.ground_truth or {}).get(str(m))
                f = next((x for x in d.findings if x.module == m), None)
                if gt is None and f is None:
                    continue
                score = f.score if f else 0.0
                pred = score >= th[m]
                mark = "  " if gt is None else ("OK" if pred == bool(gt) else "XX")
                print(f" {mark} {score:.3f} gt={str(gt):5} {(f.category if f else '(nie dotyczy)')[:42]:42} {d.url[:70]}")
                if gt is None:
                    continue
                tp += pred and gt
                fp += pred and not gt
                fn += (not pred) and gt
                tn += (not pred) and (not gt)
            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / (tp + fn) if tp + fn else 0.0
            print(f" TP={tp} FP={fp} FN={fn} TN={tn}  precyzja={p:.2f} pełność={r:.2f}")
            out[m] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r}
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="iw_backend")
    ap.add_argument("cmd", choices=["init", "crawl", "reanalyze", "registry-knf", "evaluate"])
    args = ap.parse_args()

    from .db import init_db

    init_db()
    if args.cmd == "init":
        from .demo import make_demo
        from .tasks import import_registry

        make_demo.main()
        print("rejestr:", import_registry())
    elif args.cmd == "crawl":
        from .tasks import run_all

        run_all()
    elif args.cmd == "reanalyze":
        from .tasks import reanalyze_all

        print("przeanalizowano", reanalyze_all())
    elif args.cmd == "registry-knf":
        from .tasks import import_registry

        print(import_registry(["knf"]))
    elif args.cmd == "evaluate":
        evaluate()


if __name__ == "__main__":
    main()
