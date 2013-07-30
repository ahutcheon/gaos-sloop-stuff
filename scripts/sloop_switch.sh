#!/bin/sh
# run as sloop_switch.sh xxxxx in db/images directory, xxxxx is sloop id of skink with mirror-images 
# say "y" to first question if images are to be  renamed between L and R
# second prompt is just to let you see the result, value entered is irrelevant
if [ -f originals/${1}_L.jpg ]
then
	source="L"
	dest="R"
fi
if [ -f originals/${1}_R.jpg ]
then
	if [ $source ]
	then
		echo "Both sides exist..."
		exit
	else
		source="R"
		dest="L"
	fi
fi
display originals/${1}_${source}.jpg &
P1=$!
display thumbs/${1}_${source}-thumb.jpg &
P2=$!
echo "Mirror images?"
read CONF
if test $CONF = "y" 
	then
	# kill the current display windows
	kill $P1
	kill $P2
	mv originals/${1}_${source}.jpg originals/${1}_${dest}.jpg 
	mv thumbs/${1}_${source}-thumb.jpg thumbs/${1}_${dest}-thumb.jpg 
	echo "Swtching..."
	# re-display for confirmation
	display originals/${1}_?.jpg &
	P1=$!
	display thumbs/${1}_?-thumb.jpg &
	P2=$!
	echo "Happy?"
	read CONF
	echo "!!!!!!!!!!!!!!!!!!!!!!!"
	echo "!!!!!!!!!!!!!!!!!!!!!!!"
	echo "Now fix the database from " ${source} " to " ${dest}
	echo "!!!!!!!!!!!!!!!!!!!!!!!"
	echo "!!!!!!!!!!!!!!!!!!!!!!!"
fi
# kill whichever display windows are open
kill $P1
kill $P2

