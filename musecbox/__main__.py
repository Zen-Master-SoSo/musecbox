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
"""
Application entry point
"""
import sys, logging, argparse
from os import environ, unlink
from os.path import abspath, expanduser
from socket import socket, AF_UNIX, SOCK_DGRAM, error as sock_error
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QGuiApplication
from qt_extras import DevilBox
from musecbox import SOCKET_PATH, CARRIAGE_RETURN, carla, EngineInitFailure, LOG_FORMAT
from musecbox.gui.main_window import MainWindow


def main():
	p = argparse.ArgumentParser()
	p.epilog = """
	Hosts multiple LiquidSFZ instances for real-time music generation.
	"""
	p.add_argument('Filename', type=str, nargs='?',
		help='MuseScore score to use for port setup, or saved port setup')
	p.add_argument("--horizontal-layout", "-H", action="store_true",
		help="Use standard (horizontal) layout")
	p.add_argument("--vertical-layout", "-V", action="store_true",
		help="Use compact (vertical) layout")
	p.add_argument("--log-file", "-l", type=str,
		help="Log to this file")
	p.add_argument("--verbose", "-v", action="store_true",
		help="Show more detailed debug information")
	options = p.parse_args()

	# Setup logging
	if 'TERM' in environ:
		log_level = logging.DEBUG if options.verbose else logging.ERROR
		log_file = options.log_file
	else:
		log_level = logging.DEBUG
		log_file = expanduser('~/musecbox.log')
	if log_file:
		logging.basicConfig(filename = log_file, filemode = 'w',
			level = log_level, format = LOG_FORMAT)
	else:
		logging.basicConfig(level = log_level, format = LOG_FORMAT)

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
		sock.connect(SOCKET_PATH)
	except ConnectionRefusedError:
		unlink(SOCKET_PATH)
	except FileNotFoundError:
		pass
	except sock_error as e:
		logging.error('%s: %s', type(e).__name__, str(e))
		return 1
	else:
		sock.sendall(bytes(abspath(options.Filename) \
			if options.Filename else '???', 'utf-8') + CARRIAGE_RETURN)
		sock.close()
		return 4
	# Delete previous SOCKET_PATH hanging around
	try:
		unlink(SOCKET_PATH)
	except FileNotFoundError:
		pass

	try:
		sys.getwindowsversion()
	except AttributeError:
		isWindows = False
	else:
		isWindows = True
	if isWindows:
		import win32api, win32process, win32con
		pid = win32api.GetCurrentProcessId()
		handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
		win32process.SetPriorityClass(handle, win32process.ABOVE_NORMAL_PRIORITY_CLASS)
	else:
		from os import nice
		nice(-10)

	application = QApplication([])
	QGuiApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
	try:
		main_window = MainWindow(options)
	except EngineInitFailure as e:
		DevilBox(e)
		return 1
	main_window.show()
	return_value = application.exec()
	unlink(SOCKET_PATH)
	carla().delete()
	return return_value


if __name__ == "__main__":
	sys.exit(main())


#  end musecbox/__main__.py
