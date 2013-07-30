#!/bin/sh

# helper scrip for check_zip_sites.sh
# run in directory containing per-survey directories
# each contain single .xls file and all .jpg files for upload
# directory structure doesn't contain anything else; directory names don't contain spaces
# (hopefully spaces in directories and extraneous non-directory files are dealt with, but error checking isn't robust)
# if all ok, zips up .jpg files


for s in *
do
	if test -d "$s"
		then (cd "$s"; check_zip.sh >> ERROR.txt)
	fi
done
