#!/bin/bash
# HIUH Cron Job - jobbar på självkompilering var 5:e minut
cd /home/karl/.openclaw/workspace/hiuh-repo

LOG="/tmp/hiuh-cron.log"
echo "=== $(date) ===" >> $LOG

# Hämta senaste kod
git pull --quiet 2>&1 >> $LOG

# Kompilera test-programmet
python3 native/hiuh-native.py hiuh-tokenizer.hiuh /tmp/hiuh-test-bin >> $LOG 2>&1
if [ $? -eq 0 ]; then
    echo "Kompilering: OK" >> $LOG
else
    echo "Kompilering: FEL" >> $LOG
fi

# Kör test om det finns
echo "" >> $LOG
