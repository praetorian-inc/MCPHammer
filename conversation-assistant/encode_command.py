#!/usr/bin/env python3
import sys
import base64

if len(sys.argv) < 2:
    print("Usage: python encode_command.py 'command to encode'")
    sys.exit(1)

command = sys.argv[1]
encoded = base64.b64encode(command.encode()).decode().rstrip('=')
slack_message = f"Status update for project-{encoded}"

print(f"Command: {command}")
print(f"Encoded: {encoded}")
print(f"Slack message: {slack_message}")
