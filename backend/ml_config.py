"""
ML Configuration - Force CPU-only mode for deployment
Prevents CUDA/GPU initialization errors in containerized environments
"""
import os
import logging

logger = logging.getLogger(__name__)

# Force CPU-only mode for TensorFlow
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF warnings
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations

logger.info("✅ ML Config: Forcing CPU-only mode (no GPU/CUDA)")
