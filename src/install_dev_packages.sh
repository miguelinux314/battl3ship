#!/bin/bash

# Install packages needed for development


sudo apt -y install npm nodejs-legacy

sudo npm install -g less

sudo ln -s ·$(which nodejs) /usr/bin/node