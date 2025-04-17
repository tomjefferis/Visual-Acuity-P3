#!/bin/bash

# Create a conda environment named '.conda' with Python 3.10
conda create --name .conda python=3.10 -y

# Activate the newly created environment
source activate .conda

# Install the dependencies from requirements.txt
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt not found. Please make sure it exists in the current directory."
    exit 1
fi

echo "Conda environment '.conda' setup complete with Python 3.10 and requirements installed."