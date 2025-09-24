#  musecbox/dialogs/score_import_dialog.py
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
from os.path import join, basename, dirname, splitext
from functools import partial, reduce
from collections import defaultdict
from operator import and_
from shutil import copy2 as copy
from datetime import datetime

# PyQt5 imports
from PyQt5 import			uic
from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import		QIcon
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QInputDialog, \
							QWidget, QSpinBox, QLabel, QAction, QStyle

from qt_extras import SigBlock, ShutUpQT
from qt_extras.list_layout import VListLayout
from qt_extras.menu_button import QtMenuButton
from mscore import Score, Part, Instrument, VoiceName

from musecbox import	set_application_style, APP_PATH, TEXT_NO_GROUP, TEXT_NEW_GROUP, \
						LAYOUT_COMPLETE_DELAY, LOG_FORMAT
from musecbox.dialogs.sfz_file_dialog import SFZFileDialog
from musecbox.dialogs.instrument_selection_dialog import InstrumentSelectionDialog
from musecbox.sfzdb import SFZDatabase


class ScoreImportDialog(QDialog):
	"""
	Dialog which is used to setup importing a MuseScore score.
	Allows the user to select which instruments to import, and which SFZ file to use.
	"""

	def __init__(self, parent, filename):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'score_import_dialog.ui'), self)
		self.filename = filename
		self.restore_geometry()
		self.setFixedWidth(704)
		self.finished.connect(self.save_geometry)

		self.score_edited = False
		path, ext = splitext(filename)
		date_str = datetime.now().strftime('%Y-%m-%d-%H-%M')
		self.backup_name = f'{path}-backup-{date_str}{ext}'

		PartWidget.menu_icon = QIcon(join(APP_PATH, 'res', 'narrow-menu.svg'))
		PartWidget.add_channel_icon = QIcon(join(APP_PATH, 'res', 'plus.svg'))
		ChannelWidget.remove_icon = QIcon(join(APP_PATH, 'res', 'minus.svg'))
		self.lock_icon = QIcon(join(APP_PATH, 'res', 'lock.svg'))
		self.unlock_icon = QIcon(join(APP_PATH, 'res', 'unlock.svg'))
		self.b_may_modify.setIcon(self.lock_icon)
		self.b_cancel.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))
		self.b_okay.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))

		self.part_widgets = VListLayout(end_space = 100)
		# :setContentsMargins(int left, int top, int right, int bottom)
		self.part_widgets.setContentsMargins(8,8,8,16)
		self.part_widgets.setSpacing(16)
		self.frm_parts.setLayout(self.part_widgets)

		self.setCursor(Qt.WaitCursor)
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	def layout_complete(self):
		self.score = EncodingScore(self.filename)

		for part in self.score.parts():
			part_widget = PartWidget(self, part)
			part_widget.sig_channels_changed.connect(self.slot_channels_changed)
			self.part_widgets.append(part_widget)

		for channel_widget in self.findChildren(ChannelWidget):
			channel_widget.sig_sfz_changed.connect(self.slot_sfz_changed)

		self.fill_group_combo()
		self.b_auto_fill.clicked.connect(self.slot_auto_fill)
		self.b_auto_share.clicked.connect(self.slot_auto_share)
		self.b_may_modify.toggled.connect(self.slot_may_modify_toggled)
		self.b_cancel.clicked.connect(self.reject)
		self.b_okay.clicked.connect(self.slot_okay_clicked)
		self.chk_auto_number.stateChanged.connect(self.slot_autonum_chkstate_change)
		self.cmb_group.currentTextChanged.connect(self.group_changed)

		self.overwrite_warning_shown = False
		self.update_enable_states()
		self.unsetCursor()

	def slot_okay_clicked(self, _):
		if self.score_edited:
			while True:
				try:
					copy(self.score.filename, self.backup_name)
				except Exception as e:
					ret = QMessageBox.warning(None, "Backup failed",
						f"""<p>There was an error when creating a backup file:</p><p><b>{e}</b></p>
						<p>If you want to continue making changes to your score without a backup,
						click "Ignore".</p>
						<p>If you would like to fix the problem and try again, click "Retry".</p>""",
						QMessageBox.Ignore | QMessageBox.Retry | QMessageBox.Cancel,
						QMessageBox.Cancel)
					if ret == QMessageBox.Cancel:
						return
					if ret == QMessageBox.Ignore:
						break
				else:
					break
			while True:
				try:
					self.score.save()
				except Exception as e:
					ret = QMessageBox.warning(None, "Failed to save score",
						f"""<p>There was an error when saving your score:</p><p><b>{e}</b></p>
						<p>If you want to continue creating this MusecBox project without saving
						changes to your score, click "Ignore". You can always apply this project to
						your score later, after you find and fix the issue.</p>
						<p>If you would like to fix the problem and try again, click "Retry".</p>""",
						QMessageBox.Ignore | QMessageBox.Retry | QMessageBox.Cancel,
						QMessageBox.Cancel)
					if ret == QMessageBox.Cancel:
						return
					if ret == QMessageBox.Ignore:
						break
				else:
					break
		# Save mappings for when autofilled sfzs are accepted:
		for part_widget in self.part_widgets:
			for chan_widget in part_widget.channel_widgets:
				SFZDatabase().map_instrument(VoiceName(
					part_widget.lbl_instrument_name.text(),
					chan_widget.lbl_voice.text()
				), chan_widget.sfz_filename)
		self.accept()

	@pyqtSlot(str)
	def group_changed(self, text):
		"""
		Triggered by cmb_group.currentTextChanged, allows user to import SFZs into a
		new group.
		(see also: sfzdb module)
		"""
		from musecbox.dialogs.add_group_dialog import AddGroupDialog
		if text == TEXT_NEW_GROUP:
			dlg = AddGroupDialog()
			if dlg.exec():
				self.fill_group_combo()
				self.cmb_group.setCurrentText(dlg.group_name)
			else:
				self.cmb_group.setCurrentText(TEXT_NO_GROUP)

	def fill_group_combo(self):
		"""
		Fills the group selection combo for the auto_fill function.
		"""
		self.cmb_group.clear()
		self.cmb_group.addItem(TEXT_NO_GROUP)
		self.cmb_group.addItems(SFZDatabase().group_names())
		self.cmb_group.addItem(TEXT_NEW_GROUP)

	@pyqtSlot()
	def slot_auto_fill(self):
		"""
		Executes the auto_fill function.
		Chooses the "best" SFZ for each instrument based on the instrument / voice.
		"""
		self.setCursor(Qt.WaitCursor)
		group_name = None if self.cmb_group.currentText() == TEXT_NO_GROUP \
			else self.cmb_group.currentText()
		with SigBlock(* self.findChildren(ChannelWidget)):
			for part_widget in self.part_widgets:
				instrument_name = part_widget.lbl_instrument_name.text()
				for chan_widget in part_widget.channel_widgets:
					chan_widget.set_sfz_filename(SFZDatabase().best_match(
						VoiceName(instrument_name, chan_widget.lbl_voice.text()),
						group_name
					).path)
		self.unsetCursor()
		self.slot_sfz_changed()

	@pyqtSlot()
	def slot_sfz_changed(self):
		self.b_okay.setEnabled(not any(chan_widget.sfz_filename is None \
			for chan_widget in self.findChildren(ChannelWidget)))

	@pyqtSlot(int)
	def slot_autonum_chkstate_change(self, state):
		if state and self.get_edit_permission():
			self.auto_number()
			readonly = True
		else:
			readonly = False
			for chan_widget in self.findChildren(ChannelWidget):
				chan_widget.reset_midi_spinners()
		for widget in self.findChildren(QSpinBox):
			widget.setReadOnly(readonly)

	@pyqtSlot(bool)
	def slot_may_modify_toggled(self, state):
		self.b_may_modify.setIcon(self.unlock_icon if state else self.lock_icon)
		self.update_enable_states()

	def has_edit_perm(self):
		return not self.overwrite_warning_shown or self.b_may_modify.isChecked()

	def get_edit_permission(self):
		if not self.overwrite_warning_shown and not self.b_may_modify.isChecked():
			dlg = ScoreOverwriteDialog(self)
			self.overwrite_warning_shown = True
			if dlg.exec() == QMessageBox.Ok:
				self.b_may_modify.click()
			else:
				self.update_enable_states()
		return self.b_may_modify.isChecked()

	def update_enable_states(self):
		editable = self.has_edit_perm()
		self.chk_auto_number.setEnabled(editable)
		self.chk_auto_number.setChecked(
			bool(self.chk_auto_number.checkState()) and editable)
		for part_widget in self.part_widgets:
			part_widget.update_enable_states()
		if self.chk_auto_number.checkState():
			self.auto_number()

	def auto_number(self):
		port = 1
		channel = 1
		for part_widget in self.part_widgets:
			channels_to_partition = [ chan_widget \
				for chan_widget in part_widget.channel_widgets \
				if chan_widget.make() ]
			if channels_to_partition:
				if channel + len(channels_to_partition) > 17:
					port += 1
					channel = 1
				for chan_widget in channels_to_partition:
					chan_widget.midi_port = port
					chan_widget.midi_channel = channel
					channel += 1
					if channel > 16:
						port += 1
						channel = 1
		self.score_edited = True

	@pyqtSlot()
	def slot_auto_share(self):
		"""
		Share every channel which uses the same SFZ.
		"""
		for chan_widget in self.findChildren(ChannelWidget):
			if not chan_widget.shares_with and chan_widget.may_share_with:
				other_widget = chan_widget.may_share_with.copy().pop()
				if not other_widget.shares_with is chan_widget:
					chan_widget.shares_with = other_widget

	@pyqtSlot()
	def slot_channels_changed(self):
		self.score_edited = True
		if self.chk_auto_number.checkState():
			self.auto_number()

	def find_shared_sfzs(self):
		"""
		Find which channels share the same SFZ.
		Each ChannelWidget's "may_share_with" property is updated.
		"""
		assignments = defaultdict(list)
		for chan_widget in self.findChildren(ChannelWidget):
			if chan_widget.sfz_filename:
				assignments[chan_widget.sfz_filename].append(chan_widget)
		for widget_list in assignments.values():
			for chan_widget in widget_list:
				chan_widget.may_share_with = set(widget_list) - set([chan_widget])
		self.b_auto_share.setEnabled(
			any(len(widget_list) > 1 for widget_list in assignments.values()))

	def track_setup(self):
		"""
		Returns a list of dicts, each dict the definition of a track to add to the project.
		"""
		return [
			{
				'part'			: chan_widget.part_widget().lbl_part_name.text(),
				'instrument'	: chan_widget.part_widget().lbl_instrument_name.text(),
				'voice'			: chan_widget.lbl_voice.text(),
				'midi_port'		: chan_widget.spn_port.value(),
				'midi_channel'	: chan_widget.spn_channel.value(),
				'pan'			: chan_widget.pan,
				'balance'		: chan_widget.balance,
				'sfz'			: chan_widget.sfz_filename
			} for chan_widget in self.findChildren(ChannelWidget) \
			if chan_widget.make() and chan_widget.sfz_filename ]

	def encoded_score(self):
		return self.score.encode_saved_state()


