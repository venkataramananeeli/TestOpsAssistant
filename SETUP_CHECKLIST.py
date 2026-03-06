"""
NEXT STEPS CHECKLIST - TestOps Custom Agent Setup
==================================================

Follow these steps to get your agent up and running.
"""

# ========================================
# STEP 1: VERIFY PYTHON & DEPENDENCIES
# ========================================
# Run in PowerShell:

# 1a. Check Python version (should be 3.9+)
python --version

# 1b. Verify venv is active (Windows). If not:
.\.venv\Scripts\Activate.ps1
# or
venv\Scripts\Activate.ps1

# 1c. Install/update requirements
pip install -r requirements.txt

# Expected output:
# Successfully installed streamlit pandas mysql-connector-python python-dotenv ...


# ========================================
# STEP 2: CONFIGURE MYSQL CREDENTIALS
# ========================================

# Option A: Environment Variables (Recommended)
# Set these in PowerShell:
$env:MYSQL_HOST = "172.21.18.50"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "your_db_username"
$env:MYSQL_PASS = "your_db_password"
$env:MYSQL_DB = "your_database_name"

# Then verify they're set:
Get-Item Env:MYSQL_* | Format-Table Name,Value

# Option B: Streamlit Secrets (Alternative)
# Create .streamlit/secrets.toml:
# [mysql]
# host = "172.21.18.50"
# port = 3306
# user = "your_db_username"
# password = "your_db_password"
# database = "your_database_name"


# ========================================
# STEP 3: VERIFY DATABASE SETUP
# ========================================

# Check that your MySQL table exists:
# - Table: test_transaction_ids_view (or your actual table name)
# - Columns: suite_name, script_name, area_name, platform_name, active, ...

# Run this in MySQL client to verify:
USE your_database_name;
DESCRIBE test_transaction_ids_view;
SELECT COUNT(*) as total_rows FROM test_transaction_ids_view;
SELECT DISTINCT suite_name FROM test_transaction_ids_view LIMIT 10;


# ========================================
# STEP 4: TEST DATABASE ENGINE (Optional)
# ========================================

# Run this quick Python test to ensure DB connectivity:
python -c "
from modules.database_engine import DatabaseEngine

db = DatabaseEngine(
    host='172.21.18.50',
    user='your_username',
    password='your_password',
    database='your_database'
)

try:
    rows = db.query('SELECT VERSION() AS version;')
    print(f'✅ Connected! MySQL version: {rows}')
except Exception as e:
    print(f'❌ Connection failed: {e}')
"


# ========================================
# STEP 5: RUN THE STREAMLIT APP
# ========================================

streamlit run app.py

# Expected output:
# You can now view your Streamlit app in your browser.
# 
#   Local URL: http://localhost:8080
#   Network URL: http://YOUR_IP:8080

# Open http://localhost:8080 in your browser


# ========================================
# STEP 6: QUICK FUNCTIONAL TESTS (In Browser)
# ========================================

# Test 1: Check Connection
# - Click "🔌 Test Connection" button in sidebar
# - Should show: "Connected! MySQL: ..."

# Test 2: List All Suites
# - Click "📋 List all suites" button
# - Should show table of suite names

# Test 3: Query Specific Suite
# - Click "🔍 Show suite details" button
# - Should show detailed suite records

# Test 4: Chat Input
# - Type: "show me suites for Suite1"
# - Click "Chat input" button or press Enter
# - Should return results

# Test 5: Diagnostics
# - Type: "test database"
# - Should show TCP and DB connection status

# Test 6: Help
# - Type: "help"
# - Should list all supported commands


# ========================================
# STEP 7: CUSTOMIZE FOR YOUR DATA
# ========================================

# Task A: Update SQL queries in modules/agent.py
# -------
# Find these methods and update table/column names:
#
# 1. _list_suites() -> Change table name if needed
# 2. _query_suites() -> Add/remove columns based on your schema
#
# Example:
#   OLD: SELECT suite_name FROM test_transaction_ids_view
#   NEW: SELECT suite_name FROM your_actual_table_name
#
# Reference your actual table schema:
#   DESCRIBE test_transaction_ids_view;

# Task B: Add new intents for TP7.0 and Mainline data
# -------
# Currently these are placeholders. Add real queries:
#
# In modules/agent.py, find _fetch_tp_data() method:
#   - Add SQL query for TP7.0 release data
#   - Add filters (date range, build number, etc.)
#   - Return structured data

