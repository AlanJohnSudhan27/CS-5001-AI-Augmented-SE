"""
LocalClaw Gateway Orchestrator
===============================
Runs all gateways simultaneously.

  python gateway.py            ← start all three
  python email_gateway.py      ← start email only   (port 5000)
  python github_gateway.py     ← start GitHub only  (port 5001)
  python canvas_gateway.py     ← start Canvas only  (port 5002)
"""

import threading
import email_gateway
import github_gateway
import canvas_gateway


def main():
    print("\n" + "═" * 60)
    print("  🦞  LocalClaw — Starting all gateways")
    print("═" * 60)
    print("     Email  → http://127.0.0.1:5000")
    print("     GitHub → http://127.0.0.1:5001")
    print("     Canvas → http://127.0.0.1:5002")
    print()

    t_email  = threading.Thread(target=email_gateway.run,  daemon=True, name="email-gateway")
    t_github = threading.Thread(target=github_gateway.run, daemon=True, name="github-gateway")
    t_canvas = threading.Thread(target=canvas_gateway.run, daemon=True, name="canvas-gateway")

    t_email.start()
    t_github.start()
    t_canvas.start()

    t_email.join()
    t_github.join()
    t_canvas.join()


if __name__ == "__main__":
    main()
