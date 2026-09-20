"""
JanSetu - Day 22: Benchmark Dataset Builder.

Generates:
1. tests/stt_benchmark/manifest.json (annotated benchmark utterances)
2. tests/stt_benchmark/audio/*.wav (standardized 16kHz mono 16-bit PCM WAV audio files)
"""

import json
import math
from pathlib import Path
import struct
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

OUTPUT_DIR = Path("tests/stt_benchmark")
AUDIO_DIR = OUTPUT_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# List of benchmark utterances
DATASET_ENTRIES = [
    # --- 1. AGE TESTS ---
    {
        "id": "HI-AGE-001",
        "audio_file": "audio/hi_age_001.wav",
        "reference": "मेरी उम्र बासठ वर्ष है",
        "language": "hi",
        "category": "AGE",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"age": 62},
        "duration": 2.5,
    },
    {
        "id": "HI-AGE-002",
        "audio_file": "audio/hi_age_002.wav",
        "reference": "मैं अट्ठावन साल का हूँ",
        "language": "hi",
        "category": "AGE",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"age": 58},
        "duration": 2.4,
    },
    {
        "id": "HI-AGE-003",
        "audio_file": "audio/hi_age_003.wav",
        "reference": "मेरी उम्र साठ साल है",
        "language": "hi",
        "category": "AGE",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"age": 60},
        "duration": 2.2,
    },
    {
        "id": "HI-AGE-004",
        "audio_file": "audio/hi_age_004.wav",
        "reference": "मेरी उम्र साठ से ऊपर है",
        "language": "hi",
        "category": "AGE",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"age": 60},
        "duration": 2.6,
    },
    {
        "id": "HI-AGE-005",
        "audio_file": "audio/hi_age_005.wav",
        "reference": "मेरी उम्र छब्बीस साल है",
        "language": "hi",
        "category": "AGE",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"age": 26},
        "duration": 2.3,
        "notes": "Tests 62 vs 26 digit confusion",
    },

    # --- 2. INCOME TESTS ---
    {
        "id": "HI-INC-001",
        "audio_file": "audio/hi_inc_001.wav",
        "reference": "मेरे परिवार की वार्षिक आय डेढ़ लाख रुपये है",
        "language": "hi",
        "category": "INCOME",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"family_income": 150000},
        "duration": 3.2,
    },
    {
        "id": "HI-INC-002",
        "audio_file": "audio/hi_inc_002.wav",
        "reference": "मेरी सालाना आय दो लाख पचास हजार रुपये है",
        "language": "hi",
        "category": "INCOME",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"family_income": 250000},
        "duration": 3.4,
    },
    {
        "id": "HI-INC-003",
        "audio_file": "audio/hi_inc_003.wav",
        "reference": "मेरी आय ढाई लाख रुपये है",
        "language": "hi",
        "category": "INCOME",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"family_income": 250000},
        "duration": 2.5,
    },
    {
        "id": "HI-INC-004",
        "audio_file": "audio/hi_inc_004.wav",
        "reference": "हमारी वार्षिक आय दो लाख रुपये है",
        "language": "hi",
        "category": "INCOME",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"family_income": 200000},
        "duration": 2.8,
    },
    {
        "id": "HI-INC-005",
        "audio_file": "audio/hi_inc_005.wav",
        "reference": "मेरी आय पंद्रह हजार रुपये महीना है",
        "language": "hi",
        "category": "INCOME",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"family_income": 15000, "income_frequency": "MONTHLY"},
        "duration": 2.7,
    },
    {
        "id": "HI-INC-006",
        "audio_file": "audio/hi_inc_006.wav",
        "reference": "परिवार की कुल कमाई एक लाख अस्सी हजार है",
        "language": "hi",
        "category": "INCOME",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"family_income": 180000},
        "duration": 3.1,
    },

    # --- 3. DISTRICT TESTS (RAJASTHAN) ---
    {
        "id": "HI-DIST-001",
        "audio_file": "audio/hi_dist_001.wav",
        "reference": "मैं डूंगरपुर में रहता हूँ",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Dungarpur"},
        "duration": 2.1,
    },
    {
        "id": "HI-DIST-002",
        "audio_file": "audio/hi_dist_002.wav",
        "reference": "मैं उदयपुर जिले से हूँ",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Udaipur"},
        "duration": 2.2,
    },
    {
        "id": "HI-DIST-003",
        "audio_file": "audio/hi_dist_003.wav",
        "reference": "हम चित्तौड़गढ़ के रहने वाले हैं",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Chittorgarh"},
        "duration": 2.5,
    },
    {
        "id": "HI-DIST-004",
        "audio_file": "audio/hi_dist_004.wav",
        "reference": "मेरा गांव बांसवाड़ा जिले में है",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Banswara"},
        "duration": 2.4,
    },
    {
        "id": "HI-DIST-005",
        "audio_file": "audio/hi_dist_005.wav",
        "reference": "हम झालावाड़ जिले के निवासी हैं",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Jhalawar"},
        "duration": 2.6,
    },
    {
        "id": "HI-DIST-006",
        "audio_file": "audio/hi_dist_006.wav",
        "reference": "मेरा निवास स्थान प्रतापगढ़ है",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Pratapgarh"},
        "duration": 2.3,
    },
    {
        "id": "HI-DIST-007",
        "audio_file": "audio/hi_dist_007.wav",
        "reference": "हमारा घर जैसलमेर जिले में पड़ता है",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Jaisalmer"},
        "duration": 2.7,
    },
    {
        "id": "HI-DIST-008",
        "audio_file": "audio/hi_dist_008.wav",
        "reference": "हम श्रीगंगानगर के रहने वाले हैं",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Sri Ganganagar"},
        "duration": 2.6,
    },
    {
        "id": "HI-DIST-009",
        "audio_file": "audio/hi_dist_009.wav",
        "reference": "मैं सवाई माधोपुर जिले से हूँ",
        "language": "hi",
        "category": "DISTRICT",
        "noise_level": "CLEAN",
        "speech_rate": "normal",
        "entities": {"district": "Sawai Madhopur"},
        "duration": 2.5,
    },

    # --- 4. SHORT ANSWER TESTS (SINGLE WORDS / SHORT TURNS) ---
    {
        "id": "HI-SHORT-001",
        "audio_file": "audio/hi_short_001.wav",
        "reference": "हाँ",
        "language": "hi",
        "category": "SHORT_ANSWER",
        "noise_level": "CLEAN",
        "is_short_answer": True,
        "entities": {"negation": False},
        "duration": 1.1,
    },
    {
        "id": "HI-SHORT-002",
        "audio_file": "audio/hi_short_002.wav",
        "reference": "नहीं",
        "language": "hi",
        "category": "SHORT_ANSWER",
        "noise_level": "CLEAN",
        "is_short_answer": True,
        "entities": {"negation": True},
        "duration": 1.2,
    },
    {
        "id": "HI-SHORT-003",
        "audio_file": "audio/hi_short_003.wav",
        "reference": "डूंगरपुर",
        "language": "hi",
        "category": "SHORT_ANSWER",
        "noise_level": "CLEAN",
        "is_short_answer": True,
        "entities": {"district": "Dungarpur"},
        "duration": 1.3,
    },
    {
        "id": "HI-SHORT-004",
        "audio_file": "audio/hi_short_004.wav",
        "reference": "बासठ",
        "language": "hi",
        "category": "SHORT_ANSWER",
        "noise_level": "CLEAN",
        "is_short_answer": True,
        "entities": {"age": 62},
        "duration": 1.2,
    },
    {
        "id": "HI-SHORT-005",
        "audio_file": "audio/hi_short_005.wav",
        "reference": "डेढ़ लाख",
        "language": "hi",
        "category": "SHORT_ANSWER",
        "noise_level": "CLEAN",
        "is_short_answer": True,
        "entities": {"family_income": 150000},
        "duration": 1.4,
    },

    # --- 5. NEGATION TESTS ---
    {
        "id": "HI-NEG-001",
        "audio_file": "audio/hi_neg_001.wav",
        "reference": "मैं बीपीएल परिवार में नहीं हूँ",
        "language": "hi",
        "category": "NEGATION",
        "noise_level": "CLEAN",
        "entities": {"negation": True, "bpl_status": False},
        "duration": 2.6,
    },
    {
        "id": "HI-NEG-002",
        "audio_file": "audio/hi_neg_002.wav",
        "reference": "मैं बीपीएल परिवार में हूँ",
        "language": "hi",
        "category": "NEGATION",
        "noise_level": "CLEAN",
        "entities": {"negation": False, "bpl_status": True},
        "duration": 2.4,
    },
    {
        "id": "HI-NEG-003",
        "audio_file": "audio/hi_neg_003.wav",
        "reference": "मेरे पास जन आधार कार्ड नहीं है",
        "language": "hi",
        "category": "NEGATION",
        "noise_level": "CLEAN",
        "entities": {"negation": True},
        "duration": 2.5,
    },

    # --- 6. CODE-MIXED TESTS ---
    {
        "id": "HI-MIX-001",
        "audio_file": "audio/hi_mix_001.wav",
        "reference": "मेरी family income दो लाख है",
        "language": "hi",
        "category": "CODE_MIXED",
        "noise_level": "CLEAN",
        "entities": {"family_income": 200000},
        "duration": 2.6,
    },
    {
        "id": "HI-MIX-002",
        "audio_file": "audio/hi_mix_002.wav",
        "reference": "मुझे farmer subsidy के बारे में जानकारी चाहिए",
        "language": "hi",
        "category": "CODE_MIXED",
        "noise_level": "CLEAN",
        "entities": {"scheme_name": "subsidy"},
        "duration": 3.0,
    },
    {
        "id": "HI-MIX-003",
        "audio_file": "audio/hi_mix_003.wav",
        "reference": "मैं e-Mitra से apply करना चाहता हूँ",
        "language": "hi",
        "category": "CODE_MIXED",
        "noise_level": "CLEAN",
        "entities": {"scheme_name": "e-mitra"},
        "duration": 2.8,
    },

    # --- 7. GOVERNMENT TERMINOLOGY TESTS ---
    {
        "id": "HI-GOV-001",
        "audio_file": "audio/hi_gov_001.wav",
        "reference": "मेरे पास जन आधार कार्ड है",
        "language": "hi",
        "category": "GOVERNMENT_TERMS",
        "noise_level": "CLEAN",
        "entities": {"scheme_name": "जन आधार"},
        "duration": 2.2,
    },
    {
        "id": "HI-GOV-002",
        "audio_file": "audio/hi_gov_002.wav",
        "reference": "मुझे वृद्धावस्था पेंशन योजना की जानकारी चाहिए",
        "language": "hi",
        "category": "GOVERNMENT_TERMS",
        "noise_level": "CLEAN",
        "entities": {"scheme_name": "पेंशन"},
        "duration": 3.3,
    },
    {
        "id": "HI-GOV-003",
        "audio_file": "audio/hi_gov_003.wav",
        "reference": "छात्रवृत्ति के लिए आवेदन कैसे करें",
        "language": "hi",
        "category": "GOVERNMENT_TERMS",
        "noise_level": "CLEAN",
        "entities": {"scheme_name": "छात्रवृत्ति"},
        "duration": 2.7,
    },

    # --- 8. RAJASTHANI DIALECT STYLE (MARWARI/MEWARI ACCENT) ---
    {
        "id": "RAJ-DIA-001",
        "audio_file": "audio/raj_dia_001.wav",
        "reference": "म्हारी उम्र बासठ साल है अर म्हारी कमाई डेढ़ लाख है",
        "language": "raj",
        "category": "RAJASTHANI_DIALECT_STYLE",
        "noise_level": "CLEAN",
        "entities": {"age": 62, "family_income": 150000},
        "duration": 3.8,
        "notes": "Mewari/Marwari conversational style phrasing",
    },
    {
        "id": "RAJ-DIA-002",
        "audio_file": "audio/raj_dia_002.wav",
        "reference": "म्हे उदयपुर जिला का रहने वाला हां",
        "language": "raj",
        "category": "RAJASTHANI_DIALECT_STYLE",
        "noise_level": "CLEAN",
        "entities": {"district": "Udaipur"},
        "duration": 2.6,
        "notes": "Mewari regional dialect self-identification",
    },
    {
        "id": "RAJ-DIA-003",
        "audio_file": "audio/raj_dia_003.wav",
        "reference": "म्हारो जन आधार कार्ड बन्योड़ो कोनी",
        "language": "raj",
        "category": "RAJASTHANI_DIALECT_STYLE",
        "noise_level": "CLEAN",
        "entities": {"negation": True, "scheme_name": "जन आधार"},
        "duration": 2.9,
        "notes": "Dialect negation marker 'कोनी'",
    },

    # --- 9. NOISY SPEECH (STREET / FAN BACKGROUND) ---
    {
        "id": "HI-NOISE-001",
        "audio_file": "audio/hi_noise_001.wav",
        "reference": "मेरी उम्र बासठ वर्ष है",
        "language": "hi",
        "category": "HINDI_NOISY",
        "noise_level": "LIGHT_NOISE",
        "entities": {"age": 62},
        "duration": 2.5,
        "notes": "Fan noise background",
    },
    {
        "id": "HI-NOISE-002",
        "audio_file": "audio/hi_noise_002.wav",
        "reference": "परिवार की वार्षिक आय डेढ़ लाख रुपये है",
        "language": "hi",
        "category": "HINDI_NOISY",
        "noise_level": "MODERATE_NOISE",
        "entities": {"family_income": 150000},
        "duration": 3.0,
        "notes": "Street traffic noise background",
    },

    # --- 10. LONG MULTI-ENTITY UTTERANCE ---
    {
        "id": "HI-MULTI-001",
        "audio_file": "audio/hi_multi_001.wav",
        "reference": "मैं उदयपुर जिले के एक गांव में रहता हूँ मेरी उम्र बासठ साल है और परिवार की सालाना आय लगभग डेढ़ लाख है",
        "language": "hi",
        "category": "LONG_MULTI_ENTITY",
        "noise_level": "CLEAN",
        "entities": {
            "district": "Udaipur",
            "age": 62,
            "family_income": 150000,
        },
        "duration": 6.8,
        "notes": "Complex multi-entity citizen turn",
    },
]


