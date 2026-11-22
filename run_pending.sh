#!/usr/bin/env bash
cd "/home/modise/Desktop/data science/Data Engineering/warehouse project" || exit 1

exec 9>.sales_load.lock
/usr/bin/flock -n -E 75 9
lock_status=$?

if [ "$lock_status" -eq 75 ]; then
    echo "Skipped: another pending load is running." >> load.log
    exit 0
elif [ "$lock_status" -ne 0 ]; then
    exit "$lock_status"
fi

/home/modise/anaconda3/bin/python load.py --pending >> load.log 2>&1
