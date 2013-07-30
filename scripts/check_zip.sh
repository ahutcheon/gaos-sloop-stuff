#!/bin/sh

# run in directory containing Sloop upload .xls sheet and  .jpg files
# performs consistency checks that file list and actual files match
# if all ok, zips up .jpg files
# Note: <xxxy.jpg indicates that filename is used in .xls but actual .jpg file is missing
#       >xxxz.jpg indicates that .jpg file exists but name is not used in .xls
#       both occuring as above potentially indicates misspelling in one place or other

tmp=$$
xls=*.xls
get_files.py $xls | sort > /tmp/${tmp}photos.txt
ls *.jpg | sort > /tmp/${tmp}files.txt
diff /tmp/${tmp}photos.txt /tmp/${tmp}files.txt # return code 0 if files match
photos_ok=$?

# this bit only needed when we upload files with skink ids
#for i in *L.jpg
#do
#	echo $(basename $i L.jpg) >> /tmp/${tmp}skinkfiles.txt
#done
#for i in *R.jpg
#do
#	echo $(basename $i R.jpg) >> /tmp/${tmp}skinkfiles.txt
#done
#sort /tmp/${tmp}skinkfiles.txt | uniq > /tmp/${tmp}skinkfiles1.txt
#get_skinks.py $xls | sort > /tmp/${tmp}skinks.txt
#diff /tmp/${tmp}skinks.txt /tmp/${tmp}skinkfiles1.txt # return code 0 if files match
#skinks_ok=$? 	# doesn't test for this on archive generation

# end of skink id only


archive=$(basename $xls .xls)
if [ $photos_ok -eq 0 ]
	then zip $archive *.jpg > /dev/null
	else echo $archive >&2	# put failure message on stderr, should appear on console even if traversing script is redirecting detailed error lists
fi

# tidy up temp files
#rm /tmp/${tmp}photos.txt /tmp/${tmp}files.txt /tmp/${tmp}skinkfiles.txt /tmp/${tmp}skinkfiles1.txt /tmp/${tmp}skinks.txt
rm /tmp/${tmp}photos.txt /tmp/${tmp}files.txt

