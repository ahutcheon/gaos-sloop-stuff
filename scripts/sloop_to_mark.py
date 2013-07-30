#!/usr/bin/python

# pull all of the sightings for a survey series out of Sloop
# process them for size consistency of animals across years
# output in format suitable for use in Mark analysis

# usage:
# sloop_to_mark.py [options] species site surveyfile.xls
# options:
# -v causes details of processing to be dumped to standard output

import psycopg2	# postgres interface package
import xlrd	# .xls decoder package
import sys	# so we can get at the command line
import datetime	# to get date conversion functions

verbose = False	# global to turn on debug/information output


class SurveySeries:
	'Class to manage skink sightings for a survey series'

	def __init__(self, site, keep_ones):
		self.site = site		# not sure if we'll ever use this
		self.keep_size_one = keep_ones	# is site closed to size 1 births during survey period?
		self.surveys = []		# list of lists of dates
		self.current_series = []	# list of dates in current series during assembly
		self.skinks = []		# list of skinks seen in the survey series
		self.dates = []			# and list of lists of dates
		self.sizes = []			# and list of lists of sizes
 
	def AddSurvey(self, date):	# add survey on given date to current series
		self.current_series.append(date)


	def EndSeries(self):	# mark that all surveys in current series have been added
		self.surveys.append(self.current_series)
		self.current_series = []

	def SurveyDates(self):	# generator to return each date in turn
		for series in self.surveys:
			for date in series:
				yield date

	def SurveyGaps(self):	# generator to return interval in years between each survey series
		# gap is taken between first surveys in successive series
		# (we assume survesy in series are closed to births etc. so any consistent reference point should be OK)
		# values returned to 2 decimal places so ~3.5 day resolution
		for i in range(len(self.surveys)-1):
			start1 = self.surveys[i][0]
			start2 = self.surveys[i+1][0]
			yield round((datetime.datetime(start2[0],start2[1],start2[2]) - datetime.datetime(start1[0],start1[1],start1[2])).days / 365.0, 2)


	def AddSkink(self, date, skink, size):	# put a skink sighting into the survey records
		# multiple occurrences of a skink on the same date are removed in the add process
		# estimated size is averaged over all non-zero estimates for that animal on that date

		# convert size to floating point numeric value, unsure sizes to halves
		if size == "1":
			size=1.0
		elif size == "2":
			size=2.0
		elif size == "3":
			size=3.0
		elif size == "4":
			size=4.0
		elif size == "1-2":
			size= 1.5
		elif size == "2-3":
			size=2.5
		elif size == "3-4":
			size=3.5
		else:	# convert unexpected sizes to 0
			size = 0
		if skink == "":		# anonymous singletons have been seen exactly once by definition, don't want to combine them
			# add new entry with this date and size
			self.skinks.append(skink)	# append skink to list
			self.dates.append([date])	# append list containing date to list
			self.sizes.append([size])	# ditto for size
		else:	# a skink with an id
			if skink in self.skinks:	# is this skink already in the list?
				i=self.skinks.index(skink)	# yes: pick up its index
				if self.dates[i][-1] == date:	# is this a repeat entry for the day? dates queried in sequence, so would be at end of list
					if size != 0:	# only interested in size, and then only if meaningful
						if self.sizes[i][-1] == 0:	# drop already entered size if zero
							self.sizes[i][-1] = size
						else:
							self.sizes[i][-1] = (size + self.sizes[i][-1])/2	# average the size
							# !!!BUG!!! if more than two sightings, later entries are over-weighted
				else:	# straightforward new date for existing skink
					self.dates[i].append(date)	# append new date to list of dates for this skink
					self.sizes[i].append(size)	# ditto for size
			else:	# not in list, new entry on the end
				self.skinks.append(skink)	# append skink to list
				self.dates.append([date])	# append list containing date to list
				self.sizes.append([size])	# ditto for size

	def _try_fit(self, hist, gaps, size):
		# takes a list of estimated sizes, one per survey series
		#	a list of gaps between survey series, in years
		#	a presumed size at the start of the survey seriese, to test the fit of
		# returns residual between idealised growth from that size and estimated sizes

		# calculate residual for first survey series
		residual = 0.0
		if hist[0] != "":
			residual = abs(hist[0] - size)
		# if we have gaps, there are more years to recurse through
		if gaps != []:
			# increase size by number of years to next survey, capping at size 4
			n_size = size + gaps[0]
			if n_size > 4.0:
				n_size = 4.0
			# now get residual for remaining survey series
			residual += self._try_fit(hist[1:], gaps[1:], n_size)
		return residual
			

	def ProcessSizes(self):	# apply consistency rules to estimated sizes
		# best fit (least residuals) of skink growing from size x at first sighting until size 4
		# with fit of idealised growth curve against arithmetic mean of estimated sizes across survey series in year
		# ISSUE: mean may not (always) be best (e.g. 1.0, 4.0, 4.0 should probably go to 4.0, not 3.0)
		for skink in range(len(self.sizes)):	# go through all of the capture histories
			size_hist = []
			for survey in self.surveys:	# look through each survey in turn
				tmp_s = 0
				tmp_c = 0
				for date in survey:	# look through each date in the survey
					if date in self.dates[skink]:	# saw this skink on this day
						sz = self.sizes[skink][self.dates[skink].index(date)]
						if sz > 0:	# skip 0 because 0 indicates unsized, not zero size
							tmp_s += sz
							tmp_c += 1
							if verbose:
								print sz
				if tmp_c > 0:
					size_hist.append(tmp_s/tmp_c)
					if verbose:
						print
				else:
					size_hist.append("")
			# now have sequence of mean estimated sizes for this skink over the years

			# ASSUMPTION: surveys are roughly a whole number of years apart
			# (i.e. surveys always take place in summer, but some years may be skipped)
			# BUG: if we include Wildlife winter grands survey this isn't true around that winter survey

			# build a list of inter-series time gaps for use in size fitting
			years_to_next = []
			spare_gap = 0.0
			for g in self.SurveyGaps():
				years_to_next.append(round(g))
			# years_to_next will be empty list if there is only one survey series

			if verbose:
				print size_hist
			for first_sight in range(len(size_hist)):
				if size_hist[first_sight] != "":
					break	# we know there is a first sighting
			# now get the fits for each possible starting size class, based on sightings and survey spacings from first sighting
			# size class is float because residual calculation is floating point
			fit1 = self._try_fit(size_hist[first_sight:], years_to_next[first_sight:], 1.0)
			fit2 = self._try_fit(size_hist[first_sight:], years_to_next[first_sight:], 2.0)
			fit3 = self._try_fit(size_hist[first_sight:], years_to_next[first_sight:], 3.0)
			fit4 = self._try_fit(size_hist[first_sight:], years_to_next[first_sight:], 4.0)
			# pick the best fit, use of < means we will chose larger start size in the event of an x.5 residual
			if fit1 < fit2:
				first_fit = 1
			elif fit2 < fit3:
				first_fit = 2
			elif fit3 < fit4:
				first_fit = 3
			else:
				first_fit = 4
			if verbose:
				print first_fit, fit1, fit2, fit3, fit4
				print
			# first_sight is now the first survey year in which the skink was seen
			# and first_fit the size class when it was first seen
			derived_size = first_fit
			for s in self.surveys[first_sight:]:	# can now look through from the first survey the skink was seen
				for d in s:	# look through each date in the survey
					if d in self.dates[skink]:	# saw this skink on this day, so set size to moderated value
						self.sizes[skink][self.dates[skink].index(d)] = derived_size
				if derived_size< 4:
					derived_size += 1	# increase size for next year, until we hit 4

			

	# local helper function
	def _survey_count(self):
		count = 0
		for s in self.surveys:
			count += len(s)
		return count

	def WriteMetadata(self, f):	# write out metadata describing major/minor survey series
		# first line of output file is inter-survey times for reading into Rmark (one less value than there are surveys)
		gaps = self.SurveyGaps();	# get the gaps between survey years for use below
		for yr in self.surveys:		# go through the surveys for each year
			for z in range(len(yr)-1):	# write 0.0 gaps between the surveys for the year
				f.write("0.0 ")
			f.write(str(next(gaps, "")) + " ")		# write the between-year gap to the first survey of the next series
							# empty string when we run out of between-year gaps (i.e. after last survey)
		f.write("\r\n")		# job done...

		# now output human-readable form
		f.write(str(self._survey_count()) + " encounter occasions (total surveys)\r\n")
		f.write(str(len(self.surveys)) + " primary occasions (survey years)\r\n")
		f.write("Secondary occasions (surveys per year):")
		for s in self.surveys:
			f.write(" " + str(len(s)))
		f.write("\r\n")
		if len(self.surveys) > 1:	# only pull out the inter-series gaps if we have more than one survey series
			f.write("Years between survey series: ")
			for g in self.SurveyGaps():
				f.write(str(g) + " ")
			f.write("\r\n")


	def WriteMetadataAirport(self, f):	# write out metadata for Airport, allowing for 5/6 April 2006 split survey
						# take off one survey from total count and in first year of surveys
		# first line of output file is inter-survey times for reading into Rmark (one less value than there are surveys)
		gaps = self.SurveyGaps();	# get the gaps between survey years for use below
		adjust_for_2006 = -1	# lose the apparent extra survey from the 5/6 April 2006 split: nasty, but we know it's in the first year
		for yr in self.surveys:		# go through the surveys for each year
			for z in range(len(yr)-1 + adjust_for_2006):	# write 0.0 gaps between the surveys for the year
				f.write("0.0 ")
			f.write(str(next(gaps, "")) + " ")		# write the between-year gap to the first survey of the next series
							# empty string when we run out of between-year gaps (i.e. after last survey)
			adjust_for_2006 = 0	# fixed up 5/6 April 2006 split first time through so cancel adjustment
		f.write("\r\n")		# job done...

		# now output human-readable form
		f.write(str(self._survey_count()-1) + " encounter occasions (total surveys)\r\n")
		f.write(str(len(self.surveys)) + " primary occasions (survey years)\r\n")
		f.write("Secondary occasions (surveys per year):")
		adjust_for_2006 = -1	# lose the apparent extra survey from the 5/6 April 2006 split: nasty, but we know it's in the first year
		for s in self.surveys:
			f.write(" " + str(len(s) + adjust_for_2006))
			adjust_for_2006 = 0
		f.write("\r\n")
		if len(self.surveys) > 1:	# only pull out the inter-series gaps if we have more than one survey series
			f.write("Years between survey series: ")
			for g in self.SurveyGaps():
				f.write(str(g) + " ")
			f.write("\r\n")


	def WriteMarkINP(self, f):		# write out MARK input file
		for i in range(len(self.dates)):	# go through all of the capture histories we've built up
			output_sighting = False	# Mark doesn't like all-zero histories, and we may only have seen at size 1
			output_string = ""
			for date in self.SurveyDates():	# build output string for all surveys in series
				if date in self.dates[i]:	# was this animal seen on this survey date?
					if self.keep_size_one or self.sizes[i][self.dates[i].index(date)] > 1:
						# either it's a size 2 or bigger
						# or we're including size 1 animals at this site
						output_string = output_string + "1"
						output_sighting = True
					else:
						# we're ignoring size 1 animals for this site
						output_string = output_string + "0"
				else:
					output_string = output_string + "0"	# didn't see this animal on this day
				# BEWARE: horrible special case to fold together Airport split surveys on 5th and 6th April in 2006
				# safe to recognise via date as that's the only site that was surveyed then, and we can't go back and survey other sites now
				if date == (2006, 4, 6):
					# "or" the last two entries into a single character
					if output_string[-2:] == "00":
						output_string = output_string[:-2] + "0"	# replace pair of zeros with zero
					else:
						output_string = output_string[:-2] + "1"	# replace anything else with a one
				# end BEWARE special case
			output_string = output_string + " 1;"	# tell Mark that there is one animal with this capture history
			if output_sighting:	# at least one sighting bigger than size 1?
				f.write(output_string + "\r\n")	# output capture history with Windows end of line characters
				if verbose:
					print output_string
					print self.skinks[i]
				

	def WriteMarkCohorts(self, f):		# write out MARK input file for multi-state analysis
		# derive this from WriteMarkINP, but convert size classes to Mark cohort letter codes
		mark_cohort_class = "0ABCD"
		if not self.keep_size_one:
			mark_cohort_class = "00ABC"
		for i in range(len(self.dates)):	# go through all of the capture histories we've built up
			output_sighting = False	# Mark doesn't like all-zero histories, and we may only have seen at size 1
			output_string = ""
			for date in self.SurveyDates():	# build output string for all surveys in series
				if date in self.dates[i]:	# was this animal seen on this survey date?
					output_string = output_string + mark_cohort_class[self.sizes[i][self.dates[i].index(date)]]
					if output_string[-1] != "0":	# if stripping size one we might have added a zero to the history 
						output_sighting = True
				else:
					output_string = output_string + "0"	# didn't see this animal on this day
				# BEWARE: horrible special case to fold together Airport split surveys on 5th and 6th April in 2006
				# safe to recognise via date as that's the only site that was surveyed then, and we can't go back and survey other sites now
				if date == (2006, 4, 6):
					# "or" the last two entries into a single character; ASSUMPTION: size will be the same on each day (forced by ProcessSizes)
					first_char = output_string[-2]
					second_char = output_string[-1]
					if first_char == "A" or second_char == "A":
						output_string = output_string[:-2] + "A"
					elif first_char == "B" or second_char == "B":
						output_string = output_string[:-2] + "B"
					elif first_char == "C" or second_char == "C":
						output_string = output_string[:-2] + "C"
					elif first_char == "D" or second_char == "D":
						output_string = output_string[:-2] + "D"
					else:
						output_string = output_string[:-2] + "0"	# didn't see it either time
				# end BEWARE special case
			output_string = output_string + " 1;"	# tell Mark that there is one animal with this capture history
			if output_sighting:	# at least one sighting bigger than size 1?
				f.write(output_string + "\r\n")	# output capture history with Windows end of line characters
				if verbose:
					print output_string
					print self.skinks[i]




	def DumpSurveys(self):	# debug function to dump assembled survey series
		for i in self.surveys:
			print i

	def DumpSkinks(self):	# debug function to dump list of skinks in surveys
		for i in range(len(self.skinks)):
			print self.skinks[i], self.dates[i], self.sizes[i]





