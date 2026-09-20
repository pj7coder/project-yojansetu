import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.eligibility.fields import get_field_definition, is_registered_field
from app.eligibility.models import ASTNode, ConditionNode, GroupNode
from app.eligibility.operators import evaluate_operator
from app.eligibility.profile import CitizenProfile
from app.eligibility.result import (
    ConditionEvaluationResult,
    MissingFieldInfo,
    ReasonCode,
)
from app.eligibility.truth import TruthState, evaluate_and, evaluate_not, evaluate_or


class RuleEvaluator:
    """
    Evaluates compiled AST rule trees against a citizen profile using three-state Kleene logic.
    Performs deterministic short-circuiting and minimal missing field discovery.
    """

    def __init__(self, profile: CitizenProfile):
        self.profile = profile
        self.passed_conditions: List[ConditionEvaluationResult] = []
        self.failed_conditions: List[ConditionEvaluationResult] = []
        self.missing_fields: List[MissingFieldInfo] = []
        self._missing_field_names: Set[str] = set()
        self.conditions_evaluated_count: int = 0
        self.conditions_short_circuited_count: int = 0

    def evaluate(self, node: Optional[ASTNode]) -> Tuple[TruthState, Dict[str, Any]]:
        """
        Entry point to evaluate a root AST node.
        Returns (TruthState, evaluation_trace).
        """
        if node is None:
            return TruthState.TRUE, {"type": "EMPTY", "result": TruthState.TRUE.value}

        start_time = time.perf_counter()
        state, trace = self._eval_node(node)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        trace["evaluation_duration_ms"] = round(duration_ms, 3)
        return state, trace

    def _eval_node(self, node: ASTNode) -> Tuple[TruthState, Dict[str, Any]]:
        if isinstance(node, GroupNode):
            return self._eval_group(node)
        elif isinstance(node, ConditionNode):
            return self._eval_condition(node)
        else:
            return TruthState.UNKNOWN, {
                "node_id": getattr(node, "node_id", "UNKNOWN"),
                "result": TruthState.UNKNOWN.value,
                "error": "Unrecognized node type",
            }

    def _eval_group(self, group: GroupNode) -> Tuple[TruthState, Dict[str, Any]]:
        group_type = group.type.upper()
        children_traces: List[Dict[str, Any]] = []

        if group_type == "AND":
            child_states: List[TruthState] = []
            short_circuited = False

            for child in group.children:
                if short_circuited:
                    self.conditions_short_circuited_count += 1
                    children_traces.append({
                        "node_id": child.node_id,
                        "result": "SKIPPED_SHORT_CIRCUIT",
                    })
                    continue

                c_state, c_trace = self._eval_node(child)
                child_states.append(c_state)
                children_traces.append(c_trace)

                # AND Short-circuit on definitive FALSE
                if c_state == TruthState.FALSE:
                    short_circuited = True

            final_state = evaluate_and(child_states)
            return final_state, {
                "node_id": group.node_id,
                "type": "AND",
                "result": final_state.value,
                "children": children_traces,
            }

        elif group_type == "OR":
            child_states: List[TruthState] = []
            short_circuited = False

            # Temporary missing tracking for OR branches:
            # If any branch in an OR evaluates to TRUE, missing fields from other branches must NOT be required!
            saved_missing = list(self.missing_fields)
            saved_names = set(self._missing_field_names)

            or_branch_missing: List[Tuple[MissingFieldInfo, str]] = []

            for child in group.children:
                if short_circuited:
                    self.conditions_short_circuited_count += 1
                    children_traces.append({
                        "node_id": child.node_id,
                        "result": "SKIPPED_SHORT_CIRCUIT",
                    })
                    continue

                pre_eval_count = len(self.missing_fields)
                c_state, c_trace = self._eval_node(child)
                child_states.append(c_state)
                children_traces.append(c_trace)

                if c_state == TruthState.TRUE:
                    short_circuited = True

            final_state = evaluate_or(child_states)

            # If OR evaluated to TRUE, discard missing fields collected in branches of this OR group
            if final_state == TruthState.TRUE:
                self.missing_fields = saved_missing
                self._missing_field_names = saved_names

            return final_state, {
                "node_id": group.node_id,
                "type": "OR",
                "result": final_state.value,
                "children": children_traces,
            }

        elif group_type == "NOT":
            if not group.children:
                return TruthState.UNKNOWN, {
                    "node_id": group.node_id,
                    "type": "NOT",
                    "result": TruthState.UNKNOWN.value,
                    "error": "Empty NOT group",
                }

            c_state, c_trace = self._eval_node(group.children[0])
            final_state = evaluate_not(c_state)
            return final_state, {
                "node_id": group.node_id,
                "type": "NOT",
                "result": final_state.value,
                "children": [c_trace],
            }

        else:
            return TruthState.UNKNOWN, {
                "node_id": group.node_id,
                "type": group_type,
                "result": TruthState.UNKNOWN.value,
                "error": f"Unsupported group type: {group_type}",
            }

    def _eval_condition(self, cond: ConditionNode) -> Tuple[TruthState, Dict[str, Any]]:
        self.conditions_evaluated_count += 1

        field_name = cond.field
        citizen_val = self.profile.get_value(field_name)

        # 1. Custom / Unsupported field handling
        if field_name.lower() in ("custom", "unsupported") or (
            cond.custom_field_name and not is_registered_field(cond.custom_field_name)
        ):
            res_item = ConditionEvaluationResult(
                condition_id=cond.node_id,
                field=cond.custom_field_name or field_name,
                result=TruthState.UNKNOWN,
                operator=cond.operator,
                required_value=cond.value,
                citizen_value=citizen_val,
                reason_code=ReasonCode.RULE_UNSUPPORTED,
                evidence_refs=cond.evidence_refs,
                message=f"Custom rule condition '{cond.custom_field_name or field_name}' requires manual review",
            )
            return TruthState.UNKNOWN, {
                "node_id": cond.node_id,
                "field": field_name,
                "result": TruthState.UNKNOWN.value,
                "reason_code": ReasonCode.RULE_UNSUPPORTED.value,
            }

        # 2. Missing citizen value check
        if citizen_val is None:
            # Special case: NOT_EXISTS operator is satisfied when citizen_val is None!
            if cond.operator in ("NOT_EXISTS",):
                state = evaluate_operator(cond.operator, citizen_val, cond.value)
                res_item = ConditionEvaluationResult(
                    condition_id=cond.node_id,
                    field=field_name,
                    result=state,
                    operator=cond.operator,
                    required_value=cond.value,
                    citizen_value=citizen_val,
                    reason_code=ReasonCode.CONDITION_SATISFIED if state == TruthState.TRUE else ReasonCode.CONDITION_NOT_SATISFIED,
                    evidence_refs=cond.evidence_refs,
                    message=f"Field '{field_name}' absence evaluated successfully",
                )
                if state == TruthState.TRUE:
                    self.passed_conditions.append(res_item)
                else:
                    self.failed_conditions.append(res_item)
                return state, {
                    "node_id": cond.node_id,
                    "field": field_name,
                    "result": state.value,
                    "operator": cond.operator,
                }

            # Otherwise, missing citizen value yields UNKNOWN and records missing field
            field_def = get_field_definition(field_name)
            missing_info = MissingFieldInfo(
                field=field_name,
                reason="VALUE_NOT_PROVIDED",
                condition_id=cond.node_id,
                display_name_en=field_def.display_name_en if field_def else field_name.replace("_", " ").title(),
                display_name_hi=field_def.display_name_hi if field_def else None,
            )
            if field_name not in self._missing_field_names:
                self._missing_field_names.add(field_name)
                self.missing_fields.append(missing_info)

            return TruthState.UNKNOWN, {
                "node_id": cond.node_id,
                "field": field_name,
                "result": TruthState.UNKNOWN.value,
                "reason_code": ReasonCode.VALUE_NOT_PROVIDED.value,
            }

        # 3. Evaluate operator
        state = evaluate_operator(cond.operator, citizen_val, cond.value)

        # 4. Record passed / failed results
        if state == TruthState.TRUE:
            res_item = ConditionEvaluationResult(
                condition_id=cond.node_id,
                field=field_name,
                result=TruthState.TRUE,
                operator=cond.operator,
                required_value=cond.value,
                citizen_value=citizen_val,
                reason_code=ReasonCode.CONDITION_SATISFIED,
                evidence_refs=cond.evidence_refs,
                message=f"Requirement met for {field_name}: provided {citizen_val} matches rule {cond.operator} {cond.value}",
            )
            self.passed_conditions.append(res_item)
        elif state == TruthState.FALSE:
            res_item = ConditionEvaluationResult(
                condition_id=cond.node_id,
                field=field_name,
                result=TruthState.FALSE,
                operator=cond.operator,
                required_value=cond.value,
                citizen_value=citizen_val,
                reason_code=ReasonCode.CONDITION_NOT_SATISFIED,
                evidence_refs=cond.evidence_refs,
                message=f"Requirement not met for {field_name}: provided {citizen_val} fails rule {cond.operator} {cond.value}",
            )
            self.failed_conditions.append(res_item)
        else:
            # UNKNOWN (e.g. type mismatch or unsupported value)
            res_item = ConditionEvaluationResult(
                condition_id=cond.node_id,
                field=field_name,
                result=TruthState.UNKNOWN,
                operator=cond.operator,
                required_value=cond.value,
                citizen_value=citizen_val,
                reason_code=ReasonCode.TYPE_MISMATCH,
                evidence_refs=cond.evidence_refs,
                message=f"Could not compare {field_name} value '{citizen_val}' with rule {cond.operator} {cond.value}",
            )

        return state, {
            "node_id": cond.node_id,
            "field": field_name,
            "result": state.value,
            "operator": cond.operator,
            "required_value": cond.value,
            "citizen_value": str(citizen_val),
            "reason_code": res_item.reason_code.value,
        }
