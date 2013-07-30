#!/usr/bin/python

# extract 2nd column (skinkids) from sightings sheet in Sloop upload file,
# write filenames (without column header) to stdout

# usage: get_files filename.xls > skinkids.txt


import xlrd
import sys

book = xlrd.open_workbook(sys.argv[1]) 
sheet = book.sheet_by_name('sightings')
for skink in sheet.col_slice(1,1):	# 2nd column, starting from 2nd row
	print skink.value

