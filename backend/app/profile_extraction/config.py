"""
Configuration settings for Citizen Profile Extraction, Normalization & Confirmation.
"""

from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProfileExtractionSettings(BaseSettings):
    """Settings controlling language normalization, deterministic fast path, and LLM extraction."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    profile_llm_extraction_enabled: bool = Field(default=True, alias="PROFILE_LLM_EXTRACTION_ENABLED")
    profile_confirm_stt_critical_fields: bool = Field(default=True, alias="PROFILE_CONFIRM_STT_CRITICAL_FIELDS")
    profile_confirm_llm_assisted_values: bool = Field(default=True, alias="PROFILE_CONFIRM_LLM_ASSISTED_VALUES")
    dialect_normalization_enabled: bool = Field(default=True, alias="DIALECT_NORMALIZATION_ENABLED")
    dialect_lexicon_version: str = Field(default="1.0", alias="DIALECT_LEXICON_VERSION")
    profile_extraction_version: str = Field(default="1.0", alias="PROFILE_EXTRACTION_VERSION")
    text_normalizer_version: str = Field(default="1.0", alias="TEXT_NORMALIZER_VERSION")
    confirmation_policy_version: str = Field(default="1.0", alias="CONFIRMATION_POLICY_VERSION")
    profile_extraction_max_input_chars: int = Field(default=1000, alias="PROFILE_EXTRACTION_MAX_INPUT_CHARS")
    profile_max_facts_per_utterance: int = Field(default=10, alias="PROFILE_MAX_FACTS_PER_UTTERANCE")
    profile_extraction_debug: bool = Field(default=False, alias="PROFILE_EXTRACTION_DEBUG")

    stt_confirm_fields: List[str] = Field(
        default=[
            "age",
            "date_of_birth",
            "annual_income",
            "family_income",
            "bpl_status",
            "social_category",
            "disability_status",
            "disability_percentage",
            "district",
            "domicile_status",
            "land_holding",
        ],
        alias="STT_CONFIRM_FIELDS",
    )


@lru_cache()
def get_profile_extraction_settings() -> ProfileExtractionSettings:
    return ProfileExtractionSettings()
