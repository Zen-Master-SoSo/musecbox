#  musecbox/dialogs/sfz_file_dialog.py
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
Provides a dialog for selecting SFZ files from either the file system or the
integrated database.
"""
import logging, glob
from os.path import join, dirname, basename, realpath
from functools import partial
from qt_extras import ShutUpQT
from qt_extras.list_button import QtListButton

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import	Qt, pyqtSlot, QVariant, QDir, QPoint, QModelIndex
from PyQt5.QtCore import	QTimer
from PyQt5.QtWidgets import	QApplication, QDialog, QFileSystemModel, QAbstractItemView, \
							QDialogButtonBox, QListWidgetItem, QMenu

# musecbox imports
from mscore import VoiceName
from musecbox import 	carla, previewer, setting, set_setting, set_application_style, bold, \
						TEXT_NO_CONN, TEXT_NO_GROUP, TEXT_NEW_GROUP, KEY_SFZ_DIR, \
						KEY_PREVIEW_FILES, KEY_PREVIEWER_MIDI_SRC, KEY_PREVIEWER_AUDIO_TGT, \
						LAYOUT_COMPLETE_DELAY, LOG_FORMAT, EngineInitFailure
from musecbox.dialogs.add_group_dialog import AddGroupDialog
from musecbox.sfz_previewer import SFZPreviewer
from musecbox.sfzdb import SFZDatabase

SOURCE_TYPE_DIR		= 1
SOURCE_TYPE_GROUP	= 2
KEY_SELECT_SOURCE	= 'SFZFileDialog/sel_source'
KEY_DIRECTORY		= 'SFZFileDialog/directory'
KEY_GROUP			= 'SFZFileDialog/group'


class SFZFileDialog(QDialog):

	def __init__(self, voice_name = None):
		super().__init__()
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'sfz_file_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.finished.connect(previewer().deactivate)
		self.accepted.connect(self.slot_accepted)
		self.setModal(True)

		root_path = setting(KEY_SFZ_DIR, str, QDir.rootPath())

		self.voice_name = voice_name
		if self.voice_name is not None:
			self.setWindowTitle(f'Select SFZ for "{self.voice_name}"')
		self.sfz_filename = None

		self.initializing = True
		self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
		self.db = SFZDatabase()

		self.directory_model = QFileSystemModel()
		self.directory_model.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
		self.directory_model.setRootPath(QDir.rootPath())
		self.tree_directories.setModel(self.directory_model)
		self.tree_directories.setRootIndex(self.directory_model.index(root_path))
		self.tree_directories.hideColumn(1)
		self.tree_directories.hideColumn(2)
		self.tree_directories.hideColumn(3)
		self.tree_directories.selectionModel().currentChanged.connect(self.slot_directory_current_changed)
		self.tree_directories.setContextMenuPolicy(Qt.CustomContextMenu)
		self.tree_directories.customContextMenuRequested.connect(self.slot_directory_context_menu)

		self.fill_group_list()
		self.lst_groups.currentItemChanged.connect(self.slot_groups_current_changed)
		self.lst_groups.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_groups.customContextMenuRequested.connect(self.slot_group_context_menu)

		self.lst_sfzs.currentItemChanged.connect(self.slot_sfz_selection_changed)
		self.lst_sfzs.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_sfzs.customContextMenuRequested.connect(self.slot_sfz_context_menu)
		self.lst_sfzs.itemDoubleClicked.connect(self.slot_sfz_double_click)

		self.txt_search.textChanged.connect(self.slot_search_box_changed)
		self.b_clear_search.clicked.connect(self.slot_clear_search_clicked)

		index = self.directory_model.index(self.directory)
		self.tree_directories.setExpanded(index, True)
		self.tree_directories.setCurrentIndex(index)

		for item in self.lst_groups.findItems(self.group_name, Qt.MatchExactly):
			item.setSelected(True)
			if self.selection_source == SOURCE_TYPE_GROUP:
				self.select_group(item)
			break

		# Setup input select button:
		self.b_input = QtListButton(self, SFZPreviewer.midi_sources)
		self.b_input.setText(setting(KEY_PREVIEWER_MIDI_SRC, str, TEXT_NO_CONN))
		self.b_input.sig_item_selected.connect(self.slot_input_selected)
		self.input_layout.replaceWidget(self.input_select_placeholder, self.b_input)
		self.input_select_placeholder.setVisible(False)
		self.input_select_placeholder.deleteLater()
		del self.input_select_placeholder

		# Setup output select button:
		self.b_output = QtListButton(self, SFZPreviewer.audio_targets)
		self.b_output.setText(setting(KEY_PREVIEWER_AUDIO_TGT, str, TEXT_NO_CONN))
		self.b_output.sig_item_selected.connect(self.slot_output_client_selected)
		self.output_layout.replaceWidget(self.b_output_placeholder, self.b_output)
		self.b_output_placeholder.setVisible(False)
		self.b_output_placeholder.deleteLater()
		del self.b_output_placeholder

		self.chk_live_preview.stateChanged.connect(self.slot_chk_preview_state)
		enable = setting(KEY_PREVIEW_FILES, bool)
		self.chk_live_preview.setChecked(enable)
		self.frm_preview_settings.setEnabled(enable)

		# Delay after showing dialog so Qt can scroll tree_directories correctly
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	@pyqtSlot()
	def layout_complete(self):
		index = self.directory_model.index(self.directory)
		self.tree_directories.scrollTo(index, QAbstractItemView.PositionAtTop)
		self.lst_sfzs.setFocus()
		self.initializing = False

	@pyqtSlot(str, QVariant)
	def slot_input_selected(self, _, midi_src):
		previewer().midi_src = midi_src

	@pyqtSlot(str, QVariant)
	def slot_output_client_selected(self, _, audio_tgt):
		previewer().audio_tgt = audio_tgt

	@pyqtSlot(int)
	def slot_chk_preview_state(self, state):
		enable = bool(state)
		self.frm_preview_settings.setEnabled(enable)
		previewer().active = enable
		set_setting(KEY_PREVIEW_FILES, enable)

	# ------------------------------------------------
	# Directory / Group / SFZ selection change events:

	@pyqtSlot(QModelIndex)
	def slot_directory_current_changed(self, index):
		self.directory = self.directory_model.filePath(index)
		self.lbl_directory.setText(self.directory)
		if not self.initializing or self.selection_source == SOURCE_TYPE_DIR:
			self.lbl_selection.setText('Directory "%s"' % basename(self.directory))
			entries = glob.glob('%s/*.sfz' % self.directory)
			if entries:
				self.fill_sfz_list(self.db.sfzs_by_paths(entries), None, False)
			else:
				self.lst_sfzs.clear()
			self.selection_source = SOURCE_TYPE_DIR

	@pyqtSlot(QListWidgetItem)
	def slot_groups_current_changed(self, item):
		if self.lst_groups.hasFocus() and not item is None:
			self.select_group(item)

	@pyqtSlot(QListWidgetItem, QListWidgetItem)
	def slot_sfz_selection_changed(self, current, _):
		ok = not current is None and not current.data(Qt.UserRole) is None
		self.buttons.button(QDialogButtonBox.Ok).setEnabled(ok)
		self.sfz_filename = current.data(Qt.UserRole).path if ok else None
		if ok:
			previewer().load_sfz(self.sfz_filename)

	# -------------------------------------------------
	# Properties which are directly mapped to settings:

	@property
	def directory(self):
		return setting(KEY_DIRECTORY, str, QDir.homePath())

	@directory.setter
	def directory(self, value):
		set_setting(KEY_DIRECTORY, realpath(value))

	@property
	def group_name(self):
		return setting(KEY_GROUP, str, TEXT_NO_GROUP)

	@group_name.setter
	def group_name(self, value):
		set_setting(KEY_GROUP, value)

	@property
	def selection_source(self):
		return setting(KEY_SELECT_SOURCE, int, SOURCE_TYPE_DIR)

	@selection_source.setter
	def selection_source(self, value):
		set_setting(KEY_SELECT_SOURCE, value)

	# -------------------------------------------------
	# Context menu handlers:

	@pyqtSlot(QPoint)
	def slot_directory_context_menu(self, position):
		menu = QMenu(self)
		index = self.tree_directories.rootIndex()
		root_path = self.directory_model.filePath(index)
		set_root_action = menu.addAction('Set as directory root')
		up_level_action = menu.addAction('Up to parent directory')
		up_level_action.setEnabled(root_path != QDir.rootPath())
		collapse_action = menu.addAction('Collapse All')
		menu.addSeparator()	# ---------------------
		group_menu = menu.addMenu('Add all to group:')
		for group_name in self.db.group_names():
			group_menu.addAction(group_name)
		add_group_action = group_menu.addAction(TEXT_NEW_GROUP)
		action = menu.exec(self.tree_directories.mapToGlobal(position))
		if action is not None:
			if action is collapse_action:
				self.tree_directories.collapseAll()
			elif action is add_group_action:
				if group_name := self.show_add_group():
					self.assign_dir_to_group(group_name)
			elif action is set_root_action:
				set_setting(KEY_SFZ_DIR, realpath(self.directory))
				self.tree_directories.setRootIndex(self.tree_directories.currentIndex())
			elif action is up_level_action:
				root_path = dirname(root_path)
				set_setting(KEY_SFZ_DIR, realpath(root_path))
				self.lbl_directory.setText(root_path)
				index = self.directory_model.index(root_path)
				self.tree_directories.setRootIndex(index)
			else:
				self.assign_dir_to_group(action.text())

	@pyqtSlot(QPoint)
	def slot_group_context_menu(self, position):
		menu = QMenu(self)
		item = self.lst_groups.currentItem()
		if item is not None and item.text() != TEXT_NO_GROUP:
			remove_group_action = menu.addAction('Delete group "%s"' % item.text())
		add_group_action = menu.addAction(TEXT_NEW_GROUP)
		action = menu.exec(self.lst_groups.mapToGlobal(position))
		if action is add_group_action:
			if group_name := self.show_add_group():
				self.lst_sfzs.clear()
				self.fill_group_list()
				for item in self.lst_groups.findItems(group_name, Qt.MatchExactly):
					self.lst_groups.setCurrentItem(item)
					self.select_group(item)
					break
		elif action:
			self.db.remove_group(item.text())
			self.lst_sfzs.clear()
			self.fill_group_list()


	@pyqtSlot(QPoint)
	def slot_sfz_context_menu(self, position):
		item = self.lst_sfzs.currentItem()
		if item is not None:
			menu = QMenu(self)
			for group_name in self.db.group_names():
				menu.addAction('Add to "%s" group' % group_name,
					partial(self.assign_sfz_to_group, group_name, item))
			add_group_action = menu.addAction('Add to new group ...')
			action = menu.exec(self.lst_sfzs.mapToGlobal(position))
			if action is add_group_action:
				if group_name := self.show_add_group():
					self.assign_sfz_to_group(group_name, item)

	# -------------------------------------------------
	# Filtering:

	@pyqtSlot(str)
	def slot_search_box_changed(self, text):
		self.filter_sfz_list(text)

	@pyqtSlot()
	def slot_clear_search_clicked(self):
		self.txt_search.setText('')

	def filter_sfz_list(self, text):
		if len(text):
			text = text.lower()
		else:
			text = False
		for i in range(self.lst_sfzs.count()):
			item = self.lst_sfzs.item(i)
			item.setHidden(text and not text in item.text().lower())

	# -------------------------------------------------
	# Fill lists:

	def fill_group_list(self):
		self.lst_groups.clear()
		self.lst_groups.addItem(TEXT_NO_GROUP)
		self.lst_groups.addItems(self.db.group_names())

	def fill_sfz_list(self, sfzs, group_name, show_dirs):
		self.lst_sfzs.clear()
		if self.voice_name:
			mapped, unmapped = self.db.ranked_sfzs(self.voice_name, sfzs, group_name = group_name)
			for sfz in mapped:
				self._append_sfz(sfz, True, show_dirs)
			for sfz in unmapped:
				self._append_sfz(sfz, False, show_dirs)
		else:
			for sfz in sfzs:
				self._append_sfz(sfz, False, show_dirs)
		self.filter_sfz_list(self.txt_search.text())

	def select_group(self, item):
		group_name = item.text()
		if group_name == TEXT_NO_GROUP:
			self.fill_sfz_list(self.db.sfzs(), None, True)
			self.lbl_selection.setText('All SFZs')
		else:
			self.fill_sfz_list(self.db.sfzs(group_name), group_name, True)
			self.lbl_selection.setText('Group "%s"' % group_name)
		self.group_name = group_name
		self.selection_source = SOURCE_TYPE_GROUP

	def _append_sfz(self, sfz, mapped, show_dirs):
		sfz_list_item = QListWidgetItem(self.lst_sfzs)
		sfz_list_item.setToolTip(sfz.path)
		sfz_list_item.setText(f'{sfz.dirname} / {sfz.title}' \
			if show_dirs else sfz.title)
		sfz_list_item.setData(Qt.UserRole, sfz)
		if mapped:
			bold(sfz_list_item)

	def show_add_group(self):
		dlg = AddGroupDialog()
		return dlg.group_name if dlg.exec() else None

	def assign_dir_to_group(self, group_name):
		entries = glob.glob('%s/**/*.sfz' % self.directory, recursive = True)
		self.db.insert_sfzs(entries)
		self.db.assign_group(group_name, entries)
		self.lst_groups.clear()
		self.lst_groups.addItems(self.db.group_names())

	def assign_sfz_to_group(self, group_name, item):
		self.db.assign_group(group_name, [item.data(Qt.UserRole).path])
		self.fill_group_list()

	# -------------------------------------------------
	# Accept & close:

	@pyqtSlot(QListWidgetItem)
	def slot_sfz_double_click(self, item):
		self.sfz_filename = item.data(Qt.UserRole).path
		self.accept()

	@pyqtSlot()
	def slot_accepted(self):
		if self.voice_name is not None:
			self.db.map_instrument(self.voice_name, self.sfz_filename)

	@pyqtSlot()
	def closeEvent(self, _):
		logging.debug('closeEvent')


class TestApp(QApplication):

	def __init__(self):
		super().__init__([])
		set_application_style()
		carla().sig_engine_started.connect(self.slot_engine_started, type = Qt.QueuedConnection)
		if not carla().engine_init():
			raise EngineInitFailure()

	@pyqtSlot(int, int, int, int, float, str)
	def slot_engine_started(*_):
		logging.debug('======= Engine started ======== ')
		dialog = SFZFileDialog(VoiceName('Violins II', None))
		if dialog.exec():
			print(dialog.sfz_filename)
		carla().delete()


def main():
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	TestApp().exec()


if __name__ == "__main__":
	main()


#  end musecbox/dialogs/sfz_file_dialog.py
