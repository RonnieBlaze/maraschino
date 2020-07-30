#!/bin/bash

if [[ $KIOSK = "yes" ]]; then
   KIOSKARG="--kiosk "
fi

python /opt/maraschino/Maraschino.py $KIOSKARG --datadir /config
