#  musecbox/dialogs/project_info_dialog.py
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
#  pylint: disable = duplicate-code
#
"""
Provides a dialog which displays information about the current project,
"""
import logging	 # pylint: disable = unused-import
from os import linesep
from pathlib import Path
from qt_extras import ShutUpQT

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, QDir
from PyQt5.QtWidgets import QFileDialog, QDialog, QTableWidgetItem, QHeaderView

from musecbox import (setting, set_setting, main_window,
	KEY_RECENT_EXPORT_DIR, TRACK_DEF_FILE_TYPE, LAYOUT_COMPLETE_DELAY)


class ProjectInfoDialog(QDialog):
	"""
	Just shows what ports, channels, and sfz are in this project.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(str(Path(__file__).parent / 'project_info_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.b_export.clicked.connect(self.slot_export)

		self.tbl.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

		headers = ["MIDI Port", "MIDI Channel", "Moniker", "Voice", "SFZ"]
		self.tbl.setColumnCount(len(headers))
		self.tbl.setHorizontalHeaderLabels(headers)

		tracks = [track_widget for track_widget in main_window().iterate_track_widgets()]
		self.tbl.setRowCount(len(tracks))
		center_flags = int(Qt.AlignHCenter | Qt.AlignVCenter)
		for row, track_widget in enumerate(tracks):
			item = QTableWidgetItem("%02d" % track_widget.port)
			item.setTextAlignment(center_flags)
			self.tbl.setItem(row, 0, item)
			item = QTableWidgetItem("%02d" % track_widget.channel)
			item.setTextAlignment(center_flags)
			self.tbl.setItem(row, 1, item)
			self.tbl.setItem(row, 2, QTableWidgetItem(track_widget.moniker.replace('&', '&&')))
			self.tbl.setItem(row, 3, QTableWidgetItem(str(track_widget.voice_name).replace('&', '&&')))
			self.tbl.setItem(row, 4, QTableWidgetItem(track_widget.sfz_path.replace('&', '&&')))

		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	def layout_complete(self):
		self.tbl.resizeColumnsToContents()
		self.resize(
			self.size().width() - self.tbl.size().width() + self.tbl.sizeHint().width(),
			self.size().height() - self.tbl.size().height() + self.tbl.sizeHint().height()
		)

	@pyqtSlot()
	def slot_export(self):
		sugg_name = main_window().project_path.with_suffix('.tsv') \
			if main_window().project_path else \
			Path(setting(KEY_RECENT_EXPORT_DIR, str, QDir.homePath())) / 'musecbox-project.tsv'
		filename, _ = QFileDialog.getSaveFileName(
			self, "Export project layout ...", sugg_name, TRACK_DEF_FILE_TYPE)
		if filename:
			set_setting(KEY_RECENT_EXPORT_DIR, str(Path(filename).parent.resolve()))
			tab = "\t"
			with open(filename, 'w') as fh:
				for track_widget in main_window().iterate_track_widgets():
					fh.write(tab.joinpath([
						str(track_widget.port),
						str(track_widget.channel),
						track_widget.moniker,
						track_widget.voice_name.instrument_name,
						track_widget.voice_name.voice,
						track_widget.sfz_path
					]))
					fh.write(linesep)


#  end musecbox/dialogs/score_import_dialog.py
