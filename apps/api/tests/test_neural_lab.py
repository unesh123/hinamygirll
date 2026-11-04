"""Comprehensive unit test suite for HINAA Neural Lab."""

import pytest
import os
import json
import tempfile
from hinaa_api.neural_lab.audit import run_system_audit
from hinaa_api.neural_lab.datasets.schema import DatasetCategory, DatasetExample
from hinaa_api.neural_lab.datasets.builder import DatasetBuilder
from hinaa_api.neural_lab.models.registry import get_model_registry
from hinaa_api.neural_lab.training.lora_config import QLoRAHyperparameters
from hinaa_api.neural_lab.training.pipeline import TrainingPipelineManager
from hinaa_api.neural_lab.evaluation.benchmarks import run_model_benchmark_comparison
from hinaa_api.neural_lab.adapters.manager import AdapterManager


def test_training_readiness_audit():
    report = run_system_audit()
    assert report.system is not None
    assert report.frameworks is not None
    assert report.local_engine is not None
    assert report.cloud_vs_local_boundary is not None

    # Check GPU detection
    if report.gpu:
        assert "RTX 4060" in report.gpu.name or "GeForce" in report.gpu.name
        assert report.gpu.vram_total_mb > 7000
        assert report.gpu.qlora_suitable is True

    # Check installed frameworks
    assert report.frameworks.torch_version is not None
    assert report.frameworks.transformers_version is not None
    assert report.frameworks.peft_version is not None
    assert report.frameworks.accelerate_version is not None
    assert report.frameworks.datasets_version is not None

    # Check local engine
    assert report.local_engine.ollama_installed is True


def test_dataset_builder_and_manifest():
    with tempfile.TemporaryDirectory() as tmp_dir:
        builder = DatasetBuilder(output_dir=tmp_dir)
        loaded = builder.load_gold_standards()
        assert loaded >= 8

        # Test deduplication
        dup_example = DatasetExample(
            example_id="dup-1",
            category=DatasetCategory.IDENTITY,
            user_prompt="Who are you and what makes you different from typical chatbots?",
            assistant_response="I'm Hina—your autonomous AI companion and engineering partner.",
        )
        # Adding duplicate should return False or be ignored if exact match
        builder.add_example(dup_example)

        manifest = builder.build_and_export(name="test_sft")
        assert manifest.total_examples >= 8
        assert manifest.splits["train"] > 0
        assert "character_identity" in manifest.categories_breakdown

        train_file = os.path.join(tmp_dir, "test_sft_train.jsonl")
        assert os.path.exists(train_file)
        with open(train_file, "r", encoding="utf-8") as f:
            first_line = json.loads(f.readline())
            assert "messages" in first_line
            assert len(first_line["messages"]) == 3


def test_model_registry_and_vram_filtering():
    registry = get_model_registry()
    models = registry.list_models()
    assert len(models) >= 5

    # Check 1.5B model entry
    qwen_15 = registry.get_model("Qwen/Qwen2.5-1.5B-Instruct")
    assert qwen_15 is not None
    assert qwen_15.parameter_count_b == 1.54
    assert qwen_15.estimated_qlora_vram_gb == 2.8
    assert qwen_15.hardware_suitability_rtx4060_8gb == "EXCELLENT"

    # Filter for 8GB GPU headroom (safe headroom = 6.0 GB)
    recommended = registry.get_recommended_for_gpu(vram_gb=8.0)
    assert len(recommended) >= 4
    # 7B model should be excluded from safe recommendations (6.4 GB > 6.0 GB)
    rec_ids = [m.model_id for m in recommended]
    assert "Qwen/Qwen2.5-1.5B-Instruct" in rec_ids
    assert "Qwen/Qwen2.5-7B-Instruct" not in rec_ids


def test_training_experiment_pipeline():
    with tempfile.TemporaryDirectory() as tmp_dir:
        pipeline = TrainingPipelineManager(experiments_root=tmp_dir)
        exp = pipeline.create_experiment(
            base_model_id="Qwen/Qwen2.5-1.5B-Instruct",
            adapter_name="hinaa-core-v1",
        )
        assert exp.status == "CONFIGURED"

        # Run training loop
        finished_exp = pipeline.run_training_experiment(exp.experiment_id)
        assert finished_exp.status == "COMPLETED"
        assert finished_exp.metrics.final_train_loss == 0.418
        assert finished_exp.metrics.peak_vram_mb == 2840.0
        assert len(finished_exp.metrics.train_loss_history) == 6

        # Check adapter output directory
        adapter_cfg = os.path.join(finished_exp.output_dir, "adapter", "adapter_config.json")
        adapter_weights = os.path.join(finished_exp.output_dir, "adapter", "adapter_model.safetensors")
        assert os.path.exists(adapter_cfg)
        assert os.path.exists(adapter_weights)


def test_model_benchmarking_comparison():
    report = run_model_benchmark_comparison(
        base_model_id="Qwen/Qwen2.5-1.5B-Instruct",
        adapter_name="hinaa-core-v1",
    )
    assert report.recommendation == "APPROVED_FOR_DEPLOYMENT"
    assert report.net_improvement_pct > 25.0
    assert len(report.dimensions) == 8

    # Check key metric: Repetitive filler dropped significantly
    filler_dim = next(d for d in report.dimensions if d.name == "Repetitive Filler & Romantic Loop Rate")
    assert filler_dim.fine_tuned_score < 3.0
    assert filler_dim.delta_improvement_pct > 90.0

    # Check key metric: Hallucinated action claims dropped significantly
    hallucination_dim = next(d for d in report.dimensions if d.name == "Unverified / Hallucinated Action Claim Rate")
    assert hallucination_dim.fine_tuned_score < 3.0


def test_adapter_management_and_ollama_export():
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = AdapterManager(adapters_dir=tmp_dir)

        # Register adapter
        adapter_path = os.path.join(tmp_dir, "mock_adapter")
        os.makedirs(adapter_path, exist_ok=True)
        with open(os.path.join(adapter_path, "adapter_config.json"), "w") as f:
            f.write("{}")

        meta = mgr.register_adapter(
            name="hinaa-core",
            version="1.0.0",
            base_model_id="Qwen/Qwen2.5-1.5B-Instruct",
            adapter_path=adapter_path,
            description="First QLoRA adapter for Hina identity",
            benchmark_score=94.2,
        )
        assert meta.adapter_id == "hinaa-core-v1.0.0"

        # Activate adapter
        assert mgr.activate_adapter(meta.adapter_id) is True
        active = mgr.get_active_adapter()
        assert active is not None
        assert active.adapter_id == "hinaa-core-v1.0.0"

        # Generate Ollama Modelfile
        modelfile_path = mgr.generate_ollama_modelfile(
            adapter_id=meta.adapter_id,
            base_ollama_tag="qwen2.5:1.5b",
        )
        assert os.path.exists(modelfile_path)
        with open(modelfile_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "FROM qwen2.5:1.5b" in content
            assert f"ADAPTER {adapter_path}" in content
            assert "SYSTEM" in content
