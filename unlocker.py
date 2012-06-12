#!/usr/bin/env python
#
# unlocker.py
# - Remove simlock on huawei modems
#
# Copyright (C) 2012 Neil McPhail
#		neil@mcphail.homedns.org
#
# Unlock code generator Copyright (C) 2010 dogbert
#                                     dogber1@gmail.com

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import time, serial, re, hashlib, glob

# Intro
def intro():
	print 80 * "*"
	print "\tHuawei modem unlocker"
	print "\tBy Neil McPhail and dogbert"
	print "\tThis is Free Software as defined by the GNU GENERAL PUBLIC"
	print "\tLICENSE version 2"
	print 80 * "*"
	print "\tThis software comes with NO WARRANTY"
	print "\tThis software can damage your hardware"
	print "\tUse it at your own risk"
	print 80 * "*"
	print "\tNot all modems can be unlocked with this software."
	print "\tUsers have reported problems with the following devices:"
	print "\t\tE220, E353"
	print "\tAttempting to unlock these devices with this software is not"
	print "\trecommended. I hope to fix this in a later release."
	print 80 * "*"
	if not _requireYes():
		print "Bye"
		exit(0)

# Helper function
# Require an explicit "YES" in upper case
# Returns True if "YES"
# Asks for explicit uppercase "YES" if mixed or lower case used
# Returns False for anything else
def _requireYes():
	print "If you wish to proceed, please type YES at the prompt"
	while 1:
		response = raw_input(">> ")
		if response == "YES":
			return True
		if response.upper() == "YES":
			print "You must type YES in upper case to proceed"
			continue
		else:
			return False

# These modems seem to open 3 USB serial ports. Only one is the control port
# and this seems to vary from device to device. The other 2 ports appear to
# remain silent
def identifyPort():
	print "Trying to find which port is the active modem connection."
	print "Please be patient as this can take a while.\n\n"
	for p in glob.glob('/dev/ttyUSB*'):
		print "Testing port " + p
		ser = serial.Serial(port = p,
				timeout = 15)
		activity = ser.read(5)
		if activity == '':
			print "\tNo activity\n"
			ser.close()
			continue
		
		print "\tActivity detected\n"
		ser.close()
		return p
	return ''

# The modem should respond with the IMEI with the AT+CGSN command
def obtainImei(port):
	print "\nTrying to obtain IMEI."
	print "The modem will be given 5 seconds to respond."
	ser = serial.Serial(port = port,
			timeout = 0)
	ser.flushInput()
	ser.write('AT+CGSN\r\n')
	time.sleep(5)
	response = ser.read(4096)
	ser.close()
	match = re.search('\r\n(\d{15})\r\n', response)
	if match:
		print "Found probable IMEI: " + match.group(1)
		return match.group(1)
	else:
		print "IMEI not found"
		return ''

# Check the IMEI is correct
# Adapted from dogbert's original
def testImeiChecksum(imei):
	digits = []
	for i in imei:
		digits.append(int(i))
	_sum = 0
	alt = False
	for d in reversed(digits):
		assert 0 <= d <= 9
		if alt:
			d *= 2
		if d > 9:
			d -= 9
		_sum += d
		alt = not alt
	return (_sum % 10) == 0

# Interrogate the lock status
# Returns a dictionary with the lock status, remaining unlock attempts
# and the - largely unused - carrier code
#
# lockStatus 0 = unobtainable
#            1 = locked but can be unlocked
#            2 = unlocked to the inserted sim
#            3 = locked and cannot be unlocked
def checkLockStatus(port):
	status = {'lockStatus': 0, 'remaining': 0, 'carrier': 0}
	print "\nChecking the lock status of the SIM."
	print "The modem will be given 5 seconds to respond."
	ser = serial.Serial(port = port,
			timeout = 0)
	ser.flushInput()
	ser.write('AT^CARDLOCK?\r\n')
	time.sleep(5)
	response = ser.read(4096)
	ser.close()

	match = re.search('CARDLOCK: (\d),(\d\d?),(\d+)\r', response)
	if match:
		status['lockStatus'] = int(match.group(1))
		status['remaining'] = int(match.group(2))
		status['carrier'] = int(match.group(3))
	return status

