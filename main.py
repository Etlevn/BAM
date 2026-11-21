"""Entry point: optional CLI overrides, then src.runtime.runner.start."""

from __future__ import annotations

import argparse
import sys

import config
from src.cli.run import apply_run_overrides
from src.runtime.runner import start


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Run one BAM experiment. With no args, uses config.py as-is. "
            "Or pass group, mode, BAS id, and model; other settings still come from config.py."
        ),
    )
    p.add_argument(
        "group",
        nargs="?",
        help="EXP_GROUP folder under exp/ (e.g. SGL, BR, BAS, TEST)",
    )
    p.add_argument(
        "mode",
        nargs="?",
        choices=("sgl", "br"),
        help="market type (omit all four to use config.py)",
    )
    p.add_argument(
        "bas",
        nargs="?",
        help="BAS id: base | amp_NN | sup_NN | off",
    )
    p.add_argument(
        "model",
        nargs="?",
        help="sgl: one model; br: two names separated by comma or '&'",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    provided = [args.group, args.mode, args.bas, args.model]
    n_set = sum(1 for x in provided if x is not None)
    if n_set not in (0, 4):
        parser.error(
            "pass either no positional args, or all four: group mode bas model"
        )

    if n_set == 4:
        try:
            group = str(args.group).strip()
            if not group:
                raise ValueError("group must be non-empty")
            config.EXP_GROUP = group
            apply_run_overrides(mode=args.mode, bas=args.bas, model=args.model)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        bas_disp = config.BAS_BIAS_ID if config.USE_BAS_MODE else "off"
        if config.EXPERIMENT_MODE == "sgl":
            model_disp = config.SINGLE_MODEL_CONFIG["model_name"]
        else:
            names = [m["name"] for m in config.BATTLE_ROYALE_CONFIG["custom_models"]]
            model_disp = " & ".join(names)
        print(
            f"[main] group={config.EXP_GROUP} mode={config.EXPERIMENT_MODE} "
            f"bas={bas_disp} model={model_disp}"
        )

    start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