class PartWidget(QWidget):

	sig_channels_changed = pyqtSignal()

	def __init__(self, parent, score_part):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'score_import_part_widget.ui'), self)
		self.score_part = score_part
		self.lbl_part_name.setText(score_part.name)
		self.lbl_instrument_name.setText(score_part.instrument().name)
		self.make = True

		self.b_menu = QtMenuButton(self, fill_callback = self.fill_menu)
		self.b_menu.setIcon(PartWidget.menu_icon)
		self.b_menu.setFixedSize(20, 24)
		self.layout().replaceWidget(self.b_menu_placeholder, self.b_menu)
		self.b_menu_placeholder.setVisible(False)
		self.b_menu_placeholder.deleteLater()
		del self.b_menu_placeholder

		self.channel_widgets = VListLayout(end_space = 18)
		self.channel_widgets.setSpacing(0)
		self.channel_widgets.setContentsMargins(0,0,0,0)
		self.frm_channels.setLayout(self.channel_widgets)

		for channel in score_part.instrument().channels():
			self.append_channel_widget(channel)

	def append_channel_widget(self, score_channel):
		chan_widget = ChannelWidget(self, score_channel)
		chan_widget.sig_remove_channel.connect(self.slot_remove_channel)
		chan_widget.sig_shares_with_changed.connect(self.sig_channels_changed)
		self.channel_widgets.append(chan_widget)

	def parent_dialog(self):
		return self.parent().parent().parent().parent().parent()

	def sfz_dict(self):
		"""
		Returns a dict whose keys are SFZ path, and values are ChannelWidget objects
		"""
		return { chan_widget.sfz_filename:chan_widget \
			for chan_widget in self.channel_widgets \
			if chan_widget.sfz_filename }

	def fill_menu(self):
		self.b_menu.clear()
		self.parent_dialog().find_shared_sfzs()

		sets = [ chan_widget.shareable_part_widgets() \
			for chan_widget in self.channel_widgets ]
		shareable_parts = reduce(and_, sets) if sets else set()
		for other_part_widget in shareable_parts:
			action = QAction(f'Share all tracks with {other_part_widget}', self.b_menu)
			state = self.shares_all_with(other_part_widget)
			action.setCheckable(True)
			action.setChecked(state)
			action.triggered.connect(partial(self.slot_share_all_with, other_part_widget, not state))
			self.b_menu.addAction(action)

		for chan_widget in self.channel_widgets:
			for other_chan_widget in chan_widget.may_share_with:
				action = QAction(f'Share {chan_widget} with {other_chan_widget}', self.b_menu)
				state = chan_widget.shares_with is other_chan_widget
				action.setCheckable(True)
				action.setChecked(state)
				action.triggered.connect(partial(chan_widget.slot_share_with, other_chan_widget, not state))
				self.b_menu.addAction(action)

		self.b_menu.addSeparator()	# ---------------------

		action = QAction('Replace instrument', self.b_menu)
		action.triggered.connect(self.slot_replace_instrument)
		self.b_menu.addAction(action)

		action = QAction('Add a channel', self.b_menu)
		action.setIcon(PartWidget.add_channel_icon)
		action.triggered.connect(self.slot_add_channel)
		self.b_menu.addAction(action)

		self.b_menu.addSeparator()	# ---------------------

		action = QAction('Create these tracks', self.b_menu)
		action.setCheckable(True)
		action.setChecked(self.make)
		action.triggered.connect(self.slot_make_me_checked)
		self.b_menu.addAction(action)

	@pyqtSlot()
	def slot_replace_instrument(self):
		"""
		Called from menu
		"""
		if self.parent_dialog().get_edit_permission():
			dlg = InstrumentSelectionDialog(self, self.score_part)
			if dlg.exec():
				self.score_part.replace_instrument(dlg.new_instrument)
				self.channel_widgets.clear()
				for channel in self.score_part.instrument().channels():
					self.append_channel_widget(channel)
				self.sig_channels_changed.emit()

	@pyqtSlot()
	def slot_add_channel(self):
		"""
		Called from menu.
		"""
		if self.parent_dialog().get_edit_permission():
			channel_name, res = QInputDialog.getText(self, 'New Channel', 'Name of the new channel:')
			if res:
				last_channel = self.channel_widgets[-1].score_channel
				new_channel = self.score_part.instrument().add_channel(channel_name)
				if not last_channel.pan is None:
					new_channel.pan = last_channel.pan
				if not last_channel.balance is None:
					new_channel.balance = last_channel.balance
				if not self.parent_dialog().chk_auto_number.checkState():
					new_channel.midi_port = last_channel.midi_port
					new_channel.midi_channel = last_channel.midi_channel
				self.append_channel_widget(new_channel)
				self.update_enable_states()
				self.sig_channels_changed.emit()

	@pyqtSlot(QWidget)
	def slot_remove_channel(self, chan_widget):
		"""
		Called from existing ChannelWidget
		"""
		if self.parent_dialog().get_edit_permission():
			self.score_part.instrument().remove_channel(chan_widget.lbl_voice.text())
			self.channel_widgets.remove(chan_widget)
			self.update_enable_states()
			self.sig_channels_changed.emit()

	@pyqtSlot(QWidget, bool)
	def slot_share_all_with(self, other_part_widget, state):
		"""
		Called from menu. Set "shares_with" in every channel in other_part_widget.
		"""
		self_chans = self.sfz_dict()
		other_chans = other_part_widget.sfz_dict()
		for key in set(self_chans.keys()) & set(other_chans.keys()):
			self_chans[key].shares_with = other_chans[key] if state else None

	def shares_all_with(self, other_part_widget):
		"""
		Returns true if ALL channels are shared.
		"""
		self_chans = self.sfz_dict()
		other_chans = other_part_widget.sfz_dict()
		for key in set(self_chans.keys()) & set(other_chans.keys()):
			if self_chans[key].shares_with != other_chans[key]:
				return False
		return True

	@pyqtSlot(bool)
	def slot_make_me_checked(self, state):
		self.make = state
		self.update_enable_states()

	def update_enable_states(self):
		for chan_widget in self.channel_widgets:
			chan_widget.update_enable_states()

	def enable_delete(self):
		return len(self.channel_widgets) > 1

	def __str__(self):
		return self.lbl_part_name.text() if hasattr(self, 'lbl_part_name') \
			else super().__str__()

	def __repr__(self):
		return '<PartWidget "{}">'.format(self.lbl_part_name.text()) \
			if hasattr(self, 'lbl_part_name') else super().__repr__()


