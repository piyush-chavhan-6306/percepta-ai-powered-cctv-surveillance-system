"""
PERCEPTA Core Module.
Contains core infrastructure: model manager, manifests, and system health utilities.
"""
from backend.core.model_manager import (
    MODELS_MANIFEST,
    ModelSpec,
    verify_models,
    report_model_readiness,
    calculate_sha256,
)

# Compatibility aliases
ModelEntry = ModelSpec
verify_all_models = verify_models
verify_model_file = calculate_sha256
MODELS_DIR = "models"

__all__ = [
    "MODELS_DIR",
    "MODELS_MANIFEST",
    "ModelSpec",
    "ModelEntry",
    "verify_models",
    "verify_all_models",
    "verify_model_file",
    "report_model_readiness",
    "calculate_sha256",
]
