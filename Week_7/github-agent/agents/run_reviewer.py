#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import uvicorn
from agents.reviewer import ReviewerAgent
from config import REVIEWER_PORT

agent = ReviewerAgent()

if __name__ == "__main__":
    print(f"Reviewer agent on http://localhost:{REVIEWER_PORT}")
    uvicorn.run(agent.app, host="0.0.0.0", port=REVIEWER_PORT)
