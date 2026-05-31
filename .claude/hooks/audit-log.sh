#!/bin/bash
# Audit log — adapté d'Orbit
echo "[bulletinwatch] $(date '+%H:%M:%S') ${CLAUDE_HOOK_EVENT:-EVENT}: ${CLAUDE_TOOL_INPUT_FILE_PATH:-${CLAUDE_TOOL_INPUT_COMMAND:0:80}}" >> /tmp/bulletinwatch-audit.log