class ChannelWidget(QWidget):

	sig_remove_channel = pyqtSignal(QWidget)
	sig_shares_with_changed = pyqtSignal()
	sig_sfz_changed = pyqtSignal()

	def __init__(self, parent, score_channel):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'score_import_channel_widget.ui'), self)
		self.sfz_filename = None
		self.score_channel = score_channel
		self.lbl_voice.setText(score_channel.name)
		self.original_midi_port = score_channel.midi_port
		self.original_midi_channel = score_channel.midi_channel
		self.pan = score_channel.pan
		self.balance = score_channel.balance
		if not self.original_midi_port is None:
			self.spn_port.setValue(self.original_midi_port)
		if not self.original_midi_channel is None:
			self.spn_channel.setValue(self.original_midi_channel)
		self.spn_port.valueChanged.connect(self.slot_port_changed)
		self.spn_channel.valueChanged.connect(self.slot_channel_changed)
		self.b_delete.setIcon(ChannelWidget.remove_icon)
		self.b_delete.clicked.connect(self.slot_delete_clicked)
		self.b_select_sfz.clicked.connect(self.slot_sfz_select_click)
		self._may_share_with = set()
		self._shares_with = None
		self._shared_port_connection = None
		self._shared_channel_connection = None

	def part_widget(self):
		return self.parent().parent()

	def parent_dialog(self):
		return self.part_widget().parent_dialog()

	@pyqtSlot()
	def slot_sfz_select_click(self):
		sfz_dialog = SFZFileDialog(VoiceName(
			self.part_widget().lbl_instrument_name.text(),
			self.lbl_voice.text()
		))
		if sfz_dialog.exec():
			self.set_sfz_filename(sfz_dialog.sfz_filename)

	@pyqtSlot(int)
	def slot_port_changed(self, value):
		if self.parent_dialog().get_edit_permission():
			self.midi_port = value
			self.parent_dialog().score_edited = True
		else:
			self.midi_port = self.original_midi_port

	@pyqtSlot(int)
	def slot_channel_changed(self, value):
		if self.parent_dialog().get_edit_permission():
			self.midi_channel = value
			self.parent_dialog().score_edited = True
		else:
			self.midi_channel = self.original_midi_channel

	@property
	def midi_port(self):
		return self.score_channel.midi_port

	@midi_port.setter
	def midi_port(self, value):
		self.score_channel.midi_port = value
		with SigBlock(self.spn_port):
			self.spn_port.setValue(value)

	@property
	def midi_channel(self):
		return self.score_channel.midi_channel

	@midi_channel.setter
	def midi_channel(self, value):
		self.score_channel.midi_channel = value
		with SigBlock(self.spn_channel):
			self.spn_channel.setValue(value)

	def reset_midi_spinners(self):
		self.midi_port = self.original_midi_port
		self.midi_channel = self.original_midi_channel

	@pyqtSlot()
	def slot_delete_clicked(self):
		self.sig_remove_channel.emit(self)

	def set_sfz_filename(self, sfz_filename):
		"""
		Called from both slot_auto_fill and sfz_select_click.
		"""
		self.sfz_filename = sfz_filename
		self.b_select_sfz.setText(basename(self.sfz_filename).replace('&', '&&'))
		self.sig_sfz_changed.emit()

	def shareable_part_widgets(self):
		"""
		Returns a set of PartWidgets that this ChannelWidget "may_share_with".
		When "may_share_with" is empty, returns an empty set.
		"""
		return set(other_chan_widget.part_widget() for other_chan_widget in self._may_share_with)

	@pyqtSlot(QWidget, bool)
	def slot_share_with(self, other_chan_widget, state):
		"""
		Called from menu.
		"""
		self.shares_with = other_chan_widget if state else None

	@property
	def may_share_with(self):
		"""
		Returns all channels in other parts which use the same SFZ.
		"""
		return self._may_share_with

	@may_share_with.setter
	def may_share_with(self, other_chan_widgets):
		"""
		Set all channels in other parts which use the same SFZ.
		"""
		if self._shares_with and not self._shares_with in other_chan_widgets:
			self.shares_with = None
		self._may_share_with = other_chan_widgets

	@property
	def shares_with(self):
		"""
		Returns another part's channel if this channel is duplicated by it, else None
		"""
		return self._shares_with

	@shares_with.setter
	def shares_with(self, other_chan_widget):
		"""
		Set another part's channel as the destination for this channel.
		"""
		if self._shares_with:
			self._shares_with.spn_port.disconnect(self._shared_port_connection)
			self._shares_with.spn_channel.disconnect(self._shared_channel_connection)
		self._shares_with = other_chan_widget
		if self._shares_with:
			self.spn_port.setValue(self._shares_with.spn_port.value())
			self.spn_channel.setValue(self._shares_with.spn_channel.value())
			self._shared_port_connection = \
				self._shares_with.spn_port.valueChanged.connect(self.spn_port.setValue)
			self._shared_channel_connection = \
				self._shares_with.spn_channel.valueChanged.connect(self.spn_channel.setValue)
		self.update_enable_states()
		self.sig_shares_with_changed.emit()

	def make(self):
		"""
		Returns True if this ChannelWidget is not shared and the parent PartWidget is
		flagged to make.
		"""
		return self._shares_with is None and self.part_widget().make

	def update_enable_states(self):
		make = self.make()
		for widget in self.findChildren(QLabel):
			widget.setEnabled(make)
		self.b_select_sfz.setEnabled(make)
		editable = make and self.parent_dialog().has_edit_perm()
		self.spn_port.setEnabled(editable)
		self.spn_channel.setEnabled(editable)
		if not editable:
			self.reset_midi_spinners()
		deleteable = editable and self.part_widget().enable_delete()
		self.b_delete.setEnabled(deleteable)

	def __str__(self):
		return '{} "{}"'.format(
			self.part_widget().lbl_part_name.text(),
			self.lbl_voice.text()) \
			if hasattr(self.part_widget(), 'lbl_part_name') \
			else super().__str__()

	def __repr__(self):
		return '<ChannelWidget {} "{}">'.format(
			self.part_widget().lbl_part_name.text(),
			self.lbl_voice.text()) \
			if hasattr(self.part_widget(), 'lbl_part_name') \
			else super().__repr__()


