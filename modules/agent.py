"""
QueryAgent: Conversational database query interface with intent parsing.

Features:
- Natural language intent parsing via regex patterns
- Smart differentiation: "list suites" (distinct names) vs "show suites" (full details)
- Safe database operations with proper error handling
- Optional LLM support (graceful degradation if not available)
"""

import re
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

try:
    import streamlit as st
except Exception:
    st = None

# Optional LLM support
try:
    from openai import OpenAI
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False

from modules.database_engine import DatabaseEngine


@dataclass
class AgentResponse:
    """Standard response format from agent."""
    success: bool
    action: str
    message: str
    data: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _log_info(msg: str) -> None:
    """Log info message to Streamlit if available, else print."""
    if st is not None:
        try:
            st.info(msg)
            return
        except Exception:
            pass
    print(f"INFO: {msg}")


class QueryAgent:
    """Conversational agent for suite/TP queries."""

    def __init__(self, db_engine: DatabaseEngine):
        self.db = db_engine
        self.conversation_history: List[Dict[str, Any]] = []
        self.llm_client = None
        self.use_llm = False
        
        # Try to initialize LLM (optional)
        if HAS_OPENAI:
            try:
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.llm_client = OpenAI(api_key=api_key)
                    self.use_llm = True
                    _log_info("✅ LLM enabled (OpenAI)")
            except Exception as e:
                _log_info(f"⚠️ LLM disabled: {str(e)[:50]}")

    def log_interaction(self, user_input: str, action: str, success: bool) -> None:
        """Log user interaction for debugging."""
        self.conversation_history.append({
            "user": user_input,
            "action": action,
            "success": success,
        })

    def _extract_query_filters(self, prompt: str) -> Dict[str, Any]:
        """Extract suite query filters (suite name, active/inactive, owner)."""
        prompt_lower = prompt.lower().strip()
        params: Dict[str, Any] = {}

        def _clean_suite_names(items: List[str]) -> List[str]:
            cleaned: List[str] = []
            blocked = {"name", "names", "suite", "s", "given", "the"}
            for item in items:
                candidate = item.strip(" '\"")
                if not candidate:
                    continue
                if candidate in blocked:
                    continue
                if candidate.startswith("given suite"):
                    continue
                cleaned.append(candidate)
            return cleaned

        # Support explicit "suite name <value>" / "suite names <a,b>" phrases.
        suite_name_match = re.search(
            r"\bsuite\s*name[s]?\s*(?::|=|is)?\s*([a-z0-9_\-,\s]+?)(?:\s+(?:and|for|with|where|owner|active|inactive|script|scripts|modified|modification|after|before|between|since|on|then)\b|$)",
            prompt_lower,
            re.IGNORECASE,
        )
        if suite_name_match:
            suite_str = suite_name_match.group(1).strip(" '\"")
            suite_names = _clean_suite_names([s.strip() for s in re.split(r"\s*,\s*", suite_str) if s.strip()])
            if suite_names:
                params["suite_names"] = suite_names

        suite_match = re.search(
            r"(?:suite[s]?\s*(?:(?:named?|for|=|:)\s*)?(?:the\s+)?)([a-z0-9_\-,\s]+?)(?:\s+(?:and|for|with|where|owner|active|inactive|script|scripts|modified|modification|after|before|between|since|on|then)\b|$)",
            prompt_lower,
            re.IGNORECASE,
        )
        if "suite_names" not in params and suite_match:
            suite_str = suite_match.group(1).strip(" '\"")
            suite_names = _clean_suite_names([s.strip() for s in re.split(r"\s*,\s*", suite_str) if s.strip()])
            if suite_names:
                params["suite_names"] = suite_names
        elif "suite_names" not in params:
            # Also support phrases like: "active scripts for the TPREGGOLD"
            generic_for_match = re.search(
                r"\bfor\s+(?:the\s+)?([a-z0-9_\-,\s]+?)(?:\s+(?:and|with|where|owner|active|inactive|script|scripts|modified|modification|after|before|between|since|on|then)\b|$)",
                prompt_lower,
                re.IGNORECASE,
            )
            if generic_for_match:
                suite_str = generic_for_match.group(1).strip(" '\"")
                suite_names = _clean_suite_names([s.strip() for s in re.split(r"\s*,\s*", suite_str) if s.strip()])
                if suite_names:
                    params["suite_names"] = suite_names

        has_active = bool(re.search(r"\bactive\b", prompt_lower))
        has_inactive = bool(re.search(r"\binactive\b|\bnot\s+active\b", prompt_lower))
        if has_active and has_inactive:
            params["active_states"] = ["yes", "no"]
        elif has_inactive:
            params["active_states"] = ["no"]
        elif has_active:
            params["active_states"] = ["yes"]

        owner_match = re.search(
            r"owner\s*(?:is|=|:)\s*([a-z0-9@._\-\s,\/]+)",
            prompt_lower,
            re.IGNORECASE,
        )
        if owner_match:
            owner_segment = owner_match.group(1).strip()
            owner_segment = re.split(
                r"\b(?:then|for|in|with|where|modified|modification|after|before|between|since|on)\b",
                owner_segment,
                maxsplit=1
            )[0].strip()
            owner_values = [o.strip() for o in re.split(r"\s+or\s+|,|/", owner_segment) if o.strip()]
            owner_values = [o for o in owner_values if o not in {"and", "the"}]
            if owner_values:
                params["owners"] = owner_values

        def _norm_date(raw: str) -> Optional[str]:
            try:
                datetime.strptime(raw, "%Y-%m-%d")
                return raw
            except Exception:
                return None

        between_match = re.search(
            r"\b(?:modified|modification(?:\s+date)?)\s+(?:between|from)\s+(\d{4}-\d{2}-\d{2})\s+(?:and|to)\s+(\d{4}-\d{2}-\d{2})",
            prompt_lower,
            re.IGNORECASE,
        )
        if between_match:
            d1 = _norm_date(between_match.group(1))
            d2 = _norm_date(between_match.group(2))
            if d1 and d2:
                if d1 <= d2:
                    params["modified_between"] = [d1, d2]
                else:
                    params["modified_between"] = [d2, d1]

        on_match = re.search(
            r"\b(?:modified|modification(?:\s+date)?)\s+on\s+(\d{4}-\d{2}-\d{2})",
            prompt_lower,
            re.IGNORECASE,
        )
        if on_match:
            d = _norm_date(on_match.group(1))
            if d:
                params["modified_on"] = d

        after_match = re.search(
            r"\b(?:modified|modification(?:\s+date)?)\s+(?:after|since|from)\s+(\d{4}-\d{2}-\d{2})",
            prompt_lower,
            re.IGNORECASE,
        )
        if after_match:
            d = _norm_date(after_match.group(1))
            if d:
                params["modified_after"] = d

        before_match = re.search(
            r"\b(?:modified|modification(?:\s+date)?)\s+(?:before|until|till|upto|up to)\s+(\d{4}-\d{2}-\d{2})",
            prompt_lower,
            re.IGNORECASE,
        )
        if before_match:
            d = _norm_date(before_match.group(1))
            if d:
                params["modified_before"] = d

        return params

    def parse_intent(self, prompt: str) -> Tuple[str, Dict[str, Any]]:
        """Parse user prompt to extract intent and parameters."""
        prompt_lower = prompt.lower().strip()
        params = self._extract_query_filters(prompt)

        # INTENT: List suite NAMES ONLY (distinct)
        if any(kw in prompt_lower for kw in ["show suite name", "show suite names"]):
            return "list_suites", {}

        # INTENT: Show ALL suite DETAILS
        if any(kw in prompt_lower for kw in ["show suite", "get suite", "display suite"]):
            # Check if they specified suite names to filter
            suite_match = re.search(
                r"(?:for|named?|=|:)\s*['\"]?([^'\"]+?)['\"]?(?:\s+and|\s*,|\s*or|$)",
                prompt_lower,
                re.IGNORECASE
            )
            if suite_match:
                suite_str = suite_match.group(1)
                params["suite_names"] = [s.strip() for s in re.split(r",\s*(?:and\s+)?", suite_str) if s.strip()]
                return "query_suites", params
            # No filter specified → show all details
            return "show_suites", params

        # INTENT: Query with specific suite filters
        if any(kw in prompt_lower for kw in ["query suite", "find suite", "search suite"]):
            suite_match = re.search(r"suite[s]?\s+(?:named?|for|=)?\s*['\"]?([^'\"]+)['\"]?", prompt_lower)
            if suite_match:
                params["suite_names"] = [s.strip() for s in suite_match.group(1).split(",")]
            return "query_suites", params

        if "script" in prompt_lower and "suite" in prompt_lower and any(
            kw in prompt_lower for kw in ["active", "inactive", "owner", "show", "only", "modified", "modification", "date"]
        ):
            return "query_suites", params
        
        if "script" in prompt_lower and any(kw in prompt_lower for kw in ["show", "list", "get", "find", "search", "active", "inactive", "modified", "modification", "date"]):
            return "query_suites", params

        # Safety net: if we already extracted meaningful filters and user is asking to view data,
        # route to suite query instead of falling back to unknown.
        has_filters = bool(
            params.get("suite_names")
            or params.get("owners")
            or params.get("active_states")
            or params.get("modified_after")
            or params.get("modified_before")
            or params.get("modified_on")
            or params.get("modified_between")
        )
        has_query_verb = any(kw in prompt_lower for kw in ["show", "list", "get", "find", "search", "fetch", "retrieve"])
        if has_filters and has_query_verb:
            return "query_suites", params

        # INTENT: List suite NAMES ONLY (distinct) - strict to avoid collisions
        list_only_pattern = re.compile(
            r"^\s*(?:list\s+(?:all\s+)?suites?|list\s+suite\s+names?|show\s+suite\s+names?|suite\s+names?|how\s+many\s+suites?|count(?:\s+of)?\s+suites?)\s*[?.!]?\s*$",
            re.IGNORECASE,
        )
        if list_only_pattern.match(prompt_lower):
            return "list_suites", params

        # INTENT: Fetch TP release data
        if "tp7" in prompt_lower or "tp 7" in prompt_lower:
            return "fetch_tp7_data", params
        if "mainline" in prompt_lower or "main line" in prompt_lower:
            return "fetch_mainline_data", params

        # INTENT: Diagnostics
        if any(kw in prompt_lower for kw in ["diagnos", "test", "check", "connect", "health"]):
            return "diagnostics", params

        # INTENT: Help
        if any(kw in prompt_lower for kw in ["help", "what can", "examples", "support"]):
            return "help", params

        # ===== FLEXIBLE/FALLBACK LOGIC =====
        # If just "suite" or "suites" alone → list suites
        if prompt_lower in ["suite", "suites", "suite?", "suites?"]:
            return "list_suites", params
        
        # If only "count" or "how many" → list suites with count
        if any(kw in prompt_lower for kw in ["count", "how many", "total suite"]):
            return "list_suites", params
        
        # If looks like a suite name (no keywords, just text) → query that suite
        # This catches: "tpreggold", "mysuite", "tp7release", etc.
        if len(prompt_lower) > 2 and not any(kw in prompt_lower for kw in ["?", "help", "what", "why", "how", "show", "list", "get", "display", "query", "search", "diagnos"]):
            # Looks like a suite name - query it
            params["suite_names"] = [prompt.strip()]  # Keep original case
            return "query_suites", params

        return "unknown", params

    def execute_intent(self, intent: str, params: Dict[str, Any]) -> AgentResponse:
        """Execute the identified intent; establishes DB connection only here."""
        try:
            if intent == "list_suites":
                return self._list_suites()
            elif intent == "show_suites":
                return self._show_suites(params)
            elif intent == "query_suites":
                return self._query_suites(params)
            elif intent == "fetch_tp7_data":
                return self._fetch_tp_data("7.0", params)
            elif intent == "fetch_mainline_data":
                return self._fetch_tp_data("mainline", params)
            elif intent == "diagnostics":
                return self._run_diagnostics()
            elif intent == "help":
                return self._show_help()
            else:
                return AgentResponse(
                    success=False,
                    action="unknown",
                    message="💡 Try one of these:\n- 'list suites' → See all suite names\n- 'show suites' → See all details\n- 'tpreggold' → See records for that specific suite\n- 'help' → Show all options",
                )
        except Exception as e:
            return AgentResponse(
                success=False,
                action=intent,
                message=f"Error executing {intent}.",
                error=str(e),
            )

    def _list_suites(self) -> AgentResponse:
        """Fetch and return list of DISTINCT suite names only."""
        try:
            rows = self.db.query(
                "SELECT DISTINCT suite_name FROM test_transaction_ids_view ORDER BY suite_name;"
            )
            suite_names = [
                r.get("suite_name") if isinstance(r, dict) else r[0] 
                for r in (rows or [])
            ]
            suite_names = [s for s in suite_names if s]
            
            return AgentResponse(
                success=True,
                action="list_suites",
                message=f"Found {len(suite_names)} unique suite names.",
                data=[{"suite_name": s} for s in suite_names],
                metadata={"count": len(suite_names), "type": "distinct_names_only"},
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                action="list_suites",
                message="Failed to list suites.",
                error=str(e),
            )

    def _show_suites(self, params: Dict[str, Any]) -> AgentResponse:
        """Show metadata about suites and suggest next steps."""
        try:
            # Get total count of suites
            count_result = self.db.query(
                "SELECT COUNT(DISTINCT suite_name) as total FROM test_transaction_ids_view;"
            )
            total_suites = count_result[0].get("total", 0) if count_result else 0
            
            # Get sample of first 5 suite names for suggestion
            sample_result = self.db.query(
                "SELECT DISTINCT suite_name FROM test_transaction_ids_view ORDER BY suite_name LIMIT 5;"
            )
            sample_names = [r.get("suite_name") if isinstance(r, dict) else r[0] for r in (sample_result or [])]
            sample_names = [s for s in sample_names if s]
            
            # Build helpful message
            sample_str = ", ".join([f"'{s}'" for s in sample_names])
            first_sample = sample_names[0] if sample_names else "mysuite"
            message = f"""📊 **Suite Overview**

We have **{total_suites:,} total suites** in the database.

**Sample suite names:** {sample_str}...

💡 **Next step:** Type a suite name to see its details!
   Example: 'tpreggold' or '{first_sample}'"""
            
            return AgentResponse(
                success=True,
                action="show_suites",
                message=message,
                data=[],  # Don't return all records - just metadata
                metadata={
                    "total_suites": total_suites,
                    "sample_names": sample_names,
                    "type": "metadata_only",
                },
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                action="show_suites",
                message="Failed to retrieve suite information.",
                error=str(e),
            )

    def _query_suites(self, params: Dict[str, Any]) -> AgentResponse:
        """Query suites with optional filters (specific suite names)."""
        try:
            suite_names = params.get("suite_names", [])
            active_states = params.get("active_states", [])
            owners = params.get("owners", [])
            modified_after = params.get("modified_after")
            modified_before = params.get("modified_before")
            modified_on = params.get("modified_on")
            modified_between = params.get("modified_between")

            cols = [
                "suite_name", "script_name", "area_name", "sub_area_name",
                "platform_name", "repo_name", "creation_date", "modification_date",
                "active", "remarks", "owner",
            ]
            sql = f"SELECT {', '.join(cols)} FROM test_transaction_ids_view WHERE 1=1"
            query_params = []

            if suite_names:
                placeholders = ", ".join(["%s"] * len(suite_names))
                sql += f" AND suite_name IN ({placeholders})"
                query_params.extend(suite_names)
            if active_states:
                active_yes_clause = "LOWER(CAST(active AS CHAR)) IN ('1', 'true', 'yes', 'y')"
                active_no_clause = "LOWER(CAST(active AS CHAR)) IN ('0', 'false', 'no', 'n')"
                if "yes" in active_states and "no" in active_states:
                    sql += f" AND ({active_yes_clause} OR {active_no_clause})"
                elif "yes" in active_states:
                    sql += f" AND {active_yes_clause}"
                elif "no" in active_states:
                    sql += f" AND {active_no_clause}"
            if owners:
                owner_clauses = []
                for owner in owners:
                    owner_clauses.append("LOWER(CAST(owner AS CHAR)) LIKE %s")
                    # Partial, case-insensitive owner match (e.g., "tulasi" matches "tulasi@company.com")
                    query_params.append(f"%{owner.lower().strip()}%")
                sql += f" AND ({' OR '.join(owner_clauses)})"
            if modified_between and isinstance(modified_between, list) and len(modified_between) == 2:
                sql += " AND DATE(modification_date) BETWEEN %s AND %s"
                query_params.extend(modified_between)
            else:
                if modified_after:
                    sql += " AND DATE(modification_date) >= %s"
                    query_params.append(modified_after)
                if modified_before:
                    sql += " AND DATE(modification_date) <= %s"
                    query_params.append(modified_before)
            if modified_on:
                sql += " AND DATE(modification_date) = %s"
                query_params.append(modified_on)

            sql += " LIMIT 100000;"

            rows = self.db.query(sql, params=tuple(query_params) if query_params else None)
            row_count = len(rows or [])
            if owners and row_count == 0:
                owner_text = ", ".join(owners)
                message = f"No records exist for owner(s): {owner_text}."
            else:
                message = f"Found {row_count} suite records."

            return AgentResponse(
                success=True,
                action="query_suites",
                message=message,
                data=rows or [],
                metadata={
                    "count": row_count,
                    "filters": {
                        "suite_names": suite_names or "any",
                        "active_states": active_states or "any",
                        "owners": owners or "any",
                        "modified_after": modified_after or "any",
                        "modified_before": modified_before or "any",
                        "modified_on": modified_on or "any",
                        "modified_between": modified_between or "any",
                    },
                },
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                action="query_suites",
                message="Failed to query suites.",
                error=str(e),
            )

    def _fetch_tp_data(self, release: str, params: Dict[str, Any]) -> AgentResponse:
        """Fetch TP7.0 or Mainline data (placeholder)."""
        return AgentResponse(
            success=True,
            action=f"fetch_{release.lower()}_data",
            message=f"Placeholder: TP {release} data would appear here. Customize with your actual TP tables.",
            data=[],
            metadata={"release": release},
        )

    def _run_diagnostics(self) -> AgentResponse:
        """Run basic connectivity diagnostics."""
        import socket
        
        try:
            host = self.db.host
            port = getattr(self.db, "port", 3306)
            
            # Test TCP connectivity
            try:
                with socket.create_connection((host, int(port)), timeout=5.0):
                    tcp_ok = True
                    tcp_msg = f"✅ TCP connect to {host}:{port} succeeded."
            except Exception as tcp_err:
                tcp_ok = False
                tcp_msg = f"❌ TCP connect failed: {tcp_err}"

            # Test database query
            db_ok = False
            db_msg = ""
            try:
                rows = self.db.query("SELECT VERSION() AS ver;")
                if rows:
                    db_ok = True
                    db_msg = f"✅ DB connected. MySQL version: {rows[0]}"
            except Exception as db_err:
                db_msg = f"❌ DB query failed: {db_err}"

            return AgentResponse(
                success=tcp_ok and db_ok,
                action="diagnostics",
                message="Diagnostics complete.",
                metadata={
                    "tcp_reachable": tcp_ok,
                    "tcp_message": tcp_msg,
                    "db_reachable": db_ok,
                    "db_message": db_msg,
                    "llm_enabled": self.use_llm,
                },
            )
        except Exception as e:
            return AgentResponse(
                success=False,
                action="diagnostics",
                message="Diagnostics error.",
                error=str(e),
            )

    def _show_help(self) -> AgentResponse:
        """Show available commands and examples."""
        help_text = """
**🤖 TestOps Chat Agent - Command Guide**

**📋 LIST SUITE NAMES (Distinct Only)**
- "list suites"
- "show suite names"
- "suite names"
- "how many suites"
- Just: "suite" or "suites"

**📊 SHOW ALL SUITE DETAILS**
- "show suites"
- "get all suites"
- "display suites"

**🔍 QUERY SPECIFIC SUITES (Just type the name!)**
- "show suites for tpreggold"
- "get details for Suite1, Suite2"
- Just: "tpreggold" → Shows all records for that suite
- Just: "mysuite" → Shows all records for that suite

**🚀 RELEASE DATA**
- "show TP7.0 data" or "view TP7"
- "show mainline builds"

**🔌 DIAGNOSTICS**
- "check database" or "test connectivity"
- "health check"

**💡 QUICK EXAMPLES**
- "list suites" → Lists all ~7,380 distinct suite names
- "show suites" → Shows first 1,000 suite records with full details
- "tpreggold" → Shows all records for tpreggold suite
- "count" → Shows total number of unique suites
- "help" → Shows this help message
"""
        return AgentResponse(
            success=True,
            action="help",
            message=help_text,
        )

    def respond(self, user_prompt: str) -> AgentResponse:
        """Main entry point: parse prompt and return response."""
        intent, params = self.parse_intent(user_prompt)
        response = self.execute_intent(intent, params)
        self.log_interaction(user_prompt, intent, response.success)
        return response


