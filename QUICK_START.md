# Quick Start Commands

## 1. Activate Virtual Environment (PowerShell)
```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. Set Database Credentials (PowerShell - One-time)
```powershell
# Replace with your actual credentials
$env:MYSQL_HOST = "172.21.18.50"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "your_username"
$env:MYSQL_PASS = "your_password"
$env:MYSQL_DB = "your_database"

# Verify they're set
Get-Item Env:MYSQL_* | Format-Table Name,Value
```

## 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

## 4. Test Database Connection (Python)
```powershell
python -c "
from modules.database_engine import DatabaseEngine

db = DatabaseEngine(
    host='172.21.18.50',
    user=input('Username: '),
    password=input('Password: '),
    database=input('Database: ')
)

try:
    rows = db.query('SELECT VERSION() AS ver;')
    print('✅ Connected!', rows[0] if rows else '')
except Exception as e:
    print('❌ Error:', e)
"
```

## 5. Run the Streamlit App
```powershell
streamlit run app.py
```

Then open: **http://localhost:8080** in your browser

## 6. Test in Browser
- Click **"🔌 Test Connection"** → Should show MySQL version
- Click **"📋 List all suites"** → Should show list of suite names
- Type **"show suites for Suite1"** → Should show suite details
- Type **"test database"** → Should show diagnostics

---

## Folder Structure
```
testops-app/
├── app.py                    # Main Streamlit UI
├── requirements.txt          # Python dependencies
├── AGENT_GUIDE.md           # Detailed agent documentation
├── SETUP_CHECKLIST.py       # This setup guide
├── modules/
│   ├── __init__.py
│   ├── database_engine.py   # Safe DB wrapper
│   └── agent.py             # Custom agent logic
└── .streamlit/
    └── secrets.toml         # (Create this with MySQL credentials)
```

---

## What Happens When You Submit a Prompt

```
You type: "show suites for SuiteA"
         ↓
app.py receives input
         ↓
Calls agent.respond(prompt)
         ↓
agent.parse_intent() → Intent="query_suites", Params={"suite_names": ["SuiteA"]}
         ↓
agent.execute_intent() → Runs SQL query
         ↓
database_engine.query() → Opens connection, runs query, closes connection
         ↓
agent returns AgentResponse with data
         ↓
app.py renders table + CSV download
```

---

## Next Actions (Pick One)

### A. Get It Running Now
1. Run: `.\.venv\Scripts\Activate.ps1`
2. Set ENV vars (see Step 2 above)
3. Run: `streamlit run app.py`
4. Click test buttons in the app

### B. Customize SQL Queries
1. Find your actual table name: `SHOW TABLES;` in MySQL
2. Update `_list_suites()` and `_query_suites()` SQL in `modules/agent.py`
3. Restart: `streamlit run app.py`

### C. Add More Intents (TP7.0, Mainline)
1. Open `modules/agent.py`
2. Update `_fetch_tp_data()` method with real SQL query
3. Test by typing: "show TP7.0 data"

### D. Deploy to Production
- Use Docker container
- Run on a server with Python 3.9+
- Manage with systemd or supervisord

---

## Common MySQL Commands to Verify Your Data

```sql
-- Show all tables
SHOW TABLES;

-- Describe your suite table
DESCRIBE test_transaction_ids_view;

-- Count rows
SELECT COUNT(*) FROM test_transaction_ids_view;

-- Show distinct suite names
SELECT DISTINCT suite_name FROM test_transaction_ids_view LIMIT 10;

-- Show column names
SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'test_transaction_ids_view';
```

---

## Which Step Do You Want to Focus On?

1. **Get the app running** (Steps 1-5)
2. **Test it works** (Step 6)
3. **Customize SQL for your tables** (Step 7)
4. **Add new intents** (Step 8)
5. **Deploy to production** (Step 10)

Let me know which one, and I'll provide detailed help!