class ScoreOverwriteDialog(QMessageBox):
	"""
	Dialog which is used to warn when about to modify a MuseScore score.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		self.setIcon(QMessageBox.Warning)
		self.setText('Modify your score?')
		self.setInformativeText("""<p>The operation you requested makes it necessary to
			modify the MuseScore3 file that you are importing from.</p><p>This will not
			affect the notes in your score, but MAY affect the voices available to each
			part.</p><p>A backup will be made. Click "Show Details" to view and copy the
			backup file name.</p>""")
		self.setDetailedText(self.parent().backup_name)
		self.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
		self.setDefaultButton(QMessageBox.Ok)


class EncodingScore(Score):
	"""
	Encodes Score
	Allows for compiling a list of part/instrument with complete instrument xml.
	This allows the instrument definition to be copied to other scores.
	"""

	def encode_saved_state(self):
		parts = EncodingPart.from_elements(self.findall('./Part'))
		return {
			'filename'	: self.filename,
			'parts'		: [ part.encode_saved_state() for part in parts ]
		}


class EncodingPart(Part):
	"""
	Encodes Score.Part
	"""

	def encode_saved_state(self):
		instrument = EncodingInstrument.from_element(self.find('./Instrument'))
		return {
			'name'			: self.name,
			'instrument'	: instrument.encode_saved_state()
		}


class EncodingInstrument(Instrument):
	"""
	Encodes Score.Part.Instrument
	"""

	def encode_saved_state(self):
		return {
			'name'		: self.name,
			'xml'		: self.concise_xml()
		}


if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dialog = ScoreImportDialog(None, join(APP_PATH, 'res', 'musescore_score.mscx'))
	if dialog.exec_():
		from pprint import pprint
		pprint(dialog.track_setup())
		pprint(dialog.encoded_score())


#  end musecbox/dialogs/score_import_dialog.py
