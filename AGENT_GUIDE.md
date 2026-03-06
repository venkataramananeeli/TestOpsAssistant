# TestOps Custom Agent Guide

## Overview

The **TestOps Custom Agent** is a conversational interface that lets users interact with test suite data using natural language prompts. Instead of navigating menus and forms, users can simply ask questions like **"show me suites for MySuite"** and get instant results.

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────┐
│                   app.py (Streamlit UI)             │
│  - Chat interface, conversation history, buttons    │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│            modules/agent.py (QueryAgent)            │
│  - Intent parsing (NLP-lite pattern matching)       │
│  - Action execution (query, list, diagnostics)      │
│  - Structured responses (AgentResponse dataclass)   │
└─────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────┐
│        modules/database_engine.py (DatabaseEngine)  │
│  - MySQL connection management                      │
│  - Safe cursor handling with transient fallback     │
│  - Query/execute methods                           │
└─────────────────────────────────────────────────────┘
                          ↓
                    MySQL Database
```

---

## How It Works

### 1. User Submits a Prompt

```
User: "show me suites for SuiteA and SuiteB"
```

### 2. Agent Parses Intent

The `QueryAgent.parse_intent()` method uses regex patterns to identify:
- **Intent**: e.g., `"query_suites"`
- **Parameters**: e.g., `{"suite_names": ["SuiteA", "SuiteB"]}`

```python
intent, params = agent.parse_intent(prompt)
# intent = "query_suites"
# params = {"suite_names": ["SuiteA", "SuiteB"]}
```

### 3. Agent Executes Intent

Based on the intent, the agent runs the corresponding SQL query:

```python
response = agent.execute_intent(intent, params)
```

This **opens a database connection, executes the query, and closes the connection** — no persistent connection is held.

### 4. Agent Returns Structured Response

```python
@dataclass
class AgentResponse:
    success: bool                              # True/False
    action: str                                # "query_suites", "list_suites", etc.
    message: str                               # Human-readable message
    data: Optional[List[Dict[str, Any]]]   # Rows (for tables)
    metadata: Optional[Dict[str, Any]]     # Filters, counts, etc.
    error: Optional[str]                      # Error trace (if failed)
```

### 5. UI Displays Results

The Streamlit app renders the response as:
- Status badge (✅ success or ❌ failure)
- Message
- Metadata (filters, row count)
- Table of results
- CSV download button

---

## Supported Intents

### 1. `list_suites`

**User Prompts:**
- "list suites"
- "show suite names"
- "available suites"

**What It Does:**
Fetches distinct `suite_name` values from the database.

**Example Response:**
```
✅ Found 15 suites.

Results (15 rows):
| suite_name   |
| ------------ |
| SuiteA       |
| SuiteB       |
| ...          |
```

---

### 2. `query_suites`

**User Prompts:**
- "show suites for SuiteA"
- "query suite named 'SuiteB'"
- "show suites for SuiteA, SuiteB, SuiteC"
- "show active suites"

**What It Does:**
Fetches suite details (script_name, area, platform, owner, etc.) with optional filters.

**Extracted Parameters:**
- `suite_names`: List of suite names to filter by
- `active_only`: Whether to show only active suites

**Example Response:**
```
✅ Found 42 suite records.

Results (42 rows):
| suite_name | script_name | area_name | active |
| --------- | --------- | --------- | ------ |
| SuiteA    | script1   | area1     | Yes    |
| ...       | ...       | ...       | ...    |
```

---

### 3. `fetch_tp7_data`

**User Prompts:**
- "show TP7.0 data"
- "view TP 7"
- "TP7 builds"

**What It Does:**
Fetches TP 7.0 release data (currently a placeholder; wire up your actual table as needed).

---

### 4. `fetch_mainline_data`

**User Prompts:**
- "show mainline data"
- "mainline builds"
- "view mainline"

**What It Does:**
Fetches Mainline release data (placeholder).

---

### 5. `diagnostics`

**User Prompts:**
- "test database"
- "check connectivity"
- "diagnose connection"

**What It Does:**
1. Tries TCP connection to MySQL host:port
2. Executes `SELECT VERSION()` query
3. Reports both results

**Example Response:**
```
✅ Diagnostics complete.

Metadata:
{
  "tcp_reachable": true,
  "tcp_message": "TCP connect to 172.21.18.50:3306 succeeded.",
  "db_reachable": true,
  "db_message": "DB connected. MySQL version: 8.0.32"
}
```

---

### 6. `help`

**User Prompts:**
- "help"
- "what can you do?"
- "examples"

**What It Does:**
Shows all supported commands and example prompts.

---

## Configuration

### Environment Variables

Set these before running the app:

```bash
# MySQL Connection
export MYSQL_HOST=172.21.18.50
export MYSQL_PORT=3306
export MYSQL_USER=your_db_user
export MYSQL_PASS=your_db_password
export MYSQL_DB=your_database_name
```

### Streamlit Secrets (Alternative)

Create `.streamlit/secrets.toml`:

```toml
[mysql]
host = "172.21.18.50"
port = 3306
user = "your_db_user"
password = "your_db_password"
database = "your_database_name"
```

---

## Running the App

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Ensure `requirements.txt` includes:
```
streamlit==1.31.0
pandas>=2.1.0
mysql-connector-python==8.2.0
```

### 2. Set Credentials

```bash
export MYSQL_USER=your_user
export MYSQL_PASS=your_password
export MYSQL_DB=your_database
```

### 3. Run Streamlit

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8080`.

