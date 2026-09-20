from typing import Any, Dict, List, Optional, Union

from app.normalization.schemas import (
    CanonicalSchemeDraft,
    EligibilityCondition,
    LogicalGroupType,
    RuleGroup,
)
from app.verification.schemas import FactRiskLevel, FactType, VerifiableFact


class CanonicalFactBuilder:
    """
    Deconstructs a CanonicalSchemeDraft (Pydantic model or parsed dictionary)
    into atomic verifiable claims.
    Assigns stable fact IDs, field paths, fact types, and risk levels.
    """

    @classmethod
    def build_facts(
        cls, draft: Union[CanonicalSchemeDraft, Dict[str, Any]]
    ) -> List[VerifiableFact]:
        facts: List[VerifiableFact] = []

        # Helper getters for dict or object
        def get_val(obj: Any, *keys: str, default: Any = None) -> Any:
            for k in keys:
                if isinstance(obj, dict):
                    if k in obj and obj[k] is not None:
                        return obj[k]
                elif hasattr(obj, k):
                    val = getattr(obj, k)
                    if val is not None:
                        return val
            return default

        internal_code = get_val(
            draft, "internal_scheme_code", "scheme_code", default="SCHEME"
        )
        short_id = str(internal_code)[-8:]
        fact_idx = 0

        def next_fact_id(prefix: str) -> str:
            nonlocal fact_idx
            fact_idx += 1
            return f"FACT-{short_id}-{prefix}-{fact_idx:03d}"

        # 1. Scheme Identity / Name
        ident = get_val(draft, "identity", "scheme_identity")
        if ident:
            name_raw = get_val(ident, "official_name_raw", "name_hindi", "name_english")
            if not name_raw:
                name_obj = get_val(ident, "name")
                if name_obj:
                    name_raw = get_val(name_obj, "raw", "hi", "en")

            ident_refs = get_val(ident, "evidence_refs", default=[])
            if name_raw:
                facts.append(
                    VerifiableFact(
                        fact_id=next_fact_id("IDENT"),
                        field_path="identity.official_name_raw",
                        fact_type=FactType.IDENTITY,
                        risk_level=FactRiskLevel.NORMAL,
                        statement=f"Official scheme name is '{name_raw}'.",
                        canonical_value={"name": name_raw},
                        evidence_refs=ident_refs or [],
                    )
                )

        # 2. Scope
        scope = get_val(draft, "scope")
        if scope:
            state = get_val(scope, "state")
            scope_refs = get_val(scope, "evidence_refs", default=[])
            if state:
                facts.append(
                    VerifiableFact(
                        fact_id=next_fact_id("SCOPE"),
                        field_path="scope.state",
                        fact_type=FactType.ELIGIBILITY,
                        risk_level=FactRiskLevel.HIGH,
                        statement=f"Scheme applies to state: {state}.",
                        canonical_value={"state": state},
                        evidence_refs=scope_refs or [],
                    )
                )

        # 3. Eligibility Conditions & Rule Tree Connectors
        eligibility = get_val(draft, "eligibility")
        if eligibility:
            root_rule = get_val(eligibility, "root_rule")
            if root_rule:
                def walk_rule_node(node: Any, path: str) -> None:
                    node_type = get_val(node, "type", "group_type")
                    if hasattr(node_type, "value"):
                        node_type = node_type.value
                    node_type_str = str(node_type).upper() if node_type else "AND"

                    children = get_val(node, "children", default=[])
                    node_refs = get_val(node, "evidence_refs", default=[])

                    # Add connector fact if multiple children
                    if len(children) >= 2 and node_type_str in ["AND", "OR"]:
                        all_child_refs = list(node_refs)
                        child_names = []
                        for c in children:
                            c_field = get_val(c, "field")
                            c_op = get_val(c, "operator")
                            if hasattr(c_op, "value"):
                                c_op = c_op.value
                            c_val = get_val(c, "value")
                            c_refs = get_val(c, "evidence_refs", default=[])
                            all_child_refs.extend(c_refs)
                            if c_field:
                                child_names.append(f"{c_field} {c_op or ''} {c_val or ''}")
                            else:
                                child_names.append("CHILD_GROUP")

                        facts.append(
                            VerifiableFact(
                                fact_id=next_fact_id("CONN"),
                                field_path=f"{path}.group_type",
                                fact_type=FactType.LOGICAL_CONNECTOR,
                                risk_level=FactRiskLevel.CRITICAL,
                                statement=f"Eligibility criteria [{', '.join(child_names)}] are joined by {node_type_str} logical relationship.",
                                canonical_value={
                                    "group_type": node_type_str,
                                    "connector_type": node_type_str,
                                    "children_count": len(children),
                                },
                                evidence_refs=list(dict.fromkeys(all_child_refs)),
                            )
                        )

                    for c_idx, child in enumerate(children):
                        child_path = f"{path}.children[{c_idx}]"
                        sub_children = get_val(child, "children")
                        if sub_children is not None:
                            walk_rule_node(child, child_path)
                        else:
                            # Atomic condition
                            c_field = get_val(child, "field", default="condition")
                            c_op = get_val(child, "operator", default="EQ")
                            if hasattr(c_op, "value"):
                                c_op = c_op.value
                            c_val = get_val(child, "value")
                            c_unit = get_val(child, "unit")
                            c_period = get_val(child, "periodicity", "period")
                            if hasattr(c_period, "value"):
                                c_period = c_period.value
                            c_refs = get_val(child, "evidence_refs", default=[])

                            is_critical = any(
                                k in str(c_field).lower()
                                for k in [
                                    "age",
                                    "income",
                                    "residency",
                                    "category",
                                    "caste",
                                    "gender",
                                    "disability",
                                ]
                            )
                            risk = (
                                FactRiskLevel.CRITICAL
                                if is_critical
                                else FactRiskLevel.HIGH
                            )

                            period_str = f" ({c_period})" if c_period else ""
                            unit_str = f" {c_unit}" if c_unit else ""
                            statement = f"Applicant {c_field} must satisfy: {c_op} {c_val}{unit_str}{period_str}."

                            canon_dict = (
                                child.model_dump()
                                if hasattr(child, "model_dump")
                                else dict(child)
                            )

                            facts.append(
                                VerifiableFact(
                                    fact_id=next_fact_id("ELIG"),
                                    field_path=child_path,
                                    fact_type=FactType.ELIGIBILITY,
                                    risk_level=risk,
                                    statement=statement,
                                    canonical_value=canon_dict,
                                    evidence_refs=c_refs or [],
                                )
                            )

                walk_rule_node(root_rule, "eligibility.root_rule")

            # Exclusions under eligibility
            exclusions = get_val(eligibility, "exclusions", default=[])
            for idx, excl in enumerate(exclusions):
                raw_txt = get_val(excl, "raw_text", "description", "condition", default="")
                if not raw_txt and isinstance(excl, str):
                    raw_txt = excl
                e_refs = get_val(excl, "evidence_refs", default=[]) if isinstance(excl, dict) or hasattr(excl, "evidence_refs") else []
                excl_dict = (
                    excl.model_dump()
                    if hasattr(excl, "model_dump")
                    else (dict(excl) if isinstance(excl, dict) else {"description": str(excl)})
                )
                facts.append(
                    VerifiableFact(
                        fact_id=next_fact_id("EXCL"),
                        field_path=f"eligibility.exclusions[{idx}]",
                        fact_type=FactType.EXCLUSION,
                        risk_level=FactRiskLevel.CRITICAL,
                        statement=f"Applicant is disqualified/excluded if: {raw_txt}.",
                        canonical_value=excl_dict,
                        evidence_refs=e_refs or [],
                    )
                )

        # Top-level exclusions (if present)
        top_exclusions = get_val(draft, "exclusions", default=[])
        if top_exclusions and not (eligibility and get_val(eligibility, "exclusions")):
            for idx, excl in enumerate(top_exclusions):
                raw_txt = get_val(excl, "raw_text", "description", "condition", default="")
                if not raw_txt and isinstance(excl, str):
                    raw_txt = excl
                e_refs = get_val(excl, "evidence_refs", default=[]) if isinstance(excl, dict) or hasattr(excl, "evidence_refs") else []
                excl_dict = (
                    excl.model_dump()
                    if hasattr(excl, "model_dump")
                    else (dict(excl) if isinstance(excl, dict) else {"description": str(excl)})
                )
                facts.append(
                    VerifiableFact(
                        fact_id=next_fact_id("EXCL"),
                        field_path=f"exclusions[{idx}]",
                        fact_type=FactType.EXCLUSION,
                        risk_level=FactRiskLevel.CRITICAL,
                        statement=f"Applicant is disqualified/excluded if: {raw_txt}.",
                        canonical_value=excl_dict,
                        evidence_refs=e_refs or [],
                    )
                )

        # 4. Benefits
        benefits = get_val(draft, "benefits", default=[])
        for idx, ben in enumerate(benefits):
            b_amount = get_val(ben, "amount")
            b_curr = get_val(ben, "currency", default="INR")
            b_freq = get_val(ben, "periodicity", "frequency")
            if hasattr(b_freq, "value"):
                b_freq = b_freq.value
            b_type = get_val(ben, "type", "benefit_type", default="CASH")
            if hasattr(b_type, "value"):
                b_type = b_type.value
            b_desc = get_val(ben, "description", "raw_text", default="")
            b_refs = get_val(ben, "evidence_refs", default=[])

            amount_str = f"{b_curr} {b_amount}" if b_amount is not None else "unstated amount"
            freq_str = f" ({b_freq})" if b_freq else ""
            statement = f"Entitlement benefit ({b_type}): {amount_str}{freq_str}. Description: {b_desc}."

            ben_dict = ben.model_dump() if hasattr(ben, "model_dump") else dict(ben)
            facts.append(
                VerifiableFact(
                    fact_id=next_fact_id("BEN"),
                    field_path=f"benefits[{idx}]",
                    fact_type=FactType.BENEFIT,
                    risk_level=FactRiskLevel.CRITICAL if b_amount is not None else FactRiskLevel.HIGH,
                    statement=statement,
                    canonical_value=ben_dict,
                    evidence_refs=b_refs or [],
                )
            )

        # 5. Required Documents
        docs = get_val(draft, "documents", "required_documents", default=[])
        for idx, doc in enumerate(docs):
            d_name = get_val(doc, "document_name", "name_raw", default="Document")
            d_type = get_val(doc, "document_type", default="IDENTITY")
            if hasattr(d_type, "value"):
                d_type = d_type.value
            d_mand = get_val(doc, "is_mandatory", "mandatory", default=False)
            d_refs = get_val(doc, "evidence_refs", default=[])

            mand_str = "mandatory" if d_mand else "optional/supporting"
            statement = f"Document requirement: '{d_name}' ({d_type}) is {mand_str}."

            doc_dict = doc.model_dump() if hasattr(doc, "model_dump") else dict(doc)
            facts.append(
                VerifiableFact(
                    fact_id=next_fact_id("DOC"),
                    field_path=f"documents[{idx}]",
                    fact_type=FactType.DOCUMENT,
                    risk_level=FactRiskLevel.CRITICAL if d_mand else FactRiskLevel.NORMAL,
                    statement=statement,
                    canonical_value=doc_dict,
                    evidence_refs=d_refs or [],
                )
            )

        # 6. Application Channels & Procedure
        app_sec = get_val(draft, "application")
        if app_sec:
            channels = get_val(app_sec, "channels", default=[])
            app_refs = get_val(app_sec, "evidence_refs", default=[])
            for idx, ch in enumerate(channels):
                ch_val = get_val(ch, "channel_type", default=ch)
                if hasattr(ch_val, "value"):
                    ch_val = ch_val.value
                ch_refs = get_val(ch, "evidence_refs", default=app_refs)
                facts.append(
                    VerifiableFact(
                        fact_id=next_fact_id("APP"),
                        field_path=f"application.channels[{idx}]",
                        fact_type=FactType.APPLICATION,
                        risk_level=FactRiskLevel.NORMAL,
                        statement=f"Application can be submitted through channel: {ch_val}.",
                        canonical_value={"channel": str(ch_val)},
                        evidence_refs=ch_refs or [],
                    )
                )

            portal_url = get_val(app_sec, "portal_url")
            if portal_url:
                facts.append(
                    VerifiableFact(
                        fact_id=next_fact_id("APP"),
                        field_path="application.portal_url",
                        fact_type=FactType.APPLICATION,
                        risk_level=FactRiskLevel.NORMAL,
                        statement=f"Official online submission portal URL is: {portal_url}.",
                        canonical_value={"portal_url": portal_url},
                        evidence_refs=app_refs or [],
                    )
                )

        # 7. Important Dates
        dates = get_val(draft, "important_dates", "dates", default=[])
        for idx, dt in enumerate(dates):
            date_val = get_val(dt, "normalized_date", "date", "raw_date_text")
            ev_name = get_val(dt, "event_name", default="Event")
            dt_type = get_val(dt, "date_type", default="DEADLINE")
            dt_refs = get_val(dt, "evidence_refs", default=[])

            statement = f"Important date for '{ev_name}': {date_val} (Type: {dt_type})."
            dt_dict = dt.model_dump() if hasattr(dt, "model_dump") else dict(dt)

            facts.append(
                VerifiableFact(
                    fact_id=next_fact_id("DATE"),
                    field_path=f"important_dates[{idx}]",
                    fact_type=FactType.DATE,
                    risk_level=FactRiskLevel.HIGH,
                    statement=statement,
                    canonical_value=dt_dict,
                    evidence_refs=dt_refs or [],
                )
            )

        # 8. Statutory Definitions
        definitions = get_val(draft, "definitions", default=[])
        for idx, dfn in enumerate(definitions):
            term = get_val(dfn, "term", default="Term")
            dfn_text = get_val(dfn, "definition", default="")
            dfn_refs = get_val(dfn, "evidence_refs", default=[])
            dfn_dict = dfn.model_dump() if hasattr(dfn, "model_dump") else dict(dfn)

            facts.append(
                VerifiableFact(
                    fact_id=next_fact_id("DEF"),
                    field_path=f"definitions[{idx}]",
                    fact_type=FactType.DEFINITION,
                    risk_level=FactRiskLevel.NORMAL,
                    statement=f"Statutory definition for '{term}': {dfn_text}.",
                    canonical_value=dfn_dict,
                    evidence_refs=dfn_refs or [],
                )
            )

        return facts
