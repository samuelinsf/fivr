Free Interactive Voice Response basic documentation.
====================================================

When a call comes in, the software plays the welcome file
and all the files (in character sort order) which begin with 'clip'.

The software then waits for the user to enter a number, if the number
matches a valid sub-directory, the software goes there, plays the 'clip'
files it finds there and repeats the process.

A sub-directory is valid if: it's name begins with one or more numbers
(which are the digits the user must push to go into it) and it contains a file that begins
with 'clip'.

To go up to the parent directory the user can press *.

If a sub-directory contains no sub-directories, the software
automatically takes the user back up after playing the clip.

If a user fails to enter a number the clip is played again,
after 3 replays the software hangs up.

If a user enters a number for which there is no sub directory, the software plays
the invalid-digit.wav file and plays the clip again.

If a directory has 'clip' files it can have optional 'return' files.
Return files begin with the word 'return' instead of 'clip'.
If return file (or sequence) is present, it is played instead of any
of the 'clip' files when a user returns to a folder while on the same call.

All other files and directories are ignored by the playback system.

The demo directory contains a sample fivr tree.

Sound Files for the voice tree system should be in the following format:

RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 8000 Hz

To most audio programs this means windows .wav format with 16 bits per sample,
a sampling rate of 8kHz and mono (one channel) audio.

I believe the best playback quality will be obtained if the
audio files are individually normalized.

All of the demo files were made with the 'say' script

A wav file can be prepared with sox with a command like this:
    sox -V3 -v 0.90  in.wav -s -r 8000 -c 1 -2 clip.wav


Technical details
-----------------

The asterisk directory is taken from pyst version 0.2
it is included here to make this a drop-in usable asterisk script.

This system has been deployed and answering calls 
in a light production setting continuously
since mid 2008 on asterisk version 1.4.17 and python 2.5.2

This python script will call sox to aggressively
compress and expand the volume level of an audio clip,
backup your audio file first!

    #!/usr/bin/env python
    import subprocess
    import sys
    import os.path
    import os

    if __name__ == "__main__":
        f = sys.argv[1]
        (dir, fn) = os.path.split(f)
        fn = 'new-' + fn
        outname = os.path.join(dir, fn)
        subprocess.check_call(['sox', f, outname, 'compand', '0.3,0.8', '6:-70,-60,-20', '-15', '-90', '0.2'])
        os.rename(outname, f)


The stanzas in extension.conf to call fiver.py look like this in the deployed configuration:

    [default]
    exten => s,1,Ringing                     ; Make them comfortable with 2 seconds of ringback
    exten => s,n,Wait,2
    exten => s,n,DeadAGI(/home/user/fivr/fivr.py|/home/user/fivr/demo)
    exten => s,n,Hangup

