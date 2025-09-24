#  musecbox/dialogs/add_group_dialog.py
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
Provides a dlg for selecting SFZ files from either the file system or the
integrated database.
"""
import logging
from glob import glob
from os.path import join, dirname, basename, realpath
from qt_extras import ShutUpQT

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, QDir, QPoint, QModelIndex, QItemSelection
from PyQt5.QtWidgets import QApplication, QDialog, QFileSystemModel, QAbstractItemView, \
	QDialogButtonBox, QListWidgetItem, QMenu

# musecbox imports
from musecbox import	setting, set_setting, set_application_style, KEY_SFZ_DIR, \
						LAYOUT_COMPLETE_DELAY, LOG_FORMAT
from musecbox.sfzdb import SFZDatabase

KEY_DIRECTORY			= 'AddGroupDialog/directory'

TEXT_ADD_ALL			= 'Add all in this folder'
TEXT_ADD_ALL_RECURSIVE	= 'Add all in this folder and all subfolders'
TEXT_ADD_SELECTED		= 'Add selected'
TEXT_REMOVE_SELECTED	= 'Remove selected SFZs'
TEXT_REMOVE_ALL			= 'Remove all SFZs'
TEXT_NEW_GROUP_NAME		= 'New'
TEXT_ADDED_ONE			= '1 SFZ will be added to the {} group'
TEXT_ADDED_MANY			= '{} SFZs will be added to the {} group'
TEXT_ADDED_NONE			= 'No SFZs added yet (cannot create an empty group)'


class AddGroupDialog(QDialog):
	"""
	Allows user to add a new group of SFZs.
	"""

	def __init__(self):
		super().__init__()
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'add_group_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.accepted.connect(self.slot_accepted)

		self.sfzs = []
		self.existing_groups = SFZDatabase().group_names()
		self.lbl_warning.setVisible(False)
		self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
		self.group_edited = False
		self.ed_group_name.textChanged.connect(self.slot_group_changed)
		self.ed_group_name.textEdited.connect(self.slot_group_edited)
		self.b_clear_sfzs.clicked.connect(self.slot_clear_sfzs)

		self.directory_model = QFileSystemModel()
		self.tree_directories.setModel(self.directory_model)
		self.directory_model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
		self.directory_model.setNameFilters(['*.sfz'])
		self.directory_model.setNameFilterDisables(False)
		self.directory_model.setRootPath(QDir.rootPath())
		root_path = setting(KEY_SFZ_DIR, str, QDir.homePath())
		self.tree_directories.setRootIndex(self.directory_model.index(root_path))
		self.tree_directories.hideColumn(1)
		self.tree_directories.hideColumn(2)
		self.tree_directories.hideColumn(3)
		self.tree_directories.selectionModel().currentChanged.connect(self.slot_tree_current_changed)
		self.tree_directories.selectionModel().selectionChanged.connect(self.slot_tree_selection_changed)
		self.tree_directories.setContextMenuPolicy(Qt.CustomContextMenu)
		self.tree_directories.customContextMenuRequested.connect(self.slot_tree_context_menu)

		self.lst_sfzs.setContextMenuPolicy(Qt.CustomContextMenu)
		self.lst_sfzs.customContextMenuRequested.connect(self.slot_sfz_context_menu)

		index = self.directory_model.index(self.directory)
		self.tree_directories.setCurrentIndex(index)
		self.tree_directories.setExpanded(index, True)
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	@pyqtSlot()
	def layout_complete(self):
		index = self.directory_model.index(self.directory)
		self.tree_directories.scrollTo(index, QAbstractItemView.PositionAtTop)

	@pyqtSlot(str)
	def slot_group_changed(self, text):
		if text in self.existing_groups:
			self.lbl_warning.setVisible(True)
			self.lbl_warning.setText(f'* "{text}" is already used')
			self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
		else:
			self.lbl_warning.setVisible(False)
			self.buttons.button(QDialogButtonBox.Ok).setEnabled(len(text) > 2)

	@pyqtSlot(str)
	def slot_group_edited(self, text):
		self.group_edited = len(text) > 0

	@property
	def group_name(self):
		return self.ed_group_name.text()

	@property
	def directory(self):
		return setting(KEY_DIRECTORY, str, QDir.homePath())

	@directory.setter
	def directory(self, value):
		set_setting(KEY_DIRECTORY, realpath(value))

	@pyqtSlot(QModelIndex, QModelIndex)
	def slot_tree_current_changed(self, current, _):
		if self.directory_model.isDir(current):
			self.directory = self.directory_model.filePath(current)
			if not self.group_edited:
				self.ed_group_name.setText(basename(self.directory))
			dir_count = len(self.current_directory_sfzs(False))
			self.lbl_status.setText(f'{self.directory}: {dir_count} SFZs')
		else:
			self.directory = None

	@pyqtSlot(QItemSelection, QItemSelection)
	def slot_tree_selection_changed(self, *_):
		current_indexes = self.tree_directories.selectionModel().selectedIndexes()
		self.selected_sfzs = list(set([ self.directory_model.filePath(index) \
			for index in current_indexes \
			if not self.directory_model.isDir(index) ]))

	@pyqtSlot(QPoint)
	def slot_tree_context_menu(self, position):
		menu = QMenu(self)

		add_all_action = menu.addAction(TEXT_ADD_ALL) \
			if self.directory else None
		add_all_recursive_action = menu.addAction(TEXT_ADD_ALL_RECURSIVE) \
			if self.directory else None
		if self.directory:
			menu.addSeparator()	# ---------------------

		add_selected = menu.addAction(TEXT_ADD_SELECTED) \
			if self.selected_sfzs else None
		if self.selected_sfzs:
			menu.addSeparator()	# ---------------------

		root_path = self.directory_model.filePath(self.tree_directories.rootIndex())
		set_root_action = menu.addAction('Set as directory root')
		set_root_action.setEnabled(self.directory != root_path)
		up_level_action = menu.addAction('Up to parent directory')
		up_level_action.setEnabled(root_path != QDir.rootPath())
		collapse_action = menu.addAction('Collapse All')

		action = menu.exec(self.tree_directories.mapToGlobal(position))
		if action is not None:
			if action is add_all_action:
				self.append_sfzs(self.current_directory_sfzs(False))
			elif action is add_all_recursive_action :
				self.append_sfzs(self.current_directory_sfzs(True))
			elif action is add_selected:
				self.append_sfzs(self.selected_sfzs)
			elif action is collapse_action:
				self.tree_directories.collapseAll()
			elif action is set_root_action:
				set_setting(KEY_SFZ_DIR, realpath(self.directory))
				self.tree_directories.setRootIndex(self.tree_directories.currentIndex())
			elif action is up_level_action:
				root_path = dirname(root_path)
				set_setting(KEY_SFZ_DIR, realpath(root_path))
				index = self.directory_model.index(root_path)
				self.tree_directories.setRootIndex(index)

	def append_sfzs(self, path_list):
		for path in path_list:
			if not path in self.sfzs:
				list_item = QListWidgetItem(self.lst_sfzs)
				list_item.setToolTip(path)
				list_item.setText(basename(path))
				list_item.setData(Qt.UserRole, path)
				self.lst_sfzs.addItem(list_item)
				self.sfzs.append(path)
		self.update_count()

	@pyqtSlot()
	def slot_clear_sfzs(self):
		self.lst_sfzs.clear()
		self.sfzs = []
		self.update_count()

	@pyqtSlot(QPoint)
	def slot_sfz_context_menu(self, position):
		menu = QMenu(self)
		if self.lst_sfzs.count():
			selected_items = self.lst_sfzs.selectedItems()
			remove_selected = menu.addAction(TEXT_REMOVE_SELECTED) \
				if len(selected_items) else None
			remove_all = menu.addAction(TEXT_REMOVE_ALL)
		action = menu.exec(self.lst_sfzs.mapToGlobal(position))
		if action is not None:
			if action is remove_selected:
				for item in selected_items:
					path = item.data(Qt.UserRole)
					del self.sfzs[self.sfzs.index(path)]
					self.lst_sfzs.takeItem(self.lst_sfzs.row(item))
					del item
				self.update_count()
			elif action is remove_all:
				self.slot_clear_sfzs()

	def current_directory_sfzs(self, recursive):
		return sorted(
			glob(f'{self.directory}/**/*.sfz', recursive = True) \
			if recursive else \
			glob(f'{self.directory}/*.sfz')
		)

	def update_count(self):
		size = len(self.sfzs)
		grp = f'"{self.group_name}"' if self.group_name else TEXT_NEW_GROUP_NAME
		if size:
			if size == 1:
				text = TEXT_ADDED_ONE.format(grp)
			else:
				text = TEXT_ADDED_MANY.format(size, grp)
		else:
			text = TEXT_ADDED_NONE
		self.lbl_status.setText(text)

	@pyqtSlot()
	def slot_accepted(self):
		SFZDatabase().assign_group(self.group_name, self.sfzs)


if __name__ == "__main__":
	from rich.pretty import pprint
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dlg = AddGroupDialog()
	dlg.show()
	if dlg.exec():
		print(f'Group name: {dlg.group_name}')
		pprint(dlg.sfzs)


#  end musecbox/dialogs/add_group_dialog.py
