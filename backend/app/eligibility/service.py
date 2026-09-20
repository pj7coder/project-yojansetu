from datetime import date
import logging
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.eligibility.compiler import EligibilityRuleCompiler
from app.eligibility.engine import EligibilityEngine
from app.eligibility.models import CompiledScheme
from app.eligibility.profile import CitizenProfile
from app.eligibility.repository import VerifiedSchemeRepository
from app.eligibility.result import EligibilityResult

logger = logging.getLogger("yojansetu.eligibility.service")


class EligibilityService:
    """
    Coordinates verified scheme retrieval, in-memory rule compilation caching,
    and privacy-preserving eligibility evaluation.
    """

    @classmethod
    def clear_cache(cls) -> None:
        """Clears the compiled schemes cache."""
        from app.cache.verified_rule_cache import get_rule_cache
        get_rule_cache().clear()

    @classmethod
    def evaluate_single_scheme(
        cls,
        session: Session,
        scheme_id: str,
        profile_data: Dict[str, Any],
        evaluation_date: Optional[date] = None,
    ) -> EligibilityResult:
        """
        Evaluates a citizen profile against a single verified scheme.
        Zero permanent persistence of citizen profiles.
        Safe logging: no personal citizen details logged.
        """
        start_time = time.perf_counter()

        # 1. Compile or retrieve compiled scheme from cache
        from app.cache.verified_rule_cache import get_rule_cache
        rule_cache = get_rule_cache()
        compiled_scheme = rule_cache.get(scheme_id, session=session)
        if not compiled_scheme:
            raw_verified = VerifiedSchemeRepository.get_verified_scheme(session, scheme_id)
            compiled_scheme = EligibilityRuleCompiler.compile_scheme(raw_verified)

        # 2. Instantiate and normalize citizen profile
        profile = CitizenProfile(**profile_data)

        # 3. Evaluate using pure domain engine
        result = EligibilityEngine.evaluate_scheme(
            scheme=compiled_scheme,
            profile=profile,
            evaluation_date=evaluation_date,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # 4. Privacy-preserving audit logging (NO citizen personal attributes logged!)
        logger.info(
            f"Eligibility evaluation completed for scheme '{result.scheme_id}': "
            f"status={result.eligibility_status.value}, "
            f"missing_fields={len(result.missing_fields)}, "
            f"failed_conditions={len(result.failed_conditions)}, "
            f"duration_ms={round(duration_ms, 2)}"
        )

        return result

    @classmethod
    def evaluate_multiple_schemes(
        cls,
        session: Session,
        scheme_ids: List[str],
        profile_data: Dict[str, Any],
        evaluation_date: Optional[date] = None,
    ) -> List[EligibilityResult]:
        """
        Evaluates a single citizen profile against multiple specified verified schemes.
        Normalizes the profile once to optimize throughput.
        """
        from app.cache.verified_rule_cache import get_rule_cache
        profile = CitizenProfile(**profile_data)
        results: List[EligibilityResult] = []
        rule_cache = get_rule_cache()

        compiled_map = rule_cache.get_many(scheme_ids, session=session)

        for sid in scheme_ids:
            try:
                compiled = compiled_map.get(sid)
                if not compiled:
                    raw_verified = VerifiedSchemeRepository.get_verified_scheme(session, sid)
                    compiled = EligibilityRuleCompiler.compile_scheme(raw_verified)

                res = EligibilityEngine.evaluate_scheme(
                    scheme=compiled,
                    profile=profile,
                    evaluation_date=evaluation_date,
                )
                results.append(res)
            except Exception as e:
                logger.error(f"Error evaluating scheme '{sid}': {e}")

        return results
