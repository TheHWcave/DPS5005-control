#!/usr/bin/env python3
#MIT License
#
#Copyright (c) 2019 TheHWcave
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.
#

import copy
from time import sleep,time,localtime,strftime,perf_counter

class DPS_Recorder:

	__DH  = None		# DPS handler
	
	__recfile		= None
	__recname		= ''
	__recmode    	= 0
	__recfreq		= 0.0  # time between recordings
	__reclast		= 0.0  # last time something was recorded
	__callcnt		= 0    # counts the number of calls
	
	__data_skip	 	= 0
					# Each of the _data_xxx tuples stores the following:
					# RTIME UOUT IOUT POUT  UIN  USET ISET PROT CVCC CALL
	__data_old = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0, 0) 
	__data_prev= ()
	__data_now = ()
					# definitions to index the __data_xxx tuples
	RTIME=0
	UOUT= 1
	IOUT= 2
	POUT= 3
	UIN = 4
	USET= 5
	ISET= 6
	PROT= 7
	CVCC= 8
	CALL= 9
	
	

	def set_callcnt(self,newcallcnt): self.__callcnt = newcallcnt # to get the call counter recorded
		
	def get_recname(self): return self.__recname
		
	def set_recording(self,recmode,recfreq):
		"""
			recmode:  0 = off
					  1 = only instruction based recording
					  2 = time based recording with interval defined by recfreq, 
						  instruction based recording is also still going on
					  3 = change-based recording only
			recfreq:  time interval in seconds, only used in mode 2
		"""
		self.__recmode = recmode
		self.__recfreq = recfreq
			
	def end_recording(self):
		if self.__recfile != None:
			self.__recfile.close()
			self.__recname= ''

	def do_record(self,rtime, reg = False, callres=''):
		"""
			Create a recording file in .CSV (comma separated value) format that
			can be directly opened by spreadsheet programs like MS Excel or
			Libreoffice Calc
			
			The recording file name is based on the current date and time and 
			will always be unique. 
			
			rtime : run time in seconds
			reg   : TRUE regular recording, FALSE: recording because of 
					an instruction was executed that may have changed things..
		"""
		def write_entry(data,cres=''):
			self.__recfile.write('{:5.3f},{:04.2f},{:04.3f},{:04.2f},{:04.3f},{:05.2f},{:04.2f},{:2d},{:2d},{:5d},{:3s}\n'.format(
							data[self.RTIME],
							data[self.USET],
							data[self.ISET],
							data[self.UOUT],
							data[self.IOUT],
							data[self.POUT],
							data[self.UIN],
							data[self.PROT],
							data[self.CVCC],
							data[self.CALL],
							cres))


		if self.__recmode > 0:
			if not self.__recfile:
				#
				# create a new recording file with a unique name if there isn't one open already
				#
				self.__recname = strftime('%Y%m%d%H%M%S',localtime())
				self.__recfile = open('REC_'+self.__recname+'.csv','w')
				self.__recfile.write('Time[s],USET[V],ISET[A],UOUT[V],IOUT[A],POUT[W],UIN[V],PROT,CVCC,calls,res\n')
			#
			# assemble a tuple with the latest data
			#
			data_new = ( rtime,
						self.__DH.Get_UOUT(),
						self.__DH.Get_IOUT(),
						self.__DH.Get_POUT(),
						self.__DH.Get_UIN(),
						self.__DH.Get_USET(),
						self.__DH.Get_ISET(),
						self.__DH.Get_PROT(),
						self.__DH.Get_CVCC(),
						self.__callcnt)
						
			
			if self.__recmode == 1:
				#
				# record data if the call was due to an instruction, i.e.
				# not regular
				#
				if not reg:
					write_entry(data_new,callres)
			elif self.__recmode == 2:
				#
				# record data if the time period since the last recording
				# exceeds the set frequency value or the call was from an
				# instruction
				#
				if (rtime - self.__reclast >= self.__recfreq) or not reg:
					write_entry(data_new,callres)
					self.__reclast = rtime
			elif (self.__recmode == 3) and (reg or callres !=''):
				#
				# record data if it has (sufficient) change, otherwise skip
				# Note. If a change occurs after some data has been skipped
				# it is necessary to also record the last (previously skipped) 
				# entry before the change. Although this record contains the same 
				# data as the last recorded entry before the skipped period, the
				# time stamp is different and this added entry enables plot 
				# functions to draw the values correctly (no false slopes)
				#
				
				self.__data_prev = self.__data_now
				self.__data_now  = data_new
				
				if (abs(self.__data_old[self.UOUT] - data_new[self.UOUT]) >= 0.02 or
				    abs(self.__data_old[self.IOUT] - data_new[self.IOUT]) >= 0.002 or
					self.__data_old[self.USET:] != data_new[self.USET:] or
					callres !=''): 
					# 
					# data is different, record it (and possibly the
					# previous data entry as well
					#
					self.__data_old = data_new
					if self.__data_skip > 0:
						# surpress duplicate entries that could happen by
						# when a call is recorded
						if self.__data_prev[self.RTIME] != self.__reclast:
							write_entry(self.__data_prev)
					write_entry(data_new,callres)
					self.__reclast = rtime
					self.__data_skip = 0
				else:
					#
					# data is the same, skip recording it
					#
					self.__data_skip = self.__data_skip + 1
					
		else:
			self.end_recording()
		return None


	def __init__(self,DH):
		self.__DH = DH
			
					






