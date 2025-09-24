#  musecbox/scripts/mb_track_setup.py
#
#  Copyright 2025 Leon Dionne <ldionne@dridesign.sh.cn>
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
Allows you to create a track setup (JSON -encoded array of settings)
from a MuseScore3 score, using the same graphical interface available from the
MusecBox application.
"""
import logging, argparse, sys, json
from PyQt5.QtWidgets import QApplication
from musecbox import set_application_style, LOG_FORMAT
from musecbox.dialogs.score_import_dialog import ScoreImportDialog

def main():
	p = argparse.ArgumentParser()
	p.add_argument('Filename', type=str, nargs='+', help='MuseScore score to use for track setup.')
	p.add_argument("--verbose", "-v", action="store_true", help="Show more detailed debug information")
	p.epilog = __doc__
	options = p.parse_args()
	log_level = logging.DEBUG if options.verbose else logging.ERROR
	logging.basicConfig(level = log_level, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dialog = ScoreImportDialog(None, options.Filename[0])
	if dialog.exec():
		json.dump(dialog.track_setup(), sys.stdout, indent="\t")
		print()

if __name__ == '__main__':
	main()

#  musecbox/scripts/mb_track_setup.py
