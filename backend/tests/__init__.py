"""Test suite for FairCart AI.

Ensures that automated unit and integration tests run hermetically against
isolated local test databases rather than mutating or depending on remote
cloud databases (such as Neon PostgreSQL) configured in local .env files.
"""

import os
from backend.app.config import settings

# Isolate automated tests from remote cloud databases
os.environ["DATABASE_URL"] = ""
settings.DATABASE_URL = ""
