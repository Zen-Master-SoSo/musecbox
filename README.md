# MusecBox

A GUI application which hosts .sfz -based synthesizers designed to be tightly integrated with MuseScore.

MusecBox utilizes the Carla plugin host application as its back-end. The
front-end is written entirely in python, using PyQt.

* Multiple MIDI port inputs with up to 16 tracks per port.
* The ability to create a project by importing a MuseScore3 file.
* The ability to add any plugin available to Carla to individual tracks.
* The ability to add "shared" plugins which may consume the output of multiple tracks.
* A graphical balance control which allows you to set the stereo "location" of each instrument.
* Super quick project load times.


## Installation

You must install carla (including python resources), for this package to work.
After installing carla, check that the following directories exist on your
system:

* /usr/local/lib/carla OR /usr/lib/carla
* /usr/local/share/carla OR /usr/share/carla

On my machine, running carla --version produces the following output:

	Using Carla version 2.6.0-alpha1
	  Python version: 3.10.12
	  Qt version:     5.15.3
	  PyQt version:   5.15.6
	  Binary dir:     /usr/local/lib/carla
	  Resources dir:  /usr/local/share/carla/resources

Checking with "apt-file", it appears that the python resources are not packaged
in the official Debian / Ubuntu repository. You may have to download, build,
and install from source. (I did.)

If you do install from source, you might want to look at tweaking the "-mtune" option in the compiler flags. When I compiled, I replaced every instance of "-mtune=generic" with "-mtune=native -march-native". Since you are building for your machine only, this flag is appropriate.

