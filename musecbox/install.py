#  musecbox/musecbox/install.py
#
#  Copyright 2026 Leon Dionne <ldionne@dridesign.sh.cn>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
"""
Install eml-viewer-soso as an application on XDG-compliant systems (like gnome).
"""
import logging
from os.path import dirname, join
from xdg_soso import is_xdg, XDGSetup, XDGMime
from musecbox import APP_PATH, LOG_FORMAT

def main():
	if is_xdg():
		xdg = XDGSetup('musecbox', 'MusecBox')
		xdg.vendor_name = 'zensoso'
		xdg.comment = 'A GUI application which hosts .sfz -based synthesizers ' + \
			'designed to be tightly integrated with MuseScore.'
		xdg.categories = ['AudioVideo', 'Audio']
		xdg.keywords = ['Audio', 'Sound', 'jackd', 'lv2', 'MIDI', 'SFZ']
		xdg.application_icon = join(APP_PATH, 'res', 'application_icon.svg')
		xdg.file_icon = join(APP_PATH, 'res', 'file_icon.svg')
		xdg.custom_mime_type = XDGMime('application/x-musecbox', '*.mbxp',
			comment = 'MusecBox project', subclass_of = 'application/json')
		xdg.append_mime_type(XDGMime('application/x-musecbox-tracks', '*.mbxt',
			comment = 'MusecBox track definition', subclass_of = 'application/json'))
		xdg.append_mime_type(XDGMime('application/x-musescore3+xml', '*.mscx',
			comment = 'uncompressed MuseScore file', subclass_of = 'application/xml'))
		xdg.append_mime_type(XDGMime('application/x-musescore3', '*.mscz',
			comment = 'MuseScore file', subclass_of = 'application/zip'))
		xdg.append_mime_type(XDGMime('audio/x-sfz', '*.sfz',
			comment = 'SFZ instrument definition'))
		xdg.install()

if __name__ == '__main__':
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	main()


#  end musecbox/musecbox/install.py
