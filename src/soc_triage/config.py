import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"

USERS_CSV = DATA_DIR / "users.csv"
IP_REPUTATION_CSV = DATA_DIR / "ip_reputation.csv"
ALERTS_CSV = DATA_DIR / "alerts.csv"
POLICY_MD = DATA_DIR / "security_triage_policy.md"

CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-5.6-luna")
CHAT_REASONING_EFFORT = os.getenv("CHAT_REASONING_EFFORT", "none")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4o-mini")

TOOL_CALL_LIMIT = 5

PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
PUSHOVER_USER = os.getenv("PUSHOVER_USER")
