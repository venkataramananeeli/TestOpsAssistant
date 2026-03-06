import pandas as pd

def format_test_results(data):
    """Format raw test data for display"""
    df = pd.DataFrame(data)
    return df

def calculate_pass_rate(passed, total):
    """Calculate test pass rate percentage"""
    return round((passed / total * 100), 2) if total > 0 else 0
