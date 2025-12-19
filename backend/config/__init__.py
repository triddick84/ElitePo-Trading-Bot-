"""Configuration Module"""

import yaml
import os
from typing import Dict

def load_breakout_config() -> Dict:
    """Load breakout predictor configuration from YAML"""
    config_path = os.path.join(os.path.dirname(__file__), 'breakout_config.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}

__all__ = ['load_breakout_config']
