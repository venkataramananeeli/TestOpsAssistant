#!/usr/bin/env python
"""Quick test of database connection."""

import sys
sys.path.append('.')

from modules.database_engine import DatabaseEngine

print("Testing database connection...")
print("-" * 50)

try:
    db = DatabaseEngine(
        host='172.21.18.50',
        user='root',
        password='Tally@123',
        database='tallyrobot9'
    )
    
    # Test 1: Get database name
    rows = db.query('SELECT DATABASE() AS current_db;')
    print("✅ Connected successfully!")
    print(f"\nCurrent database: {rows[0] if rows else 'unknown'}")
    
    # Test 2: Check for test_transaction_ids_view
    print("\nChecking for test_transaction_ids_view table...")
    try:
        rows = db.query('SELECT COUNT(*) as count FROM test_transaction_ids_view LIMIT 1;')
        print(f"✅ Table exists with {rows[0]['count']} rows")
    except Exception as e:
        print(f"⚠️  Table might not exist: {e}")
    
    print("\n" + "=" * 50)
    print("Database connection test PASSED ✅")
    print("=" * 50)
    print("\nYou can now run the app:")
    print("  streamlit run app.py")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
