#!/bin/bash

# First try the enhanced fix_leveling_settings (non-destructive) approach
echo "Checking/fixing leveling_settings table..."
python fix_leveling_settings.py --ensure

# If that failed, try the reset_leveling_settings as a fallback
if [ $? -ne 0 ]; then
    echo "Non-destructive approach failed, fallback to table reset..."
    python reset_leveling_settings.py
fi

# Start the bot
echo "Starting Discord bot..."
python main.py