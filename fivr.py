#!/usr/bin/env python
#
# This script presents an interactive telephone information tree.
#
# Copyright (C) 2008 https://github.com/samuelinsf
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    
    
import asterisk.agi

import sys
import re
import string
import decimal
import datetime
import os.path
import inspect
import syslog

tree_path=sys.argv[1]
max_repeat=3

class fivr:
    "A Free Interactive Voice Response system"

    def __init__(self, location, max_repeat=5, loglevel=9):
        "Initialize agi interface"
        self._loglevel=loglevel
        self._agi = asterisk.agi.AGI()
        self._line_dead = False
        self._here=[]
        self._visited={}
        self._tree_path=location
        self._max_repeat=max_repeat
        syslog.openlog('fivr[%s]' % self._agi.env['agi_uniqueid'], 0, syslog.LOG_LOCAL1)
        

    def ask(self, dir, time, maxdigits=10, chances=3):
        """Play prompts in dir, wait for user to press keys"""
        result=""
        play_return_clip = (dir in self._visited)
        playlist = self.get_playlist(dir, play_return_clip)
        start_time = time.time()
        for clip in playlist:
            syslog.syslog("play-prompt-start: %s" % clip)
            escaped_name = re.sub(r'([ \t"\\])', lambda x: '\x5c' +x.group(1), clip)
            result=self._agi.get_data(escaped_name, timeout=5, max_digits=maxdigits)
            syslog.syslog("play-prompt-finish: %s" % clip)
            if result != '':
                break
            elif (time.time() - start_time) < (timeout / 1000.0):
                # user pressed pound key inside timeout window, restart clip playback
                syslog.syslog("play-prompt-restart-after-hash: %s" % clip)
                result=self._agi.get_data(escaped_name, timeout=5, max_digits=maxdigits)
                syslog.syslog("play-prompt-finish: %s" % clip)
                if result:
                    break
        result = self.get_rest_digits(result, time)
        self.log('got:' + result)
        return result

    def get_rest_digits(self, already_entered, timeout):
        """ read the rest of the user dtmf input """
        got = already_entered
        while 1:
            result=self._agi.wait_for_digit(timeout)
            got = got + result
            if result == '':
                break
        return got


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

    def get_playlist(self, path, prefer_return=False):
        """ Returns playlist for a dir, if prefer_return is set returns the playlist for subsequent visits of a dir"""
        #self.log("checking:" + path )
        playlist = []
        if not os.path.exists(path):
            return playlist

        listing = sorted(os.listdir(path))

        if prefer_return:
            for f in listing:
                m = re.match("^(return.*)\.[^.]+$", f)
                if m:
                    clip = m.group(1)
                    #self.log("found return clip %s" % clip )
                    playlist.append(os.path.join(path,clip))
            if playlist:
                return playlist

        for f in listing:
            m = re.match("^(clip.*)\.[^.]+$", f)
            if m:
                clip = m.group(1)
                playlist.append(os.path.join(path,clip))

        return playlist

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
            current_dir = os.path.join(self._tree_path, *self._here)
            self.log("cur dir: " + current_dir )
            digits=''
            digit_wait_ms=2000
            digits=self.ask(current_dir, digit_wait_ms, self.digit_count(current_dir))
            times_played = times_played + 1
            if self.has_no_subdirs(current_dir):
                if (len(self._here) == 0):
                    self.hangup('No available options.')
                self._here.pop()
                self._visited[self._tree_path + "/" + "/".join(self._here) + "/"] = True
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
                self._visited[self._tree_path + "/" + "/".join(self._here) + "/"] = True
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
        except asterisk.agi.AGIAppError, err:
            self.log("onerror path")
            if err.args[0] == 'Error executing application, or hangup':
                self.log("did syslog hangup in err path")
                syslog.syslog("hangup")
            raise

if __name__=='__main__':
    """Run fivr"""
    t = fivr(tree_path, max_repeat)
    t.fivr_main()