> For more information, see [GCC optimization - Gentoo wiki](https://wiki.gentoo.org/wiki/GCC_optimization)

## Overview

This synth host utilizes the carla plugin host and LiquidSFZ on the back end.
The front end is written entirely in python, utilizing PyQt5.

What it does is create several MIDI input clients, associated with a MuseScore
"port". Each "port" splits incoming MIDI events and sends each channel to a
separate LiquidSFZ instance. Each LiquidSFZ instance is represented as a "track".
The interface presents you with as many ports as you may need, with each port
containing up to 16 tracks.

Tracks can have additional plugins added to the chain, just as with any DAW.
So, for example, you need to EQ an instrument, you can add your favorite EQ
plugin to that track.

Finally, there is a "shared plugins" area which can host plugins to which you
can route the output of any number of tracks. This is a good place for a reverb
plugin to which you could route the output of several tracks. You may want
multiple reverbs, with different early / late reflection times, in order to
simulate different physical placement.

So far, it sounds like any DAW. I suppose it is, in a very limited sense. But
that wasn't the motivation for my writing it. The whole point was to make it:

1. simple
2. responsive (fast load times)
3. capable of hosting more than 25 or 30 LiquidSFZ instances
4. tightly integrated with MuseScore.

### Usage

Setting up a MusecBox project with a MuseScore score is quite easy. You can
open up the MuseScore score file (.mscz or .mscx) in MusecBox, and you will be
presented with a "Score Import Dialog". From there, you are prompted to select
the SFZ files you wish to use to play each instrument's voice. Once all
instruments are selected, it creates the track setup for you, and prompts you
to save it as a MusecBox project.

Since the track setup has to synchronize with MuseScore according to
port/channel assignments, it can modify your score (when prompted), so that the
port and channels in the score match the ports and channels in the MusecBox
project. Then, when you open up your score in MuseScore, MuseScore will create
the  "ports" (jack clients) you need to send the output to MusecBox. Select the
appropriate MIDI client for each port in your MusecBox project, and you're all
connected.

Once you have your MusecBox project set up, you can work on your compositions
in MuseScore, and hear what the final mix will sound like while composing.

Finally, you can record to a file the exact audio produced while composing.
WYSIWYG composing, without any additional steps!

This is not a DAW. It cannot record incoming MIDI, automate parameter changes
while the transport is playing, or any of that other fancy stuff you get with a
DAW. It just synthesizes audio from MIDI, with the ability to modify the audio
signal using any plugin on your machine that Carla can host, and record the
final product, exactly as you hear it while composing.

### Tips

A couple of things you may need to know if you use this:

#### SFZ Groups

SFZs are organized by "groups". This makes it easy to automatically select the
SFZ you wish to use for a particular instrument voice. In the Score Import
Dialog, you have the option to select an SFZ group, and "autofill" the SFZ
selections. It will use the best matching name from that SFZ group, or the last
SFZ you chose from that group which matches the instrument / voice.

* I'm using "voice" as a synonym for "articulation" or "channel". Instruments
in MuseScore may have multiple voices, which are each played by a different
instrument on a different channel. So, for example a Cello may have an "arco",
"marcato", and "tremolo" voice, requiring it to have three channels. Each
channel is represented in the user interface as a single "track".

With groups, one thing you can do, is take the SoundFont that you normally use,
and export it all into SFZ files in one directory. Then add all the SFZs that
directory to a new group in the SFZ selection dialog. That group becomes your
drop-in replacement for the SoundFont that you were using.

#### Lock Balance

There's an integrated Balance Control Widget, where the stereo placement of
each instrument can be set. This allows you to visually see the placement of
each instrument in relation to all the others, all inside one graphic.

If you have an instrument with several voices, it makes sense that each voice
originates from the same stereo "location", since they are all the same
instrument. In order to facilitate this, you can "lock balance" of one channel
to another. Right clicking on a track brings up its context menu, where you
will find a "Lock balance to ..." action. Selecting it brings up a dialog where
you can choose another instrument to lock to.

## Step-by-step

So, let's say you have an orchestral project you want to try out. Here are the
steps you would take to make a MusecBox project from it:

First, make sure the score is not open in MuseScore. If MusecBox makes changes
to the MIDI layout in the score, you don't want MuseScore to overwrite those
changes.

From the MusecBox File -> Open menu, open the score. The Score Import Dialog
will pop up. It's a good idea to allow MusecBox to autonumber your MIDI setup.
Check that option. Now, select the SFZ you want for each voice of each
instrument.

When finished, MusecBox will prompt you to save your project.

Go through the instruments which have multiple voices, and lock their balance
together. Ensure the Balance Control Widget is visible (you may need to choose
that option from the "View" menu). Right-click the Balance Control Widget, and
choose the "Spread evenly" action. This will give you something to work with.

Now locate your instruments on the stereo plane. You can increase or decrease
the lines available to you in the Balance Control Widget using the right-click
context menu.

Save. Save often.

Now add your favorite reverb to the shared plugins area. Set it up with the
parameters you need to make your "distant" instruments sound distant. Now,
route the output of those instruments to this reverb, using the drop-down menu
at the bottom of each track.

Now do the same thing for the closer instruments. Then route the output of your
reverbs to the system audio ports. In the drop down menu at the bottom of the
shared plugins, select your system hardware.

Now open your score in MuseScore3. MuseScore's midi outputs will now appear in
the drop down menu at the top of each port. "mscore-midi-1" gets routed to port
1, "mscore-midi-2" gets routed to port 2 (if necessary), and so on.

Save. You're done.

Oh, one more thing! If you're using MusecBox, make sure that MuseScore is NOT
using JACK audio. It's sending MIDI events to MusecBox now. It's audio output
should be off.

### MuseScore I/O options

In MuseScore, select Edit -> Preferences. In the Preferences dialog, choose the
"I/O" tab. Ensure that "JACK Audio Server" is selected. Now set the checkboxes
like so:

Use JACK audio                - UNCHECKED
Use JACK MIDI                 - Checked
Remember last connection(s)   - UNCHECKED (MusecBox will take care of that)
Use JACK transport            - Checked
Timebase master               - Checked

## Feedback

Please, PLEASE, offer feedback and bug reports. Programming is a tiresome
sport. But getting feedback from REAL PEOPLE makes it more interesting. I'm
getting old and jaded, and I don't always feel like testing everything to its
proper limit, sorry. But if I get some feedback from real people, I think it
would make the difference.


