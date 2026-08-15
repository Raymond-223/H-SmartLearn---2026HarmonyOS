"""Start the competition backend on all host interfaces.

This entry point avoids the common simulator failure caused by starting Uvicorn
on 127.0.0.1 only. The HarmonyOS emulator reaches the host through 10.0.2.2.
"""
from __future__ import annotations

import socket
import uvicorn


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


if __name__ == "__main__":
    print("=" * 64)
    print("H-SmartLearn backend")
    print("Host browser:       http://127.0.0.1:8000/health")
    print("HarmonyOS emulator: http://10.0.2.2:8000/health")
    print(f"HarmonyOS device:   http://{local_ip()}:8000/health")
    print("If the emulator cannot connect, allow TCP port 8000 in the firewall.")
    print("=" * 64)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
