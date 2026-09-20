"""
JanSetu - Day 23: Passthrough Noise Suppressor (Default).

Performs zero alteration to the audio, guaranteeing no degradation
of quiet consonants, short answers, or regional dialect phonemes.
"""

import shutil
from pathlib import Path
from typing import Tuple, Union
import numpy as np

from app.noise.interface import NoiseSuppressor


class PassthroughNoiseSuppressor(NoiseSuppressor):
    """Safe default suppressor that passes audio through unmodified."""

    def suppress_noise(
        self, samples: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, bool]:
        """Returns samples unmodified with applied=False."""
        return samples, False

    def suppress_file(
        self, input_path: Union[str, Path], output_path: Union[str, Path]
    ) -> bool:
        """Copies file unmodified to output_path if paths differ."""
        in_p = Path(input_path)
        out_p = Path(output_path)
        if in_p.resolve() != out_p.resolve():
            shutil.copy2(str(in_p), str(out_p))
        return False
