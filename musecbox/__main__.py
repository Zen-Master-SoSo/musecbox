#  musecbox/__main__.py
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
#  pylint: disable = import-outside-toplevel
#
"""
musecbox hosts multiple LiquidSFZ instances for real-time music generation.
"""
import sys, logging, argparse
from os import environ
from pathlib import Path
from socket import socket, AF_UNIX, SOCK_DGRAM, error as sock_error
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QGuiApplication
from qt_extras import DevilBox, exceptions_hook
from xdg_soso import is_xdg
from simple_carla import EngineInitFailure
from musecbox import MusecBoxSetup, SOCKET_PATH, CARRIAGE_RETURN, LOG_FORMAT
from musecbox.gui.main_window import MainWindow


def main():
	try:
		sys.getwindowsversion()
	except AttributeError:
		is_windows = False
	else:
		is_windows = True

	parser = argparse.ArgumentParser()
	parser.epilog = __doc__
	parser.add_argument('Filename', type = str, nargs = '?',
		help = 'MusecBox project, MuseScore score, MusecBox track setup, or SFZ')
	layout_group = parser.add_mutually_exclusive_group()
	layout_group.add_argument('--horizontal-layout', '-H', action = 'store_true',
		help = 'Use standard (horizontal) layout')
	layout_group.add_argument('--vertical-layout', '-V', action = 'store_true',
		help = 'Use compact (vertical) layout')
	parser.add_argument('--log-file', '-l', type = str,
		help = 'Log to this file')
	if is_xdg():
		parser.add_argument('--install', '-i', action = 'store_true',
			help = """Install this application into your desktop
environment. This will create a desktop launcher so you can start MusecBox from
your menu or Dash, and associate MusecBox with MusecBox projects, MuseScore
files, and SFZs.""")
		parser.add_argument('--uninstall', '-u', action = 'store_true',
			help = """Remove MusecBox from your desktop environment.
The program will still be on your computer, and can be called from the command
line as "musecbox", but you won't be able to see it in your desktop applications
menu.""")
	parser.add_argument('--verbose', '-v', action = 'store_true',
		help = 'Show more detailed debug information')
	options = parser.parse_args()
	given_path = Path(options.Filename) if options.Filename else None

	# Setup logging
	if 'TERM' in environ:
		log_level = logging.DEBUG if options.verbose else logging.ERROR
		log_file = options.log_file
	else:
		log_level = logging.DEBUG
		log_file = Path('~/musecbox.log').expanduser()
	if log_file:
		logging.basicConfig(filename = log_file, filemode = 'w',
			level = log_level, format = LOG_FORMAT)
	else:
		logging.basicConfig(level = log_level, format = LOG_FORMAT)

	if options.install:
		MusecBoxSetup().install()
	elif options.uninstall:
		MusecBoxSetup().uninstall()
	else:

		#-----------------------------------------------------------------------
		# Annoyance fix per:
		# https://stackoverflow.com/questions/986964/qt-session-management-error
		try:
			del environ['SESSION_MANAGER']
		except KeyError:
			pass
		#-----------------------------------------------------------------------

		# Connect to running instance:
		sock = socket(AF_UNIX, SOCK_DGRAM)
		try:
			sock.connect(str(SOCKET_PATH))
		except ConnectionRefusedError:
			SOCKET_PATH.unlink()
		except FileNotFoundError:
			pass
		except sock_error as e:
			logging.error('%s: %s', e.__class__.__name__, str(e))
			return 1
		else:
			s = str(given_path.resolve()) if given_path else '???'
			sock.sendall(bytes(s, 'utf-8') + CARRIAGE_RETURN)
			sock.close()
			return 4
		# Delete previous SOCKET_PATH hanging around
		try:
			SOCKET_PATH.unlink()
		except FileNotFoundError:
			pass

		if is_windows:
			import win32api, win32process, win32con
			pid = win32api.GetCurrentProcessId()
			handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
			win32process.SetPriorityClass(handle, win32process.ABOVE_NORMAL_PRIORITY_CLASS)
		else:
			from os import nice
			try:
				nice(-10)
			except PermissionError:
				logging.warning('Unable to set process priority')
				print("""
 Attempt to set the process priority using "nice" failed.

 You can allow a specific group to set this using a file at "/etc/security/limits.d/"
 The "jackd" package installs a file named "/etc/security/limits.d/audio.conf".
 Make sure this line exists in the file (or create a new file with this line):

	@audio   -  nice      -19

 Then, make sure that you are a member of the "audio" group. You will have to
 log out and log back in for changes to your group to take effect. You may have
 to restart your computer for changes written to "/etc/security/limits.d/" to
 take effect.
""")

		application = QApplication([])
		sys.excepthook = exceptions_hook
		QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
		try:
			main_window = MainWindow(options)
		except EngineInitFailure as e:
			DevilBox(f'<h2>{e.args[0]}</h2><p>Possible reason:<br/>{e.args[1]}</p>' \
				if e.args[1] else e.args[0])
			return 1
		main_window.show()
		return_value = application.exec()
		SOCKET_PATH.unlink()
		return return_value


if __name__ == "__main__":
	sys.exit(main() or 0)


#  end musecbox/__main__.py
