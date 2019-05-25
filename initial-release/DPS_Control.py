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
import serial,serial.tools.list_ports
import argparse, re, shlex, os
from time import sleep,time,localtime,strftime,perf_counter
from DPS_Handler import DPS_Handler
from DPS_Recorder import DPS_Recorder
from string import Template
import platform


comportlist = serial.tools.list_ports.comports()
defport = ''
for p in comportlist:
	if p.vid == 0x1a86: # QinHeng Electronics HL-340 USB-Serial adapter
		defport = p.device
		break
if defport=='':
	if platform.system() == 'Windows': 
		defport = 'COM6'
	else:
		defport = '/dev/ttyUSB0'


parser = argparse.ArgumentParser()
parser.add_argument(help='input filename',
					dest='inp_name',action='store',type=str)
parser.add_argument('--debug','-d',help='debug level 0.. (def=1)',
					dest='debug',action='store',type=int,default=1)
parser.add_argument('--port','-p',help='port (default='+defport,
					dest='port',action='store',type=str,default=defport)	
parser.add_argument('--speed','-s',help='speed (default=19200)',
					dest='speed',action='store',type=int,default=19200)
arg = parser.parse_args()

try:
	DH = DPS_Handler(arg.port,arg.speed)
except serial.serialutil.SerialException:
	print('could not open '+arg.port)
	quit()
	
Rec = DPS_Recorder(DH)

def check_IFx(condition):
	"""
		reads actual values and checks if the condition
		is met and returns true if that is the case. 
	
	"""
	
	def check(val, cond, tgt):
		if   cond == '<' : return val <  tgt
		elif cond == '<=': return val <= tgt
		elif cond == '==': return val == tgt
		elif cond == '>=': return val >= tgt
		elif cond == '>' : return val >  tgt
		else: return True
		
	go = True
	if condition != None:
		if   condition[0] == 'C': go = check(DH.Get_IOUT(), condition[1],condition[2])
		elif condition[0] == 'P': go = check(DH.Get_POUT(), condition[1],condition[2])
		elif condition[0] == 'V': go = check(DH.Get_UOUT(), condition[1],condition[2])
	return go
	


def list_op(lc,ins,p1="",p2="",p3="",note=""):
	"""
		prints a formatted line of the performed operation
	"""
	if debug_prog: 
		p = p1+' '+p2+' '+p3
		print('{:02d}: {:6s} {:10s} {:4s}'.format(lc,ins,p,note))
	return None
	
####################################################################
# Program operations. The compiled code consists of calls to these
# functions, all called op_xxxx with xxxx being the opcode of the 
# program. 
#
# Each operation has to advance the program counter (PC) when 
# it is complete. The op_goto operation changes the PC to the PC
# for the new target. 
# 
# Most operations complete in one call except for the op_wait 
# function which may take many calls until the time or the condition
# is satisfied
# 
# The iterations are about one every 500 ms. This is mainly because 
# of the slow serial interface and message exchange 
#

def op_call(pc,lc,cmd,par1,par2,rtime):
	"""
		executes a command (only works if recording is on)
		
		par1 or par2 can include the following meta strings
		
		$D  = expand to date/time string
		$N  = expand to call number 
		$F  = expands to a unique text file name which is read after the call and insert data into recording
		$$  = $
	"""
	
	
	global callcnt
	
	callcnt = callcnt+1
	callres = ''
	ns = '{:04d}'.format(callcnt)
	rfn = Rec.get_recname()
	if rfn != '':
		ofn = '_'+rfn+'.tmp'
		ds = strftime('%Y%m%d%H%M%S',localtime())
		
		p1 = Template(par1).safe_substitute(D=ds,d=ds, N= ns,n=ns, F=ofn,f=ofn, R=rfn,r=rfn)
		
		p2 = Template(par2).safe_substitute(D=ds,d=ds, N= ns,n=ns, F=ofn,f=ofn, R=rfn,r=rfn)
		
		
	
		# res = os.popen(par).read() # output in res
		
		os.system(cmd+p1+p2)
		if (ofn in p1) or (ofn in p2):
			try:
				with open(ofn,'r') as tfi:
					callres = tfi.readline().strip()
			except:
				print('error reading ', ofn)
			list_op(lc,'call',cmd+p1+p2,note='call no:'+ns+' res='+callres)
			try:
				os.remove(ofn)
			except: pass
		else:
			list_op(lc,'call',cmd+p1+p2,note='call no:'+ns)
		Rec.set_callcnt(callcnt)
		Rec.do_record(rtime,callres=callres)
	else:
		list_op(lc,'call',cmd+p1+p2,note="skipped (no recording)")
	return pc+1
	
