from datetime import date, datetime
import logging
from typing import Any, Dict, List, Optional, Set, Union

from app.eligibility.models import ASTNode, CompiledScheme, ConditionNode, ExclusionNode, GroupNode
from app.normalization.schemas import LogicalGroupType, OperatorEnum

logger = logging.getLogger("yojansetu.eligibility.compiler")

MAX_RULE_DEPTH = 10
SUPPORTED_SCHEMA_VERSIONS = {"1.0"}


class CompilationError(Exception):
    """Raised when canonical rule JSON violates compilation invariants."""
    pass


class EligibilityRuleCompiler:
    """
    Translates validated canonical rule JSON into an immutable AST structure.
    Prepares rules for fast, repeated deterministic evaluation.
    Enforces maximum nesting depth and cycle protection.
    """

    @classmethod
    def compile_scheme(cls, raw_data: Dict[str, Any]) -> CompiledScheme:
        """
        Compiles a verified scheme payload into a CompiledScheme.
        Accepts verified scheme JSON wrapper or direct canonical dictionary.
        """
        # 1. Extract canonical scheme object if wrapped
        canonical = raw_data.get("canonical_scheme") or raw_data.get("scheme") or raw_data

        # 2. Schema version validation
        schema_version = str(canonical.get("schema_version", "1.0"))
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise CompilationError(
                f"Unsupported rule schema version '{schema_version}'. Supported: {SUPPORTED_SCHEMA_VERSIONS}"
            )

        # 3. Identity and metadata
        identity = canonical.get("scheme_identity") or canonical.get("identity") or {}
        scheme_id = str(
            identity.get("scheme_id")
            or canonical.get("scheme_id")
            or canonical.get("internal_scheme_code")
            or raw_data.get("scheme_draft_id")
            or "UNKNOWN_SCHEME"
        )
        name_obj = identity.get("name") or identity.get("official_name") or {}
        if isinstance(name_obj, dict):
            scheme_name = (
                name_obj.get("en")
                or name_obj.get("english")
                or name_obj.get("raw")
                or identity.get("official_name_raw")
                or "Unknown Scheme"
            )
            scheme_name_hi = name_obj.get("hi") or name_obj.get("hindi")
        else:
            scheme_name = str(name_obj or identity.get("official_name_raw") or "Unknown Scheme")
            scheme_name_hi = identity.get("official_name_hi")

        # 4. Temporal boundaries (valid_from / valid_until from important_dates)
        valid_from: Optional[date] = None
        valid_until: Optional[date] = None
        for item in canonical.get("important_dates", []):
            event = str(item.get("event_name", "")).lower()
            date_str = item.get("normalized_date")
            if date_str:
                try:
                    d = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if "start" in event or "effective" in event or "valid_from" in event or "launch" in event:
                        valid_from = d
                    elif "end" in event or "expiry" in event or "valid_until" in event or "deadline" in event:
                        valid_until = d
                except Exception:
                    pass

        # 5. Compile eligibility root rule
        eligibility_sec = canonical.get("eligibility", {})
        raw_root = eligibility_sec.get("root_rule")
        root_rule: Optional[ASTNode] = None
        if raw_root:
            visited_ids: Set[str] = set()
            root_rule = cls._compile_node(raw_root, depth=0, visited_ids=visited_ids)

        # 6. Compile exclusions
        exclusions: List[ExclusionNode] = []
        for raw_excl in canonical.get("exclusions", []):
            excl_node = cls._compile_exclusion(raw_excl)
            if excl_node:
                exclusions.append(excl_node)

        # 7. Collect preferences if present
        preferences: List[ASTNode] = []
        # Check if root rule or children have preference qualifiers
        if root_rule and isinstance(root_rule, GroupNode):
            non_pref_children = []
            for child in root_rule.children:
                if isinstance(child, ConditionNode) and child.is_preference:
                    preferences.append(child)
                else:
                    non_pref_children.append(child)
            root_rule.children = non_pref_children

        return CompiledScheme(
            scheme_id=scheme_id,
            scheme_name=scheme_name,
            scheme_name_hi=scheme_name_hi,
            schema_version=schema_version,
            valid_from=valid_from,
            valid_until=valid_until,
            root_rule=root_rule,
            exclusions=exclusions,
            preferences=preferences,
        )

    @classmethod
    def _compile_node(
        cls,
        raw_node: Dict[str, Any],
        depth: int,
        visited_ids: Set[str],
    ) -> ASTNode:
        if depth > MAX_RULE_DEPTH:
            raise CompilationError(f"Maximum rule depth exceeded: {depth} > {MAX_RULE_DEPTH}")

        node_id = str(raw_node.get("condition_id") or raw_node.get("node_id") or f"NODE-{depth}-{len(visited_ids)}")
        if node_id in visited_ids:
            raise CompilationError(f"Cycle detected in rule graph at node {node_id}")
        visited_ids.add(node_id)

        node_type = str(
            raw_node.get("type")
            or raw_node.get("logical_operator")
            or raw_node.get("group_type")
            or raw_node.get("logic")
            or (raw_node.get("operator") if ("children" in raw_node or "conditions" in raw_node) else "")
            or ""
        ).upper()

        # Is it a logical group (AND, OR, NOT)?
        if node_type in (LogicalGroupType.AND, LogicalGroupType.OR, LogicalGroupType.NOT, "AND", "OR", "NOT"):
            children_raw = raw_node.get("children") or raw_node.get("conditions") or []
            children: List[ASTNode] = []
            for child_raw in children_raw:
                child_node = cls._compile_node(child_raw, depth=depth + 1, visited_ids=visited_ids.copy())
                children.append(child_node)

            return GroupNode(
                node_id=node_id,
                type=node_type,
                children=children,
                raw_text=raw_node.get("raw_text"),
                evidence_refs=raw_node.get("evidence_refs", []),
            )

        # Otherwise it is an atomic condition
        field_name = str(raw_node.get("field", "")).strip()
        op_raw = raw_node.get("operator", "EQ")
        if isinstance(op_raw, OperatorEnum):
            op_str = op_raw.value
        else:
            op_str = str(op_raw).upper().strip()

        # Check if condition is tagged as preference
        is_pref = (
            raw_node.get("context_qualifier") == "PREFERENCE"
            or "preference" in str(raw_node.get("raw_text", "")).lower()
            or bool(raw_node.get("is_preference"))
        )

        return ConditionNode(
            node_id=node_id,
            field=field_name,
            operator=op_str,
            value=raw_node.get("value"),
            unit=raw_node.get("unit"),
            periodicity=raw_node.get("periodicity"),
            raw_text=raw_node.get("raw_text"),
            evidence_refs=raw_node.get("evidence_refs", []),
            is_preference=is_pref,
            custom_field_name=raw_node.get("custom_field_name"),
        )

    @classmethod
    def _compile_exclusion(cls, raw_excl: Dict[str, Any]) -> Optional[ExclusionNode]:
        excl_id = str(raw_excl.get("exclusion_id") or "EXCL-UNKNOWN")
        raw_text = raw_excl.get("raw_text", "")
        evidence_refs = raw_excl.get("evidence_refs", [])

        # Check if exclusion defines a structured field/operator/value
        field_name = raw_excl.get("field")
        if not field_name:
            # Check if raw_text mentions pension or other recognized exclusion
            lower_text = raw_text.lower()
            if "pension" in lower_text or "पेंशन" in lower_text:
                field_name = "receiving_pension_x"
            else:
                field_name = "custom_exclusion"

        op_raw = raw_excl.get("operator") or OperatorEnum.EQ
        op_str = op_raw.value if isinstance(op_raw, OperatorEnum) else str(op_raw).upper()

        val = raw_excl.get("value")
        if val is None:
            # Default for disqualification is that having this condition (True) triggers exclusion
            val = True

        cond = ConditionNode(
            node_id=excl_id,
            field=field_name,
            operator=op_str,
            value=val,
            raw_text=raw_text,
            evidence_refs=evidence_refs,
        )

        is_mandatory = raw_excl.get("mandatory_check")
        if is_mandatory is None:
            is_mandatory = (
                field_name == "receiving_pension_x"
                or bool(raw_excl.get("require_attestation", False))
            )

        return ExclusionNode(
            exclusion_id=excl_id,
            rule=cond,
            raw_text=raw_text,
            evidence_refs=evidence_refs,
            mandatory_check=bool(is_mandatory),
        )
