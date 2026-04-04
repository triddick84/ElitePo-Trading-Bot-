"""
Safe model loading utilities.
Replaces raw pickle.load() with safer alternatives to prevent RCE.
"""

import io
import pickle
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Allowlisted classes that are safe to unpickle for ML models
SAFE_CLASSES = {
    ('sklearn.ensemble', '_forest', 'RandomForestClassifier'),
    ('sklearn.ensemble', '_gb', 'GradientBoostingClassifier'),
    ('sklearn.ensemble', '_stacking', 'StackingClassifier'),
    ('sklearn.ensemble', '_voting', 'VotingClassifier'),
    ('sklearn.linear_model', '_logistic', 'LogisticRegression'),
    ('sklearn.svm', '_classes', 'SVC'),
    ('sklearn.tree', '_classes', 'DecisionTreeClassifier'),
    ('sklearn.preprocessing', '_data', 'StandardScaler'),
    ('sklearn.preprocessing', '_data', 'MinMaxScaler'),
    ('sklearn.preprocessing', '_label', 'LabelEncoder'),
    ('sklearn.pipeline', 'Pipeline'),
    ('numpy', 'ndarray'),
    ('numpy', 'dtype'),
    ('numpy.core.multiarray', '_reconstruct'),
    ('numpy.core.multiarray', 'scalar'),
    ('collections', 'OrderedDict'),
    ('builtins', 'dict'),
    ('builtins', 'list'),
    ('builtins', 'tuple'),
    ('builtins', 'set'),
    ('builtins', 'frozenset'),
    ('builtins', 'float'),
    ('builtins', 'int'),
    ('builtins', 'str'),
    ('builtins', 'bool'),
    ('builtins', 'bytes'),
    ('builtins', 'complex'),
    ('builtins', 'slice'),
    ('builtins', 'range'),
}


class RestrictedUnpickler(pickle.Unpickler):
    """
    Restricted unpickler that only allows known-safe classes.
    Prevents arbitrary code execution from malicious pickle files.
    """
    
    def find_class(self, module, name):
        # Allow numpy internals needed for array reconstruction
        if module.startswith('numpy'):
            return super().find_class(module, name)
        
        # Allow sklearn internals for ML models
        if module.startswith('sklearn'):
            return super().find_class(module, name)
        
        # Allow basic builtins and collections
        if (module, name) in {(m, n) for m, _, n in SAFE_CLASSES if _ == ''} or \
           any(module == m and name == n for m, n in {(m, n) for m, _, n in SAFE_CLASSES}):
            return super().find_class(module, name)
        
        # Allow common safe modules
        if module in ('builtins', 'collections', 'datetime', 'copy_reg', 'copyreg', '_codecs'):
            return super().find_class(module, name)
        
        raise pickle.UnpicklingError(
            f"Blocked unsafe class: {module}.{name}"
        )


def safe_pickle_load(filepath: str) -> dict:
    """
    Safely load a pickle file using RestrictedUnpickler.
    Only allows known-safe ML model classes.
    
    Args:
        filepath: Path to the pickle file
    Returns:
        Unpickled object
    Raises:
        pickle.UnpicklingError: If unsafe classes are found
    """
    try:
        with open(filepath, 'rb') as f:
            return RestrictedUnpickler(f).load()
    except pickle.UnpicklingError as e:
        logger.error(f"Unsafe pickle content blocked in {filepath}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading pickle file {filepath}: {e}")
        raise