def op_output(pc,lc,onoff,dummy,dummy2,rtime):
	"""
		turns the output on or off  
		onoff:  'ON' or 'OFF' 
	"""
	list_op(lc,'power',onoff)
	if onoff == 'ON':
		res = DH.Set_Power(1)
	else:
		res = DH.Set_Power(0)
	Rec.do_record(rtime)
	return pc+1

def op_record(pc,lc,level,freq,dummy2,rtime):
	"""
		select recording level  
		level:  0 = off,  1 = record commands only, 2 = record regular, 3 = record both
		freq:  for level 2 or 3, time in seconds between regular recording
	"""
	global recmode, recfreq
	list_op(lc,'record',level,freq)
	Rec.set_recording(int(level),float(freq))
	return pc+1
	
def op_inc(pc,lc,kind, delta,dummy2,rtime):
	"""
		increases/decreases output voltage / current by delta
		kind: 'V' = voltage or 'C' = current
		delta:  voltage / current to be added or subtracted 

	"""
	global recmode
	kind = kind.upper()
	if kind == 'V': 
		last = DH.Get_USET()
		last = last + float(delta)
		if last < 0.0: last == 0.0
		DH.Set_USET(last)
	elif kind == 'C': 
		last = DH.Get_ISET()
		last = last + float(delta)
		if last < 0.0: last == 0.0
		DH.Set_ISET(last)
		
	list_op(lc,'inc',kind,delta,note='new: '+str(last))

	Rec.do_record(rtime)
	
	return pc+1
	
def op_set(pc,lc,kind, newvalue,dummy2, rtime):
	"""
		set output voltage / current
		kind: 'V' = voltage or 'C' = current
		newvalue:  new target voltage / current

	"""
	global recmode
	kind = kind.upper()
	list_op(lc,'set',kind,newvalue)
	
	if   kind == 'V': res = DH.Set_USET(float(newvalue))
	elif kind == 'C': res = DH.Set_ISET(float(newvalue))
	
	Rec.do_record(rtime)
	return pc+1
	
def op_max(pc,lc,kind, maxval,dummy2,rtime):
	"""
		set over-[kind] protection 
		kind:   'V' (volts) , 'C' (current), 'P' (power) 
		maxval:  new limit

	"""
	global recmode
	kind = kind.upper()
	list_op(lc,'max',kind,maxval)
		
	if 		kind == 'C': res = DH.Set_OCP(float(maxval))
	elif 	kind == 'P': res = DH.Set_OPP(float(maxval))
	elif 	kind == 'V': res = DH.Set_OVP(float(maxval))
	
	Rec.do_record(rtime)
	return pc+1




	
def op_if(pc,lc,kind, cond, value,rtime):
	"""
		sets a condition (for next wait or goto command)   
		kind : C, P or V
		cond : condition (<, <=, == , >=, >)
		value: target value
	"""
	global condition
	list_op(lc,'if',kind,cond,value)

	if cond == '=': cond = '=='
	condition = (kind,cond,float(value))
	return pc+1
	
	
def op_wait(pc,lc,seconds,dummy,dummy2,rtime):
	"""
		waits for a number of seconds or on a previously set condition
		seconds : wait time, or timeout if waiting for condition
	"""
	global condition,wtime

			
	res = pc
	if (condition == None):
		# unconditional wait based on time
		if wtime == 0:
			wtime = rtime
		if rtime - wtime >= float(seconds):
			res = pc + 1
			wtime = 0
			list_op(lc,'wait',seconds,note='time reached')
		else:
			list_op(lc,'wait',seconds,note='time not reached')
	else: # conditional wait 
		if check_IFx(condition):
			res = pc+1
			condition = None
			list_op(lc,'wait',seconds,note='cond: True')
		else:
			if float(seconds) > 0:
				# conditional wait with timeout
				if wtime == 0:
					wtime = rtime
				if rtime - wtime >= float(seconds):
					wtime = 0
					res = pc+1
					condition = None
					list_op(lc,'wait',seconds,note='cond: <timeout>')
				else:
					list_op(lc,'wait',seconds,note='cond: False')
			else:
				list_op(lc,'wait',seconds,note='cond: False')
	return res
	
def op_goto(pc, lc,target,dummy,dummy2,rtime):
	"""
		jumps to a new program position or conditionally based on the
		previously set condition 
		target  : label to jump to  
	"""
	global condition
	if (condition == None):
		res = find_label(target)
		list_op(lc,'goto',target,note='unconditional')
	else:
		if check_IFx(condition):
			res = find_label(target)
			list_op(lc,'goto',target,note='cond:True')
		else:
			list_op(lc,'goto',target,note='cond:False, no GOTO')
			res = pc + 1
		condition = None
	return res
	
