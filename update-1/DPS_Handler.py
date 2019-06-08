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

import serial
from time import sleep,time,localtime,strftime,perf_counter

class DPS_Handler:

	__DPS  = None		# serial connection to the DPS
	
	SLAVEADD	= 1		# address of the DPS module
	
	REG_USET	= 0x00  # set voltage  500 = 5.00V
	REG_ISET 	= 0x01  # set current  500 = 0.500A 
	REG_UOUT	= 0x02  # output voltage
	REG_IOUT 	= 0x03  # output current
	REG_POWER 	= 0x04  # output power
	REG_UIN	 	= 0x05  # input voltage
	REG_LOCK	= 0x06  # key lock  0 = not locked, 1 = locked
	REG_PROTECT	= 0x07  # protection  0 = no, 1 = OVP,  2 = OCP  3 = OPP
	REG_CV_CC	= 0x08	# 0 = CV  1 = CC
	REG_ONOFF	= 0x09  # 
	REG_BLED	= 0x0A  # background 0 .. 5 (5 is brightest)
	REG_MODEL	= 0x0B  
	REG_VERSION	= 0x0C
	REG_EXTRACT	= 0x23  # load a preset 
	
						# each of the 10 preset groups are accessed by multiplying
						# the group# with 0x10 and adding to 0x50 
	REG_M_USET	= 0x50  # set voltage
	REG_M_ISET	= 0x51  # set current
	REG_M_SOVP	= 0x52	# set over voltage protection
	REG_M_SOCP	= 0x53  # set over current protection
	REG_M_SOPP	= 0x54  # set over power protection
	REG_M_BLED	= 0x55  # set backlight
	REG_M_MPRE	= 0x56  # set preset number
	REG_M_SIN	= 0x57  # set power switch
	
	#
	# 	The class keeps copies of the actual values in the DPS module here
	#   Note that all these values are updated based on responses from the
	#	module and not speculatively by the handler. This means there will
	#	be some delay before, for example, uset shows the last commanded
	#	voltage from the SET_USET command but on the plus side, we are 
	#   sure that that whatever uset shows is also what the module knows
	#
	__uset 		= 0.0	# last commanded voltage reported by DPS
	__iset 		= 0.0	# last commanded current reported by DPS
	__uout 		= 0.0	# present output voltage reported by DPS
	__iout 		= 0.0	# present output current reported by DPS
	__pout 		= 0.0	# present output wattage reported by DPS
	__onoff		= 0		# present output state reported bt DPS
	__uin		= 0.0	# present input voltage
	__lock		= 0		# key lock  0 = not locked, 1 = locked
	__protect 	= 0 	# 0 = no, 1 = OVP,  2 = OCP  3 = OPP
	__cvcc		= 0		# 0 = CV  1 = CC
	__ovp		= 0.0	# last commanded over-voltage protection reported by DPS
	__ocp		= 0.0	# last commanded over-current protection reported by DPS
	__opp		= 0.0	# last commanded over-power protection reported by DPS
	
	def __dump(self,prompt,buf):
		"""
			prints a hex dump of the buffer on the terminal
		"""
		print(prompt,end='')
		for b in buf:
			print('{:02x} '.format(b),end='')
		print()

	def __CRC16(self,buf):
		""" 
			calculates and returns the CRC16 checksum for all message bytes 
			excluding the two checksum bytes 
		"""
		crc = 0xffff
		for b in buf[:-2]: # exclude the checksum space
			crc = crc ^ b
			for n in range(0,8):
				if (crc & 0x0001) != 0:
					crc = crc >> 1
					crc = crc ^ 0xa001
				else:
					crc = crc >> 1
		return crc.to_bytes(2,'little')
	
	def __cmd_read_regs(self,slave,regstart,regnum):
		"""
			implements function code 0x03: read holding register(s)
			slave	: slave address
			regstart: address of first register
			regnum  : number of registers to read
			
			The expected response for this message varies with regnum. 
			For a regnum value of 5 we expect 15 bytes back
		"""
		msg = bytearray(8)
		msg[0] = slave
		msg[1] = 0x03
		msg[2:4] = regstart.to_bytes(2,byteorder='big')
		msg[4:6] = regnum.to_bytes(2,byteorder='big')
		msg[6:8] = self.__CRC16(msg)
		self.__DPS.write(msg)
		res = self.__read_response(5+2*regnum)
		return res
	
	def __cmd_write_reg(self,slave,reg,data):
		"""
			implements function code 0x06: write single register
			slave	: slave address
			reg     : address of register
			data    : data to write 
			
			The expected response for this message is always 8 bytes long
		"""
		msg = bytearray(8)
		msg[0] = slave
		msg[1] = 0x06
		msg[2:4] = reg.to_bytes(2,byteorder='big')
		msg[4:6] = data.to_bytes(2,byteorder='big')
		msg[6:8] = self.__CRC16(msg)
		self.__DPS.write(msg)
		res = self.__read_response(8)
		return res
	
	
	def __read_response(self,expected_len):
		"""
			reads and processes the responses received from the module
			Because of the Bluetooth interface quirkiness it can't rely 
			on "silent" periods to detect message ends and instead needs
			the expected message length. It verifies that the checksum is
			correct, but the further interpretation is done "cheaply" and
			really only targets the messages we are expecting to see, 
			namely:
				- response to read_regs for 9 registers starting at USET
				  response to write_reg for changing USET
				- response to write_reg for changing ISET
				- response to write_reg for changing ONOFF
			
		"""
		buf = bytearray(64)
		buflen = 0
		raw = bytearray
		res = False
		tries = 50
		while (tries > 0):
			raw = self.__DPS.read(32)
			if len(raw) > 0:
				# got something .. append in to the buffer
				buf[buflen:buflen+len(raw)] = raw 
				buflen = buflen + len(raw)
				if buflen >= expected_len:
					break
			else:
				tries = tries - 1
		if tries == 0:
			print('timeout')
		else:
			#dump('msg:',buf[:buflen])
			if buflen > 3:
				if buf[-2:] == self.__CRC16(buf):
					if buf[1:3] == b'\x03\x12': 
						# Expected response for read_regs of 9 registers starting with USET
						# extract and format the 9 registers as USET,ISET,UOUT,IOUT,POUT,UIN,LOCK,PROT,CVCC
						#    0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18  19  20  21  22
						#  [sa][03][0a][ uset ][ iset ][ uout ][ iout ][ pout ][  uin ][ lock ][ prot ][ cvcc ][ crc16]
						# 
						self.__uset		= int.from_bytes(buf[3:5],byteorder='big') / 100
						self.__iset		= int.from_bytes(buf[5:7],byteorder='big') / 1000
						self.__uout		= int.from_bytes(buf[7:9],byteorder='big') / 100
						self.__iout		= int.from_bytes(buf[9:11],byteorder='big') / 1000
						self.__pout 	= int.from_bytes(buf[11:13],byteorder='big') / 100
						self.__uin		= int.from_bytes(buf[13:15],byteorder='big') / 100
						self.__lock		= int.from_bytes(buf[15:17],byteorder='big') 
						self.__protect	= int.from_bytes(buf[17:19],byteorder='big')
						self.__cvcc		= int.from_bytes(buf[19:21],byteorder='big')
						
						#print('{:05.2f}V {:05.3f}A {:05.2f}V {:05.3f}A {:5.2f}W'.format(uset,iset,uout,iout,pout))
						#print('{:05.2f}V L={:02d} P={:02d} CVCC={:02d}'.format(self.__uin,self.__lock,self.__protect,self.__cvcc))
						res = True
					elif buf[1] == 0x06: 
						# Expected response for write_reg 
						# extract and format the response according to the register written 
						#    0   1   2   3   4   5   
						#  [sa][06][  reg  ][  val ][crc16]
						# 
						reg = int.from_bytes(buf[2:4],byteorder='big') 
						val = int.from_bytes(buf[4:6],byteorder='big')
						if reg == self.REG_USET		: self.__uset = val / 100 	# its the response to a USET command 
						elif reg == self.REG_ISET	: self.__iset = val / 1000 	# its the response to a ISET command 
						elif reg == self.REG_ONOFF	: self.__onoff= val 		# its the response to a ONOFF command 
						elif reg == self.REG_M_SOVP	: self.__ovp  = val / 100	# its the response to a SOVP command 
						elif reg == self.REG_M_SOCP	: self.__ocp  = val / 1000	# its the response to a SOCP command 
						elif reg == self.REG_M_SOPP	: self.__opp  = val / 100	# its the response to a SOPP command 
						res = True
					else:
						self.__dump('unknown valid msg:',buf[:buflen])
				else:
					self.__dump('bad checksum:',buf[:buflen])
			elif len(buf) > 0:
				self.__dump('not enough data:',buf[:buflen])
		return res
	
	# 
	#  getters for the actual values from the module
	#  
	#   
	def Get_USET(self):	return self.__uset 		# updated after Read_Output_Values or Set_USET
	def Get_ISET(self):	return self.__iset 		# updated after Read_Output_Values or Set_ISET
	def Get_UOUT(self):	return self.__uout 		# updated after Read_Output_Values
	def Get_IOUT(self):	return self.__iout 		# updated after Read_Output_Values
	def Get_POUT(self): return self.__pout 		# updated after Set_Power
	def Get_UIN(self):	return self.__uin	 	# updated after Read_Output_Values
	def Get_LOCK(self):	return self.__lock	 	# updated after Read_Output_Values
	def Get_PROT(self):	return self.__protect 	# updated after Read_Output_Values
	def Get_CVCC(self):	return self.__cvcc	 	# updated after Read_Output_Values
	def Get_OVP(self):	return self.__ovp	 	# updated after Set_OVP
	def Get_OCP(self):	return self.__ocp	 	# updated after Set_OCP
	def Get_OPP(self):	return self.__opp	 	# updated after Set_OPP
	
	def Read_Output_Values(self):
		"""
			get the present readings for USET,ISET,UOUT,IOUT, POUT .. CVCC
		"""
		res = self.__cmd_read_regs(self.SLAVEADD,self.REG_USET,9)
		return res
	
	def Set_Power(self, onoff):
		"""
			turn output on (1) or off (0)
		"""
		res = self.__cmd_write_reg(self.SLAVEADD,self.REG_ONOFF,onoff)
		return res
		
	def Set_USET(self, volts):
		"""
			set a new output voltage
		"""
		res = self.__cmd_write_reg(self.SLAVEADD,self.REG_USET,round(volts*100))
		return res
		
	def Set_ISET(self, amps):
		"""
			set a new output current
		"""
		res = self.__cmd_write_reg(self.SLAVEADD,self.REG_ISET,round(amps*1000))
		return res
		
	def Set_OVP(self, volts):
		"""
			set a new over-voltage protection value
		"""
		res = self.__cmd_write_reg(self.SLAVEADD,self.REG_M_SOVP,round(volts*100))
		return res
	
	def Set_OCP(self, amps):
		"""
			set a new over-current protection value
		"""
		res = self.__cmd_write_reg(self.SLAVEADD,self.REG_M_SOCP,round(amps*1000))
		return res
		
	def Set_OPP(self, watts):
		"""
			set a new over-power protection value
		"""
		res = self.__cmd_write_reg(self.SLAVEADD,self.REG_M_SOPP,round(watts*100))
		return res
		


	def __init__(self,DPSport,DPSspeed):
		self.__DPS = serial.Serial(port = DPSport,
						baudrate=DPSspeed,
						timeout = 0.01)	






