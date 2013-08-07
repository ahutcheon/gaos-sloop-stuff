#!/usr/bin/python

# derived from sloop_to_mark.py
# extracts newbies (animals only seen in most recent year)
# so that photos can be used to manually update SkinkPics
# generates:
#     site_species_newbies.csv - one line per newbie, each line has all sightings of that newbie (named by sl_id)
#     site_species - directory containing .jpg images named by sl_id, corresponding to entries in .csv file
# manual process is required to cut down to best left/right image for each newbie before adding to SkinkPics

# usage:
# harvest_newbies.py [options] species site surveyfile.xls
# options:
# -v causes details of processing to be dumped to standard error

# Note: errors and warnings go to stderr, verbose output goes to stdout

import psycopg2	# postgres interface package
import xlrd	# .xls decoder package
import sys	# so we can get at the command line
import datetime	# to get date conversion functions
import shutil	# file copy utilities
import os	# directory create utilities

verbose = False	# global to turn on debug/information output


class SurveySeries:
	'Class to manage skink sightings for a survey series'

	def __init__(self, site):
		self.site = site		# not sure if we'll ever use this
		self.surveys = []		# list of lists of dates
		self.current_series = []	# list of dates in current series during assembly
		self.skinks = []		# list of skinks seen in the survey series
		self.dates = []			# and list of lists of dates
		self.sloop_ids = []		# and list of lists of sloop ids
 
	def AddSurvey(self, date):	# add survey on given date to current series
		self.current_series.append(date)


	def EndSeries(self):	# mark that all surveys in current series have been added
		self.surveys.append(self.current_series)
		self.current_series = []

	def SurveyDates(self):	# generator to return each date in turn
		for series in self.surveys:
			for date in series:
				yield date

	def AddSkink(self, date, skink_id, sloop_id):	# put a skink sighting into the survey records
		# note that we keep all sightings in order to pick up all photos of newbies
		# the manual process that follows selects the best one to add to SkinkPics

		if skink_id == "SINGLETON_SO_FAR":		# anonymous singletons have been seen exactly once by definition, don't want to combine them
			# add new entry with this date and size
			self.skinks.append(skink_id)	# append skink to list
			self.dates.append([date])	# append list containing date to list
			self.sloop_ids.append([sloop_id])	# ditto for sloop id
		elif skink_id == "NEVER_COMPARED":		# Unexpected in production use: indicates that Sloop matching has not been checked for this animal
			# might be running the script for test or other purposes when Sloop matching incomplete
			# warn the user, keep this animal to allow manual checking
			print >> sys.stderr, "Warning: adding NEVER_COMPARED animal as newbie"
			# add new entry with this date and size
			self.skinks.append(skink_id)	# append skink to list
			self.dates.append([date])	# append list containing date to list
			self.sloop_ids.append([sloop_id])	# ditto for sloop id
		else:	# a skink with an id
			if skink_id in self.skinks:	# is this skink already in the list?
				i=self.skinks.index(skink_id)	# yes: pick up its index
				self.dates[i].append(date)	# append new date to list of dates for this skink
				self.sloop_ids[i].append(sloop_id)	# ditto for sloop id
			else:	# not in list, new entry on the end
				self.skinks.append(skink_id)	# append skink to list
				self.dates.append([date])	# append list containing date to list
				self.sloop_ids.append([sloop_id])	# ditto for sloop id


	def CollectNewbies(self):		# return a list of newbies; each list element is skink_id plus list of sloop_ids
		newbies = []
		for i in range(len(self.dates)):	# go through all of the capture histories we've built up
			new_animal = True		# presume this guys is new for now
			for survey in self.surveys[:-1]:	# go through all the prior surveys
				for date in survey:		# and each date in each of them
					if date in self.dates[i]:	# was this animal seen on a survey date before this year?
						new_animal = False	# not a newbie
			# ASSUMPTION: if the animal has a capture history then it was seen at least once
			#	      so if it wasn't  seen before it must have been seen in the most recent survey series
			if new_animal:	# it's a newbie so all sightings must be this year and it must have been seen at least once
				newbies.append((self.skinks[i],self.sloop_ids[i]))
		return newbies
				


	def DumpSurveys(self):	# debug function to dump assembled survey series
		for i in self.surveys:
			print i

	def DumpSkinks(self):	# debug function to dump list of skinks in surveys
		for i in range(len(self.skinks)):
			print self.skinks[i], self.dates[i], self.sloop_ids[i]





# complain and quit
def usage_exit():
	print >> sys.stderr, "usage: harvest_newbies.py [-v] species site surveyfile.xls"
	sys.exit()

# find the column headed by a cell containing the supplied string, complain and exit if we don't find it
def find_column(sheet,header):
	for col in range(sheet.ncols):
		if sheet.cell(0,col).value == header:
			return col
	# if we got to here, we ran out of columns without finding the heading
	# should perhaps raise an exception and let the caller deal with the problem?
	print >> sys.stderr, "Error: No surveys found for site ", header, " for requested species"
	sys.exit()

# pull the survey out of the supplied column and assemble the object that will hold the sightings data
def extract_surveys(book,sheet,site):
	column = find_column(sheet,site)
	survey = SurveySeries(site)
	in_survey = False	# just consume blank cells until we hit a date
	for row in range(2, sheet.nrows):
		if sheet.cell(row,column).value == "":	# consume blank cells, delimit survey series
			if in_survey:	# first blank cell after date(s) delimits survey series
				survey.EndSeries()
				in_survey = False	# just consume blank cells until we hit another date
		else:	# slice pulls out year, month, day from datetime tuple
			survey.AddSurvey(xlrd.xldate_as_tuple(sheet.cell(row,column).value,book.datemode)[0:3])
			in_survey = True	# put dates into a survey series until we hit blank cell(s)
	if in_survey:	# if last cell was a date we've just hit the end of the last series
		survey.EndSeries()
	return survey