#
# helper functions
#

def find_op(opstr):
	""" searches for opstr in ops list and returns the index
		if found, or -1 if not
	"""
	idx = 0
	res = -1
	while idx < len(ops):
		if ops[idx][0] == opstr:
			res = idx
			break
		else:
			idx = idx + 1
	return res
	
def find_label(label):
	""" searches for label in label list and returns the 
		reference if found, or -1 if not
	"""
	res = -1
	for l in labels:
		if l[0] == label:
			res = l[1]
			break
	return res
	
def new_label(label, ref):
	""" enters label and reference in label list if 
		it doesn't exist yet. 
		returns True if did not exist before, False otherwise
	"""
	res = False
	if find_label(label) == -1:
		labels.append((label,ref))
		res = True
	return res

# 
# these regex strings are used to validate the correct format of the parameters
#
re_power  = re.compile('(OFF|ON)$') 	# power: on or off
re_allkind= re.compile('(C|P|V)$') 		# current, voltage or power as C P or V
re_setkind= re.compile('(C|V)$') 		# set or inc only allow C or V
re_record = re.compile('[01-3]$')	    # record: 0..3
re_cond   = re.compile('[<=>][=]?$')	# condition:  < <= == >= >
re_labdef = re.compile('[A-Z]\w*:$')  	# label def: 1 alpha followed by n-alphanum, ends with :
re_labtgt = re.compile('[A-Z]\w*$')  	# label target: 1 alpha followed by n-alphanum
re_pnum   = re.compile('^(?=.)([+]?([0-9]*)(\.([0-9]+))?)$') # positive integer or float
re_num    = re.compile('^(?=.)([+-]?([0-9]*)(\.([0-9]+))?)$') # positive or negative integer or float
re_any1   = re.compile('.+$')			# any characters except empty or line break
re_any0   = re.compile('.*$')			# any characters or empty except line break
#
# table of operations. Each entry consists of:
#	- the opcode (string)
#	- the function that executes that operation
#	- the number of parameters (1 .. 3) following the opcode
#	- the regex to validate parameter1
#	- the regex to validate parameter2  (or None )
#	- the regex to validate parameter3  (or None )
ops = [
		('CALL'  ,op_call  	,3,re_any1,re_any0,re_any0),
		('GOTO'  ,op_goto  	,1,re_labtgt,None,None),
		('IF'	 ,op_if   	,3,re_allkind,re_cond,re_pnum),
		('INC'   ,op_inc  	,2,re_setkind,re_num,None),
		('SET'   ,op_set  	,2,re_setkind,re_pnum,None),
		('MAX'   ,op_max	,2,re_allkind,re_pnum,None),
		('OUTPUT',op_output	,1,re_power,None,None),
		('RECORD',op_record	,2,re_record,re_pnum,None),
		('WAIT'  ,op_wait  	,1,re_pnum,None,None)
]

debug_parser= (arg.debug >=2)
debug_prog  = (arg.debug >=1) 

prog   	 	= []     # the "compiled" program code (command, parameter1, parameter2, parameter3)
labels  	= []     # list of label strings and their reference in the program code
gotos   	= []
condition 	= None  # set by IF instruction: contains [kind , cond, value ] 
wtime   	= 0
callcnt		= 0    # counts the number of calls
inputError 	= False