---

## Usage Examples

### Example 1: List All Suites

**User:** "list suites"

**Agent Parses:**
- Intent: `list_suites`
- Params: `{}`

**Agent Executes:**
```sql
SELECT DISTINCT suite_name FROM test_transaction_ids_view ORDER BY suite_name;
```

**User Sees:** Table of all suite names, CSV download.

---

### Example 2: Get Details for Specific Suites

**User:** "show suites for SuiteA and SuiteB"

**Agent Parses:**
- Intent: `query_suites`
- Params: `{"suite_names": ["SuiteA", "SuiteB"]}`

**Agent Executes:**
```sql
SELECT suite_name, script_name, area_name, ...
FROM test_transaction_ids_view
WHERE suite_name IN ('SuiteA', 'SuiteB');
```

**User Sees:** Detailed table, CSV download.

---

### Example 3: Filter by Active Status

**User:** "show active suites for SuiteA"

**Agent Parses:**
- Intent: `query_suites`
- Params: `{"suite_names": ["SuiteA"], "active_only": True}`

**Agent Executes:**
```sql
SELECT ...
FROM test_transaction_ids_view
WHERE suite_name IN ('SuiteA')
  AND active IN ('1', 'true', 'yes', 1);
```

---

### Example 4: Diagnostics

**User:** "test database"

**Agent Parses:**
- Intent: `diagnostics`
- Params: `{}`

**Agent Executes:**
1. TCP connection to `MYSQL_HOST:MYSQL_PORT`
2. `SELECT VERSION()`

**User Sees:** Connection status, MySQL version.

---

## Extending the Agent

### Add a New Intent

To support a new command, follow these steps:

#### 1. Update `parse_intent()`

Add pattern matching in `modules/agent.py`:

```python
def parse_intent(self, prompt: str) -> Tuple[str, Dict[str, Any]]:
    # ... existing code ...
    
    # NEW: Sales metrics
    if "sales" in prompt_lower or "revenue" in prompt_lower:
        params["report_type"] = "sales"
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", prompt_lower)
        if date_match:
            params["date"] = date_match.group(1)
        return "sales_report", params
    
    # ... rest of code ...
```

#### 2. Add an Execute Method

```python
def _sales_report(self, params: Dict[str, Any]) -> AgentResponse:
    """Fetch sales metrics."""
    try:
        sql = "SELECT ... FROM sales_table"
        query_params = []
        
        if "date" in params:
            sql += " WHERE date >= %s"
            query_params.append(params["date"])
        
        rows = self.db.query(sql, params=tuple(query_params) if query_params else None)
        
        return AgentResponse(
            success=True,
            action="sales_report",
            message=f"Found {len(rows)} records.",
            data=rows,
            metadata={"date_filter": params.get("date", "all time")},
        )
    except Exception as e:
        return AgentResponse(
            success=False,
            action="sales_report",
            message="Failed to fetch sales data.",
            error=str(e),
        )
```

#### 3. Update `execute_intent()`

```python
def execute_intent(self, intent: str, params: Dict[str, Any]) -> AgentResponse:
    try:
        if intent == "list_suites":
            return self._list_suites()
        # ... existing intents ...
        elif intent == "sales_report":  # NEW
            return self._sales_report(params)
        # ... rest ...
```

---

## Testing

### Quick Manual Test

```bash
# In Python REPL
from modules.database_engine import DatabaseEngine
from modules.agent import QueryAgent

db = DatabaseEngine("localhost", "user", "pass", "database")
agent = QueryAgent(db)

# Test a simple prompt
response = agent.respond("list suites")
print(response.message)
print(f"Data rows: {len(response.data or [])}")
```

### Streamlit Test

1. Run the app: `streamlit run app.py`
2. Click **"List all suites"** button
3. Check that results appear

---

## Troubleshooting

### Error: "MySQL credentials not configured"

**Solution:** Set environment variables:
```bash
export MYSQL_USER=your_user
export MYSQL_PASS=your_password
export MYSQL_DB=your_database
```

Or create `.streamlit/secrets.toml` with `[mysql]` section.

---

### Error: "Failed to create cursor from connection"

**Solution:** This is handled by the `DatabaseEngine` transient fallback. Check:
1. MySQL host/port are reachable (run diagnostics: "test database")
2. Credentials are correct
3. Database exists

---

### Error: "Unknown intent"

**Solution:** Rephrase your question. Examples:
- ✅ "show suites for SuiteA"
- ❌ "what's SuiteA?"  ← Too vague

Check the Help expandable at the bottom of the app for supported commands.

---

## Best Practices

1. **Credentials:** Use environment variables, not hardcoded secrets.
2. **Connection Reuse:** The agent opens a connection per query and closes immediately. No pooling overhead.
3. **Filtering:** Use natural phrases like "for SuiteA, SuiteB, SuiteC" or "active only".
4. **Diagnostics:** Run "test database" before reporting connection issues.
5. **Logs:** Check `st.session_state.agent.conversation_history` for debugging.

---

## Summary

The **CustomAgent** provides a user-friendly, conversational way to query test data. Built on:
- **Pattern-based NLP** (regex for intent parsing)
- **Safe database handling** (temporary connections, transient fallback)
- **Streamlit UI** (chat history, buttons, downloads)
- **Modular design** (easy to extend with new intents)

For questions or enhancements, refer to `modules/agent.py` and the examples above.
