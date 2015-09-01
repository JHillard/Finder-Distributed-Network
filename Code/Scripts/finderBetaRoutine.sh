#!/bin/bash

##Finder's boot commands to be run on startup.
#written by "Jake Hillard"
echo "Logged in, configuring..."

ip link set down dev wlan0
iwconfig wlan0 mode ad-hoc channel 11 essid "FinderNet"
ip link set up dev wlan0
#ip addr add 192.168.1.4 dev wlan0
ifconfig wlan0 192.168.1.4



ifconfig
echo " "
echo " "
echo "{}###################################################{}"
echo "||###                                             ###||"
echo "||##     Please Wait,  FinderEye Booting up...     ##||"
echo "||###                                             ###||"
echo "{}###################################################{}"
sleep 10
#to fix babel instabilities. Sometimes the wlan0 interface
# hasn't completely set up

/usr/local/bin/babeld wlan0 &
cd /home/Programs
python3 finderEye.py &
sleep 10




