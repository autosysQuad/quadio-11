#!/bin/bash

CONFIG_FILE="/usr/configuration/config/system-configuration.aispl"

TIME_UPDATE=$(grep '"timeUpdate"' "$CONFIG_FILE" | sed -E 's/.*"timeUpdate" *: *"([^"]*)".*/\1/')

if [ "$TIME_UPDATE" = "local" ]; then
    API_URL=$(grep '"localTimeApi"' "$CONFIG_FILE" | sed -E 's/.*"localTimeApi" *: *"([^"]*)".*/\1/' | tr -d ' ')

    if [ -n "$API_URL" ]; then
        TIME=$(curl  --connect-timeout 2 -s "$API_URL")

        if [ -n "$TIME" ]; then
            sudo date -s "$TIME"
            echo "System date and time updated to: $TIME"
        else
            echo "Failed to fetch date-time from API: $API_URL"
        fi
    else
        echo "localTimeApi not found in the configuration file."
    fi
else
    echo "timeUpdate is not set to 'local'. Skipping time synchronization."
fi
