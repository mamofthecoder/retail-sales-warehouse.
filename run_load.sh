#!/usr/bin/env bash
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 BATCH_ID" >&2
    exit 1
fi
cd "/home/modise/Desktop/data science/Data Engineering/warehouse project" || exit 1
/home/modise/anaconda3/bin/python load.py --batch-id "$1" >> load.log 2>&1

