#!/bin/sh

# run in directory containing per-Site directories each of which contains per-survey directories
# per-survey directories each contain single .xls file and all .jpg files for upload
# directory structure doesn't contain anything else; directory names don't contain spaces
# (hopefully spaces in directories and extraneous non-directory files are dealt with, but error checking isn't robust)
# if all ok, zips up .jpg files


for s in *
do
	if test -d "$s"
		then (cd "$s"; check_zip_surveys.sh)
	fi
done
