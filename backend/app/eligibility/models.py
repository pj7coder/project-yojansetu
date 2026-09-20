from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional, Union


@dataclass
class ASTNode:
    """Base abstract syntax tree node for compiled eligibility rules."""
    node_id: str
    evidence_refs: List[str] = field(default_factory=list)
    raw_text: Optional[str] = None


@dataclass
class ConditionNode(ASTNode):
    """Atomic condition leaf node."""
    field: str = ""
    operator: str = "EQ"
    value: Any = None
    unit: Optional[str] = None
    periodicity: Optional[str] = None
    is_preference: bool = False
    custom_field_name: Optional[str] = None


@dataclass
class GroupNode(ASTNode):
    """Composite boolean logical group node (AND, OR, NOT)."""
    type: str = "AND"  # "AND", "OR", "NOT"
    children: List[ASTNode] = field(default_factory=list)


@dataclass
class ExclusionNode:
    """Disqualification condition node."""
    exclusion_id: str
    rule: ASTNode
    raw_text: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    mandatory_check: bool = False


@dataclass
class CompiledScheme:
    """
    Immutable in-memory compiled scheme structure optimized for fast deterministic evaluation.
    Separates mandatory eligibility, negative exclusions, and non-blocking preferences.
    """
    scheme_id: str
    scheme_name: str
    scheme_name_hi: Optional[str] = None
    schema_version: str = "1.0"
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    root_rule: Optional[ASTNode] = None
    exclusions: List[ExclusionNode] = field(default_factory=list)
    preferences: List[ASTNode] = field(default_factory=list)
