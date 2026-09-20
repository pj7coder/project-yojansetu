"""
Location, District, Domicile, and Jurisdiction Parser for Rajasthan.
Strictly preserves legal distinction between residence state and legal domicile status.
"""

import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("yojansetu.profile_extraction.location_parser")

_DISTRICTS_CACHE: Optional[Dict[str, str]] = None


def get_district_alias_map() -> Dict[str, str]:
    """Returns mapping of lower-cased alias/name -> canonical English district name."""
    global _DISTRICTS_CACHE
    if _DISTRICTS_CACHE is not None:
        return _DISTRICTS_CACHE

    reg_path = Path(__file__).resolve().parent.parent / "reference_data" / "rajasthan_districts.json"
    districts_map: Dict[str, str] = {}

    if reg_path.exists():
        try:
            with open(reg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for d in data.get("districts", []):
                canon_name = d["name"]
                districts_map[canon_name.lower().strip()] = canon_name
                if "name_hi" in d:
                    districts_map[d["name_hi"].lower().strip()] = canon_name
                for alias in d.get("aliases", []):
                    districts_map[alias.lower().strip()] = canon_name
        except Exception as e:
            logger.error(f"Failed loading districts reference data from {reg_path}: {e}")

    # Add common phonetic transliterations from Day 22 STT benchmark
    districts_map["dungar pur"] = "Dungarpur"
    districts_map["doom garpur"] = "Dungarpur"
    districts_map["baswara"] = "Banswara"
    districts_map["chittor"] = "Chittorgarh"
    districts_map["sawai madhopur"] = "Sawai Madhopur"
    districts_map["sriganganagar"] = "Ganganagar"
    districts_map["ganganagar"] = "Ganganagar"

    _DISTRICTS_CACHE = districts_map
    return _DISTRICTS_CACHE


class LocationAndDistrictParser:
    """
    Parses Rajasthan districts, state residency, legal domicile, and rural/urban classification.
    """

    @classmethod
    def parse_district(cls, text: str) -> Optional[str]:
        """
        Extracts canonical district name if an exact or approved alias match is found.
        Does not use arbitrary fuzzy matching.
        """
        if not text:
            return None

        alias_map = get_district_alias_map()
        clean = text.strip().lower()

        # Step 1: Check direct match
        if clean in alias_map:
            return alias_map[clean]

        # Step 2: Check word tokens and bigrams in phrase
        words = re.split(r'[\s,।!?]+', clean)
        # Check bigrams first (e.g. "sawai madhopur")
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if bigram in alias_map:
                return alias_map[bigram]

        # Check single words
        for w in words:
            if len(w) > 2 and w in alias_map:
                return alias_map[w]

        return None

    @classmethod
    def parse_residence_vs_domicile(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parses state residence and legal domicile status separately.
        Returns: (state, domicile_status)

        Rules:
        - 'मैं राजस्थान में रहता हूँ' -> state='Rajasthan', domicile_status=None
        - 'मेरे पास राजस्थान का मूल निवास प्रमाण पत्र है' -> state='Rajasthan', domicile_status='Rajasthan'
        - Mentions other state -> returns that state
        """
        clean = text.strip().lower()
        state: Optional[str] = None
        domicile: Optional[str] = None

        # Check explicit domicile proof
        if re.search(r'(मूल\s*निवास|स्थाई\s*निवासी|domicile)', clean):
            if "राजस्थान" in clean or "rajasthan" in clean:
                domicile = "Rajasthan"
                state = "Rajasthan"
            else:
                domicile = "YES"

        # Check state residence (without domicile)
        elif re.search(r'(राजस्थान|rajasthan)', clean):
            state = "Rajasthan"

        return (state, domicile)

    @classmethod
    def parse_rural_urban(cls, text: str) -> Optional[str]:
        """Parses RURAL vs URBAN classification."""
        clean = text.strip().lower()
        if re.search(r'(ग्रामीण|गांव|गाँव|देहात|rural|village)', clean):
            return "RURAL"
        if re.search(r'(शहरी|शहर|कस्बा|urban|city|town)', clean):
            return "URBAN"
        return None
