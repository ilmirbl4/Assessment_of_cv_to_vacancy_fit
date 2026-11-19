"""Score the manual cross-encoder calibration set and report preliminary thresholds.

Run from ``backend`` with the requirements installed and the local model available:

    .venv/bin/python -m scripts.calibrate_cross_encoder

The set is a small manual spot check, not a training or acceptance benchmark.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT_PAIRS = Path(__file__).resolve().parents[2] / "data/demo/calibration_pairs.json"
DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "models/mmarco-mMiniLMv2-L12-H384-v1"
LABELS = ("not_covered", "partially_covered", "covered")


def sigmoid(value: float) -> float:
    """One stable sigmoid over a raw logit."""
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)


def main() -> None:
    """Print scores and the best coarse threshold grid over the manual labels."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    from sentence_transformers import CrossEncoder
    from torch import nn

    data = json.loads(args.pairs.read_text())
    model = CrossEncoder(str(args.model), local_files_only=True, device="cpu", activation_fn=nn.Identity())
    logits = model.predict(
        [[item["requirement"], item["fragment"]] for item in data["pairs"]],
        batch_size=16,
        activation_fn=nn.Identity(),
        show_progress_bar=False,
    )
    scores = [sigmoid(float(value)) for value in logits]
    rows = [{**item, "score": score} for item, score in zip(data["pairs"], scores, strict=True)]

    def status(score: float, partial: float, covered: float) -> str:
        if score >= covered:
            return "covered"
        if score >= partial:
            return "partially_covered"
        return "not_covered"

    grid = []
    for partial in (0.05, 0.1, 0.2, 0.3, 0.4, 0.45):
        for covered in (0.45, 0.5, 0.6, 0.7, 0.75, 0.8):
            if partial >= covered:
                continue
            hits = sum(status(row["score"], partial, covered) == row["label"] for row in rows)
            grid.append((hits / len(rows), partial, covered))
    grid.sort(reverse=True)
    result = {
        "model": str(args.model),
        "pairs": str(args.pairs),
        "count": len(rows),
        "thresholds": {
            "partial": min(grid, key=lambda item: (-item[0], item[1], item[2]))[1] if grid else None,
            "covered": min(grid, key=lambda item: (-item[0], item[1], item[2]))[2] if grid else None,
        },
        "rows": rows,
        "threshold_grid": [{"partial": p, "covered": c, "accuracy": a} for a, p, c in grid],
    }
    lines = ["| Пара | Требование | Фрагмент | Ожидание | Score |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['requirement']} | {row['fragment']} | {row['label']} | {row['score']:.4f} |"
        )
    result["markdown"] = "\n".join(lines)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(result["markdown"])
    print("\nЛучшая точность на ручном наборе:", f"{grid[0][0]:.3f}" if grid else "n/a")
    print("Порог partial / covered:", result["thresholds"])
    print("Текущие пороги не меняются автоматически: набор мал, классы пересекаются.")


if __name__ == "__main__":
    main()
