#  musecbox/gui/__init__.py
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
#  end musecbox/gui/__init__.py
import sys, logging
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QErrorMessage

LAYOUT_COMPLETE_DELAY	= 50

def exceptions_hook(exception_type, value, traceback):
	if not QApplication.instance() is None:
		msg = QErrorMessage.qtHandler()
		msg.setWindowModality(Qt.ApplicationModal)
		msg.showMessage(
			f'{exception_type.__name__}: "{value}"',
			exception_type.__name__)
	logging.error('Exception "%s": %s', exception_type.__name__, value)

sys.excepthook = exceptions_hook

