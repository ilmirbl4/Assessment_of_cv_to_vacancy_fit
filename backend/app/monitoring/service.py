"""Immutable vacancy reference, observations and persisted monitoring results."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import ks_2samp

from app.collector.json_source import checksum, records
from app.collector.normalizer import normalize
from app.ml.artifacts import fingerprint
from app.ml.vacancy_text import vacancy_embedding_text
from app.monitoring.statistics import adversarial, indicator
from app.repositories.postgres._mapping import vector_from_text

SKILL_TYPES = {"HARD_SKILL", "SOFT_SKILL", "LANGUAGE"}


def skill_key(value: Any) -> Any:
    """Normalizes a skill name for comparison and deduplication."""
    return " ".join(value.casefold().replace("ё", "е").split())


def features(category: Any, requirements: Any, embedding: Any) -> Any:
    """Builds the versioned feature snapshot of one vacancy."""
    skills = sorted({skill_key(r["text"]) for r in requirements if r["type"] in SKILL_TYPES})
    return {
        "category": category or "__missing__",
        "skills": skills,
        "skills_count": len(skills),
        "embedding": [float(x) for x in embedding],
    }


def compute_reference(raw: Any, ml: Any) -> Any:
    """Computes reference features with the active models."""
    norm = normalize(raw)
    embedding = ml.bi_encoder.encode([vacancy_embedding_text(norm.title, norm.requirements, norm.duties)])[0]
    reqs = [{"type": r.type.value, "text": r.text} for r in ml.extractor.extract(norm)]
    return features(norm.professional_area, reqs, embedding)


class Monitoring:
    """Owns the immutable vacancy reference and the persisted monitoring dashboard."""

    def __init__(self, c: Any) -> None:
        """Creates the service around a fully built container."""
        self.c = c
        self.reference_id = ""
        self.feature_id = fingerprint([c.ml.vacancy_model_version, "skills-HARD-SOFT-LANGUAGE-dedup-v1", "features-v1"])
        self.manifest: dict[str, Any] = {}
        self.centroid: Any = None
        self.vocabulary: set[str] = set()

    async def prepare_reference(self) -> Any:
        """Verifies the reference package and reuses compatible cached features."""
        c = self.c
        db = c.database
        s = c.settings
        root = Path(s.monitoring_reference_path)
        manifest = json.loads((root / "manifest.json").read_text())
        for name, sha in manifest["files"].items():
            if await asyncio.to_thread(checksum, root / name) != sha:
                raise ValueError("Повреждён эталон: " + name)
        if manifest["count"] != 20000:
            raise ValueError("Общий эталон должен содержать 20000 вакансий")
        self.reference_id = manifest["reference_id"]
        self.manifest = manifest
        saved = {
            r["source_id"]: r["content_hash"]
            for r in await db.pool.fetch(
                "SELECT source_id,content_hash FROM reference_features WHERE reference_id=$1 AND pipeline_id=$2",
                self.reference_id,
                self.feature_id,
            )
        }
        precomputed = manifest.get("precomputed_features", {})
        if precomputed.get("pipeline_id") == self.feature_id and len(saved) < 20000:
            cache_path = root / precomputed["file"]
            if await asyncio.to_thread(checksum, cache_path) != precomputed["sha256"]:
                raise ValueError("Повреждён кэш эталона")
            for item in records(cache_path, s.json_max_bytes):
                if item["source_id"] not in saved:
                    await db.pool.execute(
                        """INSERT INTO reference_features(reference_id,pipeline_id,source_id,content_hash,features)
                        VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                        self.reference_id,
                        self.feature_id,
                        item["source_id"],
                        item["content_hash"],
                        item["features"],
                    )
                    saved[item["source_id"]] = item["content_hash"]
        ids = c.repos.models._active
        seen = set()
        for raw in records(root / "vacancies.jsonl.gz", s.json_max_bytes):
            norm = normalize(raw)
            source_id = norm.id
            if source_id in seen:
                raise ValueError("Повтор source_id в эталоне")
            seen.add(source_id)
            if saved.get(source_id) == norm.content_hash.hex():
                continue
            # Reuse only proven identical content and mathematical versions.
            row = await db.pool.fetchrow(
                """SELECT v.id,e.embedding::text vector,p.name category FROM vacancy v
                JOIN vacancy_embedding e ON e.vacancy_id=v.id AND e.model_id=$2
                    AND e.content_hash=v.content_hash
                LEFT JOIN profession_category p ON p.id=v.category_id
                WHERE v.source_id=$1 AND v.content_hash=$3 AND v.model_version=$4""",
                source_id,
                ids.bi_id,
                norm.content_hash,
                c.ml.vacancy_model_version,
            )
            if row:
                reqs = await db.pool.fetch(
                    """SELECT requirement_type AS type,text FROM vacancy_requirement
                    WHERE vacancy_id=$1 AND extractor_model_id=$2""",
                    row["id"],
                    ids.ner_id,
                )
                f = features(row["category"], reqs, vector_from_text(row["vector"]))
            else:
                f = await c.ml.run(compute_reference, raw, c.ml)
            await db.pool.execute(
                """INSERT INTO reference_features(reference_id,pipeline_id,source_id,content_hash,features)
                VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                self.reference_id,
                self.feature_id,
                source_id,
                norm.content_hash.hex(),
                f,
            )
            if len(seen) % 100 == 0:
                await db.pool.execute(
                    "UPDATE pipeline_state SET phase='reference',progress=$1,total=20000,updated_at=now()", len(seen)
                )
        if len(seen) != 20000:
            raise ValueError("Неполный эталон")
        cache_key = "reference:" + self.reference_id + ":" + self.feature_id
        cache = await db.pool.fetchval("SELECT payload FROM monitoring_cache WHERE cache_key=$1", cache_key)
        if cache:
            self.centroid = np.asarray(cache["centroid"])
            self.vocabulary = set(cache["vocabulary"])
            return
        vector_sum = np.zeros(c.ml.bi_encoder.dim, dtype=float)
        cursor = ""
        while rows := await db.pool.fetch(
            """SELECT source_id,features FROM reference_features
            WHERE reference_id=$1 AND pipeline_id=$2 AND source_id>$3
            ORDER BY source_id LIMIT 64""",
            self.reference_id,
            self.feature_id,
            cursor,
        ):
            for row in rows:
                f = row["features"]
                vector_sum += np.asarray(f["embedding"])
                self.vocabulary.update(f["skills"])
            cursor = rows[-1]["source_id"]
        self.centroid = vector_sum / np.linalg.norm(vector_sum)
        await db.pool.execute(
            """INSERT INTO monitoring_cache(cache_key,payload) VALUES($1,$2)
            ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload""",
            cache_key,
            {"centroid": self.centroid.tolist(), "vocabulary": sorted(self.vocabulary)},
        )

    def enrich(self, rows: Any) -> Any:
        """Adds centroid distance and unknown-skill share to stored features."""
        result = []
        for row in rows:
            f = dict(row["features"])
            v = np.asarray(f.pop("embedding"), dtype=float)
            f["distance"] = float(1 - np.dot(v, self.centroid) / max(np.linalg.norm(v), 1e-12))
            f["unknown_share"] = sum(x not in self.vocabulary for x in f["skills"]) / max(1, len(f["skills"]))
            f["source_id"] = row["source_id"]
            result.append(f)
        return result

    async def _load_features(self, reference: Any, start: Any, end: Any, batch: Any) -> Any:
        """Loads paginated features of the reference or of the current cohort."""
        db = self.c.database
        out = []
        cursor = ""
        while True:
            if reference:
                rows = await db.pool.fetch(
                    """SELECT source_id,features FROM reference_features
                    WHERE reference_id=$1 AND pipeline_id=$2 AND source_id>$3
                    ORDER BY source_id LIMIT 128""",
                    self.reference_id,
                    self.feature_id,
                    cursor,
                )
            else:
                rows = await db.pool.fetch(
                    """SELECT DISTINCT ON(source_id) source_id,features FROM feature_observation
                    WHERE pipeline_id=$1 AND observed_at>=$2 AND observed_at<$3
                    AND ($4::uuid IS NULL OR batch_id=$4)
                    AND source_id>$5 ORDER BY source_id,observed_at DESC LIMIT 128""",
                    self.feature_id,
                    start,
                    end,
                    batch,
                    cursor,
                )
            if not rows:
                break
            out.extend(self.enrich(rows))
            cursor = rows[-1]["source_id"]
        return out

    def optional(self, path: Any, version: Any) -> Any:
        """Loads an optional fixed monitoring artifact and reports its availability."""
        if not path:
            return None, "reference_missing"
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            return None, "reference_missing"
        if data.get("pipeline_id") != version:
            return None, "reference_incompatible"
        if not data.get("provenance") or not data.get("reference_id"):
            return None, "reference_incompatible"
        return data, "ready"

    async def dashboard(self, from_date: Any = None, to_date: Any = None, batch: Any = None) -> Any:
        """Builds and persists the PSI, AUC, KS and feedback dashboard."""
        c = self.c
        s = c.settings
        tz = ZoneInfo(s.app_timezone)
        today = c.clock.now().astimezone(tz).date()
        begin = from_date or today - timedelta(days=29)
        end_date = to_date or today
        start = datetime.combine(begin, time(), tz)
        end = datetime.combine(end_date + timedelta(days=1), time(), tz)
        if begin > end_date:
            raise ValueError("Начало периода позже конца")
        reference = await self._load_features(True, start, end, batch) if self.centroid is not None else []
        current = await self._load_features(False, start, end, batch) if self.centroid is not None else []
        pairs = [
            ("skills_per_vacancy", "Число навыков", "skills_count", False),
            ("professional_area", "Профессиональная область", "category", True),
            ("vacancy_embeddings", "Расстояние до центроида", "distance", False),
            ("unknown_skills", "Навыки вне словаря эталона", "unknown_share", False),
        ]
        indicators = [
            indicator(
                key,
                name,
                [r[field] for r in reference],
                [r[field] for r in current],
                s.monitoring_min_samples,
                s.monitoring_bins,
                categorical=cat,
            )
            for key, name, field, cat in pairs
        ]
        adv = await asyncio.to_thread(adversarial, reference, current, s.monitoring_min_samples, s.monitoring_seed)
        adv["roc_auc_threshold"] = s.monitoring_auc_threshold
        adv["periods"] = (
            [{"from": str(begin), "to": str(end_date), "roc_auc": adv["roc_auc"]}] if adv["roc_auc"] is not None else []
        )
        resume_ref, status = self.optional(s.monitoring_resume_reference, c.ml.resume_model_version)
        observations = await c.database.pool.fetch(
            "SELECT features FROM resume_observation WHERE pipeline_id=$1 AND observed_at>=$2 AND observed_at<$3",
            c.ml.resume_model_version,
            start,
            end,
        )
        ri = indicator(
            "resume_embeddings", "Расстояние резюме до центроида", [], [], s.monitoring_min_samples, entity="resumes"
        )
        if resume_ref:
            rv = np.asarray(resume_ref["projections"])
            cv = np.asarray([r["features"]["projection"] for r in observations])
            centroid = rv.mean(axis=0)
            centroid /= max(np.linalg.norm(centroid), 1e-12)

            def distances(v: Any) -> Any:
                return (1 - v @ centroid / np.maximum(np.linalg.norm(v, axis=1), 1e-12)).tolist() if len(v) else []

            ri = indicator(
                "resume_embeddings",
                "Расстояние резюме до центроида",
                distances(rv),
                distances(cv),
                s.monitoring_min_samples,
                entity="resumes",
            )
        else:
            ri.update(
                status=status, reason="Отдельный совместимый эталон резюме не подключён", current_size=len(observations)
            )
        indicators.append(ri)
        scores, status = self.optional(s.monitoring_score_reference, c.pipeline_id)
        current_scores = [
            r["score"]
            for r in await c.database.pool.fetch(
                """SELECT o.score FROM score_observation o JOIN matching_event e USING(run_id)
                WHERE o.pipeline_id=$1 AND e.at>=$2 AND e.at<$3""",
                c.pipeline_id,
                start,
                end,
            )
        ]
        score_ref = scores.get("scores", []) if scores else []
        ks = dict(
            status=status,
            reason="Эталон реальных оценок не подключён",
            statistic=None,
            p_value=None,
            alpha=s.monitoring_ks_alpha,
            reference_size=len(score_ref),
            current_size=len(current_scores),
            reference=[],
            current=[],
        )
        if scores:
            hist = indicator("scores", "Оценки", score_ref, current_scores, s.monitoring_min_samples)
            ks.update(
                status=hist["status"], reason=hist["reason"], reference=hist["reference"], current=hist["current"]
            )
            if hist["status"] == "ready":
                test = ks_2samp(score_ref, current_scores)
                ks.update(statistic=float(test.statistic), p_value=float(test.pvalue))
        feedback, status = self.optional(s.monitoring_favorite_reference, c.pipeline_id)
        days = await c.database.pool.fetch(
            """SELECT (e.at AT TIME ZONE $4)::date date,count(*) runs,
            count(f.run_id) FILTER(WHERE f.at>=e.at AND f.at<=e.at+$5::interval) runs_with_favorite
            FROM matching_event e LEFT JOIN favorite_from_run_event f USING(run_id)
            WHERE e.pipeline_id=$1 AND e.at>=$2 AND e.at<$3 AND e.at+$5::interval<=now()
            GROUP BY 1 ORDER BY 1""",
            c.pipeline_id,
            start,
            end,
            s.app_timezone,
            timedelta(hours=s.monitoring_favorite_window_hours),
        )
        rate = dict(
            status=status,
            reason="Фиксированный эталон отклика не подключён",
            reference_share=None,
            max_drop=s.monitoring_favorite_max_drop,
            days=[{**dict(d), "date": str(d["date"]), "share": d["runs_with_favorite"] / d["runs"]} for d in days],
        )
        if feedback:
            denominator = feedback.get("runs", 0)
            rate.update(
                reference_share=feedback["runs_with_favorite"] / denominator if denominator else None,
                status="ready" if denominator and days else "insufficient_data",
                reason=None if denominator and days else "Нет завершённых когорт",
            )
        result = dict(
            reference_period={
                "from": self.manifest.get("snapshot_utc", "")[:10],
                "to": self.manifest.get("snapshot_utc", "")[:10],
            },
            current_period={"from": str(begin), "to": str(end_date)},
            reference_id=self.reference_id,
            pipeline_id=self.feature_id,
            reference_size=len(reference),
            current_size=len(current),
            batch_id=str(batch) if batch else None,
            checked_at=c.clock.now().isoformat(),
            psi_threshold=s.monitoring_psi_threshold,
            indicators=indicators,
            adversarial=adv,
            model_scores=ks,
            favorite_rate=rate,
        )
        key = fingerprint([self.feature_id, self.reference_id, str(begin), str(end_date), str(batch)])
        await c.database.pool.execute(
            """INSERT INTO monitoring_cache(cache_key,payload) VALUES($1,$2)
            ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,computed_at=now()""",
            key,
            result,
        )
        return result

    async def refresh(self) -> Any:
        """Recomputes the dashboard after an ingestion run when the reference is ready."""
        if self.centroid is not None:
            await self.dashboard()