# Example template:
#
#   def _fetch_tp_data(self, release: str, params: Dict[str, Any]) -> AgentResponse:
#       try:
#           if release == "7.0":
#               sql = """
#                   SELECT BuildNumber, ExecutedOn, ScriptsPassed, ScriptsFailed
#                   FROM tp7_builds
#                   ORDER BY ExecutedOn DESC
#                   LIMIT 10;
#               """
#           else:  # mainline
#               sql = """
#                   SELECT BuildNumber, ExecutedOn, ScriptsPassed, ScriptsFailed
#                   FROM mainline_builds
#                   ORDER BY ExecutedOn DESC
#                   LIMIT 10;
#               """
#           rows = self.db.query(sql)
#           return AgentResponse(
#               success=True,
#               action=f"fetch_{release}_data",
#               message=f"Found {len(rows)} {release} builds.",
#               data=rows,
#           )
#       except Exception as e:
#           return AgentResponse(
#               success=False,
#               action=f"fetch_{release}_data",
#               message=f"Failed to fetch {release} data.",
#               error=str(e),
#           )


# ========================================
# STEP 8: EXTEND WITH CUSTOM INTENTS
# ========================================

# Example: Add "show failures" intent
#
# 1. In parse_intent(), add pattern:
#    if "failure" in prompt_lower or "failed" in prompt_lower:
#        return "show_failures", {}
#
# 2. In execute_intent(), add handler:
#    elif intent == "show_failures":
#        return self._show_failures()
#
# 3. Add the method:
#    def _show_failures(self) -> AgentResponse:
#        try:
#            rows = self.db.query("""
#                SELECT suite_name, script_name, failure_reason, failure_count
#                FROM failure_log
#                WHERE failure_count > 0
#                ORDER BY failure_count DESC
#                LIMIT 20;
#            """)
#            return AgentResponse(
#                success=True,
#                action="show_failures",
#                message=f"Found {len(rows)} failed scripts.",
#                data=rows,
#            )
#        except Exception as e:
#            return AgentResponse(
#                success=False,
#                action="show_failures",
#                message="Failed to fetch failures.",
#                error=str(e),
#            )


# ========================================
# STEP 9: TEST IN PRODUCTION
# ========================================

# Once you've customized:
# 1. Ask different prompts: "show failures for SuiteA", etc.
# 2. Check conversation history in sidebar
# 3. Download CSV results
# 4. Clear history and retest
# 5. Check app logs for any errors


# ========================================
# STEP 10: DEPLOY (Optional)
# ========================================

# To deploy on Streamlit Cloud:
#   1. Push code to GitHub (with .gitignore for secrets)
#   2. Go to share.streamlit.io
#   3. Deploy from GitHub repo
#   4. Set secrets in Streamlit Cloud dashboard
#
# For internal deployment:
#   - Run on a server with systemd or Docker
#   - Use a supervisord/PM2 process manager
#   - Configure Nginx reverse proxy


# ========================================
# TROUBLESHOOTING
# ========================================

# Issue: "MySQL credentials not configured"
# - Check environment variables: Get-Item Env:MYSQL_*
# - Or create .streamlit/secrets.toml with [mysql] section
#
# Issue: "No such table: test_transaction_ids_view"
# - Run in MySQL: SHOW TABLES; DESCRIBE test_transaction_ids_view;
# - Update table name in modules/agent.py
#
# Issue: "AttributeError: 'NoneType' has no attribute 'cursor'"
# - This is handled by transient fallback
# - Check MySQL is running and reachable
# - Run "test database" in the agent
#
# Issue: "Streamlit not found"
# - Activate venv: .venv\Scripts\Activate.ps1
# - Install: pip install streamlit


# ========================================
# QUICK REFERENCE: SUPPORTED PROMPTS
# ========================================

# "list suites"
#   → Shows all distinct suite names
#
# "show suites for SuiteA"
# "show suites for SuiteA and SuiteB"
#   → Shows details for specific suite(s)
#
# "show active suites"
#   → Filters for active=1/yes/true
#
# "show TP7.0 data"
#   → (Placeholder, customize with actual query)
#
# "show mainline builds"
#   → (Placeholder, customize with actual query)
#
# "test database" or "check connectivity"
#   → Runs diagnostics (TCP + DB query)
#
# "help"
#   → Shows all supported commands


print(__doc__)
