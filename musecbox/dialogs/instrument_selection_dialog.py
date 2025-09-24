#  musecbox/dialogs/instrument_selection_dialog.py
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
"""
import logging
from os.path import join, dirname, realpath
from functools import lru_cache

# PyQt5 imports
from PyQt5 import			uic
from PyQt5.QtCore import	Qt, pyqtSlot, QTimer, QDir, QModelIndex
from PyQt5.QtGui import		QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QFileSystemModel, QAbstractItemView, \
							QListWidgetItem

from qt_extras import ShutUpQT
from mscore import Score, Part
from mscore.instruments import Instruments
from mscore.fuzzy import FuzzyCandidate, FuzzyName
from musecbox import	setting, set_setting, set_application_style, \
						KEY_SCORES_DIR, KEY_RECENT_SCORE_DIR, LAYOUT_COMPLETE_DELAY, LOG_FORMAT

TEXT_ANY = '[Any]'
TEXT_NOTHING = '-'

class InstrumentSelectionDialog(QDialog):
	"""
	Dialog which is used to setup importing a MuseScore score.
	Allows the user to select which instruments to import, and which SFZ file to use.
	"""

	def __init__(self, parent, part):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'instrument_selection_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.current_instrument = part.instrument()
		self.new_instrument = None
		self.selected_score = None

		self.setWindowTitle(f'Choose new instrument for "{part.name}"')
		self.lbl_search_icon.setPixmap(QIcon.fromTheme('edit-find').pixmap(16,16))
		self.lbl_old_instrument_name.setText(self.current_instrument.name)
		self.lst_old_channels.addItems(list(self.current_instrument.channel_names()))

		# Setup MScore selection page:
		self.msdb = Instruments()
		self.cmb_group.addItem(TEXT_ANY)
		for group in self.msdb.groups():
			self.cmb_group.addItem(group.name)
		self.cmb_genre.addItem(TEXT_ANY, None)
		for genre in self.msdb.genres():
			self.cmb_genre.addItem(genre.name, genre.id)
		self.cmb_group.currentTextChanged.connect(self.slot_combo_changed)
		self.cmb_genre.currentTextChanged.connect(self.slot_combo_changed)

		# Setup score copy page:
		self.file_model = QFileSystemModel()
		self.file_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
		self.file_model.setNameFilters(['*.mscz', '*.mscx'])
		self.file_model.setRootPath(QDir.rootPath())
		self.tree_scores.setModel(self.file_model)
		root_path = setting(KEY_SCORES_DIR, str, QDir.homePath())
		self.tree_scores.setRootIndex(self.file_model.index(root_path))
		self.tree_scores.hideColumn(1)
		self.tree_scores.hideColumn(2)
		self.tree_scores.hideColumn(3)
		self.tree_scores.selectionModel().currentChanged.connect(self.slot_file_current_changed)
		index = self.file_model.index(self.directory)
		self.tree_scores.setCurrentIndex(index)
		self.tree_scores.setExpanded(index, True)

		self.lbl_new_instrument_name.setText(TEXT_NOTHING)
		self.ed_mscore_search.textChanged.connect(self.search_changed)
		self.b_search.clicked.connect(self.clear_search)
		self.lst_instruments.currentItemChanged.connect(self.slot_inst_list_selection_changed)

		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	@pyqtSlot()
	def layout_complete(self):
		index = self.file_model.index(self.directory)
		self.tree_scores.scrollTo(index, QAbstractItemView.PositionAtTop)

	@pyqtSlot(str)
	def slot_combo_changed(self, _):
		self.select_from_mscore()

	@pyqtSlot(str)
	def search_changed(self, _):
		self.select_from_mscore()

	@pyqtSlot()
	def clear_search(self):
		self.ed_mscore_search.setText('')
		self.select_from_mscore()

	def select_from_mscore(self):
		group = self.cmb_group.currentText()
		genre = self.cmb_genre.currentData()
		candidates = list(
			self.msdb.instruments() \
			if group == TEXT_ANY else \
			self.msdb.group(group).instruments() )
		if not genre is None:
			candidates = [ inst for inst in candidates \
				if genre in inst.genres() ]
		self.fill_sorted(candidates)

	@pyqtSlot(QModelIndex, QModelIndex)
	def slot_file_current_changed(self, current, _):
		path = self.file_model.filePath(current)
		if self.file_model.isDir(current):
			self.directory = path
		else:
			self.directory = dirname(path)
			self.selected_score = self.get_score(path)
			self.fill_sorted(self.selected_score.instruments())

	def fill_sorted(self, candidates):
		if len(candidates):
			text_filter = self.ed_mscore_search.text()
			if text_filter:
				text_filter = text_filter.lower()
				candidates = [ inst for inst in candidates \
					if text_filter in inst.name.lower() ]
			self.lst_instruments.clear()
			results = FuzzyName(self.current_instrument.name).score_candidates([
				FuzzyCandidate(inst.name, idx) for idx, inst in enumerate(candidates) ])
			for res in results:
				inst = candidates[res.candidate.index]
				list_item = QListWidgetItem(self.lst_instruments)
				list_item.setText(inst.name)
				list_item.setData(Qt.UserRole, inst)
				self.lst_instruments.addItem(list_item)

	@pyqtSlot(QListWidgetItem, QListWidgetItem)
	def slot_inst_list_selection_changed(self, current, _):
		self.lst_new_channels.clear()
		if current:
			self.new_instrument = current.data(Qt.UserRole)
			self.lbl_new_instrument_name.setText(self.new_instrument.name)
			self.lst_new_channels.addItems(list(self.new_instrument.channel_names()))
		else:
			self.lbl_new_instrument_name.setText(TEXT_NOTHING)

	@lru_cache
	def get_score(self, path):
		return Score(path)

	@property
	def directory(self):
		return setting(KEY_RECENT_SCORE_DIR, str, QDir.homePath())

	@directory.setter
	def directory(self, value):
		set_setting(KEY_RECENT_SCORE_DIR, realpath(value))



if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	part = Part.from_string("""
<Part>
	<Staff id="5">
		<StaffType group="pitched">
			<name>stdNormal</name>
		</StaffType>
		<defaultConcertClef>F8vb</defaultConcertClef>
		<defaultTransposingClef>F</defaultTransposingClef>
	</Staff>
	<trackName>Electric Bass</trackName>
	<Instrument>
		<longName>Electric Bass</longName>
		<shortName>El. B.</shortName>
		<trackName>Electric Bass</trackName>
		<minPitchP>28</minPitchP>
		<maxPitchP>67</maxPitchP>
		<minPitchA>28</minPitchA>
		<maxPitchA>65</maxPitchA>
		<transposeDiatonic>-7</transposeDiatonic>
		<transposeChromatic>-12</transposeChromatic>
		<instrumentId>pluck.bass.electric</instrumentId>
		<concertClef>F8vb</concertClef>
		<transposingClef>F</transposingClef>
		<StringData>
			<frets>24</frets>
			<string>40</string>
			<string>45</string>
			<string>50</string>
			<string>55</string>
		</StringData>
		<Articulation>
			<velocity>100</velocity>
			<gateTime>100</gateTime>
		</Articulation>
		<Articulation name="staccatissimo">
			<velocity>100</velocity>
			<gateTime>33</gateTime>
		</Articulation>
		<Articulation name="staccato">
			<velocity>100</velocity>
			<gateTime>50</gateTime>
		</Articulation>
		<Articulation name="portato">
			<velocity>100</velocity>
			<gateTime>67</gateTime>
		</Articulation>
		<Articulation name="tenuto">
			<velocity>100</velocity>
			<gateTime>100</gateTime>
		</Articulation>
		<Articulation name="marcato">
			<velocity>120</velocity>
			<gateTime>67</gateTime>
		</Articulation>
		<Articulation name="sforzato">
			<velocity>150</velocity>
			<gateTime>100</gateTime>
		</Articulation>
		<Articulation name="sforzatoStaccato">
			<velocity>150</velocity>
			<gateTime>50</gateTime>
		</Articulation>
		<Articulation name="marcatoStaccato">
			<velocity>120</velocity>
			<gateTime>50</gateTime>
		</Articulation>
		<Articulation name="marcatoTenuto">
			<velocity>120</velocity>
			<gateTime>100</gateTime>
		</Articulation>
		<Channel>
			<program value="33" />
			<controller ctrl="7" value="80" />
			<controller ctrl="10" value="82" />
			<synti>Fluid</synti>
			<midiPort>1</midiPort>
			<midiChannel>0</midiChannel>
		</Channel>
		<Channel name="slap">
			<program value="36" />
			<controller ctrl="7" value="80" />
			<controller ctrl="10" value="82" />
			<synti>Fluid</synti>
			<midiPort>1</midiPort>
			<midiChannel>1</midiChannel>
		</Channel>
		<Channel name="pop">
			<program value="37" />
			<controller ctrl="7" value="80" />
			<controller ctrl="10" value="82" />
			<synti>Fluid</synti>
			<midiPort>1</midiPort>
			<midiChannel>2</midiChannel>
		</Channel>
	</Instrument>
</Part>
	""")
	dialog = InstrumentSelectionDialog(None, part)
	if dialog.exec_():
		print(dialog.new_instrument)



#  end musecbox/dialogs/instrument_selection_dialog.py
