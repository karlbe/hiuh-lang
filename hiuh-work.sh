#!/bin/bash
# HIUH Cron Job - jobbar på självkompilering var 5:e minut
cd /home/karl/.openclaw/workspace/hiuh-repo
git pull --quiet 2>/dev/null
# Läs TODO.md och gör nästa item
echo "HIUH cron: TODO-check" >> /tmp/hiuh-cron.log
