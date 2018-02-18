#!/bin/bash

DEVICE=$1
M_POINT=/backup
FSTYPE=ext4
IS_DEVICE_EXISTS=`df -hT | grep "$DEVICE"`
#IS_DEVICE_IN_FSTAB=`cat /etc/fstab | grep "$DEVICE"`

if ! [[ -e $M_POINT ]];then
	sudo mkdir -p $M_POINT
fi

if [[ $IS_DEVICE_EXISTS != "" ]];then
	echo "$DEVICE exists and already mounted."
	echo "Details:"
	echo -e "\tFilesystem     Type      Size  Used Avail Use% Mounted on\n\t$IS_DEVICE_EXISTS"
	exit -1
else
	sudo mkfs.ext4 $DEVICE
	echo -e "$DEVICE   $M_POINT       $FSTYPE    defaults        1   1" | sudo tee -a /etc/fstab 1> /dev/null
	sudo mount -a
fi
