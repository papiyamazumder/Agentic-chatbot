"""
Azure App Insights Connector — query system logs and telemetry via REST API
Pattern: try real App Insights Kusto query → fall back to mock log data

Production: set AZURE_INSIGHTS_APP_ID, AZURE_INSIGHTS_API_KEY in .env
Local dev:  returns mock system log entries
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_LOG_FILE = Path("data/raw_docs/System_Log.csv")

def _get_system_logs_df() -> pd.DataFrame:
    """Load system logs securely from CSV and normalize columns."""
    if SYSTEM_LOG_FILE.exists():
        try:
            df = pd.read_csv(SYSTEM_LOG_FILE)
            df.columns = df.columns.str.lower()
            return df
        except Exception as e:
            logger.error(f"Failed to read System_Log CSV file: {e}")
            
    # Return empty schema if missing
    return pd.DataFrame(columns=[
        "timestamp", "log_level", "service_name", "user_id", "ip_address", "action", "status", "response_time_ms", "error_code"
    ])


def query_logs(severity: str = None, hours: int = 24, limit: int = 50, timeframe: str = None) -> list[dict]:
    """
    Query system logs directly from System_Log.csv with strict timeframe filtering.
    """
    df = _get_system_logs_df()
    
    if len(df) == 0:
        return []
        
    # Map external 'severity' (from LLM) to internal 'log_level' (CSV)
    if severity:
        sev_map = {
            "information": "info",
            "warning": "warn",
            "error": "error",
            "critical": "error"
        }
        target_sev = sev_map.get(severity.lower(), severity.lower())
        mask = df['log_level'].str.lower() == target_sev
        df = df[mask]
        
    # Time filtering (strict date-based)
    if 'timestamp' in df.columns:
        try:
            df['dt'] = pd.to_datetime(df['timestamp'])
            now = pd.Timestamp.now() # Use local time for demo consistency
            
            if timeframe:
                timeframe = timeframe.lower()
                if "yesterday" in timeframe:
                    # Filter for exactly yesterday
                    yesterday = (now - pd.Timedelta(days=1)).date()
                    df = df[df['dt'].dt.date == yesterday]
                elif "today" in timeframe:
                    # Filter for exactly today
                    today = now.date()
                    df = df[df['dt'].dt.date == today]
                elif "hour" in timeframe:
                    # Extract number of hours (e.g. "last 4 hours")
                    import re
                    match = re.search(r'(\d+)', timeframe)
                    if match:
                        h = int(match.group(1))
                        cutoff = now - pd.Timedelta(hours=h)
                        df = df[df['dt'] >= cutoff]
                else:
                    # Fallback to general hours if timeframe is vague
                    cutoff = now - pd.Timedelta(hours=hours)
                    df = df[df['dt'] >= cutoff]
            else:
                # Default behavior: use 'hours' parameter
                cutoff = now - pd.Timedelta(hours=hours)
                df = df[df['dt'] >= cutoff]
                
            df = df.sort_values('dt', ascending=False)
        except Exception as e:
            logger.error(f"Time filtering error: {e}")
            pass
            
    # Send most recent first based on limit
    df = df.head(limit)
    
    # Output cleanly handling NaNs
    results = df.to_dict('records')
    results = [{k: ("" if pd.isna(v) else (v.isoformat() if hasattr(v, 'isoformat') else v)) 
                for k, v in t.items() if k != 'dt'} for t in results]
    
    logger.info(f"[CSV LOGS] Returning {len(results)} system log entries for timeframe: {timeframe}")
    return results

def get_performance_summary() -> dict:
    """Calculate performance metrics summary dynamically from CSV."""
    df = _get_system_logs_df()
    
    if len(df) == 0:
        return {
            "avg_response_time_ms": 0.0,
            "p95_response_time_ms": 0.0,
            "total_requests_24h": 0,
            "error_rate_percent": 0.0
        }
    
    # Calculate native metrics
    total_requests = len(df)
    
    # Avg and 95th Percentile
    avg_ms = 0.0
    p95_ms = 0.0
    if 'response_time_ms' in df.columns:
        ms_series = pd.to_numeric(df['response_time_ms'], errors='coerce').dropna()
        if not ms_series.empty:
            avg_ms = float(ms_series.mean())
            p95_ms = float(ms_series.quantile(0.95))
            
    # Error rate (count of 'FAILED' vs total)
    err_rate = 0.0
    if 'status' in df.columns:
        fails = len(df[df['status'].str.lower() == 'failed'])
        err_rate = (fails / total_requests) * 100.0 if total_requests > 0 else 0.0
        
    return {
        "avg_response_time_ms": round(avg_ms, 1),
        "p95_response_time_ms": round(p95_ms, 1),
        "total_requests_24h": total_requests,
        "error_rate_percent": round(err_rate, 1),
    }