# parse the input file and build up the program code and label list
linecnt = 0
with open(arg.inp_name,'r') as fi:
	line = fi.readline()
	while line:
		linecnt = linecnt +1
		if len(line) > 0:
			# first strip any comments. Note we may end with an empty line
			com = line.find('#')
			if com >=0: line = line[:com]
			line = line.lstrip()
		if len(line) > 0:
			#
			# we have a non-empty line with comments removed
			# now we break the text into components
			# label, operation, parameter1, parameter2 parameter3
			# not all need to be always present. There are
			# six possible cases to consider:
			#  0        1        2       3     4    
			#1 cmdstr param1  
			#2 label: cmdstr  param1  
			#3 cmdstr param1  param2 
			#4 label: cmdstr  param1 param2  
			#5 cmdstr param1  param2 param3
			#6 label: cmdstr  param1 param2 param3
			try:
				words = shlex.split(line)
			except ValueError as err:
				print('syntax error: {0} '.format(err))
				print(linecnt,line)
				inputError = True
				break 
			#line = line.upper()
			#words = line.split()
			label    = ''
			opstr    = ''
			param1   = ''
			param2   = ''
			param3   = ''
			if len(words) == 2: # case 1
				opstr  = words[0]
				param1 = words[1]
			elif len(words) == 3:  # cases 2..3
				if re_labdef.match(words[0]): # case 2
					label = words[0]
					opstr = words[1]
					param1= words[2]
				else: # case 3 
					opstr = words[0]
					param1= words[1]
					param2= words[2]
			elif len(words) == 4:  # case 4..5
				if re_labdef.match(words[0]):  # case 4
					label = words[0]
					opstr = words[1]
					param1= words[2]
					param2= words[3]
				else: # case 5
					opstr = words[0]
					param1= words[1]
					param2= words[2]
					param3= words[3]
			elif len(words) == 5:  # case 6
				if re_labdef.match(words[0]):  
					label = words[0]
					opstr = words[1]
					param1= words[2]
					param2= words[3]
					param3= words[4]
				else:
					inputError = True
					print('too many statements in line')
					print(linecnt,line)
					break	
			else:
				inputError = True
				print('wrong number of statements in line')
				print(linecnt,line)
				break	
			#
			# now that we have broken the line into label, opstr and parameters
			# first we need to check if the opstr is something we recognize
			# then we can check how many parameters are needed and if their
			# format is correct
			#
			opx = find_op(opstr.upper())
			if opx >= 0:  # yes it is a valid operation 
				op = ops[opx]
				if op[2] >= 1: 
					if not op[3].match(param1.upper()):
						inputError = True
						print('parameter validation error in: '+param1)
						print(linecnt,line)
						break	
				if op[2] >= 2: 
					if not op[4].match(param2.upper()):
						inputError = True
						print('parameter validation error in: '+param2)
						print(linecnt,line)
						break	
				if op[2] >= 3: 
					if not op[5].match(param3.upper()):
						inputError = True
						print('parameter validation error in: '+param3)
						print(linecnt,line)
						break	
				# 		
				# We have a valid operation and valid parameters. Lets
				# add them to the program code
				#
				prog.append((op[1],linecnt,param1,param2,param3))
				
				# if the input line had a lable, we need to associate it 
				# with the line (pc) of the program code. They are different!
				# Also check that all labels are unique 
				if label != '':
					label = label.upper()
					if not new_label(label[:-1],len(prog)-1):
						inputError = True
						print('duplicate label def: '+label)
						print(linecnt,line)
						break
				# 
				# this next part is not necessary for program execution but
				# building the goto table allows us to add a check if all 
				# goto's will find a target later before starting to 
				# execute the program. We can't check this now because a goto
				# may come before its target label (forward reference)
				# 
				if opstr == 'GOTO': gotos.append((param1.upper(),linecnt))
			else:
				inputError = True
				print('unknown operation: '+opstr)
				print(linecnt,line)
				break	
		line = fi.readline()
#######################################################################
# At this stage the program text is completely compiled into an executable
# program. 
# 

if debug_parser:
	# Produce a listing of the compiled program code
	n = 0
	for ins in prog:
		print(n,end='')
		print(ins)
		n = n + 1
	# Print a list of all labels and where they are in the program code
	n = 0
	for lline in labels:
		print(n,end='')
		print(lline)
		n = n + 1
	

	#  A quick sanity check to see if all goto labels can be found, in 
	#  particular forward references. This prevents unpleasant surprises
	#  later when we are actually running possible high power stuff... 
	#
	for g in gotos:
		res = find_label(g[0])
		if res == -1:
			print('label '+g[0]+' used in line #'+str(g[1])+' not found')
		inputError = True

if inputError:
	print('program execution stopped')
	exit()

########################################################################
# if we made it to here we have a program in memory that is reasonably 
# error free. There could still be bugs, like crazy voltage or current
# numbers. In such cases the program excution will go ahead and rely on 
# the module to react sensibly...  
#

try:
	pc = 0
	start = perf_counter()
	
	while pc < len(prog):
		res = DH.Read_Output_Values()
		runtime = perf_counter() - start
		if not res:
			print('DPS read error')
		else:
			w = DH.Get_PROT()
			if w > 0: 
				print('*** PROTECTION '+str(w)+' ***')
				break
			#Rec.do_record(runtime,True)
		
			ins = prog[pc]
			pc = ins[0](pc, ins[1],ins[2], ins[3], ins[4],runtime)
			Rec.do_record(runtime,True)
			
except KeyboardInterrupt:
	Rec.end_recording()
	res = DH.Set_Power(0)
	quit()
Rec.end_recording()
# if recfile: 
		# recfile.close()
		# recfile = None
