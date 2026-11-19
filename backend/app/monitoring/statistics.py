"""Fixed-reference distributions, PSI and held-out adversarial validation."""

from __future__ import annotations

import itertools
from typing import Any

import numpy as np


def numeric_bins(reference: Any, count: Any = 10) -> Any:
    """Quantiles belong to the reference; extremes always have a bucket."""
    values = np.asarray(reference, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        return [-np.inf, np.inf]
    inner = np.unique(np.quantile(values, np.linspace(0, 1, count + 1)[1:-1]))
    return [-np.inf, *inner.tolist(), np.inf]


def distribution(values: Any, bins: Any, categorical: Any = False) -> Any:
    """Builds a smoothed, normalized distribution over fixed reference bins."""
    if categorical:
        lookup = {str(x): i for i, x in enumerate(bins)}
        counts = np.zeros(len(bins), dtype=float)
        for value in values:
            counts[lookup.get(str(value), lookup["__unknown__"])] += 1
    else:
        counts = np.histogram(np.asarray(values, dtype=float), bins)[0].astype(float)
    # Symmetric additive smoothing, then normalize both distributions.
    return (counts + 0.5) / (counts.sum() + 0.5 * len(counts))


def psi(reference: Any, current: Any) -> Any:
    """Computes PSI for aligned positive shares."""
    r, c = np.asarray(reference, dtype=float), np.asarray(current, dtype=float)
    if len(r) != len(c) or np.any(r <= 0) or np.any(c <= 0):
        raise ValueError("PSI needs aligned positive shares")
    return float(np.sum((c - r) * np.log(c / r)))


def indicator(
    key: Any,
    name: Any,
    reference: Any,
    current: Any,
    minimum: Any,
    bins_count: Any = 10,
    entity: Any = "vacancies",
    categorical: Any = False,
) -> Any:
    """Builds one PSI indicator with an explicit unavailable state."""
    state = "ready" if len(reference) >= minimum and len(current) >= minimum else "insufficient_data"
    result: dict[str, Any] = dict(
        key=key,
        name=name,
        entity=entity,
        bins_label=name,
        psi=None,
        status=state,
        reason=None if state == "ready" else "Недостаточно наблюдений для сравнения",
        reference_size=len(reference),
        current_size=len(current),
        reference=[],
        current=[],
    )
    if state != "ready":
        return result
    bins = (
        sorted(set(str(v) for v in reference) | {"__unknown__", "__missing__"})
        if categorical
        else numeric_bins(reference, bins_count)
    )
    r, c = distribution(reference, bins, categorical), distribution(current, bins, categorical)
    labels = bins if categorical else [f"{a:.3g}…{b:.3g}" for a, b in itertools.pairwise(bins)]
    result.update(
        psi=psi(r, c),
        reference=[dict(bin=str(k), share=float(v)) for k, v in zip(labels, r, strict=False)],
        current=[dict(bin=str(k), share=float(v)) for k, v in zip(labels, c, strict=False)],
    )
    return result


def adversarial(reference: Any, current: Any, minimum: Any, seed: Any) -> Any:
    """Deduplicate by source identity; shared IDs stay in the same holdout group."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupShuffleSplit

    result: dict[str, Any] = dict(
        status="insufficient_data",
        reason="Недостаточно независимых объектов",
        roc_auc=None,
        top_features=[],
        reference_size=len(reference),
        current_size=len(current),
    )
    if min(len(reference), len(current)) < minimum:
        return result
    rows = reference + current
    # Neither dates nor identifiers are features. IDs are used for grouping only.
    features = [
        {
            "skills": r["skills_count"],
            "area": r.get("category") or "__missing__",
            "distance": r["distance"],
            "unknown_share": r["unknown_share"],
        }
        for r in rows
    ]
    groups = [r["source_id"] for r in rows]
    y = np.r_[np.zeros(len(reference)), np.ones(len(current))]
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=seed).split(features, y, groups))
    if len(set(y[train])) < 2 or len(set(y[test])) < 2:
        return result
    vectorizer = DictVectorizer(sparse=False)
    xtrain = vectorizer.fit_transform([features[i] for i in train])
    xtest = vectorizer.transform([features[i] for i in test])
    classifier = RandomForestClassifier(n_estimators=80, max_depth=6, min_samples_leaf=5, random_state=seed, n_jobs=1)
    classifier.fit(xtrain, y[train])
    score = float(roc_auc_score(y[test], classifier.predict_proba(xtest)[:, 1]))
    importance = permutation_importance(
        classifier, xtest, y[test], scoring="roc_auc", n_repeats=3, random_state=seed, n_jobs=1
    )
    names = vectorizer.get_feature_names_out()
    ordered = sorted(zip(names, importance.importances_mean, strict=False), key=lambda x: -x[1])[:5]
    result.update(
        status="ready",
        reason=None,
        roc_auc=score,
        top_features=[dict(name=str(n), importance=max(0, float(v))) for n, v in ordered],
        train_size=len(train),
        test_size=len(test),
        method="group holdout 30%; permutation ROC-AUC importance",
    )
    return result
