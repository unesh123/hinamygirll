"""Dataset Builder and Export Pipeline for HINAA Neural Lab."""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Optional

from .curated_data import GOLD_EXAMPLES
from .schema import DatasetCategory, DatasetExample, DatasetManifest


class DatasetBuilder:
    """Manages dataset collection, deduplication, splitting, and JSONL export."""

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = Path(output_dir or Path(__file__).resolve().parent / "exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._examples: dict[str, DatasetExample] = {}

    def load_gold_standards(self) -> int:
        """Load all verified gold-standard examples."""
        added = 0
        for ex in GOLD_EXAMPLES:
            h = ex.content_hash
            if h not in self._examples:
                self._examples[h] = ex
                added += 1
        return added

    def add_example(self, example: DatasetExample) -> bool:
        """Add a custom reviewed example with deduplication."""
        h = example.content_hash
        if h in self._examples:
            return False
        self._examples[h] = example
        return True

    def build_and_export(
        self,
        name: str = "hinaa_gold_sft_v1",
        version: str = "1.0.0",
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
    ) -> DatasetManifest:
        """Partition into train, val, test splits and export to JSONL files."""
        examples = list(self._examples.values())
        random.seed(42)
        random.shuffle(examples)

        n = len(examples)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train_split = examples[:n_train]
        val_split = examples[n_train : n_train + n_val]
        test_split = examples[n_train + n_val :]

        # Export splits to ChatML JSONL
        splits_map = {
            "train": train_split,
            "val": val_split,
            "test": test_split,
        }

        for split_name, split_data in splits_map.items():
            file_path = self.output_dir / f"{name}_{split_name}.jsonl"
            with open(file_path, "w", encoding="utf-8") as f:
                for ex in split_data:
                    line = json.dumps({"messages": ex.to_chatml()}, ensure_ascii=False)
                    f.write(line + "\n")

        # Compute breakdown metrics
        cat_counts: dict[str, int] = {}
        lang_counts: dict[str, int] = {}
        for ex in examples:
            cat_counts[ex.category.value] = cat_counts.get(ex.category.value, 0) + 1
            lang_counts[ex.language] = lang_counts.get(ex.language, 0) + 1

        manifest = DatasetManifest(
            name=name,
            version=version,
            total_examples=n,
            categories_breakdown=cat_counts,
            languages_breakdown=lang_counts,
            splits={
                "train": len(train_split),
                "val": len(val_split),
                "test": len(test_split),
            },
        )

        manifest_path = self.output_dir / f"{name}_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))

        return manifest
