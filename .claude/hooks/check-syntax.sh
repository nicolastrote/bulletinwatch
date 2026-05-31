#!/bin/bash
# Vérifie la syntaxe Python après chaque Write/Edit
FILE="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"
if [[ "$FILE" == *.py ]]; then
    python3 -m py_compile "$FILE" 2>/tmp/bulletinwatch-pycheck.log
    if [ $? -eq 0 ]; then
        echo "[bulletinwatch] syntax OK: $FILE"
    else
        echo "[bulletinwatch] SYNTAX ERROR: $FILE"
        cat /tmp/bulletinwatch-pycheck.log
    fi
fi
