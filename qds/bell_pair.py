"""
Bell pair state vector preparation: |Φ+⟩ = (|00⟩ + |11⟩) / √2
"""
import numpy as np
from qds.bell_pair import KET_0, KET_1, tensor_product


def prepare_bell_pair() -> np.ndarray:
    """
    Returns 2-qubit entangled Bell statevector |Φ+⟩.
    State dimension: 4.
    """
    bell_00 = tensor_product(KET_0, KET_0)
    bell_11 = tensor_product(KET_1, KET_1)
    return (bell_00 + bell_11) / np.sqrt(2.0)
