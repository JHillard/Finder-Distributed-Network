#!/bin/bash

#FinderEye AutoInit Script
#Written by 'Jake Hillard'


echo "Enter Sensor Number :"
read eyeNum

EyeP='192.168.10.'$eyeNum
#^see what I did there?

echo "Connecting to "$EyeP"..."
ssh root@$EyeP 'bash -s' < finderGammaRoutine.sh $eyeNum
echo $"
       ___________   ______  __________ 
      / ____/  _/ | / / __ \/ ____/ __ \\
     / /_   / //  |/ / / / / __/ / /_/ /
    / __/ _/ // /|  / /_/ / /___/ _, _/ 
   /_/   /___/_/ |_/_____/_____/_/ |_|  
   
                EYE OPEN
                 ,-''-.
                / ,--. \\
               | ( () ) |
                \\ \`--' /
                 \`-..-'      
"
    
