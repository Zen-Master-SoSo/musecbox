#  musecbox/dialogs/score_apply_dialog.py
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
Provides a dialog used for verifying channel assignments when applying a score to a MuseScore3 file.
"""

import logging
from os.path import join, dirname

# PyQt5 imports
from PyQt5 import			uic
from PyQt5.QtCore import	Qt, pyqtSlot, QTimer
from PyQt5.QtGui import		QPalette
from PyQt5.QtWidgets import QApplication, QDialog, QTableWidgetItem, QStyle

from qt_extras import ShutUpQT
from musecbox.score_fixer import ScoreFixer
from musecbox import LAYOUT_COMPLETE_DELAY

CHAR_OK = '😊'
CHAR_HAS_MISSING = '😕'
CHAR_HAS_EXTRANEOUS = '😯'

TEXT_HAS_EXTRANEOUS = "<p>There are extraneous channels in this score.</p>"
TEXT_HAS_MISSING = "<p>There are missing channels in this score.</p>"
TEXT_ALSO_HAS_MISSING = "<p>There are also missing channels in this score.</p>"
TEXT_IS_OKAY = "<p>This score matches the MusecBox project.</p>"
TEXT_MISSING_EXPLANATION = """<p>This means that there is a track in the MusecBox
project which won't be used by this score. If that's what you intended, (as when
multiple scores share the same MusecBox project, but this one don't use all the
intruments/channels), then you can safely ignore this.</p>"""
TEXT_EXTRANEOUS_EXPLANATION = """<p>This means that there's a channel in your
score which hasn't been assigned a track in the MusecBox project. If you
continue, this channel will be left unmodified in your score. Maybe you should
fix this problem first before clicking "Ok".</p>"""


class ApplyScoreDialog(QDialog):
	"""
	Dialog which is used to setup importing a MuseScore score.
	Allows the user to select which instruments to import, and which SFZ file to use.
	"""

	def __init__(self, parent, project_definition, mscore_filename):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'score_apply_dialog.ui'), self)

		self.resize(100, 100)
		self.fixer = ScoreFixer(project_definition, mscore_filename)
		self.lbl_score.setText(self.fixer.score.filename)

		self.headers = ["Project track", "Port", "Channel", "Score channel", "MIDI Port", "MIDI Channel"]

		font = self.lbl_smiley.font()
		font.setPixelSize(48)
		self.lbl_smiley.setFont(font)
		self.b_cancel.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))
		self.b_okay.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
		self.b_cancel.clicked.connect(self.reject)
		self.b_okay.clicked.connect(self.slot_okay_clicked)
		self.chk_fuzzy_match.stateChanged.connect(self.slot_fuzzy_state_changed)

		self.fill_pairs(False)

	def fill_pairs(self, fuzzy):
		pairs = self.fixer.pairs(fuzzy = fuzzy)
		self.tbl.clear()
		self.tbl.setColumnCount(len(self.headers))
		self.tbl.setHorizontalHeaderLabels(self.headers)
		self.tbl.setRowCount(len(pairs))
		row = 0
		for pair in pairs:
			if pair.track is None:
				item = QTableWidgetItem('[Undefined]')
				item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
				item.setBackground(self.palette().color(QPalette.Window))
				self.tbl.setItem(row, 0, item)
				self.append_space(row, 1)
				self.append_space(row, 2)
			else:
				item = QTableWidgetItem(str(pair.track.voice_name))
				self.tbl.setItem(row, 0, item)
				self.append_number(row, 1, pair.track.port)
				self.append_number(row, 2, pair.track.channel)
			if pair.channel is None:
				item = QTableWidgetItem('[Missing]')
				item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
				item.setBackground(self.palette().color(QPalette.Window))
				self.tbl.setItem(row, 3, item)
				self.append_space(row, 4)
				self.append_space(row, 5)
			else:
				item = QTableWidgetItem(str(pair.channel.voice_name))
				self.tbl.setItem(row, 3, item)
				self.append_number(row, 4, pair.channel.midi_port)
				self.append_number(row, 5, pair.channel.midi_channel)
			row += 1

		missing = [ pair for pair in pairs if pair.channel is None ]
		extraneous = [ pair for pair in pairs if pair.track is None ]
		if extraneous:
			self.lbl_smiley.setText(CHAR_HAS_EXTRANEOUS)
			text = TEXT_HAS_EXTRANEOUS + TEXT_EXTRANEOUS_EXPLANATION
			if missing:
				text += TEXT_ALSO_HAS_MISSING + TEXT_MISSING_EXPLANATION
		elif missing:
			self.lbl_smiley.setText(CHAR_HAS_MISSING)
			text = TEXT_HAS_MISSING + TEXT_MISSING_EXPLANATION
		else:
			self.lbl_smiley.setText(CHAR_OK)
			text = TEXT_IS_OKAY
		self.txt_status.setText(text)
		enable_fuzzy = bool(extraneous)
		self.chk_fuzzy_match.setVisible(enable_fuzzy)
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	def append_number(self, row, col, number):
		item = QTableWidgetItem(f'{number:02d}')
		item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
		self.tbl.setItem(row, col, item)

	def append_space(self, row, col):
		item = QTableWidgetItem('')
		item.setBackground(self.palette().color(QPalette.Window))
		self.tbl.setItem(row, col, item)

	def layout_complete(self):
		self.tbl.resizeColumnsToContents()
		self.resize(
			self.size().width() - self.tbl.size().width() + self.tbl.sizeHint().width(),
			self.size().height() - self.tbl.size().height() + self.tbl.sizeHint().height()
		)

	@pyqtSlot(int)
	def slot_fuzzy_state_changed(self, state):
		self.fill_pairs(fuzzy = bool(state))

	@pyqtSlot()
	def slot_okay_clicked(self):
		self.fixer.fix(ignore_extraneous = True, make_backup = True)
		self.accept()


#  end musecbox/dialogs/score_apply_dialog.py
