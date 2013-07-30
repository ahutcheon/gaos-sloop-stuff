#!/usr/bin/python

# extract 2nd column (.jpg file names) from photo sheet in Sloop upload file,
# write filenames (without column header) to stdout

# usage: get_files filename.xls > photos.txt


import xlrd
import sys

book = xlrd.open_workbook(sys.argv[1]) 
sheet = book.sheet_by_name('photos')
filenames = sheet.col_slice(1,1)	# 2nd column, starting from 2nd row
for filename in filenames:
	print filename.value

