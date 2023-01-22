#!/bin/bash

# Setup venv
python3 -m venv venv
# Activate venv
source venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Deactivate venv
deactivate
