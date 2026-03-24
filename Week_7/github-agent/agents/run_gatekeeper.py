#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uvicorn
from agents.gatekeeper import GatekeeperAgent
from config import GATEKEEPER_PORT

agent = GatekeeperAgent()

if __name__ == "__main__":
    print(f"Gatekeeper agent on http://localhost:{GATEKEEPER_PORT}")
    uvicorn.run(agent.app, host="0.0.0.0", port=GATEKEEPER_PORT)
