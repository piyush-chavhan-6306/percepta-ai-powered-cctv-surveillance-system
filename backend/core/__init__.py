"""
PERCEPTA Core Module.
Contains core infrastructure: model manager, manifests, and system health utilities.
"""
from backend.core.model_manager import (
    MODELS_DIR,
    MODELS_MANIFEST,
    ModelEntry,
    verify_model_file,
    verify_all_models,
    report_model_readiness,
)

__all__ = [
    "MODELS_DIR",
    "MODELS_MANIFEST",
    "ModelEntry",
    "verify_model_file",
    "verify_all_models",
    "report_model_readiness",
]
