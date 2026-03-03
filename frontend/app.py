import streamlit as st
import time
import os
import uuid
import base64
import requests
import pandas as pd
from pathlib import Path

# --- INITIAL APP CONFIG ---
st.set_page_config(
    page_title="KPMG PMO AI Core",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTS ---
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
DOC_BASE_PATH = Path(__file__).parent.parent / "Project_Flowchart"

USERS = {
    "admin":    {"password": "", "role": "PMO Admin"},
    "manager":  {"password": "", "role": "Manager"},
    "resource": {"password": "", "role": "Resource"},
}

ROLE_PERMS = {
    "PMO Admin": {"color": "#00F5FF", "label": "Full Clearance", "access_level": 3,
                  "agents": ["Retrieval Agent", "API Agent", "Helpdesk Agent", "Workflow Agent"], "avatar": "👑"},
    "Manager":   {"color": "#8A2BE2", "label": "Manager Level", "access_level": 2,
                  "agents": ["Retrieval Agent", "API Agent", "Helpdesk Agent", "Workflow Agent"], "avatar": "📋"},
    "Resource":  {"color": "#D91E5B", "label": "Standard Access", "access_level": 1,
                  "agents": ["Retrieval Agent", "Helpdesk Agent"], "avatar": "👤"},
}

DOC_CARDS = [
    {"title": "AI Concepts",       "icon": "🧠", "file": "AI_ML_conecpts.html",                    "desc": "54 AI/ML concepts and prep.",       "min_access": 1, "cls": "vault-card-1"},
    {"title": "Architecture Flow",  "icon": "🏗️", "file": "Architechture_Flow.html",                "desc": "Cloud system design.",               "min_access": 1, "cls": "vault-card-2"},
    {"title": "Build Guide",        "icon": "🔨", "file": "BUILD_SCRATCH_GUIDE.html",               "desc": "Step-by-step dev setup.",            "min_access": 2, "cls": "vault-card-3"},
    {"title": "Features",           "icon": "⚡", "file": "Chatbot_Features+Functionalities.html",  "desc": "Functional and technical specs.",    "min_access": 1, "cls": "vault-card-4"},
    {"title": "Deployment",         "icon": "🔄", "file": "P1+P2_workflow+diff.html",               "desc": "Local vs Azure deployment diffs.",   "min_access": 2, "cls": "vault-card-5"},
    {"title": "Tech Stack",         "icon": "🐍", "file": "Python Libraries & HuggingFace Models.html", "desc": "Library and API documentation.", "min_access": 1, "cls": "vault-card-6"},
]

FEATURE_NAV = [
    {"key": "dashboard",   "icon": "🏠", "label": "Dashboard"},
    {"key": "doc_query",   "icon": "📄", "label": "Doc Query"},
    {"key": "kpi_live",    "icon": "📊", "label": "KPI Live"},
    {"key": "helpdesk",    "icon": "🎫", "label": "Helpdesk"},
    {"key": "workflows",   "icon": "⚙️", "label": "Workflows"},
    {"key": "logs",        "icon": "📋", "label": "RAID & Logs"},
    {"key": "doc_upload",  "icon": "📤", "label": "Doc Upload"},
]

# --- SESSION STATE DEFAULTS ---
state_defaults = {
    "logged_in": False, "username": "", "messages": [],
    "session_id": str(uuid.uuid4()), "total_queries": 0,
    "current_page": "dashboard", "viewing_doc": None, "chat_open": False,
    "chat_expanded": False, "chat_history_log": [],
    "page_stack": ["dashboard"], # History stack for back navigation
    "active_kpi": None,
    "pending_action_query": None,  # For multi-turn field collection
}
for k, v in state_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def navigate_to(page: str):
    """Navigates to a new page and pushes current to stack if different."""
    if st.session_state.current_page != page:
        st.session_state.page_stack.append(st.session_state.current_page)
        st.session_state.current_page = page
        st.session_state.chat_open = False # Auto-minimize
        st.rerun()


def go_back():
    """Pops the last page from history and navigates to it."""
    if len(st.session_state.page_stack) > 1:
        prev_page = st.session_state.page_stack.pop()
        st.session_state.current_page = prev_page
        st.session_state.viewing_doc = None if prev_page != "doc_viewer" else st.session_state.viewing_doc
        st.session_state.chat_open = False # Auto-minimize
        st.rerun()
    else:
        # Fallback to dashboard if stack is empty
        st.session_state.current_page = "dashboard"
        st.session_state.page_stack = ["dashboard"]
        st.session_state.chat_open = False # Auto-minimize
        st.rerun()


# ================================================
# THEME
# ================================================
def apply_custom_theme():
    # Dynamic background based on login state
    if not st.session_state.get("logged_in", False):
        # Login Gradient: Deep Midnight / Charcoal (Serious Enterprise Feel)
        bg_gradient = "linear-gradient(135deg, #020202 0%, #0a0a0f 40%, #1a1a2e 100%)"
    else:
        # Dashboard Gradient: Sleek Navy / Deep Indigo / Subtle Purple (Premium Modern Feel)
        bg_gradient = "linear-gradient(135deg, #050505 0%, #011627 45%, #1d1b4b 100%)"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
        /* High-Contrast Glass-Dark Evolution */
        .stApp {{ 
            background: {bg_gradient} !important; 
            background-attachment: fixed; 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            color: #FFFFFF !important;
        }}

        /* Login Card - Curved, Glowing, Popping */
        .login-card {{
            background: rgba(10, 10, 10, 0.8) !important;
            backdrop-filter: blur(20px) !important;
            border: 2px solid rgba(217, 30, 91, 0.3) !important;
            border-radius: 40px !important; /* Deep curved corners */
            padding: 3rem !important;
            text-align: center !important;
            box-shadow: 0 0 20px rgba(217, 30, 91, 0.2), 0 10px 40px rgba(0,0,0,0.8) !important;
            transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            margin: 2rem auto !important;
            max-width: 500px !important;
        }}

        .login-card:hover {{
            transform: scale(1.05) translateY(-5px) !important; /* Popping effect */
            box-shadow: 0 0 40px rgba(217, 30, 91, 0.6), 0 20px 60px rgba(0,0,0,0.9) !important;
            border-color: rgba(217, 30, 91, 0.8) !important;
        }}

        /* Pulsating Glow Animation */
        @keyframes pulsate-glow {{
            0% {{ box-shadow: 0 0 15px rgba(217, 30, 91, 0.2), 0 10px 40px rgba(0,0,0,0.8); border-color: rgba(217, 30, 91, 0.4); }}
            50% {{ box-shadow: 0 0 30px rgba(217, 30, 91, 0.5), 0 15px 50px rgba(0,0,0,0.9); border-color: rgba(217, 30, 91, 0.8); }}
            100% {{ box-shadow: 0 0 15px rgba(217, 30, 91, 0.2), 0 10px 40px rgba(0,0,0,0.8); border-color: rgba(217, 30, 91, 0.4); }}
        }}

        /* Enterprise Meow - Container Evolution */
        .meow-container {{
            background: rgba(10, 10, 10, 0.75) !important;
            backdrop-filter: blur(30px) !important;
            border: 1px solid rgba(217, 30, 91, 0.4) !important;
            border-radius: 28px !important;
            padding: 0 !important;
            overflow: hidden !important;
            animation: pulsate-glow 4s infinite ease-in-out;
            transition: all 0.6s cubic-bezier(0.22, 1, 0.36, 1) !important;
            transform-origin: bottom right !important;
        }}
        .meow-container:hover {{
            transform: scale(1.02) !important;
            box-shadow: 0 0 45px rgba(217, 30, 91, 0.6) !important;
        }}

        .meow-header {{
            background: rgba(217, 30, 91, 0.95) !important;
            padding: 18px 25px !important;
            color: white !important;
            font-weight: 800 !important;
            letter-spacing: 2px !important;
            text-transform: uppercase !important;
            font-size: 0.9rem !important;
            display: flex !important;
            align-items: center !important;
        }}

        /* Message Bubbles - High Contrast Tonal Shifts */
        .msg-system {{
            background: rgba(29, 27, 75, 0.8) !important;
            border-left: 4px solid #4F46E5 !important;
            color: #FFFFFF !important;
            padding: 14px 18px !important;
            border-radius: 16px !important;
            margin-bottom: 15px !important;
            font-size: 0.95rem !important;
            line-height: 1.6 !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2) !important;
        }}
        .msg-user {{
            background: rgba(40, 40, 40, 0.7) !important;
            border-left: 4px solid #9CA3AF !important;
            color: #F8F8F8 !important;
            padding: 14px 18px !important;
            border-radius: 16px !important;
            margin-bottom: 15px !important;
            font-size: 0.95rem !important;
            line-height: 1.6 !important;
        }}

        /* Input Bar Alignment */
        .meow-footer {{
            padding: 15px 20px !important;
            border-top: 1px solid rgba(255,255,255,0.08) !important;
        }}
        
        div[data-testid="column"] > div > div > div > button {{
            height: 45px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}
        .stSelectbox div[data-baseweb="select"], .stTextInput input {{ background-color: rgba(255,255,255,0.07) !important; border: 1px solid rgba(255,255,255,0.12) !important; border-radius: 16px !important; color: white !important; }}

        /* Global Pill Button Style */
        div.stButton > button {{ 
            background: #D91E5B !important; 
            color: white !important; 
            border: none !important; 
            border-radius: 100px !important; 
            font-weight: 700 !important; 
            transition: all 0.3s ease; 
            padding: 0.5rem 1.5rem !important;
        }}
        div.stButton > button:hover {{ box-shadow: 0 10px 25px rgba(217,30,91,0.4); background: #FF2E7E !important; }}

        /* Meow & Sync Toggle (Premium Radial Bloom) */
        div.stButton > button[key="meow_circle_toggle"], 
        div.stButton > button[key="sync_kpi_header"] {{ 
            background: radial-gradient(circle at center, rgba(217, 30, 91, 0.15) 0%, rgba(10, 10, 15, 0.7) 100%) !important;
            border: 2px solid rgba(255,255,255,0.2) !important; 
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5) !important; 
            float: right !important; 
            margin-bottom: 12px !important;
            min-width: 120px !important;
            opacity: 0.75 !important;
            transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1) !important;
        }}
        div.stButton > button[key="meow_circle_toggle"]:hover,
        div.stButton > button[key="sync_kpi_header"]:hover {{
            opacity: 1 !important;
            transform: scale(1.05) !important;
            background: radial-gradient(circle at center, rgba(217, 30, 91, 0.4) 0%, rgba(15, 15, 20, 0.9) 100%) !important;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.8), 0 0 25px rgba(217, 30, 91, 0.3) !important;
            border-color: rgba(217, 30, 91, 0.6) !important;
            color: white !important;
        }}

        /* Circular Back Button */
        div.stButton > button[key="sidebar_back_circle"] {{ 
            position: relative !important;
            width: 38px !important; 
            height: 38px !important; 
            border-radius: 50% !important; 
            background: rgba(255,255,255,0.08) !important; 
            border: 1px solid rgba(255,255,255,0.15) !important; 
            font-size: 18px !important; 
            display: flex !important; 
            align-items: center !important; 
            justify-content: center !important; 
            padding: 0 !important; 
            color: white !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            margin-top: -15px !important;
            margin-bottom: 5px !important;
        }}
        div.stButton > button[key="sidebar_back_circle"]:hover {{ 
            border-color: #D91E5B !important; 
            color: #D91E5B !important; 
            transform: scale(1.15) !important; 
            background: rgba(217,30,91,0.15) !important;
            box-shadow: 0 0 15px rgba(217,30,91,0.3) !important;
        }}

        /* Typography Evolution */
        h1, h2, h3, h4 {{ 
            font-weight: 800 !important;
            letter-spacing: -1.5px !important;
            color: white !important;
        }}

        /* Feature cards */
        .feature-card {{ 
            background: linear-gradient(145deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.03) 100%) !important; 
            border: 1px solid rgba(255,255,255,0.12) !important; 
            border-radius: 20px; 
            padding: 2rem; 
            transition: all 0.3s ease; 
            cursor: pointer; 
            margin-bottom: 1rem; 
        }}
        .feature-card:hover {{ 
            border-color: rgba(217,30,91,0.5) !important; 
            box-shadow: 0 10px 30px rgba(217,30,91,0.15); 
            transform: translateY(-5px);
        }}

        /* Dashboard KPI Cards */
        .dash-kpi {{
            border-radius: 20px !important;
            padding: 1.5rem !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            transition: all 0.3s ease !important;
        }}
        .dash-kpi:hover {{
            transform: translateY(-3px) !important;
            box-shadow: 0 8px 25px rgba(0,0,0,0.3) !important;
        }}
        .dash-kpi-1 {{ background: linear-gradient(135deg, rgba(0,123,255,0.15) 0%, rgba(0,123,255,0.05) 100%) !important; border-color: rgba(0,123,255,0.3) !important; }}
        .dash-kpi-2 {{ background: linear-gradient(135deg, rgba(102,51,153,0.15) 0%, rgba(102,51,153,0.05) 100%) !important; border-color: rgba(102,51,153,0.3) !important; }}
        .dash-kpi-3 {{ background: linear-gradient(135deg, rgba(217,30,91,0.15) 0%, rgba(217,30,91,0.05) 100%) !important; border-color: rgba(217,30,91,0.3) !important; }}
        .dash-kpi-4 {{ background: linear-gradient(135deg, rgba(40,167,69,0.15) 0%, rgba(40,167,69,0.05) 100%) !important; border-color: rgba(40,167,69,0.3) !important; }}

        /* Vault Card Gradients */
        .vault-card {{
            border-radius: 30px !important;
            padding: 2rem !important;
            margin-bottom: 1.5rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
        }}
        .vault-card:hover {{
            transform: translateY(-8px) scale(1.02) !important;
            box-shadow: 0 15px 40px rgba(0,0,0,0.4) !important;
        }}
        .vault-card-1 {{ background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(99, 102, 241, 0.02) 100%) !important; border-color: rgba(99, 102, 241, 0.25) !important; }}
        .vault-card-1:hover {{ border-color: #6366f1 !important; background: rgba(99, 102, 241, 0.15) !important; box-shadow: 0 15px 35px rgba(99, 102, 241, 0.2) !important; }}
        
        .vault-card-2 {{ background: linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0.02) 100%) !important; border-color: rgba(245, 158, 11, 0.25) !important; }}
        .vault-card-2:hover {{ border-color: #f59e0b !important; background: rgba(245, 158, 11, 0.15) !important; box-shadow: 0 15px 35px rgba(245, 158, 11, 0.2) !important; }}
        
        .vault-card-3 {{ background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.02) 100%) !important; border-color: rgba(16, 185, 129, 0.25) !important; }}
        .vault-card-3:hover {{ border-color: #10b981 !important; background: rgba(16, 185, 129, 0.15) !important; box-shadow: 0 15px 35px rgba(16, 185, 129, 0.2) !important; }}
        
        .vault-card-4 {{ background: linear-gradient(135deg, rgba(236, 72, 153, 0.12) 0%, rgba(236, 72, 153, 0.02) 100%) !important; border-color: rgba(236, 72, 153, 0.25) !important; }}
        .vault-card-4:hover {{ border-color: #ec4899 !important; background: rgba(236, 72, 153, 0.15) !important; box-shadow: 0 15px 35px rgba(236, 72, 153, 0.2) !important; }}
        
        .vault-card-5 {{ background: linear-gradient(135deg, rgba(139, 92, 246, 0.12) 0%, rgba(139, 92, 246, 0.02) 100%) !important; border-color: rgba(139, 92, 246, 0.25) !important; }}
        .vault-card-5:hover {{ border-color: #8b5cf6 !important; background: rgba(139, 92, 246, 0.15) !important; box-shadow: 0 15px 35px rgba(139, 92, 246, 0.2) !important; }}
        
        .vault-card-6 {{ background: linear-gradient(135deg, rgba(6, 182, 212, 0.12) 0%, rgba(6, 182, 212, 0.02) 100%) !important; border-color: rgba(6, 182, 212, 0.25) !important; }}
        .vault-card-6:hover {{ border-color: #06b6d4 !important; background: rgba(6, 182, 212, 0.15) !important; box-shadow: 0 15px 35px rgba(6, 182, 212, 0.2) !important; }}

        /* KPI Specific Cards */
        .kpi-card-new {{
            background: linear-gradient(165deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.02) 100%) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 24px !important;
            padding: 1.5rem !important;
            text-align: center !important;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
            cursor: pointer !important;
            height: 100% !important;
        }}
        .kpi-card-new:hover {{
            transform: translateY(-8px) scale(1.02) !important;
        }}
        .kpi-label {{ font-size: 0.9rem !important; font-weight: 700 !important; color: white !important; margin: 0 !important; }}

        /* KPI Card Color Variants (Complementing Dark Background) */
        .kpi-clr-1 {{ background: linear-gradient(135deg, rgba(255, 69, 0, 0.12) 0%, rgba(255, 69, 0, 0.02) 100%) !important; border-color: rgba(255, 69, 0, 0.25) !important; }}
        .kpi-clr-1:hover {{ border-color: #FF4500 !important; background: rgba(255, 69, 0, 0.15) !important; box-shadow: 0 15px 35px rgba(255, 69, 0, 0.2) !important; }}
        
        .kpi-clr-2 {{ background: linear-gradient(135deg, rgba(255, 215, 0, 0.12) 0%, rgba(255, 215, 0, 0.02) 100%) !important; border-color: rgba(255, 215, 0, 0.25) !important; }}
        .kpi-clr-2:hover {{ border-color: #FFD700 !important; background: rgba(255, 215, 0, 0.15) !important; box-shadow: 0 15px 35px rgba(255, 215, 0, 0.2) !important; }}
        
        .kpi-clr-3 {{ background: linear-gradient(135deg, rgba(50, 205, 50, 0.12) 0%, rgba(50, 205, 50, 0.02) 100%) !important; border-color: rgba(50, 205, 50, 0.25) !important; }}
        .kpi-clr-3:hover {{ border-color: #32CD32 !important; background: rgba(50, 205, 50, 0.15) !important; box-shadow: 0 15px 35px rgba(50, 205, 50, 0.2) !important; }}
        
        .kpi-clr-4 {{ background: linear-gradient(135deg, rgba(30, 144, 255, 0.12) 0%, rgba(30, 144, 255, 0.02) 100%) !important; border-color: rgba(30, 144, 255, 0.25) !important; }}
        .kpi-clr-4:hover {{ border-color: #1E90FF !important; background: rgba(30, 144, 255, 0.15) !important; box-shadow: 0 15px 35px rgba(30, 144, 255, 0.2) !important; }}
        
        .kpi-clr-5 {{ background: linear-gradient(135deg, rgba(0, 255, 255, 0.12) 0%, rgba(0, 255, 255, 0.02) 100%) !important; border-color: rgba(0, 255, 255, 0.25) !important; }}
        .kpi-clr-5:hover {{ border-color: #00FFFF !important; background: rgba(0, 255, 255, 0.15) !important; box-shadow: 0 15px 35px rgba(0, 255, 255, 0.2) !important; }}
        
        .kpi-clr-6 {{ background: linear-gradient(135deg, rgba(255, 99, 71, 0.12) 0%, rgba(255, 99, 71, 0.02) 100%) !important; border-color: rgba(255, 99, 71, 0.25) !important; }}
        .kpi-clr-6:hover {{ border-color: #FF6347 !important; background: rgba(255, 99, 71, 0.15) !important; box-shadow: 0 15px 35px rgba(255, 99, 71, 0.2) !important; }}
        
        .kpi-clr-7 {{ background: linear-gradient(135deg, rgba(138, 43, 226, 0.12) 0%, rgba(138, 43, 226, 0.02) 100%) !important; border-color: rgba(138, 43, 226, 0.25) !important; }}
        .kpi-clr-7:hover {{ border-color: #8A2BE2 !important; background: rgba(138, 43, 226, 0.15) !important; box-shadow: 0 15px 35px rgba(138, 43, 226, 0.2) !important; }}
        
        .kpi-clr-8 {{ background: linear-gradient(135deg, rgba(255, 20, 147, 0.12) 0%, rgba(255, 20, 147, 0.02) 100%) !important; border-color: rgba(255, 20, 147, 0.25) !important; }}
        .kpi-clr-8:hover {{ border-color: #FF1493 !important; background: rgba(255, 20, 147, 0.15) !important; box-shadow: 0 15px 35px rgba(255, 20, 147, 0.2) !important; }}
        
        .kpi-clr-9 {{ background: linear-gradient(135deg, rgba(112, 128, 144, 0.12) 0%, rgba(112, 128, 144, 0.02) 100%) !important; border-color: rgba(112, 128, 144, 0.25) !important; }}
        .kpi-clr-9:hover {{ border-color: #708090 !important; background: rgba(112, 128, 144, 0.15) !important; box-shadow: 0 15px 35px rgba(112, 128, 144, 0.2) !important; }}
        
        .kpi-clr-10 {{ background: linear-gradient(135deg, rgba(0, 191, 255, 0.12) 0%, rgba(0, 191, 255, 0.02) 100%) !important; border-color: rgba(0, 191, 255, 0.25) !important; }}
        .kpi-clr-10:hover {{ border-color: #00BFFF !important; background: rgba(0, 191, 255, 0.15) !important; box-shadow: 0 15px 35px rgba(0, 191, 255, 0.2) !important; }}
        
        .kpi-clr-11 {{ background: linear-gradient(135deg, rgba(255, 191, 0, 0.12) 0%, rgba(255, 191, 0, 0.02) 100%) !important; border-color: rgba(255, 191, 0, 0.25) !important; }}
        .kpi-clr-11:hover {{ border-color: #FFBF00 !important; background: rgba(255, 191, 0, 0.15) !important; box-shadow: 0 15px 35px rgba(255, 191, 0, 0.2) !important; }}
        
        .kpi-clr-12 {{ background: linear-gradient(135deg, rgba(147, 51, 234, 0.18) 0%, rgba(147, 51, 234, 0.05) 100%) !important; border-color: rgba(147, 51, 234, 0.35) !important; }}
        .kpi-clr-12:hover {{ border-color: #9333ea !important; background: rgba(147, 51, 234, 0.25) !important; box-shadow: 0 15px 35px rgba(147, 51, 234, 0.3) !important; }}

        /* Agent Card */
        .agent-card {{
            background: linear-gradient(135deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%) !important;
            border-radius: 24px !important;
            padding: 1.5rem !important;
            text-align: center !important;
            min-height: 180px !important;
            display: flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }}
        .agent-card:hover {{
            transform: translateY(-8px) scale(1.02) !important;
            box-shadow: 0 15px 40px rgba(0, 245, 255, 0.2) !important;
            border-color: #00F5FF !important;
            background: rgba(0, 245, 255, 0.08) !important;
        }}

        /* Cap Card */
        .cap-card {{
            text-align: center !important;
            padding: 1.2rem !important;
            border-radius: 18px !important;
            margin-bottom: 1rem !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            backdrop-filter: blur(12px) !important;
        }}
        .cap-card:hover {{
            transform: translateY(-5px) scale(1.02) !important;
            box-shadow: 0 10px 30px rgba(138, 43, 226, 0.2) !important;
            border-color: #A5B4FC !important;
            background: rgba(138, 43, 226, 0.1) !important;
        }}

        /* Result Area */
        .result-container {{
            background: rgba(10, 10, 10, 0.6) !important;
            backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(217, 30, 91, 0.3) !important;
            border-radius: 24px !important;
            padding: 2rem !important;
            margin-top: 2rem !important;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5) !important;
            animation: slideUp 0.5s ease-out !important;
        }}
        @keyframes slideUp {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Midnight Hover for KPI Buttons */
        .kpi-btn-midnight div.stButton > button {{
            background: rgba(15, 15, 20, 0.5) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: rgba(255, 255, 255, 0.9) !important;
            border-radius: 14px !important;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }}
        .kpi-btn-midnight div.stButton > button:hover {{
            background: #000000 !important;
            border-color: #D91E5B !important;
            color: white !important;
            transform: scale(1.02) !important;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.8), 0 0 15px rgba(217, 30, 91, 0.2) !important;
        }}

        /* Nav button active */
        .nav-active {{ background: rgba(217,30,91,0.2) !important; border-left: 3px solid #D91E5B !important; }}

        h1, h2, h3, p, label {{ color: white !important; }}
    </style>
    """, unsafe_allow_html=True)

apply_custom_theme()


# ================================================
# BACKEND HELPERS
# ================================================

def _get_recent_history(n=5) -> list:
    """Get the last N messages for context memory."""
    msgs = st.session_state.get("messages", [])
    recent = msgs[-(n*2):]  # Get last N pairs (user+assistant)
    return [{"role": m["role"], "content": m["content"][:500]} for m in recent if m.get("content")]


def call_backend(query: str, agent_override: str = "auto") -> dict:
    try:
        resp = requests.post(f"{BACKEND_URL}/chat",
                             json={
                                 "query": query,
                                 "session_id": st.session_state.session_id,
                                 "agent_override": agent_override,
                                 "chat_history": _get_recent_history()
                             }, timeout=90)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"answer": f"\u274c Backend error: {str(e)}", "agent_used": "System", "sources": []}


def read_vault_doc(filename: str) -> str:
    import re
    try:
        filepath = DOC_BASE_PATH / filename
        if not filepath.exists(): return ""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        # Truncate to ~8000 chars for LLM context (was 4000, increased for accuracy)
        return text[:8000]
    except Exception:
        return ""


def vault_query(doc_filename: str, question: str, agent_override: str = "auto") -> dict:
    """Query a vault document directly — reads HTML, sends content + question to backend."""
    content = read_vault_doc(doc_filename)
    if not content:
        return {"answer": f"\u274c Could not read document: {doc_filename}", "agent_used": "Vault Reader", "sources": [doc_filename]}
    augmented_query = f"Based on this document content, {question}\n\nDocument ({doc_filename}):\n{content}"
    # Force route vault queries to the docs agent for accurate RAG processing
    try:
        resp = requests.post(f"{BACKEND_URL}/chat",
                             json={
                                 "query": augmented_query, 
                                 "session_id": st.session_state.session_id,
                                 "agent_override": "docs",
                                 "chat_history": _get_recent_history()
                             }, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        data["sources"] = [doc_filename] + data.get("sources", [])
        return data
    except Exception as e:
        return {"answer": f"\u274c Error: {str(e)}", "agent_used": "Vault Reader", "sources": [doc_filename]}

def fetch_get(endpoint: str) -> dict:
    try:
        resp = requests.get(f"{BACKEND_URL}{endpoint}", timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def clear_meow_chat():
    st.session_state.messages = []
    st.session_state.pending_action_query = None

def handle_query(query: str, agent_override: str = "auto"):
    # Multi-turn: If there's a pending action, merge follow-up with original context
    effective_query = query
    if st.session_state.pending_action_query:
        effective_query = f"{st.session_state.pending_action_query}. Additional details: {query}"
        st.session_state.pending_action_query = None  # Clear pending
    
    # Log to Recent History log (all queries since login)
    st.session_state.chat_history_log.append({"role": "user", "content": query, "time": time.time()})
    
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant"):
        with st.spinner("🤖 Routing to neural network..."):
            result = call_backend(effective_query, agent_override=agent_override)
        badge = f"""<span style="border:1px solid #D91E5B; padding:2px 8px; border-radius:10px; font-size:0.7rem; color:#D91E5B;">{result.get('agent_used', 'Agent')}</span>"""
        st.markdown(badge, unsafe_allow_html=True)
        st.markdown(result["answer"])
        
        # Add download button for the answer
        st.download_button(
            label="Download Answer",
            data=result["answer"],
            file_name="kpmg_ai_answer.md",
            mime="text/markdown",
            key=f"download_answer_{st.session_state.total_queries}"
        )
    
    # Detect if agent is asking for more details (multi-turn)
    sources = result.get("sources", [])
    if any("awaiting details" in str(s) for s in sources):
        st.session_state.pending_action_query = effective_query
    
    st.session_state.chat_history_log.append({"role": "assistant", "content": result["answer"], "time": time.time()})
    st.session_state.messages.append({"role": "assistant", "content": result["answer"],
                                      "agent_used": result.get("agent_used", ""), "sources": result.get("sources", [])})
    st.session_state.total_queries += 1


# ================================================
# LOGIN
# ================================================
def render_dynamic_background():
    st.components.v1.html("""
    <style> body { margin:0; overflow:hidden; background:#050505; } canvas { position:fixed; top:0; left:0; z-index:-1; }
    .cursor-glow { position:fixed; width:400px; height:400px; background:radial-gradient(circle, rgba(217,30,91,0.15) 0%, transparent 70%); border-radius:50%; pointer-events:none; z-index:0; transform:translate(-50%,-50%); }
    .grid-bg { position:fixed; top:0; left:0; width:100vw; height:100vh; background-image: linear-gradient(rgba(217,30,91,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(217,30,91,0.05) 1px, transparent 1px); background-size:50px 50px; z-index:-2; transform:rotateX(45deg); opacity:0.3; }
    </style>
    <div class="grid-bg"></div><div id="glow" class="cursor-glow"></div><canvas id="canvas"></canvas>
    <script>
    const c=document.getElementById('canvas'),x=c.getContext('2d'),g=document.getElementById('glow');let w,h,d=[];
    function init(){w=c.width=innerWidth;h=c.height=innerHeight;d=[];for(let i=0;i<80;i++)d.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-0.5)*0.5,vy:(Math.random()-0.5)*0.5,s:Math.random()*2});}
    addEventListener('mousemove',e=>{g.style.left=e.clientX+'px';g.style.top=e.clientY+'px';});
    function draw(){x.clearRect(0,0,w,h);x.fillStyle="rgba(217,30,91,0.5)";d.forEach(p=>{p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>w)p.vx*=-1;if(p.y<0||p.y>h)p.vy*=-1;x.beginPath();x.arc(p.x,p.y,p.s,0,Math.PI*2);x.fill();});requestAnimationFrame(draw);}
    addEventListener('resize',init);init();draw();
    </script>
    """, height=0, width=0)

def render_login():
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("""
            <h1 style="margin:0; letter-spacing:-3px; font-weight:800; font-size:3.5rem;">KPMG <span style="color:#D91E5B;">AI</span></h1>
            <p style="margin-bottom:2.5rem; opacity:0.5; font-size:0.8rem; letter-spacing:2px;">SECURE ACCESS PORTAL</p>
    """, unsafe_allow_html=True)
    
    u = st.selectbox("Profile", options=["Select Identity", "admin", "manager", "resource"], label_visibility="collapsed", key="login_u")
    p = st.text_input("Password", type="password", placeholder="••••••••", label_visibility="collapsed", key="login_p")
    
    if st.button("Submit  →", width='stretch', key="login_submit"):
        if u != "Select Identity" and USERS.get(u, {}).get("password") == p:
            st.session_state.logged_in = True
            st.session_state.username = u
            st.rerun()
        else:
            st.error("Authentication Denied")
            
    if st.button("Forgot Password?", type="secondary", width='stretch', key="login_forgot"):
        st.toast("Redirecting to helpdesk...")
        
    st.markdown("</div>", unsafe_allow_html=True)


# ================================================
# SIDEBAR NAVIGATION
# ================================================
def render_sidebar():
    user = USERS[st.session_state.username]
    perms = ROLE_PERMS[user["role"]]
    with st.sidebar:
        # Back button at the very top for non-dashboard pages
        if st.session_state.current_page != "dashboard" or len(st.session_state.page_stack) > 1:
            if st.button("←", key="sidebar_back_circle"):
                go_back()

        st.markdown(f"""
            <div style="text-align:center; padding:1.5rem; border:1px solid rgba(255,255,255,0.1); border-radius:24px; margin-bottom:1.5rem; background:rgba(0,0,0,0.4)">
                <div style="font-size:3rem; margin-bottom:10px; text-shadow:0 0 10px {perms['color']}">{perms['avatar']}</div>
                <h3 style="margin:0; font-size:1.1rem; font-weight:800;">{st.session_state.username.title()}</h3>
                <div style="margin-top:8px;"><span style="background:rgba(255,255,255,0.05); color:{perms['color']}; padding:4px 12px; border-radius:12px; font-size:0.7rem; font-weight:800; text-transform:uppercase; border:1px solid {perms['color']}80;">{perms['label']}</span></div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🧭 Navigation")
        for nav in FEATURE_NAV:
            is_active = st.session_state.current_page == nav["key"]
            label = f"{nav['icon']} {nav['label']}"
            if st.button(label, key=f"nav_{nav['key']}", width='stretch',
                         type="primary" if is_active else "secondary"):
                navigate_to(nav["key"])

        st.markdown("---")
        st.markdown("### ⚙️ Controls")
        if st.button("🗑️ Clear Meow Chat", key="clr_chat_meow", width='stretch'):
            clear_meow_chat()
            st.toast("Meow history cleared.")
            st.rerun()
            
        if st.button("📜 Clear Recent History", key="clr_history_recent", width='stretch'):
            st.session_state.chat_history_log = []
            st.toast("Session history cleared.")
            st.rerun()

        if st.button("🚪 Logout", key="logout", width='stretch'):
            st.session_state.logged_in = False
            st.rerun()
        st.caption(f"SID: {st.session_state.session_id[:8]}")


# ================================================
# MEOW CHATBOT (appears on every page)
# ================================================
def render_meow():
    # 🐱 Compact Bot Button (Bottom Right Floating)
    st.markdown("""
        <style>
        .meow-trigger {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 9999;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        .meow-trigger:hover {
            transform: scale(1.2) rotate(5deg);
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Toggle button using a columns-based placement as a fallback if fixed CSS is tricky with Streamlit
    welcome_col, btn_col = st.columns([5, 1.2])
    with btn_col:
        btn_label = "🐾 CLOSE" if st.session_state.chat_open else "🐱 BOT"
        if st.button(btn_label, key="meow_circle_toggle", width='stretch'):
            st.session_state.chat_open = not st.session_state.chat_open
            st.rerun()

    if not st.session_state.chat_open:
        return

    # Expanded Meow Window
    st.markdown('<div class="meow-container">', unsafe_allow_html=True)
    
    # Header (Simple - No Arrow)
    st.markdown("""
        <div class="meow-header">
            <span>🐾 ENTERPRISE MEOW</span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="meow-content">', unsafe_allow_html=True)

    # Intelligence & Vault Controls
    user_perms = ROLE_PERMS[USERS[st.session_state.username]["role"]]
    accessible_docs = [c for c in DOC_CARDS if user_perms["access_level"] >= c["min_access"]]
    doc_options = ["— Select a Vault Doc —"] + [f"{c['icon']} {c['title']}" for c in accessible_docs]
    
    routing_options = {
        "🧠 Smart Auto": "auto",
        "📚 Doc Intelligence": "docs",
        "📊 KPI Dashboard": "kpis",
        "🎫 IT Helpdesk": "helpdesk",
        "⚙️ Automation": "automation"
    }

    c_over1, c_over2 = st.columns(2)
    with c_over1:
        st.caption("🎯 Target Intelligence")
        selected_routing_label = st.selectbox("Intelligence Mode:", list(routing_options.keys()), key="meow_routing_select", label_visibility="collapsed")
        agent_override = routing_options[selected_routing_label]
    with c_over2:
        st.caption("📂 Vault Document")
        selected_doc = st.selectbox("📂 Vault Doc:", doc_options, key="meow_vault_select", label_visibility="collapsed")

    if selected_doc != "— Select a Vault Doc —":
        vault_actions = ["— Choose Action —", "Summarize", "Key Points", "Find Data"]
        vault_action = st.selectbox("Action:", vault_actions, key="meow_vault_action", label_visibility="collapsed")
        
        doc_idx = doc_options.index(selected_doc) - 1
        doc_card = accessible_docs[doc_idx]
        
        if vault_action != "— Choose Action —":
            if st.button(f"📖 {vault_action} → {doc_card['title']}", key="meow_vault_go", width='stretch'):
                action_prompts = {
                    "Summarize": f"Summarize this document in a clear executive summary",
                    "Key Points": f"Extract the top 5-7 key points and takeaways from this document",
                    "Find Data": f"List all important data points, numbers, metrics, and facts from this document",
                }
                with st.spinner(f"🐾 Meow is reading {doc_card['title']}..."):
                    result = vault_query(doc_card["file"], action_prompts[vault_action], agent_override=agent_override)
                st.session_state.messages.append({"role": "user", "content": f"📂 {vault_action}: {doc_card['title']}"})
                st.session_state.messages.append({"role": "assistant", "content": result["answer"]})
                st.session_state.chat_history_log.append({"role": "user", "content": f"📂 {vault_action}: {doc_card['title']}", "time": time.time()})
                st.session_state.chat_history_log.append({"role": "assistant", "content": result["answer"], "time": time.time()})
                st.session_state.total_queries += 1
                st.rerun()

    # Message Display
    height = 500 if st.session_state.chat_expanded else 280
    msg_box = st.container(height=height)
    with msg_box:
        if not st.session_state.messages:
            st.markdown("""<div style="text-align:center; padding:40px 20px; opacity:0.4;"><div style="font-size:3.5rem; margin-bottom:15px; filter: drop-shadow(0 0 10px rgba(217,30,91,0.3));">🐱</div><p style="font-size:0.95rem; font-weight:600;">System Ready.<br>Interactive Meow awaiting commands.</p></div>""", unsafe_allow_html=True)
        for msg in reversed(st.session_state.messages):
            cls = "msg-user" if msg["role"] == "user" else "msg-system"
            icon = "👤" if msg["role"] == "user" else "🐾"
            st.markdown(f"""
                <div class="{cls}">
                    <div style="font-size:0.65rem; opacity:0.6; font-weight:900; margin-bottom:4px; text-transform:uppercase;">{icon} {msg['role']}</div>
                    <div style="font-size:0.9rem;">{msg['content']}</div>
                </div>
            """, unsafe_allow_html=True)

    # Input Bar Alignment: [Input] [Submit] [Trash]
    with st.container():
        st.markdown('<div class="meow-footer">', unsafe_allow_html=True)
        c_in1, c_in2, c_in3 = st.columns([4.2, 0.8, 0.8])
        with c_in1:
            prompt = st.text_input("Ask Meow...", label_visibility="collapsed", placeholder="Enterprise command line...")
        with c_in2:
            if st.button("Submit →", key="meow_submit", width="stretch"):
                if prompt:
                    handle_query(prompt, agent_override=agent_override)
                    st.rerun()
        with c_in3:
            if st.button("🗑️", key="meow_clear_trash", help="Clear Meow Chat", width="stretch"):
                clear_meow_chat()
                st.toast("Meow session cleared.")
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div></div>', unsafe_allow_html=True)


# ================================================
# PAGE: DASHBOARD
# ================================================
def render_dashboard():
    user_perms = ROLE_PERMS[USERS[st.session_state.username]["role"]]

    st.markdown(f"""<h1 style="font-size:3rem; font-weight:800; margin-bottom:0;">Welcome, <span style="color:#D91E5B;">{st.session_state.username.title()}</span></h1>
        <p style="opacity:0.6; font-size:1rem; margin-top:0; margin-bottom:2rem;">KPMG PMO Intelligence Center</p>""", unsafe_allow_html=True)

    # KPIs
    m1, m2, m3, m4 = st.columns(4)
    from pathlib import Path
    try:
        raw_docs_count = len([f for f in Path("data/raw_docs").glob("*") if f.is_file() and not f.name.startswith(".")])
        kpi_docs_count = len([f for f in Path("data/KPI Data").glob("*") if f.is_file() and not f.name.startswith(".")])
        total_modules = raw_docs_count + kpi_docs_count
    except Exception:
        total_modules = 20 # Fallback
        
    kpis = [("Knowledge Modules", total_modules, "📚", "dash-kpi-1"), ("Clearance", f"L-{user_perms['access_level']}", "🔒", "dash-kpi-2"),
            ("Queries", st.session_state.total_queries, "🤖", "dash-kpi-3"), ("System", "Operational", "🛡️", "dash-kpi-4")]
    for i, (label, val, ic, cls) in enumerate(kpis):
        with [m1, m2, m3, m4][i]:
            st.markdown(f"""<div class="dash-kpi {cls}">
                <div style="color:rgba(255,255,255,0.6); font-size:0.7rem; font-weight:800; text-transform:uppercase; letter-spacing:1px; margin-bottom:8px;">{label}</div>
                <div style="font-size:1.8rem; font-weight:800; display:flex; align-items:center; gap:12px;">
                    <span>{ic}</span>
                    <span style="color:white; filter: drop-shadow(0 0 5px rgba(255,255,255,0.2));">{val}</span>
                </div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 1. ENCRYPTED DATA VAULT (first) ---
    st.markdown("<h3 style='font-weight:700;'>📂 Encrypted Data Vault</h3>", unsafe_allow_html=True)
    doc_cols = st.columns(3)
    for idx, card in enumerate(DOC_CARDS):
        with doc_cols[idx % 3]:
            has_access = user_perms['access_level'] >= card["min_access"]
            st.markdown(f"""<div class="vault-card {card['cls'] if has_access else ''}" style="opacity:{1 if has_access else 0.4}; background: {'' if has_access else 'rgba(255,255,255,0.02)'}; border-color: {'' if has_access else 'rgba(255,255,255,0.05)'};">
                <div style="font-size:2.8rem; margin-bottom:1rem; filter: drop-shadow(0 5px 15px rgba(0,0,0,0.3));">{card['icon']}</div>
                <h4 style="margin:0 0 0.5rem 0; font-weight:800; letter-spacing:-0.5px; color:white;">{card['title']}</h4>
                <p style="font-size:0.85rem; color:rgba(255,255,255,0.6); line-height:1.5;">{card['desc']}</p></div>""", unsafe_allow_html=True)
            if has_access:
                if st.button(f"Decrypt {card['title']}", key=f"btn_{idx}", width='stretch'):
                    st.session_state.viewing_doc = card["file"]
                    navigate_to("doc_viewer")
            else:
                st.button("Access Denied 🔒", key=f"lock_{idx}", disabled=True, width='stretch')

    # --- 2. CONNECTED AGENTS ---
    st.markdown("<br><h3 style='font-weight:700; margin-bottom:1rem;'>🧠 Connected Agents</h3>", unsafe_allow_html=True)
    agents_info = [
        ("�", "Retrieval Agent", "Document Q&A via RAG", "Online"),
        ("📊", "API Agent", "KPI & metric live fetch", "Online"),
        ("🎫", "Helpdesk Agent", "IT ticket operations", "Online"),
        ("⚙️", "Workflow Agent", "Automation & approvals", "Online"),
    ]
    agent_cols = st.columns(4)
    for i, (ag_icon, ag_name, ag_desc, ag_status) in enumerate(agents_info):
        with agent_cols[i]:
            is_allowed = ag_name in user_perms["agents"]
            opacity = "1" if is_allowed else "0.35"
            dot = "🟢" if is_allowed else "🔒"
            # Unified Section Border: Cyan/Blue (#00F5FF)
            border_color = "rgba(0, 245, 255, 0.4)" if is_allowed else "rgba(255, 255, 255, 0.05)"
            st.markdown(f"""<div class="agent-card" style="border:1px solid {border_color}; opacity:{opacity};">
                <div style="font-size:2.5rem; margin-bottom:0.8rem;">{ag_icon}</div>
                <div style="font-size:0.9rem; font-weight:800; color:white;">{ag_name.split(' ')[0]}</div>
                <div style="font-size:0.7rem; color:rgba(255,255,255,0.5); margin:8px 0; line-height:1.3;">{ag_desc}</div>
                <div style="font-size:0.7rem; padding:4px 10px; background:rgba(255,255,255,0.05); border-radius:20px; border:1px solid rgba(255,255,255,0.1); margin-top:8px;">{dot} {ag_status if is_allowed else "Locked"}</div></div>""", unsafe_allow_html=True)

    # --- 3. YOUR CAPABILITIES ---
    st.markdown("<br><h3 style='font-weight:700; margin-bottom:1rem;'>🎯 Your Capabilities</h3>", unsafe_allow_html=True)
    all_caps = [
        ("�", "Doc Query", user_perms["access_level"] >= 1),
        ("📊", "KPI Live", user_perms["access_level"] >= 2 or "API Agent" in user_perms["agents"]),
        ("🎫", "Helpdesk", True),
        ("⚙️", "Workflows", "Workflow Agent" in user_perms["agents"]),
        ("📋", "RAID Logs", user_perms["access_level"] >= 2),
        ("📤", "Doc Upload", True),
        ("🧠", "Vault Read", True),
        ("📧", "Email/Approval", "Workflow Agent" in user_perms["agents"]),
    ]
    cap_cols = st.columns(4)
    for i, (cap_ic, cap_name, cap_ok) in enumerate(all_caps):
        with cap_cols[i % 4]:
            # Unified Section Border: Slate Silver (Distinct but integrated)
            section_border = "rgba(200, 200, 220, 0.25)" if cap_ok else "rgba(255,255,255,0.05)"
            text_color = "#E0E0E6" if cap_ok else "rgba(255,255,255,0.2)"
            bg_color = "rgba(255, 255, 255, 0.05)" if cap_ok else "rgba(255,255,255,0.01)"
            st.markdown(f"""<div class="cap-card" style="border:1px solid {section_border}; background: {bg_color}; opacity:{1 if cap_ok else 0.4};">
                <div style="font-size:1.8rem; filter: drop-shadow(0 0 10px rgba(255,255,255,0.15)) grayscale({0 if cap_ok else 1});">{cap_ic}</div>
                <div style="font-size:0.8rem; font-weight:800; color:{text_color}; margin-top:8px; letter-spacing:0.5px;">{'✓ ' if cap_ok else '🔒 '}{cap_name}</div></div>""", unsafe_allow_html=True)

    # --- 4. RECENT ACTIVITY ---
    st.markdown("<br><h3 style='font-weight:700; margin-bottom:1rem;'>📜 Recent Activity</h3>", unsafe_allow_html=True)
    recent = st.session_state.chat_history_log[-10:] if st.session_state.chat_history_log else []
    if not recent:
        st.markdown("""<div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:2rem; text-align:center; opacity:0.4;">
            <div style="font-size:2.5rem; margin-bottom:10px;">📭</div>
            <p style="font-size:0.85rem;">No activity yet.<br>Use Meow or visit a feature page to get started.</p></div>""", unsafe_allow_html=True)
    else:
        for msg in reversed(recent):
            icon = "👤" if msg["role"] == "user" else "🐾"
            color = "#D91E5B" if msg["role"] == "assistant" else "#555"
            preview = msg["content"][:150] + ("..." if len(msg["content"]) > 150 else "")
            st.markdown(f"""<div style="background:rgba(255,255,255,0.03); border-left:3px solid {color}; border-radius:12px; padding:10px 14px; margin-bottom:8px;">
                <div style="font-size:0.6rem; opacity:0.4; font-weight:900;">{icon} {msg['role'].upper()}</div>
                <div style="font-size:0.85rem; line-height:1.3; margin-top:4px;">{preview}</div></div>""", unsafe_allow_html=True)
        if st.button("🗑️ Clear Record Log"):
            st.session_state.chat_history_log = []
            st.rerun()




# ================================================
# PAGE: DOC VIEWER
# ================================================
def render_doc_viewer():
    doc_file = st.session_state.viewing_doc
    full_path = DOC_BASE_PATH / doc_file
    st.markdown(f"### 📄 Decrypted Module: {doc_file}")
    if full_path.exists():
        html_content = full_path.read_bytes()
        b64_html = base64.b64encode(html_content).decode("utf-8")

        # Right-aligned Extract with format dropdown
        spacer, fmt_col, dl_col = st.columns([3, 1, 1])
        with fmt_col:
            export_fmt = st.selectbox("Format:", ["📁 Select Format ▼", "PDF", "Word (.docx)", "Excel (.xlsx)", "HTML"], key="export_format", label_visibility="collapsed")
        with dl_col:
            base_name = doc_file.rsplit(".", 1)[0]
            if export_fmt == "📁 Select Format ▼":
                st.button("📥 Extract", disabled=True, width='stretch')
            elif export_fmt == "HTML":
                with open(full_path, "rb") as f:
                    st.download_button("📥 Extract", data=f, file_name=doc_file, mime="text/html", width='stretch')
            else:
                fmt_map = {"PDF": "pdf", "Word (.docx)": "docx", "Excel (.xlsx)": "xlsx"}
                fmt_key = fmt_map[export_fmt]
                ext_map = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx"}
                try:
                    resp = requests.get(f"{BACKEND_URL}/convert/{doc_file}?format={fmt_key}", timeout=30)
                    if resp.status_code == 200:
                        st.download_button(
                            "📥 Extract",
                            data=resp.content,
                            file_name=f"{base_name}{ext_map[fmt_key]}",
                            mime=resp.headers.get("content-type", "application/octet-stream"),
                            width='stretch'
                        )
                    else:
                        st.error(f"Conversion failed: {resp.text}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        st.markdown(f"""<div style="background:rgba(255,255,255,0.05); border-radius:20px; overflow:hidden; border:1px solid rgba(255,255,255,0.1); height:75vh;">
            <iframe src="data:text/html;base64,{b64_html}" width="100%" height="100%" style="border:none; filter:invert(0.9) hue-rotate(180deg);"></iframe></div>""", unsafe_allow_html=True)
    else:
        st.error(f"Module '{doc_file}' offline.")


# ================================================
# PAGE: DOC QUERY
# ================================================
def render_doc_query():
    st.markdown("<h2>📄 Document Query</h2><p style='opacity:0.6;'>Ask questions about your project documents using the Retrieval Agent.</p>", unsafe_allow_html=True)

    query = st.text_input("🔍 Ask a question about your documents:", placeholder="e.g. What are the delivery risks in the Q3 report?")
    if st.button("Search Documents", width='content') and query:
        with st.spinner("🔎 Searching document index..."):
            result = call_backend(query)
        st.markdown(f"""<span style="border:1px solid #D91E5B; padding:2px 8px; border-radius:10px; font-size:0.7rem; color:#D91E5B;">{result.get('agent_used','Agent')}</span>""", unsafe_allow_html=True)
        st.markdown(result["answer"])
        if result.get("sources"):
            st.markdown(f"**Sources:** {', '.join(result['sources'])}")


# ================================================
# PAGE: KPI LIVE
# ================================================
def render_kpi_live():
    # --- 1. State Initialization ---
    if "active_kpi" not in st.session_state:
        st.session_state.active_kpi = None
    if "active_kpi_result" not in st.session_state:
        st.session_state.active_kpi_result = None

    st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem;">
            <div>
                <h1 style="font-size: 2.5rem; font-weight: 800; margin: 0;">📊 KPI <span style="color:#D91E5B;">Live</span></h1>
                <p style="opacity: 0.6; margin: 0;">Real-time project intelligence and performance tracking.</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- 2. KPI Grid (Stable) ---
    metrics = [
        ("📈", "Delivery Risk Score", "What is the delivery risk score?", "kpi-clr-1"),
        ("💰", "Budget Burn Rate", "What is the budget burn rate?", "kpi-clr-2"),
        ("🏃", "Sprint Velocity", "What is the sprint velocity?", "kpi-clr-3"),
        ("🎯", "Milestone Completion", "What is the milestone completion rate?", "kpi-clr-4"),
        ("📊", "Resource Utilisation", "What is the resource utilisation?", "kpi-clr-5"),
        ("⚠️", "Open Risk Items", "How many open risk items are there?", "kpi-clr-6"),
        ("🎫", "Helpdesk Tickets", "How many helpdesk tickets are open?", "kpi-clr-7"),
        ("😊", "Stakeholder Satisfaction", "What is the stakeholder satisfaction score?", "kpi-clr-8"),
        ("📋", "Project Summary", "Give me a project summary", "kpi-clr-9"),
        ("👥", "Team Performance", "Show team performance metrics", "kpi-clr-10"),
        ("💵", "Budget Details", "Show budget details", "kpi-clr-11"),
        ("🔄", "Jira Sprints", "Show current Jira sprints", "kpi-clr-12"),
    ]

    # Only show grid if no KPI is active, or show a minimized version?
    # Actually, keeping the grid stable means keeping it visible but manageable.
    
    cols = st.columns(4) # 4 columns for a cleaner grid
    for idx, (ic, title, query, cls) in enumerate(metrics):
        with cols[idx % 4]:
            is_active = st.session_state.active_kpi == title
            # Premium Card UI via Markdown
            st.markdown(f"""
                <div class="kpi-card-new {cls if not is_active else ''}" style="border-color: {'#D91E5B' if is_active else ''} !important; background: {'rgba(217, 30, 91, 0.1)' if is_active else ''} !important;">
                    <span class="kpi-icon" style="filter: drop-shadow(0 0 10px rgba(255,255,255,0.2));">{ic}</span>
                    <p class="kpi-label" style="background: linear-gradient(90deg, #fff, #aaa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{title}</p>
                </div>
            """, unsafe_allow_html=True)
            
            # Midnight Hover Button Wrapper
            st.markdown('<div class="kpi-btn-midnight">', unsafe_allow_html=True)
            if st.button(f"Select {title}", key=f"kpi_btn_{idx}", width='stretch', help=f"Fetch {title}"):
                st.session_state.active_kpi = title
                with st.spinner(f"🐾 Meow is fetching {title}..."):
                    result = call_backend(query)
                    st.session_state.active_kpi_result = result
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # --- 3. Centralized Result Area ---
    if st.session_state.active_kpi and st.session_state.active_kpi_result:
        res = st.session_state.active_kpi_result
        st.markdown(f"""
            <div class="result-container">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem;">
                    <div>
                        <h3 style="margin: 0; font-weight: 800; color: #D91E5B;">🔍 {st.session_state.active_kpi} Analysis</h3>
                        <p style="font-size: 0.75rem; opacity: 0.5; margin-top: 4px;">Source: {", ".join(res.get('sources', []))}</p>
                    </div>
                </div>
                <div style="color: white; line-height: 1.6;">
        """, unsafe_allow_html=True)
        
        # Streamlit markdown inside the result container (needs careful handling)
        st.markdown(res["answer"])
        
        # Close Button
        if st.button("✖️ Clear Results", key="clear_kpi_results"):
            st.session_state.active_kpi = None
            st.session_state.active_kpi_result = None
            st.rerun()
            
        st.markdown("</div></div>", unsafe_allow_html=True)


# ================================================
# PAGE: HELPDESK
# ================================================
def render_helpdesk():
    st.markdown("<h2>🎫 IT Helpdesk</h2><p style='opacity:0.6;'>Manage IT support tickets via ServiceNow.</p>", unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋 View Tickets", "➕ Create Ticket", "🔍 Check Status"])

    with tab1:
        header_col, btn_col = st.columns([3, 1])
        with header_col:
            st.markdown("### 📋 View Tickets")
        with btn_col:
            st.markdown(f'<a href="{BACKEND_URL}/download/tracker/tickets" target="_blank"><button style="width:100%; padding:0.4rem; background:#4CAF50; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.8rem;">📥 Download Excel</button></a>', unsafe_allow_html=True)
            
        if "show_tickets" not in st.session_state:
            st.session_state.show_tickets = False

        if st.button("🔄 Refresh Tickets", key="refresh_tickets"):
            st.session_state.show_tickets = True
            st.rerun()

        if st.session_state.show_tickets:
            with st.spinner("Loading tickets..."):
                data = fetch_get("/tickets")
            if "error" in data:
                st.error(f"Could not fetch tickets: {data['error']}")
            else:
                tickets = data.get("tickets", [])
                if tickets:
                    df = pd.DataFrame(tickets)
                    # Reorder and rename for better display
                    cols = ["number", "short_description", "state", "priority", "sys_created_on"]
                    df = df[[c for c in cols if c in df.columns]]
                    df.columns = [c.replace("_", " ").title() for c in df.columns]
                    
                    st.dataframe(df, width='stretch', hide_index=True)
                else:
                    st.info("No tickets found.")
        else:
            st.info("💡 Click **Refresh Tickets** to load the latest tracking data from ServiceNow.")

    with tab2:
        st.markdown("**Describe your issue and a ticket will be created:**")
        issue = st.text_area("Issue description:", placeholder="e.g. My laptop cannot connect to VPN...")
        
        # Make the urgency bar shorter using columns and a horizontal radio
        urg_col, _ = st.columns([1, 2])
        with urg_col:
            urgency = st.radio("Urgency", options=["Low", "Medium", "High"], index=1, horizontal=True)
            
        if st.button("🎫 Create Ticket", key="create_ticket") and issue:
            with st.spinner("Creating ticket..."):
                result = call_backend(f"Create a helpdesk ticket: {issue}. Urgency: {urgency}")
            st.success("Ticket submitted!")
            st.markdown(result["answer"])

    with tab3:
        ticket_num = st.text_input("Ticket Number:", placeholder="e.g. INC0010001")
        if st.button("🔍 Check", key="check_ticket") and ticket_num:
            with st.spinner("Checking..."):
                result = call_backend(f"Check status of ticket {ticket_num}")
            st.markdown(result["answer"])


# ================================================
# PAGE: WORKFLOWS
# ================================================
def render_workflows():
    st.markdown("<h2>⚙️ Workflow Automation</h2><p style='opacity:0.6;'>Execute automated workflows via the Workflow Agent.</p>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🟢 Onboarding", "🔴 Offboarding", "🏷️ Tagging", "✅ Approval", "❌ Cancel Request"])

    with tab1:
        st.markdown("### Employee Onboarding")
        name = st.text_input("Employee Name:", key="onb_name", placeholder="e.g. John Smith")
        role = st.text_input("Role:", key="onb_role", placeholder="e.g. Data Analyst")
        date = st.date_input("Start Date:", key="onb_date")
        if st.button("🚀 Start Onboarding", key="onb_go") and name:
            with st.spinner("Processing onboarding..."):
                result = call_backend(f"Onboard new employee: {name}, role: {role}, start date: {date}")
            st.markdown(result["answer"])

    with tab2:
        st.markdown("### Employee Offboarding")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            emp_id_input = st.text_input("EMP ID:", key="off_emp_id", placeholder="e.g. EMP-2412100815")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True) # padding
            if st.button("🔍 Fetch Details", key="fetch_off_details", width='stretch'):
                if emp_id_input:
                    with st.spinner("Fetching..."):
                        resp = fetch_get(f"/onboarding/{emp_id_input}")
                        if "error" in resp:
                            st.error(f"Could not fetch: {resp['error']}")
                        else:
                            st.session_state.off_name = resp.get("employee", "")
                            st.session_state.off_role = resp.get("role", "")
                            st.session_state.off_start_date = resp.get("start_date", "")
                            st.success("Details loaded!")
                            
        name = st.text_input("Employee Name:", key="off_name", placeholder="e.g. Jane Doe")
        role = st.text_input("Role:", key="off_role", placeholder="e.g. Data Analyst")
        reason = st.text_input("Reason:", key="off_reason", placeholder="e.g. Resignation")
        date = st.date_input("Last Day:", key="off_date")
        
        if st.button("🔴 Start Offboarding", key="off_go") and name and emp_id_input:
            # Date Validation: Offboarding date MUST be > Onboarding date
            start_date_str = st.session_state.get("off_start_date", "")
            if start_date_str:
                from datetime import datetime
                try:
                    start_df = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    if date <= start_df:
                        st.error(f"Validation Error: Offboarding date ({date}) must be strictly AFTER the Onboarding Date ({start_df}).")
                        st.stop()
                except ValueError:
                    pass # Ignore if format varies
            
            with st.spinner("Processing offboarding..."):
                result = call_backend(f"Offboard employee with EMP ID {emp_id_input}: {name}, role: {role}, reason: {reason}, last day: {date}")
            st.markdown(result["answer"])

    with tab3:
        st.markdown("### Resource Tagging")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            tag_emp_id = st.text_input("EMP ID:", key="tag_emp_id", placeholder="e.g. EMP-2412100815")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True) # padding
            if st.button("🔍 Fetch Details", key="fetch_tag_details", width='stretch'):
                if tag_emp_id:
                    with st.spinner("Fetching..."):
                        resp = fetch_get(f"/onboarding/{tag_emp_id}")
                        if "error" in resp:
                            st.error(f"Could not fetch: {resp['error']}")
                        else:
                            st.session_state.tag_name = resp.get("employee", "")
                            st.session_state.tag_role = resp.get("role", "")
                            st.session_state.tag_project = resp.get("project", "")
                            st.success("Details loaded!")
        
        resource = st.text_input("Resource Name:", key="tag_name", value=st.session_state.get("tag_name", ""), placeholder="e.g. Alice Chen")
        tag_role = st.text_input("Role/Tag:", key="tag_role", value=st.session_state.get("tag_role", ""), placeholder="e.g. Lead Developer")
        from_project = st.text_input("Current Project:", key="tag_project", value=st.session_state.get("tag_project", ""), placeholder="e.g. Alpha")
        to_project = st.text_input("New Project:", key="tag_new_project", placeholder="e.g. Phoenix Migration")
        
        if st.button("🏷️ Tag Resource", key="tag_go") and resource and tag_emp_id:
            with st.spinner("Tagging resource..."):
                result = call_backend(f"Tag resource {resource} (EMP ID {tag_emp_id}) from {from_project} to project {to_project} as {tag_role}")
            st.markdown(result["answer"])

    with tab4:
        st.markdown("### Manager Approval (via Outlook)")
        subject = st.text_input("Approval Subject:", key="appr_subject", placeholder="e.g. Budget increase for Q4")
        manager = st.text_input("Manager Email:", key="appr_manager", placeholder="e.g. manager@kpmg.com")
        details = st.text_area("Details:", key="appr_details", placeholder="Describe what needs approval...")
        if st.button("✅ Send Approval", key="appr_go") and subject:
            with st.spinner("Sending approval request..."):
                result = call_backend(f"Send approval request to {manager} for: {subject}. Details: {details}")
            st.markdown(result["answer"])
            
    with tab5:
        st.markdown("### Cancel an Active Request")
        st.info("**Timeline Notice**: Requests can only be cancelled within **3 business days** of being raised.", icon="ℹ️")
        
        req_type = st.selectbox("Request Type to Cancel", ["Onboarding", "Offboarding", "Tagging"], key="cancel_type")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            cancel_emp_id = st.text_input("Target EMP ID:", key="cancel_emp_id", placeholder="e.g. EMP-2412100815")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 Fetch Details", key="fetch_cancel_details", width='stretch'):
                if cancel_emp_id:
                    with st.spinner("Fetching..."):
                        resp = fetch_get(f"/onboarding/{cancel_emp_id}")
                        if "error" in resp:
                            st.error(f"Could not fetch: {resp['error']}")
                        else:
                            st.session_state.cancel_name = resp.get("employee", "")
                            st.session_state.cancel_role = resp.get("role", "")
                            st.success("Details loaded!")
        
        # Display the loaded details (disabled inputs so user can verify)
        st.text_input("Employee Name:", key="cancel_name_display", value=st.session_state.get("cancel_name", ""), disabled=True)
        st.text_input("Role:", key="cancel_role_display", value=st.session_state.get("cancel_role", ""), disabled=True)
        
        if st.button("Cancel Request", key="cancel_go", help="Cancels the request if within the 3 day window.") and cancel_emp_id:
            with st.spinner("Processing cancellation via Workflow Agent..."):
                result = call_backend(f"Cancel the {req_type} request for EMP ID: {cancel_emp_id}")
            st.markdown(result["answer"])

    st.markdown("---")
    st.markdown("### 📥 Download Trackers")
    st.markdown("Download the latest master Excel records.")
    d_col1, d_col2, d_col3 = st.columns(3)
    
    with d_col1:
        st.markdown(f'<a href="{BACKEND_URL}/download/tracker/onboarding" target="_blank"><button style="width:100%; padding:0.5rem; background:#005EB8; color:white; border:none; border-radius:4px; cursor:pointer;">🟢 Download Onboarding</button></a>', unsafe_allow_html=True)
    with d_col2:
        st.markdown(f'<a href="{BACKEND_URL}/download/tracker/offboarding" target="_blank"><button style="width:100%; padding:0.5rem; background:#D91E5B; color:white; border:none; border-radius:4px; cursor:pointer;">🔴 Download Offboarding</button></a>', unsafe_allow_html=True)
    with d_col3:
        st.markdown(f'<a href="{BACKEND_URL}/download/tracker/tagging" target="_blank"><button style="width:100%; padding:0.5rem; background:#8A2BE2; color:white; border:none; border-radius:4px; cursor:pointer;">🏷️ Download Tagging</button></a>', unsafe_allow_html=True)


# ================================================
# PAGE: RAID & LOGS
# ================================================
def render_logs():
    st.markdown("<h2>📋 RAID & System Logs</h2><p style='opacity:0.6;'>View RAID log entries and query system logs.</p>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 RAID Logs", "🖥️ System Logs"])

    with tab1:
        header_col, btn_col = st.columns([3, 1])
        with header_col:
            st.markdown("### 📋 Recent RAID Logs")
        with btn_col:
            st.markdown(f'<a href="{BACKEND_URL}/download/tracker/raid" target="_blank"><button style="width:100%; padding:0.4rem; background:#4CAF50; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.8rem;">📥 Download Excel</button></a>', unsafe_allow_html=True)
            
        if st.button("🔄 Refresh RAID Logs", key="refresh_logs"):
            st.session_state.show_raid_logs = True
            
        if st.session_state.get("show_raid_logs", False):
            with st.spinner("Loading RAID logs..."):
                data = fetch_get("/logs")
            if "error" in data:
                st.error(f"Could not fetch RAID logs: {data['error']}")
            else:
                logs = data.get("logs", [])
                if logs:
                    df = pd.DataFrame(logs)
                    
                    # Reorder columns appropriately
                    cols = ["log_id", "type", "title", "description", "owner", "status", "impact", "project", "created_at"]
                    df = df[[c for c in cols if c in df.columns]]
                    df.columns = [c.replace("_", " ").title() for c in df.columns]
                    
                    st.markdown("### Top 10 Recent RAID Entries")
                    st.dataframe(df.head(10), width='stretch', hide_index=True)
                    st.info("ℹ️ For additional entries and complete log details, please download the Excel file to your local system.")
                else:
                    st.info("No RAID logs found.")
        else:
            st.info("Click **Refresh RAID Logs** to fetch the latest tracking data.")

    with tab2:
        header_col, btn_col = st.columns([3, 1])
        with header_col:
            st.markdown("### 🖥️ Recent System Logs")
        with btn_col:
            st.markdown(f'<a href="{BACKEND_URL}/download/logs/txt" target="_blank"><button style="width:100%; padding:0.4rem; background:#2196F3; color:white; border:none; border-radius:4px; cursor:pointer; font-size:0.8rem;">📥 Download (TXT)</button></a>', unsafe_allow_html=True)
            
        if st.button("🔄 Refresh System Logs", key="refresh_sys_logs"):
            st.session_state.show_system_logs = True
            
        if st.session_state.get("show_system_logs", False):
            with st.spinner("Loading system logs..."):
                data = fetch_get("/logs/system")
            if "error" in data:
                st.error(f"Could not fetch system logs: {data['error']}")
            else:
                logs = data.get("logs", [])
                if logs:
                    df = pd.DataFrame(logs)
                    # Show meaningful columns
                    cols = ["timestamp", "log_level", "service_name", "action", "status", "response_time_ms"]
                    df = df[[c for c in cols if c in df.columns]]
                    df.columns = [c.replace("_", " ").title() for c in df.columns]
                    
                    st.markdown("### Recent System Activity")
                    st.dataframe(df, width='stretch', hide_index=True)
                else:
                    st.info("No system logs found.")
        else:
            st.info("Click **Refresh System Logs** to fetch the latest activity from the server.")

        st.markdown("---")
        st.markdown("**Search or Summarize Logs via AI:**")
        log_query = st.text_input("Log query:", placeholder="e.g. Show error logs from the last 24 hours")
        if st.button("🔍 Query via LLM", key="query_logs") and log_query:
            with st.spinner("Querying system logs..."):
                result = call_backend(f"Query system logs: {log_query}")
            st.markdown(result["answer"])


# ================================================
# PAGE: DOC UPLOAD
# ================================================
def render_doc_upload():
    st.markdown("<h2>📤 Document Upload & Fetch</h2><p style='opacity:0.6;'>Upload project documents for AI-powered Q&A.</p>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload a document:", type=["pdf", "docx", "xlsx", "csv", "txt", "pptx", "md"], key="doc_uploader")
    if uploaded_file and st.button("📤 Upload & Index", key="upload_go"):
        with st.spinner(f"Uploading {uploaded_file.name}..."):
            try:
                resp = requests.post(f"{BACKEND_URL}/upload",
                                     files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                                     data={"session_id": st.session_state.session_id}, timeout=60)
                if resp.status_code == 200:
                    st.success(f"✅ {uploaded_file.name} uploaded and indexed!")
                    st.json(resp.json())
                else:
                    st.error(f"Upload failed: {resp.text}")
            except Exception as e:
                st.error(f"Upload error: {str(e)}")

    st.markdown("---")
    st.markdown("### 🔍 Query Uploaded Docs")
    q_col1, q_col2 = st.columns([4, 1])
    with q_col1:
        u_query = st.text_input("Ask a question about your uploaded files:", key="upload_query_input", placeholder="e.g. Extract all delivery dates, or Summarize the executive summary section")
    with q_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        q_btn = st.button("Query Files", key="upload_query_go", width='stretch')
    
    if q_btn and u_query:
        with st.spinner("🤖 Analyzing uploaded documents..."):
            result = call_backend(u_query, upload_only=True)
        st.markdown(f"""<div style="background:rgba(217,30,91,0.05); border:1px solid rgba(217,30,91,0.2); border-radius:16px; padding:1.5rem; margin-top:1rem;">
            <div style="font-size:0.7rem; color:#D91E5B; font-weight:800; margin-bottom:8px;">AI RESPONSE ({result.get('agent_used','Agent')})</div>
            {result['answer']}
        </div>""", unsafe_allow_html=True)
        if result.get("sources"):
             st.caption(f"Sources: {', '.join(result['sources'])}")

    st.markdown("---")
    st.markdown("### 📁 Uploaded Files")
    if st.button("🔄 Refresh File List", key="refresh_files"):
        st.rerun()
    with st.spinner("Loading..."):
        stats = fetch_get(f"/upload/files?session_id={st.session_state.session_id}")
    
    if "error" in stats:
        st.warning(f"Could not fetch files: {stats['error']}")
    else:
        filenames = stats.get("filenames", [])
        if filenames:
            file_df = pd.DataFrame({"Filename": filenames, "Status": ["Indexed" for _ in filenames]})
            st.table(file_df)
        else:
            st.info("No files uploaded for this session yet.")

    st.markdown("---")
    if st.button("🗑️ Clear All Uploaded Docs", key="clear_uploads", width='stretch'):
        try:
            requests.post(f"{BACKEND_URL}/upload/clear", data={"session_id": st.session_state.session_id})
            st.success("All uploaded documents cleared.")
            st.rerun()
        except Exception as e:
            st.error(str(e))


# ================================================
# MAIN ROUTER
# ================================================
if not st.session_state.logged_in:
    render_dynamic_background()
    render_login()
else:
    render_sidebar()

    # Meow toggle in top-right
    render_meow()

    # Page routing
    page = st.session_state.current_page
    if page == "dashboard":
        render_dashboard()
    elif page == "doc_viewer":
        render_doc_viewer()
    elif page == "doc_query":
        render_doc_query()
    elif page == "kpi_live":
        render_kpi_live()
    elif page == "helpdesk":
        render_helpdesk()
    elif page == "workflows":
        render_workflows()
    elif page == "logs":
        render_logs()
    elif page == "doc_upload":
        render_doc_upload()
    else:
        render_dashboard()