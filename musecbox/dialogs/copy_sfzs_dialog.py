#  musecbox/dialogs/copy_sfzs_dialog.py
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
Provides a dialog used for importing MuseScore3 files
"""

import logging
from os.path import join, dirname
from functools import partial
from qt_extras import ShutUpQT

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import	pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QRadioButton, QVBoxLayout

from sfzen import	SAMPLES_ABSPATH, SAMPLES_RESOLVE, SAMPLES_COPY, \
					SAMPLES_SYMLINK, SAMPLES_HARDLINK

from musecbox import setting, set_application_style, KEY_CLEAN_SFZS, KEY_SAMPLES_MODE, \
					T_SAMPLEMODE_ABSPATH, T_SAMPLEMODE_RELPATH, T_SAMPLEMODE_COPY, \
					T_SAMPLEMODE_SYMLINK, T_SAMPLEMODE_HARDLINK, LOG_FORMAT


class CopySFZsDialog(QDialog):
	"""
	Dialog which lets the user choose how to treat samples when copying an SFZ.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'copy_sfzs_dialog.ui'), self)
		self.samples_mode = setting(KEY_SAMPLES_MODE, int, SAMPLES_ABSPATH)

		self.r_abspath = QRadioButton(T_SAMPLEMODE_ABSPATH)
		self.r_resolve = QRadioButton(T_SAMPLEMODE_RELPATH)
		self.r_copy = QRadioButton(T_SAMPLEMODE_COPY)
		self.r_symlink = QRadioButton(T_SAMPLEMODE_SYMLINK)
		self.r_hardlink = QRadioButton(T_SAMPLEMODE_HARDLINK)
		glo = QVBoxLayout()
		glo.setContentsMargins(10,2,10,2)
		glo.setSpacing(2)
		glo.addWidget(self.r_abspath)
		glo.addWidget(self.r_resolve)
		glo.addWidget(self.r_copy)
		glo.addWidget(self.r_symlink)
		glo.addWidget(self.r_hardlink)
		self.grp.setLayout(glo)

		if self.samples_mode == SAMPLES_ABSPATH:
			self.r_abspath.setChecked(True)
		elif self.samples_mode == SAMPLES_RESOLVE:
			self.r_resolve.setChecked(True)
		elif self.samples_mode == SAMPLES_COPY:
			self.r_copy.setChecked(True)
		elif self.samples_mode == SAMPLES_SYMLINK:
			self.r_symlink.setChecked(True)
		else:
			self.r_hardlink.setChecked(True)

		self.clean_sfzs = setting(KEY_CLEAN_SFZS, bool)
		self.chk_clean.setChecked(self.clean_sfzs)

		self.r_abspath.clicked.connect(partial(self.slot_set_mode, SAMPLES_ABSPATH))
		self.r_resolve.clicked.connect(partial(self.slot_set_mode, SAMPLES_RESOLVE))
		self.r_copy.clicked.connect(partial(self.slot_set_mode, SAMPLES_COPY))
		self.r_symlink.clicked.connect(partial(self.slot_set_mode, SAMPLES_SYMLINK))
		self.r_hardlink.clicked.connect(partial(self.slot_set_mode, SAMPLES_HARDLINK))

	@pyqtSlot(int, bool)
	def slot_set_mode(self, mode, _):
		"""
		Tiggered by any sample mode selection radio button.
		"""
		self.samples_mode = mode

	@pyqtSlot()
	def accept(self):
		"""
		Overloaded function sets "clean_sfzs", "copy_sfzs", and "samples_mode".
		"""
		self.copy_sfzs = True
		self.clean_sfzs = bool(self.chk_clean.checkState())
		self.samples_mode = self.samples_mode
		super().accept()


if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dlg = CopySFZsDialog(None)
	dlg.show()
	if dlg.exec():
		print(f'Copy SFZs: {dlg.copy_sfzs}')
		print(f'Clean SFZs: {dlg.clean_sfzs}')
		print(f'Samples mode: {dlg.samples_mode}')


#  end musecbox/dialogs/copy_sfzs_dialog.py
