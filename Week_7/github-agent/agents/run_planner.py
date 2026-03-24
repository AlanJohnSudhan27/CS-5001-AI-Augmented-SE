#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uvicorn
from agents.planner import PlannerAgent
from config import PLANNER_PORT

agent = PlannerAgent()

if __name__ == "__main__":
    print(f"Planner agent on http://localhost:{PLANNER_PORT}")
    uvicorn.run(agent.app, host="0.0.0.0", port=PLANNER_PORT)
