#  musecbox/dialogs/score_info_dialog.py
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
Provides a dialog which displays information about a MuseScore3 project,
including MIDI channel numbers and ports.
"""
import logging
from os.path import join, dirname
from mscore import Score
from qt_extras import ShutUpQT

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QDialog, QTableWidgetItem

from musecbox import APP_PATH, set_application_style, LAYOUT_COMPLETE_DELAY, LOG_FORMAT


class ScoreInfoDialog(QDialog):

	def __init__(self, parent, source_score):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'score_info_dialog.ui'), self)

		self.resize(100, 100)
		self.score = Score(source_score['filename'])
		self.lbl_score.setText(self.score.filename)

		headers = ["MIDI Port", "MIDI Channel", "Part", "Instrument", "Channel"]
		self.tbl.setColumnCount(len(headers))
		self.tbl.setHorizontalHeaderLabels(headers)

		self.tbl.setRowCount(len(self.score.channels()))
		row = 0
		channels = []
		for part in self.score.parts():
			inst = part.instrument()
			for chan in inst.channels():
				chan.part_name = part.name
				chan.inst_name = inst.name
				channels.append(chan)

		center_flags = int(Qt.AlignHCenter | Qt.AlignVCenter)
		channels.sort(key=lambda chan: chan.midi_port * 256 + chan.midi_channel)
		for chan in channels:
			item = QTableWidgetItem("%02d" % chan.midi_port)
			item.setTextAlignment(center_flags)
			self.tbl.setItem(row, 0, item)
			item = QTableWidgetItem("%02d" % chan.midi_channel)
			item.setTextAlignment(center_flags)
			self.tbl.setItem(row, 1, item)
			self.tbl.setItem(row, 2, QTableWidgetItem(chan.part_name))
			self.tbl.setItem(row, 3, QTableWidgetItem(chan.inst_name))
			self.tbl.setItem(row, 4, QTableWidgetItem(chan.name))
			row += 1

		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	def layout_complete(self):
		self.tbl.resizeColumnsToContents()
		self.resize(
			self.size().width() - self.tbl.size().width() + self.tbl.sizeHint().width(),
			self.size().height() - self.tbl.size().height() + self.tbl.sizeHint().height()
		)


if __name__ == "__main__":
	from PyQt5.QtWidgets import QApplication
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dialog = ScoreInfoDialog(None, {'filename':join(APP_PATH, 'res', 'musescore_score.mscx')})
	dialog.exec_()


#  end musecbox/dialogs/score_info_dialog.py
