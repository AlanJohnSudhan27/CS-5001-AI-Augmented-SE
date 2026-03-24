#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uvicorn
from agents.orchestrator import OrchestratorAgent
from config import ORCHESTRATOR_PORT

agent = OrchestratorAgent()

if __name__ == "__main__":
    print(f"Orchestrator agent on http://localhost:{ORCHESTRATOR_PORT}")
    uvicorn.run(agent.app, host="0.0.0.0", port=ORCHESTRATOR_PORT)