# convert date tuple to string format for SQL query
# this isn't pretty, but it works which is enough for now...
def make_query_date(date):
	dt=datetime.datetime(date[0],date[1],date[2])
	return dt.strftime("%Y-%m-%d")

# pull the skinks out of the survey records in the database, add them to the local survey object
def query_skinks(db_conn, db_cur, surveys, site):
	for date in surveys.SurveyDates():	# work through all of the survey dates
		# note that postgres requires quoting to prevent identifiers being folded to lower case
		# query is built in a string with " round db identifiers and ' round string literals in SQL, all \ quoted for Python
		# pick out Skink ID and Sloop ID for all skinks photo-surveyed at the site on the day
		my_query="SELECT \"INDIVIDUAL_ID\", \"SL_ID\" FROM \"CAPTURE\" WHERE \"EVENT\"=\'PhotoID\' AND \"SITE\"=\'"+site+"\' AND date_trunc(\'day\', \"CAPTURE_TIME\")=\'"+make_query_date(date)+"\'"
		db_cur.execute(my_query)
		for record in db_cur:	# loop over all photo-id skinks in the survey, noting them
			surveys.AddSkink(date, record[0], record[1])
			# ASSUMPTION: each date is queried once, so multiple adds of same skink on same date
			#             will not be separated by other dates (but may be separated by other skinks on same date)
		db_conn.rollback()	# do this as soon as practical to complete transaction and release lock


# pick up the photos of the newbies from Sloop's store and put them in the destination directory
def CollectPhotos(src,dest,newbies):
	for n in newbies:	# go through the newbies
		for s in n[1]:	# loop over each sloop id (sighting) for each newbie
			left_photo = src+str(s)+"_L.jpg"	# synthesise full path/filename of left photo
			if os.path.exists(left_photo):		# check it exists; we don't care if copy fails, but Phyton throws an error
				shutil.copy(left_photo , dest)	# copy the photo
			right_photo = src+str(s)+"_R.jpg"	# do the same for the right
			if os.path.exists(right_photo):	
				shutil.copy(right_photo , dest)
		

# write the newbies to the .csv file
# one newbie per line
# first column is skink_id (if any), remainder are sloop ids of each sighting
def WriteNewbies(f,newbies):
	for n in newbies:	# loop over the newbies
		f.write(str(n[0]))	# write the skink_id
		for s in n[1]:		# for each sighting, write a comma seperator then the sloop id
			f.write(", " + str(s))
		f.write("\r\n")


#execution starts here
arg_offset = 0
if (len(sys.argv) < 4) or (len(sys.argv) > 5): usage_exit()
if sys.argv[1] == "-v":
	if len(sys.argv) == 5:
		verbose = True
		arg_offset = 1
	else:
		usage_exit()
species = sys.argv[1+arg_offset]
site = sys.argv[2+arg_offset]
survey_file = sys.argv[3+arg_offset]

if verbose:
	print species, site, survey_file
	print

if species == "otago":
	sp_database = "otagolive"
	sp_photo_src = "/media/GAOS_DB/OtagoSkinkSloopData/db/images/originals/"
elif species == "grand":
	sp_database = "grandlive"
	sp_photo_src = "/media/GAOS_DB/GrandSkinkSloopData/db/images/originals/"
else:
	print >> sys.stderr, "Error: unknown species ", species 
	usage_exit()

# do all the spreadsheet stuff before we touch the database
# for now, assume that process exit will clean up all the spreadsheet stuff
book = xlrd.open_workbook(survey_file)	# how do we check if this worked???
sheet = book.sheet_by_name(species)
sightings = extract_surveys(book,sheet,site)

if verbose:
	sightings.DumpSurveys()
	print
	
try:	# connect to the database for the species; no password seems to be required
	conn=psycopg2.connect(database=sp_database,user="skuser")
except Exception, e:
	print >> sys.stderr, e.pgerror
	sys.exit()
conn.set_session(readonly=True)	# to be safe, prevent us from accidentally damaging the database
cur=conn.cursor()

# now pull the skink sightings out of the database
query_skinks(conn, cur, sightings, site)

# finished with database, so we can close the cursor and connection
cur.close()
conn.close()

if verbose:
	sightings.DumpSkinks()
	print

# Note that (unlike when generating MARK data) we don't need to deal with  Airport split survey on 5/6 April 2006

# pick out the newbies
newbie_list=sightings.CollectNewbies()

outfile_name=site+"_"+species	# where to put the newbies

# grab the newbie photos
# try to create an empty directory to hold them, complain and quit if we fail
photo_dir="./"+outfile_name
try:
	os.makedirs(photo_dir)
except:
	print >> sys.stderr, "Error: Failed to create new empty directory " + outfile_name + " to collect photos. Exiting."
	sys.exit()
CollectPhotos(sp_photo_src,photo_dir,newbie_list)

# output .csv file listing newbies
outfile=open(outfile_name+"_newbies.csv", 'w')	# write mode will overwrite any existing file
WriteNewbies(outfile,newbie_list)
outfile.close()

# we're done...


