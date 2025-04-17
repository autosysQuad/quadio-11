#!/bin/bash

# Path to the file
file="/etc/udev/rules.d/10-usb-serial.rules"

# Content to be added to the file
content='
SUBSYSTEM=="tty", KERNELS=="1-1.1.2", SYMLINK+="ttyUSB_X1"
SUBSYSTEM=="tty", KERNELS=="1-1.1.3", SYMLINK+="ttyUSB_X2"
SUBSYSTEM=="tty", KERNELS=="1-1.3", SYMLINK+="ttyUSB_X3"
SUBSYSTEM=="tty", KERNELS=="1-1.2", SYMLINK+="ttyUSB_X4"
'

# Check if the file exists
if [ -e "$file" ]; then
    # File exists, ask the user if they want to override it
    echo "USB rules already exists."
    read -p "Do you want to override it? (y/n): " choice

    if [[ "$choice" == "y" || "$choice" == "Y" ]]; then
        # User chose to override, perform the file update
        echo "Updating rules..."
        # echo "$content" > "$file"
        echo "Rules updated successfully."
    else
        # User chose not to override, exit the script
        echo "Exiting without updating the rules."
        exit 0
    fi
else
    # File doesn't exist, create it and add the content
    echo "Creating the rules..."
    echo "$content" > "$file"
    echo "Rules created successfully."
fi

# Trigger udev to apply changes
echo "applying rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "changes done successfully."
