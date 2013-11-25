#!/usr/bin/env python
#
# This script presents an interactive telephone information tree.
#
#

import asterisk.agi

import sys
import re
import string
import decimal
import datetime
import os.path
import inspect
import syslog

#
# Configuration
#
#tree_path='/home/sam/src/fivr/demo'
tree_path=sys.argv[1]

#
# from /etc/asterisk/extensions.conf
# exten => s,n,DeadAGI(/home/sam/src/fivr/fivr.py|/home/sam/src/fivr/demo)
#
max_repeat=3

#
# TODO:
# restrict max call time
# buffer extra numbers at entry
# catch asterisk.agi.AGIAppError and log call hangup
#

class fivr:
	"A Free Interactive Voice Response class"

	def __init__(self, location, max_repeat=5, loglevel=9):
		"Initialize agi interface"
		self._loglevel=loglevel
		self._agi = asterisk.agi.AGI()
		self._line_dead = False
		self._here=[]
		self._tree_path=location
		self._max_repeat=max_repeat
		syslog.openlog('fivr[%s]' % self._agi.env['agi_uniqueid'], 0, syslog.LOG_LOCAL1)
		

	def ask(self, prompt, time, maxdigits=10, chances=3):
		"""Play prompt, wait for """
		attempt=1
		result=""
		syslog.syslog("play-prompt-start: %s" % prompt)
		result=self._agi.get_data(prompt, timeout=time, max_digits=maxdigits)
		syslog.syslog("play-prompt-finish: %s" % prompt)
		self.log('got:' + result)
		return result

	def hangup(self, reason):
		"""Hangup, log the reason, exit script"""
		self._agi.hangup()
		self.log(reason)
		sys.exit(0)

	def play(self,file):
		if self._agi:
			syslog.syslog("play-start: %s" % file)
			self._agi.appexec("Playback",file)
			syslog.syslog("play-finish: %s" % file)
		else:
			self.log(file)

	def log(self, msg,level=0):
		if (level <= self._loglevel):
			s = inspect.stack()
			caller = s[1]
			func = caller[3]
			lineno = caller[2]
			sys.stderr.write("TREE[%d]%s(%d):%s\n" % (level, func, lineno, msg))

	def has_clip(self, path):
		""" Returns clip name if a directory exists and has a clip in it; else returns False """
		#self.log("checking:" + path )
		if os.path.exists(path):
			for c in sorted(os.listdir(path)):
				m = re.match("^(clip.*)\.[^.]+$", c)
				if m:
					clip = m.group(1)
					#self.log("found clip %s" % clip )
					return clip
		return None
	
	def has_no_subdirs(self, path):
		""" Returns True if a directory is a leaf in the tree; else return False """
		for e in os.listdir(path):
			if re.match("^[0-9]", e):
				candidate = path + e + "/."
				if self.has_clip(candidate):
					return False
		return True

	def fetch_directory(self, path, digits):
		""" Return directory for digits if it exists and has a clip in it, else returns None """
		if re.match(r"^\d+$", digits):
			for e in os.listdir(path):
				if re.match(r"^%s($|\D)" % digits, e):
					candidate = path + e + "/."
					if self.has_clip(candidate):
						return e
		return None

	def digit_count(self, path):
		""" Returns the number of digits needed to get fron the user for this menu """
		count = 1
		for e in os.listdir(path):
			m = re.match(r"^(\d+)", e)
			if m:
				candidate = path + e + "/."
				if self.has_clip(candidate):
					length = len(m.group(1))
					if (length > count):
						count = length
		return count


	def fivr_takecall(self):
		"""Take a call"""
		# basic operation:
		# play welcome
		# play clip
		# on number, switch to directory
		# if no folders go back up ; if folders repeat clip
		syslog.syslog("callerid %s" % self._agi.env['agi_callerid'])
		times_played=1
		top_dir = self._tree_path + "/" 
		self.play(top_dir + 'welcome')
		while (not self._line_dead):
			current_dir = self._tree_path + "/" + "/".join(self._here) + "/"
			self.log("cur dir: " + current_dir )
			digits=''
			digits=self.ask(current_dir + self.has_clip(current_dir),
				2000, self.digit_count(current_dir))
			times_played = times_played + 1
			if self.has_no_subdirs(current_dir):
				if (len(self._here) == 0):
					self.hangup('No available options.')
				self._here.pop()
				times_played=1
				continue
			if (digits == ''):
				if (times_played > self._max_repeat):
					self.hangup("Max repeat reached: %d" % self._max_repeat)
				continue
			if (digits[-1] == '*'):
				if (len(self._here) == 0):
					self.hangup('Caller pressed * at top level.')
				self._here.pop()
				times_played=1
				continue
			directory = self.fetch_directory(current_dir, digits)
			if (directory):
				self._here.append(directory)
				times_played=1
			else:
				self.play(top_dir + 'invalid-digit')


	def fivr_main(self):
		err=''
		try:
			self.fivr_takecall()
		except asterisk.agi.AGIAppError(err): 
			self.log(asterisk.agi.AGIAppError)
			self.log(err)

if __name__=='__main__':
	"""Run fivr"""
	t = fivr(tree_path, max_repeat)
	t.fivr_main()