# Compute the unlock code
# Adapted from dogbert's original
def computeUnlockCode(imei):
	salt = '5e8dd316726b0335'
	digest = hashlib.md5((imei+salt).lower()).digest()
	code = 0
	for i in range(0,4):
		code += (ord(digest[i])^ord(digest[4+i])^ord(digest[8+i])^ord(digest[12+i])) << (3-i)*8
	code &= 0x1ffffff
	code |= 0x2000000
	return code

# Send AT codes to unlock the modem
def unlockModem(port, lockCode):
	ser = serial.Serial(port = port)
	command = 'AT^CARDLOCK="'+ str(lockCode) + '"\r\n'
	ser.write(command)
	ser.close()
#
# Main routine
#
def main():
	intro()
	# Work out which is the control port
	try:
		activePort = identifyPort()
	except:
		print "\nAn error occurred when probing for active ports."
		print "This may be because you need to run this program as root."
		exit(1)
	else:
		if (activePort==''):
			print "\nCould not identify active port."
			exit(1)

	# Obtain and check IMEI
	try:
		imei = obtainImei(activePort)
	except:
		print "\nAn error occurred when trying to check the IMEI."
		exit(1)
	else:
		if (imei==''):
			print "\nCould not obtain IMEI."
			print "Check the modem is properly inserted"
			print "Check a SIM card is in place"
			print "Check you are not already connected"
			print "Try removing and reinserting the device"
			exit(1)
		else:
			if not testImeiChecksum(imei):
				print "\nIMEI checksum invalid."
				exit(1)
			else:
				print "IMEI checksum OK."

	# Obtain lockstatus
	try:
		lockInfo = checkLockStatus(activePort)
	except:
		print "\nAn error occurred when trying to check the SIM lock."
		exit(1)
	else:
		ls = lockInfo['lockStatus']
		if ls == 0:
			print "\nCouldn't obtain SIM lock status."
			print "Further operations would be dangerous."
			exit(1)
		elif ls == 2:
			print "\nThe modem is already unlocked for this SIM."
			exit(0)
		elif ls == 3:
			print "\nThe modem is hard locked,"
			print "This program cannot help you."
			exit(1)
		else:
			print "\nThis SIM should be unlockable..."
			print "Remaining attempts: ", lockInfo['remaining']
			print "Exceeding this will hard-lock the modem"

	unlockCode = computeUnlockCode(imei)
	print "\nUnlock code = ", unlockCode
	print "Please be aware that a failed unlocking attempt could break your modem."
	print "This is a risky procedure."
	if not _requireYes():
		print "Unlocking aborted"
		exit(0)

	print "\nAttempting to unlock..."
	try:
		unlockModem(activePort, unlockCode)
	except:
		print "\nAn error occurred when trying to unlock the modem."
		exit(1)

	print "\nWill check result in 5 seconds."
	time.sleep(5)

	# Check result
	try:
		lockInfo = checkLockStatus(activePort)
	except:
		print "\nAn error occurred when trying to check the SIM lock."
		exit(1)
	else:
		ls = lockInfo['lockStatus']
		if ls == 0:
			print "\nCouldn't obtain SIM lock status."
			print "Further operations would be dangerous."
			exit(1)
		elif ls == 1:
			print "\nUnlocking unsuccessful. Sorry."
			exit(1)
		elif ls == 3:
			print "\nUnlocking unsuccessful."
			print "The modem appears to have been hard locked. Sorry."
			exit(1)
		else:
			print "\nUnlocking successful!"

if __name__ == "__main__":
	main()