# complain and quit
def usage_exit():
	print "usage: sloop_to_mark.py [-v] species site surveyfile.xls"
	sys.exit()

# find the column headed by a cell containing the supplied string, complain and exit if we don't find it
def find_column(sheet,header):
	for col in range(sheet.ncols):
		if sheet.cell(0,col).value == header:
			return col
	# if we got to here, we ran out of columns without finding the heading
	# should perhaps raise an exception and let the caller deal with the problem?
	print "No surveys found for site ", header, " for requested species"
	sys.exit()

# pull the survey out of the supplied column and assemble the object that will hold the sightings data
def extract_surveys(book,sheet,site):
	column = find_column(sheet,site)
	keep_size_one = sheet.cell(1,column).value	# is this site closed to size 1 births?
	survey = SurveySeries(site,keep_size_one)
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
		# pick out ID and estimated size for all skinks photo-surveyed at the site on the day
		my_query="SELECT \"INDIVIDUAL_ID\", \"EST_SIZE_CLASS\" FROM \"CAPTURE\" WHERE \"EVENT\"=\'PhotoID\' AND \"SITE\"=\'"+site+"\' AND date_trunc(\'day\', \"CAPTURE_TIME\")=\'"+make_query_date(date)+"\'"
		db_cur.execute(my_query)
		for record in db_cur:	# loop over all photo-id skinks in the survey, noting them
			surveys.AddSkink(date, record[0], record[1])
			# ASSUMPTION: each date is queried once, so multiple adds of same skink on same date
			#             will not be separated by other dates (but may be separated by other skinks on same date)
		db_conn.rollback()	# do this as soon as practical to complete transaction and release lock




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
elif species == "grand":
	sp_database = "grandlive"
else:
	print "unknown species ", species 
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
	print e.pgerror
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

# now process the estimated size classes to consistent values
sightings.ProcessSizes()

if verbose:
	sightings.DumpSkinks()
	print

# now output .inp files and major/minor survey series information
outfile_name=site+"_"+species
metafile=open(outfile_name+"_surveys.txt", 'w')	# write mode will overwrite any existing file
inpfile=open(outfile_name+".inp", 'w')	# write mode will overwrite any existing file
cohortinpfile=open(outfile_name+"_cohort.inp", 'w')	# write mode will overwrite any existing file

sightings.WriteMetadata(metafile)
sightings.WriteMarkINP(inpfile)
sightings.WriteMarkCohorts(cohortinpfile)

# BEWARE: horrible bodge to deal with Airport split survey on 5/6 April 2006
if site == "Airport":
	metafile.close()
	metafile=open(outfile_name+"_surveys.txt", 'w')	# write mode will overwrite the existing file
	sightings.WriteMetadataAirport(metafile)
# end BEWARE horrible bodge

metafile.close()
inpfile.close()
cohortinpfile.close()


