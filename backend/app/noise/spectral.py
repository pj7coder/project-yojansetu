"""
JanSetu - Day 23: Spectral Gating Noise Suppressor (Optional).

Uses short-time Fourier transform (STFT) spectral subtraction / gating
to attenuate steady background noise (fan hum, steady vehicle drone).
Operates strictly locally and offline.
"""

import logging
from pathlib import Path
from typing import Tuple, Union
import numpy as np
import soundfile as sf

from app.noise.interface import NoiseSuppressor

logger = logging.getLogger(__name__)


class SpectralGatingNoiseSuppressor(NoiseSuppressor):
    """
    Local offline noise suppressor using spectral magnitude subtraction.
    Estimates stationary noise floor from the lowest 10% energy frames
    and subtracts a conservative fraction to avoid musical noise and phoneme clipping.
    """

    def __init__(self, noise_reduction_factor: float = 0.5, n_fft: int = 512, hop_length: int = 256):
        self.noise_reduction_factor = noise_reduction_factor
        self.n_fft = n_fft
        self.hop_length = hop_length

    def suppress_noise(
        self, samples: np.ndarray, sample_rate: int
    ) -> Tuple[np.ndarray, bool]:
        if len(samples) < self.n_fft:
            return samples, False

        try:
            # Framing with Hanning window
            window = np.hanning(self.n_fft)
            num_samples = len(samples)
            num_frames = 1 + (num_samples - self.n_fft) // self.hop_length
            if num_frames < 4:
                return samples, False

            # Frame extraction
            frames = np.lib.stride_tricks.as_strided(
                samples,
                shape=(num_frames, self.n_fft),
                strides=(samples.strides[0] * self.hop_length, samples.strides[0]),
            ) * window

            # Real FFT
            stft = np.fft.rfft(frames, axis=1)
            magnitude = np.abs(stft)
            phase = np.angle(stft)

            # Estimate noise profile from lowest 10% energy frames
            frame_energies = np.sum(magnitude ** 2, axis=1)
            num_noise_frames = max(1, int(0.10 * num_frames))
            noise_frame_indices = np.argsort(frame_energies)[:num_noise_frames]
            noise_profile = np.mean(magnitude[noise_frame_indices, :], axis=0)

            # Spectral subtraction with oversubtraction factor and spectral floor
            over_sub = self.noise_reduction_factor
            spectral_floor = 0.15  # Avoid zeroing out low-energy consonants

            subtracted = magnitude - (over_sub * noise_profile)
            subtracted = np.maximum(subtracted, spectral_floor * magnitude)

            # Reconstruct complex spectrum
            reconstructed_stft = subtracted * np.exp(1j * phase)

            # Inverse FFT
            inv_frames = np.fft.irfft(reconstructed_stft, n=self.n_fft, axis=1) * window

            # Overlap-add synthesis
            denoised = np.zeros(num_samples, dtype=np.float32)
            window_sum = np.zeros(num_samples, dtype=np.float32)

            for i in range(num_frames):
                start = i * self.hop_length
                end = start + self.n_fft
                denoised[start:end] += inv_frames[i]
                window_sum[start:end] += window ** 2

            # Normalize by window sum
            nonzero = window_sum > 1e-6
            denoised[nonzero] /= window_sum[nonzero]

            # Preserve tail
            if (num_frames * self.hop_length) < num_samples:
                tail_start = num_frames * self.hop_length
                denoised[tail_start:] = samples[tail_start:]

            # Normalize to avoid clipping
            max_val = np.max(np.abs(denoised))
            if max_val > 0.99:
                denoised = (denoised / max_val) * 0.95

            return denoised.astype(np.float32), True

        except Exception as exc:
            logger.warning(f"Spectral noise suppression failed, falling back to passthrough: {exc}")
            return samples, False

    def suppress_file(
        self, input_path: Union[str, Path], output_path: Union[str, Path]
    ) -> bool:
        in_p = Path(input_path)
        out_p = Path(output_path)
        try:
            samples, sr = sf.read(str(in_p), dtype="float32")
            denoised, applied = self.suppress_noise(samples, sr)
            sf.write(str(out_p), denoised, sr, subtype="PCM_16")
            return applied
        except Exception as exc:
            logger.warning(f"Spectral file suppression failed: {exc}")
            return False
