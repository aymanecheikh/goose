#!/usr/bin/env python3
"""Install a user-owned, loopback-only Ollama service with conservative limits."""

import os
from pathlib import Path
import plistlib
import subprocess
import sys

if sys.platform != "darwin":
    raise SystemExit("This service setup targets macOS.")

home = Path.home()
binary = Path("/Applications/Ollama.app/Contents/Resources/ollama")
if not binary.exists():
    raise SystemExit("Install the official Ollama macOS app first.")

label = "io.github.aymanecheikh.ollama-local"
domain = f"gui/{os.getuid()}"
logs = home / "Library/Logs/Ollama-local"
logs.mkdir(parents=True, exist_ok=True)
agent = home / f"Library/LaunchAgents/{label}.plist"
agent.parent.mkdir(parents=True, exist_ok=True)
config = {
    "Label": label,
    "ProgramArguments": [str(binary), "serve"],
    "EnvironmentVariables": {
        "OLLAMA_HOST": "127.0.0.1:11434",
        "OLLAMA_MAX_LOADED_MODELS": "1",
        "OLLAMA_NUM_PARALLEL": "1",
        "OLLAMA_KEEP_ALIVE": "2m",
        "OLLAMA_CONTEXT_LENGTH": "16384",
    },
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 10,
    "WorkingDirectory": str(home),
    "StandardOutPath": str(logs / "server.stdout.log"),
    "StandardErrorPath": str(logs / "server.stderr.log"),
}

agent.write_bytes(plistlib.dumps(config))
agent.chmod(0o644)
# Only one service should own the Ollama port. This replaces its app login launcher.
subprocess.run(["launchctl", "disable", f"{domain}/com.ollama.ollama"], check=True)
subprocess.run(["launchctl", "bootout", f"{domain}/com.ollama.ollama"], capture_output=True)
subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], capture_output=True)
subprocess.run(["launchctl", "enable", f"{domain}/{label}"], check=True)
subprocess.run(["launchctl", "bootstrap", domain, str(agent)], check=True)
print(f"Installed {label}; Ollama will run on login with a one-model limit.")
