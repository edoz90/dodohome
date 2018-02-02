#!/usr/bin/sh
#

if ps -ef | rg -v rg | rg -v nvim | rg main_r.py; then
  exit 0
else
  date >> /tmp/main.log
  /home/dodohome/.venv3/bin/python -O /home/dodohome/dododisplay/main_r.py >> /tmp/main.log
fi
