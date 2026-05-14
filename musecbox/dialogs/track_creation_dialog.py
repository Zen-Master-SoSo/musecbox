	#  musecbox/dialogs/track_creation_dialog.py
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
Provides a dialog used for defining the track properties when adding a new track.
"""
import logging
from os.path import join, basename, dirname, splitext
from qt_extras import ShutUpQT

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox

from mscore import VoiceName
from musecbox import set_application_style, LOG_FORMAT
from musecbox.sfzdb import SFZDatabase
from musecbox.dialogs.sfz_file_dialog import SFZFileDialog


class TrackCreationDialog(QDialog):

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'track_creation_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.sfz_filename = None
		db = SFZDatabase()
		self.cmb_instrument.addItem('')
		self.cmb_instrument.addItems(db.mapped_instrument_names())
		self.cmb_instrument.setEditable(True)
		self.cmb_instrument.currentTextChanged.connect(self.instrument_changed)
		self.cmb_voice.addItems(db.all_voices())
		self.cmb_voice.setEditable(True)
		self.b_sfz.clicked.connect(self.sfz_select_click)
		self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)

	@pyqtSlot(str)
	def instrument_changed(self, value):
		self.b_sfz.setEnabled(len(value))
		if len(value):
			self.b_sfz.setDefault(True)

	@pyqtSlot()
	def sfz_select_click(self):
		voice_name = VoiceName(self.cmb_instrument.currentText(), self.cmb_voice.currentText())
		sfz_dialog = SFZFileDialog(voice_name)
		if sfz_dialog.exec():
			self.sfz_filename = sfz_dialog.sfz_filename
			self.b_sfz.setText(splitext(basename(self.sfz_filename))[0])
			self.b_sfz.setDefault(False)
			self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
			self.buttons.button(QDialogButtonBox.Ok).setDefault(True)


if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dialog = TrackCreationDialog(None)
	if dialog.exec():
		print(f'{dialog.cmb_instrument.currentText()} ({dialog.cmb_voice.currentText()})')
		print(f'Port: {dialog.spn_port.value():d}')
		print(f'SFZ: {dialog.sfz_filename}')


#  end musecbox/dialogs/track_creation_dialog.py
