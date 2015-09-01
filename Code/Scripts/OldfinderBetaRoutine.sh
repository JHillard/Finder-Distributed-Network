#!/bin/bash

##Finder's boot commands to be run on startup.
#written by "Jake Hillard"
echo "Logged in, configuring..."
ifconfig
echo " "
echo " "
echo "{}###################################################{}"
echo "||###                                             ###||"
echo "||##     Please Wait,  FinderEye Booting up...     ##||"
echo "||###                                             ###||"
echo "{}###################################################{}"


cd ..
./usr/local/bin/babeld wlan0 &
cd /home/Programs
python3 finderEye.py &

 
