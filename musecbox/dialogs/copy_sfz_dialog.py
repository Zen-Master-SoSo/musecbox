#  musecbox/dialogs/copy_sfz_dialog.py
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
from os.path import realpath, splitext
from functools import partial

# PyQt5 imports
from PyQt5.QtCore import	Qt, QCoreApplication, pyqtSlot
from PyQt5.QtWidgets import QApplication, QFileDialog, QRadioButton, QCheckBox, QLabel, \
							QGroupBox, QVBoxLayout

from sfzen import	SAMPLES_ABSPATH, SAMPLES_RESOLVE, SAMPLES_COPY, \
					SAMPLES_SYMLINK, SAMPLES_HARDLINK

from musecbox import setting, set_application_style, LOG_FORMAT, SFZ_FILE_TYPE, \
					KEY_SAMPLES_MODE, KEY_CLEAN_SFZS, \
					T_SAMPLEMODE_ABSPATH, T_SAMPLEMODE_RELPATH, T_SAMPLEMODE_COPY, \
					T_SAMPLEMODE_SYMLINK, T_SAMPLEMODE_HARDLINK, \
					T_CLEAN_SFZ


class CopySFZDialog(QFileDialog):
	"""
	Custom file dialog with added option for choosing samples_mode.
	"""

	def __init__(self, parent, filename):
		QCoreApplication.setAttribute(Qt.AA_DontUseNativeDialogs)
		super().__init__(parent)
		self.target_path = None
		self.clean_sfzs = setting(KEY_CLEAN_SFZS, bool)
		self.samples_mode = setting(KEY_SAMPLES_MODE, int, SAMPLES_ABSPATH)

		self.restore_geometry()
		self.finished.connect(self.save_geometry)

		self.setWindowTitle("Copy SFZ ...")
		self.setMinimumSize(677, 533)

		self.setDirectory(filename)
		self.setFileMode(QFileDialog.AnyFile)
		self.setNameFilter(SFZ_FILE_TYPE)
		self.setViewMode(QFileDialog.List)

		self.group_box = QGroupBox(
			'When copying SFZs for this project, how do you want to handle their samples?')
		self.r_abspath = QRadioButton(T_SAMPLEMODE_ABSPATH)
		self.r_resolve = QRadioButton(T_SAMPLEMODE_RELPATH)
		self.r_copy = QRadioButton(T_SAMPLEMODE_COPY)
		self.r_symlink = QRadioButton(T_SAMPLEMODE_SYMLINK)
		self.r_hardlink = QRadioButton(T_SAMPLEMODE_HARDLINK)
		lo = QVBoxLayout()
		lo.setContentsMargins(2,2,2,2)
		lo.setSpacing(2)
		lo.addWidget(self.r_abspath)
		lo.addWidget(self.r_resolve)
		lo.addWidget(self.r_copy)
		lo.addWidget(self.r_symlink)
		lo.addWidget(self.r_hardlink)
		self.group_box.setLayout(lo)

		self.chk_clean = QCheckBox(T_CLEAN_SFZ)
		self.chk_clean.setChecked(self.clean_sfzs)

		self.layout().addWidget(QLabel())
		self.layout().addWidget(self.group_box, self.layout().rowCount() - 1, 1, 1, 2)
		self.layout().addWidget(QLabel())
		self.layout().addWidget(self.chk_clean, self.layout().rowCount() - 1, 1, 1, 2)

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
		Overloaded function sets "target_path",
		sets "clean_sfzs", "copy_sfzs", and "samples_mode".
		"""
		selected_files = self.selectedFiles()
		if selected_files:
			self.target_path = realpath(
				selected_files[0] \
				if splitext(selected_files[0])[-1].lower() == '.sfz' \
				else selected_files[0] + '.sfz')
		self.clean_sfzs = bool(self.chk_clean.checkState())
		self.samples_mode = self.samples_mode
		super().accept()

	def done(self, result):
		"""
		Overloaded function restores "AA_DontUseNativeDialogs" flag
		"""
		QCoreApplication.setAttribute(Qt.AA_DontUseNativeDialogs, False)
		super().done(result)


if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dlg = CopySFZDialog(None, None)
	dlg.show()
	if dlg.exec():
		print(f'Clean SFZs: {dlg.clean_sfzs}')
		print(f'Samples mode: {dlg.samples_mode}')
		print(f'Target path: {dlg.target_path}')


#  end musecbox/dialogs/copy_sfz_dialog.py
