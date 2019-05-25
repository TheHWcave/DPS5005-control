# DPS5005-control
Controlling a DPS5005 power supply using an easy to understand scripting language 

his software can control a DPS power supply with the standard (out-of-the-box) firmware, provided it came with the "communication" capability. I have only tested it with a DPS5005 but I see no reason why it should not work with other modules from the same series. 

The software works over USB serial port and with the Bluetooth interface (for both using the interface boards that came with the DPS). All it needs is a serial interface, so other interface boards should work as well, and you can specify the port name to use. 

I have tested it under Windows7 and XUBUNTU 18.04

It needs Python 3.x installed as well as pyserial which you can easily install using pip as in

pip install pyserial

DPS Control consists of the main program and two classes, DPS_Handler which takes care of the communication to the DPS module and DPS_Recorder which does the recording. 

call with 

DPS_Control.py  program-file  --port <port> –speed <speed> -d <debug level>

    program-file: text file that contains the instructions to be executed

    <port>: serial port number (default: port that has a HL-340 USB serial adapter)
    <speed>: default is 19200
    <debug level>: default is 1 (trace execution), 
				other values: 0 = off (silent execution)  2= trace and parser 


At a minimum, you need to specify a file with the program to be executed. 

The program searches for a serial port provided by the CH340G chip of the USB-to-Serial board that comes with the DPS module, and uses that as the default for the PORT parameter. However, if you use Bluetooth, or if you have multiple USB-to-serial converters with the same chipset, or if your board happens to use a different chipset, you can of course specify the port to use. 

By default the speed is assumed to be 19200 but you can override this with the SPEED parameter. 

The Debug_level is by default 1 which produces a trace of what your program is doing. You can turn this off by setting the level to 0. 

Please see Instruction Set and Usage.pdf for details on the commands understood and a sample program 
