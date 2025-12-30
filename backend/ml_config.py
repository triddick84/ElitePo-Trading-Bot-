"""
ML Configuration - Force CPU-only mode for deployment
Prevents CUDA/GPU initialization errors in containerized environments
"""
import os
import logging

logger = logging.getLogger(__name__)

# Force CPU-only mode for TensorFlow - CRITICAL for deployment
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Disable all GPUs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress all TF warnings/errors
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'  # Disable oneDNN custom operations
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'false'

# Limit threading for low-resource environments (250m CPU)
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['TF_NUM_INTEROP_THREADS'] = '1'
os.environ['TF_NUM_INTRAOP_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'

# Disable JIT for lower memory usage
os.environ['TF_XLA_FLAGS'] = '--tf_xla_enable_xla_devices=false'

logger.info("✅ ML Config: Forcing CPU-only mode (no GPU/CUDA)")

# Try to configure TensorFlow if available
try:
    import tensorflow as tf
    tf.config.set_visible_devices([], 'GPU')
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.threading.set_intra_op_parallelism_threads(1)
    logger.info("✅ TensorFlow configured for CPU-only deployment")
except ImportError:
    logger.info("TensorFlow not installed - skipping TF configuration")
except Exception as e:
    logger.warning(f"Could not configure TensorFlow: {e}")