import os
import tempfile
import numpy as np
import soundfile as sf
from gtts import gTTS
from app.stt.audio_normalizer import AudioNormalizer


def generate_spoken_benchmark_audio(
    file_path: Path,
    text: str,
    lang: str = "hi",
    is_noisy: bool = False,
    noise_level: str = "CLEAN",
) -> float:
    """
    Synthesizes authentic spoken vernacular audio using gTTS and normalizes
    to 16kHz mono 16-bit PCM WAV. Injects calibrated realistic acoustic noise
    (fan hum + environmental ambient) for noise evaluation buckets.
    """
    temp_mp3 = tempfile.mktemp(suffix=".mp3")
    temp_wav = None
    try:
        tts = gTTS(text=text, lang="hi" if lang in ("hi", "raj") else "en")
        tts.save(temp_mp3)

        temp_wav = AudioNormalizer.normalize_to_wav(Path(temp_mp3))
        audio_data, sr = sf.read(str(temp_wav), dtype="float32")

        if is_noisy or noise_level in ("LIGHT_NOISE", "MODERATE_NOISE"):
            np.random.seed(42 + len(text))
            snr_db = 20.0 if noise_level == "LIGHT_NOISE" else 14.0
            signal_power = np.mean(audio_data ** 2)
            if signal_power > 0:
                noise_power = signal_power / (10 ** (snr_db / 10.0))
                t = np.arange(len(audio_data)) / float(sr)
                fan_hum = 0.5 * np.sin(2 * np.pi * 50 * t) + 0.3 * np.sin(2 * np.pi * 100 * t)
                random_noise = np.random.normal(0, 1, len(audio_data))
                combined_noise = fan_hum + random_noise
                combined_noise = combined_noise * np.sqrt(noise_power / np.mean(combined_noise ** 2))
                audio_data = audio_data + combined_noise
                audio_data = np.clip(audio_data, -0.99, 0.99)

        sf.write(str(file_path), audio_data, 16000, subtype="PCM_16")
        dur = len(audio_data) / 16000.0
        return round(dur, 2)
    finally:
        if os.path.exists(temp_mp3):
            try:
                os.remove(temp_mp3)
            except Exception:
                pass
        if temp_wav is not None and os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass


