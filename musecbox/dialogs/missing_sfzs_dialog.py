#  musecbox/dialogs/missing_sfzs_dialog.py
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
Shows missing SFZ files and gives the user the opportunity to hunt for them
"""
import logging
from os.path import dirname
from collections import defaultdict
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, \
							QLabel, QFrame, QPushButton, QSizePolicy
from qt_extras.list_layout import VListLayout
from musecbox import main_window, set_application_style, xdg_open, LOG_FORMAT
from musecbox.dialogs.sfz_file_dialog import SFZFileDialog

CHAR_OKAY = '✅'
CHAR_MISSING = '❌'
TEXT_IGNORE = 'Ignore missing'
TEXT_CLOSE = 'Close'


class MissingSFZsDialog(QDialog):

	def __init__(self, parent, tracks_missing_sfzs):
		super().__init__(parent)
		self.tracks_missing_sfzs = tracks_missing_sfzs
		dirs_parted = defaultdict(list)
		for track_widget in tracks_missing_sfzs:
			path = track_widget.synth.sfz_filename
			dirs_parted[dirname(path)].append(track_widget)
		lo = QVBoxLayout()
		lo.setContentsMargins(18,12,18,20)
		lo.setSpacing(10)
		lbl = QLabel('<h3>Some SFZ files were not found:</h3>', self)
		lo.addWidget(lbl)
		self.dirs = VListLayout()
		for dirpath, tracks in dirs_parted.items():
			self.dirs.append(MissingDir(self, dirpath, tracks))
		lo.addItem(self.dirs)
		hlo = QHBoxLayout()
		self.b_close = QPushButton(TEXT_IGNORE, self)
		self.b_close.clicked.connect(self.close)
		hlo.addSpacing(20)
		hlo.addWidget(self.b_close)
		hlo.addSpacing(20)
		lo.addItem(hlo)
		self.setLayout(lo)
		for btn in self.findChildren(QPushButton):
			btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
		for widget in self.findChildren(MissingSFZ):
			widget.sig_selected.connect(self.slot_selected)

	@pyqtSlot()
	def slot_selected(self):
		self.b_close.setText(
			TEXT_IGNORE if any(widget.is_missing for widget in self.findChildren(MissingSFZ)) \
			else TEXT_CLOSE)
		main_window().set_dirty()


class MissingDir(QFrame):

	def __init__(self, parent, dirpath, tracks):
		super().__init__(parent)
		self.dirpath = dirpath
		self.tracks = tracks
		lo = QVBoxLayout()
		lo.setContentsMargins(0,5,0,10)
		lo.setSpacing(0)
		hlo = QHBoxLayout()
		hlo.setSpacing(10)
		hlo.addWidget(QLabel(f'From {dirpath}:', self))
		btn = QPushButton('Open', self)
		btn.clicked.connect(self.slot_open)
		hlo.addWidget(btn)
		lo.addItem(hlo)
		self.sfzs = VListLayout()
		for track_widget in tracks:
			self.sfzs.append(MissingSFZ(self, track_widget))
		lo.addItem(self.sfzs)
		self.setLayout(lo)

	@pyqtSlot()
	def slot_open(self):
		xdg_open(self.dirpath)


class MissingSFZ(QFrame):

	sig_selected = pyqtSignal()

	def __init__(self, parent, track_widget):
		super().__init__(parent)
		self.track_widget = track_widget
		self.is_missing = True
		lo = QHBoxLayout()
		lo.setContentsMargins(0,0,0,0)
		lo.setSpacing(8)
		self.lbl_icon = QLabel(CHAR_MISSING, self)
		self.lbl_icon.setFixedWidth(18)
		lo.addWidget(self.lbl_icon)
		self.lbl_filename = QLabel(self.track_widget.synth.sfz_filename, self)
		lo.addWidget(self.lbl_filename)
		btn = QPushButton('Select', self)
		btn.clicked.connect(self.slot_select)
		lo.addWidget(btn)
		self.setLayout(lo)

	@pyqtSlot()
	def slot_select(self):
		sfz_dialog = SFZFileDialog(self.track_widget.voice_name)
		if sfz_dialog.exec():
			self.track_widget.synth.change_sfz(sfz_dialog.sfz_filename)
			self.lbl_filename.setText(self.track_widget.synth.sfz_filename)
			self.lbl_icon.setText(CHAR_OKAY)
			self.is_missing = False
			self.sig_selected.emit()


if __name__ == "__main__":
	from collections import namedtuple
	FakeSynth = namedtuple('Synth', ['sfz_filename'])
	FakeTrack = namedtuple('Track', ['synth'])
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dialog = MissingSFZsDialog(None, [
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Brass-Notation/Trumpets-Sustain.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Strings-Notation/Cello-Solo-Looped.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Woodwinds-Notation/Piccolo-Solo-Sustain.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Strings-Notation/Violas-Staccato.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Woodwinds-Notation/Flute-Solo-2-Sustain-Non-Vibrato.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Woodwinds-Notation/Clarinet-Solo.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Strings-Notation/Celli-Staccato.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Strings-Notation/All-Strings-Col-Legno.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Organ/Great-Principal-4Ft.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Strings-Notation/Viola-Solo-Sustain.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Woodwinds-Notation/Flute-Solo-1-Looped.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Strings-Notation/Violin-Solo-2-Harmonics-Non-Vibrato.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Brass-Notation/Bass-Trombone-Solo-Staccato.sfz')),
		FakeTrack(FakeSynth('/mnt/data-drive/docs/sfz/Sonatina/Woodwinds-Notation/Contrabassoon-Solo-Looped.sfz')),
	])
	dialog.exec_()


#  end musecbox/dialogs/missing_sfzs_dialog.py
