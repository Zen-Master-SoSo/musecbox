#  musecbox/dialogs/sfzdb_dialog.py
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
Provides a database of SFZ files which may be organized by groups.
"""
import logging
from os.path import join, dirname
from qt_extras import ShutUpQT

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot, QEvent
from PyQt5.QtWidgets import QApplication, QDialog, QMenu, QListWidgetItem

from musecbox import bold, unbold, TEXT_NO_GROUP, LOG_FORMAT
from musecbox.sfzdb import SFZDatabase
from musecbox.dialogs.add_group_dialog import AddGroupDialog


class SFZMaintDialog(QDialog):

	def __init__(self):
		super().__init__()
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'sfzdb_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)
		self.lst_groups.currentItemChanged.connect(self.slot_group_item_changed)
		self.lst_sfzs.itemSelectionChanged.connect(self.slot_sfzs_selection_changed)
		self.lst_groups.installEventFilter(self)
		self.lst_sfzs.installEventFilter(self)
		self.lst_mappings.installEventFilter(self)
		self.db = SFZDatabase()
		self.fill_groups()
		self.lst_groups.setCurrentItem(self.lst_groups.item(0))

		self.txt_group_search.textChanged.connect(self.group_search_changed)
		self.b_group_search.clicked.connect(self.clear_group_search)

		self.txt_sfz_search.textChanged.connect(self.sfz_search_changed)
		self.b_sfz_search.clicked.connect(self.clear_sfz_search)

		self.txt_instrument_search.textChanged.connect(self.instrument_search_changed)
		self.b_instrument_search.clicked.connect(self.clear_instrument_search)

		self.fill_sfzs()

	def fill_groups(self):
		self.lst_groups.clear()
		self.lst_sfzs.clear()
		self.lst_mappings.clear()
		self.lst_groups.addItem(TEXT_NO_GROUP)
		self.lst_groups.addItems(self.db.group_names())
		self.show_sfz_count(0)

	def fill_sfzs(self):
		item = self.lst_groups.currentItem()
		group_name = item.text() if item else TEXT_NO_GROUP
		self.lst_sfzs.clear()
		self.lst_mappings.clear()
		for sfz_record in self.db.sfzs(
			None if group_name == TEXT_NO_GROUP else group_name):
			sfz_list_item = QListWidgetItem(self.lst_sfzs)
			sfz_list_item.setText(sfz_record.path)
			if sfz_record.mappings():
				bold(sfz_list_item)
			sfz_list_item.setData(Qt.UserRole, sfz_record)
			self.lst_sfzs.addItem(sfz_list_item)
		self.filter_sfz_list()

	def eventFilter(self, source, event):
		if event.type() == QEvent.ContextMenu:
			item = source.itemAt(event.pos())
			menu = QMenu(self)
			if source is self.lst_groups:
				return self.group_context_menu(event, item, menu)
			if source is self.lst_sfzs:
				return self.sfz_context_menu(event, item, menu)
			if source is self.lst_mappings:
				return self.instruments_context_menu(event, item, menu)
		return False

	# ----------------------------------------
	# Context menus

	def group_context_menu(self, event, item, menu):
		action_add_group = menu.addAction('Add group')
		action_remove = menu.addAction(f'Remove "{item.text()}"') \
			if item is not None \
			else None
		action_add_sfzs = menu.addAction('Add SFZs') \
			if item is not None \
			else None
		action_select_all = menu.addAction('Select all') \
			if self.lst_groups.count() > len(self.lst_groups.selectedItems()) \
			else None
		action = menu.exec_(event.globalPos())
		if action is None:
			return True
		if action is action_remove:
			self.db.remove_group(item.text())
			self.fill_groups()
		elif action is action_select_all:
			self.lst_groups.selectAll()
		elif action is action_add_group:
			dlg = AddGroupDialog()
			if dlg.exec():
				self.fill_groups()
				for item in self.lst_groups.findItems(dlg.group_name, Qt.MatchExactly):
					item.setSelected(True)
					break
				self.fill_sfzs()
		elif action is action_add_sfzs:
			from musecbox.dialogs.sfz_file_dialog import SFZFileDialog
			dlg = SFZFileDialog()
			if dlg.exec():
				# TODO: UNFINISHED!
				logging.debug(dlg.files)
		return True

	def sfz_context_menu(self, event, item, menu):
		visible_items = [ self.lst_sfzs.item(row) \
			for row in range(self.lst_sfzs.count()) \
			if not self.lst_sfzs.item(row).isHidden() ]
		len_selected = len(self.lst_sfzs.selectedItems())
		action_remove = menu.addAction(f'Remove "{item.text()}"') \
			if item is not None and len_selected == 1 \
			else None
		action_select_all = menu.addAction('Select all') \
			if len(visible_items) > len(self.lst_sfzs.selectedItems()) \
			else None
		action_remove_selected = menu.addAction('Remove selected') \
			if len_selected > 1 \
			else None
		action = menu.exec_(event.globalPos())
		if action is None:
			return True
		if action is action_remove:
			self.db.remove_sfz(item.data(Qt.UserRole).path)
			self.lst_sfzs.takeItem(self.lst_sfzs.row(item))
		elif action is action_select_all:
			for item in visible_items:
				item.setSelected(True)
		elif action is action_remove_selected:
			self.db.remove_sfzs([ item.data(Qt.UserRole).path \
				for item in self.lst_sfzs.selectedItems() ])
			self.fill_sfzs()
		return True

	def instruments_context_menu(self, event, item, menu):
		forget_item = menu.addAction(f'Forget "{item.text()}"') \
			if item is not None else None
		forget_all = menu.addAction('Forget all mappings')
		action = menu.exec_(event.globalPos())
		if action is not None:
			if action is forget_item:
				self._forget_mapping(item)
				self.lst_mappings.takeItem(self.lst_mappings.row(item))
			elif action is forget_all:
				for row in range(self.lst_mappings.count()):
					self._forget_mapping(self.lst_mappings.item(row))
				self.lst_mappings.clear()
		return True

	def _forget_mapping(self, item):
		sfz_list_item, voice_name = item.data(Qt.UserRole)
		sfz_record = sfz_list_item.data(Qt.UserRole)
		self.db.forget_mapping(voice_name, sfz_record.path)
		if not sfz_record.mappings():
			unbold(sfz_list_item)

	# ----------------------------------------
	# List interactions

	@pyqtSlot(QListWidgetItem, QListWidgetItem)
	def slot_group_item_changed(self, *_):
		self.fill_sfzs()

	@pyqtSlot()
	def slot_sfzs_selection_changed(self):
		self.lst_mappings.clear()
		for item in self.lst_sfzs.selectedItems():
			sfz_record = item.data(Qt.UserRole)
			for voice_name in sfz_record.mappings():
				map_list_item = QListWidgetItem(self.lst_mappings)
				map_list_item.setText(str(voice_name))
				map_list_item.setData(Qt.UserRole, (item, voice_name))
				self.lst_sfzs.addItem(map_list_item)
		self.filter_mappings_list()

	# ----------------------------------------
	# Filter boxes

	@pyqtSlot(str)
	def group_search_changed(self, text):
		self.filter_group_list(text)

	@pyqtSlot()
	def clear_group_search(self):
		self.txt_group_search.setText('')

	@pyqtSlot(str)
	def sfz_search_changed(self, _):
		self.filter_sfz_list()

	@pyqtSlot()
	def clear_sfz_search(self):
		self.txt_sfz_search.setText('')

	@pyqtSlot(str)
	def instrument_search_changed(self, _):
		self.filter_mappings_list()

	@pyqtSlot()
	def clear_instrument_search(self):
		self.txt_instrument_search.setText('')

	def filter_group_list(self, text):
		if len(text):
			text = text.lower()
		else:
			text = False
		for i in range(self.lst_groups.count()):
			item = self.lst_groups.item(i)
			item.setHidden(text and not text in item.text().lower())

	def filter_sfz_list(self):
		text = self.txt_sfz_search.text()
		if len(text):
			text = text.lower()
		else:
			text = False
		cnt = 0
		for i in range(self.lst_sfzs.count()):
			item = self.lst_sfzs.item(i)
			hide = text and not text in item.text().lower()
			item.setHidden(hide)
			if not hide:
				cnt += 1
		self.show_sfz_count(cnt)

	def filter_mappings_list(self):
		text = self.txt_instrument_search.text()
		if len(text):
			text = text.lower()
		else:
			text = False
		for i in range(self.lst_mappings.count()):
			item = self.lst_mappings.item(i)
			item.setHidden(text and not text in item.text().lower())

	# ----------------------------------------
	# Status label

	def show_sfz_count(self, cnt):
		if cnt == 0:
			self.lbl_status.setText('No SFZs')
		elif cnt == 1:
			self.lbl_status.setText('1 SFZ')
		else:
			self.lbl_status.setText('{} SFZs'.format(cnt))


if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	window = SFZMaintDialog()
	window.show()
	app.exec()


#  end musecbox/sfzdb.py