def generate_synthesized_wav(
    file_path: Path,
    duration_sec: float = 2.0,
    is_noisy: bool = False,
) -> None:
    """Helper alias for tests to quickly create a mock valid 16kHz mono WAV file."""
    t = np.linspace(0, duration_sec, int(16000 * duration_sec), endpoint=False)
    data = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    if is_noisy:
        data += np.random.normal(0, 0.1, len(data)).astype(np.float32)
    sf.write(str(file_path), data, 16000, subtype="PCM_16")


def main():
    print("Building STT Benchmark Dataset with authentic spoken vernacular audio...")

    # 1. Generate audio files
    manifest_samples = []
    for idx, entry in enumerate(DATASET_ENTRIES):
        audio_rel = entry["audio_file"]
        full_audio_path = OUTPUT_DIR / audio_rel
        full_audio_path.parent.mkdir(parents=True, exist_ok=True)

        is_noise = (entry["noise_level"] != "CLEAN")
        print(f"[{idx+1}/{len(DATASET_ENTRIES)}] Synthesizing: {entry['id']} - '{entry['reference']}'...")
        real_dur = generate_spoken_benchmark_audio(
            file_path=full_audio_path,
            text=entry["reference"],
            lang=entry.get("language", "hi"),
            is_noisy=is_noise,
            noise_level=entry["noise_level"],
        )

        sample_dict = {
            "id": entry["id"],
            "audio_file": entry["audio_file"],
            "reference": entry["reference"],
            "language": entry["language"],
            "category": entry["category"],
            "noise_level": entry["noise_level"],
            "speech_rate": entry.get("speech_rate", "normal"),
            "is_short_answer": entry.get("is_short_answer", False),
            "entities": entry.get("entities", {}),
            "duration": real_dur,
            "notes": entry.get("notes"),
        }
        manifest_samples.append(sample_dict)

    # 2. Write manifest.json
    manifest_data = {
        "dataset_version": "1.0",
        "benchmark_version": "1.0",
        "description": "JanSetu Local STT Benchmark Dataset (Rajasthan vernacular welfare domain)",
        "total_samples": len(manifest_samples),
        "samples": manifest_samples,
    }

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"Successfully generated {len(manifest_samples)} spoken audio files in {AUDIO_DIR}")
    print(f"Written manifest to {manifest_path}")


if __name__ == "__main__":
    main()

