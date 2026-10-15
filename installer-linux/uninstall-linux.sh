#!/usr/bin/env bash
# c3resume: put every original game file back and remove the save helper.   bash uninstall-linux.sh
cd "$(dirname "$(readlink -f "$0")")" || exit 1
python3 c3resume.py uninstall "$@"
