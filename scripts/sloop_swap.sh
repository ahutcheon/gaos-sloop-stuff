#!/bin/sh
# run as sloop_swap.sh xxxxx in db/images directory, xxxxx is sloop id of skink with swapped images
# say "y" to first question if images are to be swapped
# second prompt is just to let you see the result, value entered is irrelevant
display originals/${1}_L.jpg &
P1=$!
display originals/${1}_R.jpg &
P2=$!
display thumbs/${1}_L-thumb.jpg &
P3=$!
display thumbs/${1}_R-thumb.jpg &
P4=$!
echo "Swap images?"
read CONF
if test $CONF = "y" 
	then
	# kill the current display windows
	kill $P1
	kill $P2
	kill $P3
	kill $P4
	mv originals/${1}_L.jpg originals/${1}_tmp.jpg 
	mv originals/${1}_R.jpg originals/${1}_L.jpg 
	mv originals/${1}_tmp.jpg originals/${1}_R.jpg 
	mv thumbs/${1}_L-thumb.jpg thumbs/${1}_tmp-thumb.jpg 
	mv thumbs/${1}_R-thumb.jpg thumbs/${1}_L-thumb.jpg 
	mv thumbs/${1}_tmp-thumb.jpg thumbs/${1}_R-thumb.jpg 
	echo "Swapping..."
	# re-display for confirmation
	display originals/${1}_L.jpg &
	P1=$!
	display originals/${1}_R.jpg &
	P2=$!
	display thumbs/${1}_L-thumb.jpg &
	P3=$!
	display thumbs/${1}_R-thumb.jpg &
	P4=$!
	echo "Happy?"
	read CONF
fi
# kill whichever display windows are open
kill $P1
kill $P2
kill $P3
kill $P4

