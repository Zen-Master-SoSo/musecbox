#  musecbox/gui/plugin_widgets.py
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
Provides base class for widgets which abstract audio plugins.
"""
import logging
from os.path import join, dirname
from math import floor
from operator import attrgetter
from itertools import chain
from qt_extras import ShutUpQT, SigBlock
from qt_extras.list_button import QtListButton
from qt_extras.autofit import abbreviated_text
from simple_carla import SystemPatchbayClient, PatchbayPort, Plugin, Parameter
from simple_carla.qt import AbstractQtPlugin

# PyQt5 imports
from PyQt5 import uic
from PyQt5.QtCore import	Qt, pyqtSignal, pyqtSlot, QEvent, QVariant, \
							QPoint, QRect, pyqtProperty, QPropertyAnimation
from PyQt5.QtGui import		QPainter, QColor, QBrush, QPen, QPalette, \
							QPixmap, QIcon, QFontMetrics
from PyQt5.QtWidgets import QWidget, QDialog, QInputDialog, QLabel, QFrame, \
							QProgressBar, QHBoxLayout, QVBoxLayout, QGridLayout, \
							QAction, QSizePolicy

from musecbox import	carla, main_window, \
						APP_PATH, TEXT_NO_CONN, TEXT_MULTI_CONN
from musecbox.dialogs.generic_plugin_dialog import PluginDialog
from musecbox.gui.balance_control_widget import \
	GRAB_CENTER, GRAB_LEFT_BALANCE, GRAB_RIGHT_BALANCE, GRAB_PANNING


# -----------------------------------------------------------------
# Base class for all visible plugins, Track and Shared:

class PluginWidget(AbstractQtPlugin, QFrame):

	sig_ready						= pyqtSignal(Plugin)
	sig_removed 					= pyqtSignal(Plugin)
	sig_connection_change			= pyqtSignal(PatchbayPort, PatchbayPort, bool)
	sig_parameter_changed			= pyqtSignal(Plugin, Parameter, float)
	sig_active_changed				= pyqtSignal(Plugin, bool)
	sig_dry_wet_changed				= pyqtSignal(Plugin, float)
	sig_volume_changed				= pyqtSignal(Plugin, float)
	sig_balance_left_changed		= pyqtSignal(Plugin, float)
	sig_balance_right_changed		= pyqtSignal(Plugin, float)
	sig_panning_changed				= pyqtSignal(Plugin, float)
	sig_ctrl_channel_changed		= pyqtSignal(Plugin, float)

	fixed_height			= None
	fixed_width				= None
	pb_indicator_height		= 22

	def __init__(self, parent, plugin_def, *, saved_state = None):
		QFrame.__init__(self, parent)
		AbstractQtPlugin.__init__(self, plugin_def, saved_state)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), self.ui), self)

		self.sig_ready.connect(self.slot_self_ready, type = Qt.QueuedConnection)

		if self.fixed_height:
			self.setFixedHeight(self.fixed_height)
		if self.fixed_width:
			self.setFixedWidth(self.fixed_width)

		self.generic_dialog = None

		self.b_name.autoFit()
		self.b_name.setText(self.moniker)
		self.b_name.toggled.connect(self.show_plugin_dialog)
		self.b_name.setContextMenuPolicy(Qt.NoContextMenu)

		# Setup volume indicator
		self.pb_volume = SmallSlider(self)
		self.pb_volume.setFixedWidth(self.progressbar_width)
		self.pb_volume.setFixedHeight(self.pb_indicator_height)
		self.pb_volume.valueChanged.connect(self.slot_pb_volume_changed)
		self.frm_volume.layout().replaceWidget(self.pb_volume_placeholder, self.pb_volume)
		self.pb_volume_placeholder.setVisible(False)
		self.pb_volume_placeholder.deleteLater()
		del self.pb_volume_placeholder

		# Setup drywet indicator
		self.pb_wet = SmallSlider(self)
		self.pb_wet.setFixedWidth(self.progressbar_width)
		self.pb_wet.setFixedHeight(self.pb_indicator_height)
		self.pb_wet.valueChanged.connect(self.slot_pb_drywet_changed)
		self.frm_wet.layout().replaceWidget(self.pb_wet_placeholder, self.pb_wet)
		self.pb_wet_placeholder.setVisible(False)
		self.pb_wet_placeholder.deleteLater()
		del self.pb_wet_placeholder

	def finalize_init(self):
		self.prefer_generic_dialog = not self.has_custom_ui
		self.pb_volume.setEnabled(self.can_volume)
		self.pb_wet.setEnabled(self.can_drywet)

	@pyqtSlot(int)
	def slot_pb_volume_changed(self, value):
		"""
		Triggered by the volume slider in the GUI.
		"""
		self.volume = float(value / 100)

	@pyqtSlot(int)
	def slot_pb_drywet_changed(self, value):
		"""
		Triggered by the dry/wet slider in the GUI.
		"""
		self.dry_wet = float(value / 100)

	def internal_value_changed(self, index, value):
		super().internal_value_changed(index, value)
		main_window().set_dirty()

	def set_active(self, value):
		super().set_active(value)
		main_window().set_dirty()

	def set_dry_wet(self, value):
		super().set_dry_wet(value)
		main_window().set_dirty()

	def set_volume(self, value):
		super().set_volume(value)
		main_window().set_dirty()

	def set_balance_left(self, value):
		super().set_balance_left(value)
		main_window().set_dirty()

	def set_balance_right(self, value):
		super().set_balance_right(value)
		main_window().set_dirty()

	def set_panning(self, value):
		super().set_panning(value)
		main_window().set_dirty()

	@pyqtSlot()
	def slot_self_ready(self):
		"""
		Called after post_embed_init() and all ports ready
		"""
		if main_window().project_loading:
			self.pb_volume.setValue(int(self.volume * 100))
			self.pb_wet.setValue(int(self.dry_wet * 100))
		else:
			self.pb_volume.setValue(100)
			self.pb_wet.setValue(100)

	@pyqtSlot()
	def slot_rename(self):
		new_name, ok = QInputDialog.getText(self,
			'Rename plugin', 'Enter a name for this plugin', text=self.moniker)
		if ok:
			self.moniker = new_name

	@pyqtSlot(bool)
	def slot_prefer_generic(self, checked):
		self.prefer_generic_dialog = checked

	@pyqtSlot()
	def slot_show_generic_dialog(self):
		if self.generic_dialog is None:
			self.generic_dialog = PluginDialog(self)
			self.generic_dialog.sig_closed.connect(self.generic_dialog_closed)
		self.generic_dialog.show()

	def _update_peak_meter(self):
		pass

	def _update_peak_stereo(self):
		self.peak_out.setValues(
			carla().get_output_peak_value(self.plugin_id, True),
			carla().get_output_peak_value(self.plugin_id, False)
		)

	def _update_peak_mono(self):
		self.peak_out.setValue(carla().get_output_peak_value(self.plugin_id, True))

	def update_indicators(self):
		"""
		This method does nothing inside "PluginWidget", but will be extended.
		If / when you decide to use peak meters, use this:
			if self.peak_out.isVisible():
				self._update_peak_meter()
		"""

	def inline_display_redraw(self):
		retval = carla().render_inline_display(self.plugin_id,
			self.fixed_width, self.fixed_height)

	@pyqtSlot(bool)
	def show_plugin_dialog(self, state):
		if state:
			if self.prefer_generic_dialog or not self.has_custom_ui:
				self.slot_show_generic_dialog()
			else:
				carla().show_custom_ui(self.plugin_id, state)
		else:
			if not self.generic_dialog is None:
				self.generic_dialog.hide()

	@pyqtSlot()
	def generic_dialog_closed(self):
		with SigBlock(self.b_name):
			self.b_name.setChecked(False)

	def ui_state_changed(self, state):
		if state == 0:
			self.b_name.setChecked(False)
		else:
			self.b_name.setChecked(True)
			if state == -1:
				logging.debug('SETTING has_custom_ui = False')
				self.has_custom_ui = False

	@pyqtSlot()
	def slot_show_info_dialog(self):
		PluginInfoDialog(self).show()

	@pyqtSlot()
	def b_volume_clicked(self):
		self.volume = 0

	@pyqtSlot()
	def b_wet_clicked(self):
		self.dry_wet = 0

	def __str__(self):
		return f'"{self.moniker}"'


# -----------------------------------------------------------------
# Per- track plugins

class TrackPluginWidget(PluginWidget):

	def __init__(self, parent, port, slot, ordinal, plugin_def, *, saved_state = None):
		super().__init__(parent, plugin_def, saved_state = saved_state)
		self.port = port
		self.slot = slot
		self.ordinal = ordinal
		self.icon_collapse = QIcon(join(APP_PATH, 'res', self.icon_collapse_svg))
		self.icon_expand = QIcon(join(APP_PATH, 'res', self.icon_expand_svg))
		self.b_rollup.toggled.connect(self.slot_rollup)
		self.b_rollup.setIcon(self.icon_collapse)

	def rollup(self):
		self.slot_rollup(True)
		with SigBlock(self.b_rollup):
			self.b_rollup.setChecked(True)

	def unroll(self):
		self.slot_rollup(False)
		with SigBlock(self.b_rollup):
			self.b_rollup.setChecked(False)


class HorizontalTrackPluginWidget(TrackPluginWidget):

	ui					= 'horizontal_track_plugin_widget.ui'
	fixed_width			= 112
	pb_indicator_height	= 18
	progressbar_width	= 80
	rolled_height		= 34
	icon_collapse_svg	= 'collapse-vertical.svg'
	icon_expand_svg		= 'expand-vertical.svg'

	@pyqtSlot(bool)
	def slot_rollup(self, state):
		self.bottom_frame.setVisible(not state)
		self.b_rollup.setIcon(self.icon_expand if state else self.icon_collapse)

	def is_rolled_up(self):
		return not self.bottom_frame.isVisible()

	def show_plugin_volume(self, state):
		self.bottom_frame.setVisible(state)


class VerticalTrackPluginWidget(TrackPluginWidget):

	ui					= 'vertical_track_plugin_widget.ui'
	fixed_width			= None
	fixed_height		= 26
	progressbar_width	= 50
	icon_collapse_svg	= 'collapse.svg'
	icon_expand_svg		= 'expand.svg'

	@pyqtSlot(bool)
	def slot_rollup(self, state):
		self.right_frame.setVisible(not state)
		self.b_rollup.setIcon(self.icon_expand if state else self.icon_collapse)

	def is_rolled_up(self):
		return not self.right_frame.isVisible()

	def show_plugin_volume(self, state):
		self.frm_volume.setVisible(state)
		self.frm_wet.setVisible(state)


# -----------------------------------------------------------------
# Shared plugins

class SharedPluginWidget(PluginWidget):

	ui = 'shared_plugin_widget.ui'
	fixed_height		= 152
	fixed_width			= 116
	balance_width		= 110
	balance_height		= 22
	progressbar_width	= 84
	min_led_audio_peak	= 0.001

	def __init__(self, parent, plugin_def, *, saved_state=None):
		super().__init__(parent, plugin_def, saved_state = saved_state)
		lo_indicators = QHBoxLayout()
		lo_indicators.setContentsMargins(0,0,0,0)
		lo_indicators.setSpacing(2)
		self.frm_activity.setLayout(lo_indicators)
		policy = QSizePolicy()
		policy.setHorizontalStretch(5)
		for name in ["led_ctrl", "led_audio", "led_midi"]:
			setattr(self, name, ActivityIndicator(self, name))
			getattr(self, name).setSizePolicy(policy)
			lo_indicators.addWidget(getattr(self, name))

		# Setup balance control widget:
		self.w_balance = SmallBalanceControl(self)
		self.w_balance.setFixedWidth(self.balance_width)
		self.w_balance.setFixedHeight(self.balance_height)
		self.layout().replaceWidget(self.w_balance_placeholder, self.w_balance)
		self.w_balance_placeholder.setVisible(False)
		self.w_balance_placeholder.deleteLater()
		del self.w_balance_placeholder

		# Do initial fill of b_output items:
		self.b_output = QtListButton(self, self.available_out_clients)
		self.b_output.autoFit()
		self.b_output.setText(TEXT_NO_CONN)
		self.b_output.sig_item_selected.connect(self.slot_output_client_selected)
		self.layout().replaceWidget(self.b_output_placeholder, self.b_output)
		self.b_output_placeholder.setVisible(False)
		self.b_output_placeholder.deleteLater()
		del self.b_output_placeholder

		self.destination_client_names = saved_state["destination_client_names"] \
			if saved_state and "destination_client_names" in saved_state else []

	def finalize_init(self):
		super().finalize_init()
		# Stero / mono input "LED" indicator (sets "_update_audio_led" func):
		if self._audio_in_count > 0:
			if self._audio_in_count > 1:
				self._update_audio_led = self._update_audio_led_stereo
			else:
				self._update_audio_led = self._update_audio_led_mono

	def available_out_clients(self):
		return [ (client.moniker, client) for client in chain(
					main_window().iterate_shared_plugin_widgets(),
					carla().system_audio_in_clients()
				) if client is not self ]

	def encode_saved_state(self):
		saved_state = super().encode_saved_state()
		saved_state["destination_client_names"] = [
			client.client_name for client in self.output_clients() ]
		return saved_state

	def project_load_complete(self):
		"""
		Called after loading saved project or importing track setup.
		Updates the connection menu.
		"""
		for client_name in self.destination_client_names:
			try:
				client = carla().named_client(client_name)
				self.connect_outputs_to(client)
			except IndexError:
				logging.debug('Named client "%s" not found', client_name)
		self.update_output_connection_ui()
		self.w_balance.update()

	def _update_audio_led(self):
		"""
		Dummy function, replaced with either _update_audio_led_stereo or
		_update_audio_led_mono, depending on the number of audio outputs.
		"""

	def _update_audio_led_stereo(self):
		self.led_audio.light(	self.peak_left > self.min_led_audio_peak or \
								self.peak_right > self.min_led_audio_peak )

	def _update_audio_led_mono(self):
		self.led_audio.light(self.peak_mono > self.min_led_audio_peak)

	def update_indicators(self):
		"""
		Called only when the indicator timer is started.
		If / when you decide to use peak meters, use this:
			if self.peak_out.isVisible():
				self._update_peak_meter()
		"""
		if not self.removing_from_carla:
			self._update_audio_led()

	@pyqtSlot(str, QVariant)
	def slot_output_client_selected(self, _, client):
		self.disconnect_outputs()
		if client is not None:
			self.connect_audio_outputs_to(client)

	def output_connection_change(self, connection, state):
		if not self.removing_from_carla:
			super().output_connection_change(connection, state)
			is_project_port = connection.in_port.client_name() in self.destination_client_names
			if state != is_project_port:
				main_window().set_dirty()
			self.update_output_connection_ui()

	def update_output_connection_ui(self):
		clients = self.output_clients()
		if len(clients) == 0:
			self.b_output.setText(TEXT_NO_CONN)
		elif len(clients) == 1:
			self.b_output.setText(clients[0].moniker)
		else:
			self.b_output.setText(TEXT_MULTI_CONN % len(clients))

	@pyqtSlot()
	def go_full_stereo(self):
		"""
		Spread the balance across full left/right acoustic space.
		"""
		self.balance_left = -1.0
		self.balance_right = 1.0
		self.w_balance.update()

	@pyqtSlot()
	def center_panning(self):
		self.panning = 0.0
		self.w_balance.update()

	def midi_active(self, state):
		self.led_midi.light(state)

	def show_indicators(self, state):
		self.frm_activity.setVisible(state)


# -----------------------------------------------------------------
# Indicators (Audio, MIDI, CV) for plugin widgets:

class ActivityIndicator(QWidget):

	led_ctrl_off = None
	led_ctrl_on = None
	led_audio_off = None
	led_audio_on = None
	led_midi_off = None
	led_midi_on = None

	def __init__(self, parent, name):
		super().__init__(parent)
		if __class__.led_ctrl_off is None:
			__class__.led_ctrl_off = QPixmap(join(APP_PATH, 'res', 'control-icon-off.png'))
			__class__.led_ctrl_on = QPixmap(join(APP_PATH, 'res', 'control-icon-on.png'))
			__class__.led_audio_off = QPixmap(join(APP_PATH, 'res', 'audio-icon-off.png'))
			__class__.led_audio_on = QPixmap(join(APP_PATH, 'res', 'audio-icon-on.png'))
			__class__.led_midi_off = QPixmap(join(APP_PATH, 'res', 'midi-icon-off.png'))
			__class__.led_midi_on = QPixmap(join(APP_PATH, 'res', 'midi-icon-on.png'))
		self.name = name
		self.setFixedHeight(20)
		self.setFixedWidth(20)
		self.off_pixmap = getattr(__class__, self.name + '_off')
		self.on_pixmap = getattr(__class__, self.name + '_on')
		self._lit = False

	def light(self, state):
		if state != self._lit:
			self._lit = state
			self.update()

	def paintEvent(self, _):
		painter = QPainter(self)
		painter.drawPixmap(QPoint(0,0), self.on_pixmap if self._lit else self.off_pixmap)
		painter.end()


class SmallBalanceControl(QWidget):

	PAN_WIDTH = 2
	zero_line_pen = None

	def __init__(self, plugin_widget):
		super().__init__(plugin_widget)
		if __class__.zero_line_pen is None:
			__class__.zero_line_pen = QPen()
			__class__.zero_line_pen.setWidth(1)
		self.plugin_widget = plugin_widget
		self.grabbed_feature = None
		self.setAttribute(Qt.WA_StyledBackground, True)

		self.inner_bar = QWidget(self)
		self.inner_bar.setObjectName('inner_bar')
		self.lbl_left = QLabel('L', self)
		self.lbl_left.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
		self.lbl_right = QLabel('R', self)
		self.lbl_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

		if self.plugin_widget.can_balance:
			action = QAction('Spread balance full stereo', self)
			action.triggered.connect(self.plugin_widget.go_full_stereo)
			self.addAction(action)
		elif self.plugin_widget.can_pan:
			action = QAction('Center stereo panning', self)
			action.triggered.connect(self.plugin_widget.center_panning)
			self.addAction(action)
		self.setContextMenuPolicy(Qt.ActionsContextMenu)
		for widget in [self, self.inner_bar, self.lbl_left, self.lbl_right]:
			widget.setMouseTracking(True)
		self.set_styles()

	def changeEvent(self, event):
		if event.type() == QEvent.StyleChange:
			self.set_styles()
		super().changeEvent(event)

	def set_styles(self):
		self.metrics = QFontMetrics(self.font())
		self.zero_line_pen.setColor(self.palette().color(QPalette.WindowText))

	def resizeEvent(self, event):
		self.bounds_rect = QRect(QPoint(0, 0), event.size()).adjusted(0, 0, -1, -1)
		self.inner_bounds_rect = self.bounds_rect.adjusted(2, 1, 1, 0)
		self.center_x = self.inner_bounds_rect.center().x()
		self.f_scale = self.inner_bounds_rect.width() / 2
		self.centerline_top = QPoint(self.center_x, self.inner_bounds_rect.top())
		self.centerline_bottom = QPoint(self.center_x, self.inner_bounds_rect.bottom())
		self.lbl_left.resize(self.inner_bounds_rect.size())
		self.lbl_right.resize(self.inner_bounds_rect.size())
		self.resize_inner_bar()

	def screen_x_to_float(self, x):
		return max(-1.0, min(1.0, float(x - self.center_x) / self.f_scale))

	def float_to_screen_x(self, float_x):
		return round(float_x * self.f_scale + self.center_x)

	def mousePressEvent(self, event):
		float_x = self.screen_x_to_float(event.x())
		self.grabbed_feature = self.nearest_element
		if self.grabbed_feature.feature in (GRAB_CENTER, GRAB_PANNING):
			self.setCursor(Qt.ClosedHandCursor)
		if self.plugin_widget.can_balance:
			self.initial_balance_left = self.plugin_widget.balance_left
			self.initial_balance_right = self.plugin_widget.balance_right
		else:
			self.initial_panning = self.plugin_widget.balance_right
		self.initial_x = float_x

	def mouseReleaseEvent(self, _):
		self.grabbed_feature = None
		self.unsetCursor()

	def leaveEvent(self, _):
		self.grabbed_feature = None
		self.unsetCursor()

	def mouseMoveEvent(self, event):
		float_x = self.screen_x_to_float(event.x())
		if self.grabbed_feature:
			shift_x = float_x - self.initial_x
			if self.grabbed_feature.feature == GRAB_CENTER:
				self.plugin_widget.balance_left = min(1.0, max(-1.0, self.initial_balance_left + shift_x))
				self.plugin_widget.balance_right = min(1.0, max(-1.0, self.initial_balance_right + shift_x))
			else:
				if self.grabbed_feature.feature == GRAB_LEFT_BALANCE:
					self.plugin_widget.balance_left = min(self.plugin_widget.balance_right, max(-1.0, self.initial_x + shift_x))
				elif self.grabbed_feature.feature == GRAB_RIGHT_BALANCE:
					self.plugin_widget.balance_right = min(1.0, max(self.plugin_widget.balance_left, self.initial_x + shift_x))
				elif self.grabbed_feature.feature == GRAB_PANNING:
					self.plugin_widget.panning = float_x
			self.resize_inner_bar()
		else:
			if self.plugin_widget.can_balance:
				features = [
					GrabEvent(GRAB_LEFT_BALANCE, self.plugin_widget.balance_left, float_x),
					GrabEvent(GRAB_RIGHT_BALANCE, self.plugin_widget.balance_right, float_x),
					GrabEvent(GRAB_CENTER, self.plugin_widget.balance_center, float_x)
				]
				features.sort(key=attrgetter('distance'))
				self.nearest_element = features[0]
			else:
				self.nearest_element = GrabEvent(GRAB_PANNING, self.plugin_widget.balance_center, float_x)
			# Set cursor
			if self.nearest_element.feature in (GRAB_LEFT_BALANCE, GRAB_RIGHT_BALANCE):
				self.setCursor(Qt.SplitHCursor)
			else:
				self.setCursor(Qt.PointingHandCursor)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setPen(self.zero_line_pen)
		painter.drawLine(self.centerline_top, self.centerline_bottom)
		self.resize_inner_bar()
		super().paintEvent(event)
		painter.end()

	def resize_inner_bar(self):
		if self.plugin_widget.can_balance:
			left_x = self.float_to_screen_x(self.plugin_widget.balance_left)
			right_x = self.float_to_screen_x(self.plugin_widget.balance_right)
			self.inner_bar.setGeometry(
				left_x, self.inner_bounds_rect.top(),
				right_x - left_x, self.inner_bounds_rect.height()
			)
		elif self.plugin_widget.can_pan:
			x = self.float_to_screen_x(self.plugin_widget.panning)
			self.inner_bar.setGeometry(
				x - self.PAN_WIDTH, self.inner_bounds_rect.top(),
				x + self.PAN_WIDTH, self.inner_bounds_rect.bottom()
			)
		else:
			self.inner_bar.setVisible(False)


class GrabEvent:
	"""
	Used to sort / determine the nearest feature to the mouse pointer, and when
	grabbed, keep track of mouse movement and apply the changes to the appropriate
	target.
	"""

	def __init__ (self, feature, feature_value, float_x):
		self.feature = feature
		self.distance = abs(float_x - feature_value)


# -----------------------------------------------------------------
# Volume & dry/wet controls

class SmallSlider(QProgressBar):
	"""
	A control which is used for volume and dry/wet adjustment, inheriting from
	QProgressBar in order to make styleing with CSS easier.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		self.setMinimum(0)
		self.setMaximum(100)
		self.mouse_down = False

	def wheelEvent(self, event):
		ctrl = bool(event.modifiers() & Qt.ControlModifier)
		value = self.value() + (event.angleDelta().y() // 12 if ctrl else event.angleDelta().y() // 120)
		self.setValue(max(0, min(100, value)))
		event.accept()

	def mousePressEvent(self, event):
		self._set_value(event)
		self.mouse_down = True

	def mouseReleaseEvent(self, _):
		self.mouse_down = False

	def mouseMoveEvent(self, event):
		if self.mouse_down:
			self._set_value(event)

	def _set_value(self, event):
		self.setValue(max(0, min(100, int(100 * event.x() / self.width()))))

# -----------------------------------------------------------------
# Audio peak meters for plugin widgets:

class PeakMeter(QWidget):
	"""
	Abstract peak meter class. (See MonoPeakMeter and StereoPeakMeter)
	"""

	fixed_height	= 125
	fixed_width		= 30
	anim_duration	= 950

	fill_brush = None

	def __init__(self, parent):
		super().__init__(parent)
		if __class__.fill_brush is None:
			__class__.fill_brush = QBrush(QColor("black"), Qt.SolidPattern)
		self.setFixedHeight(self.fixed_height)
		self.setFixedWidth(self.fixed_width)
		self.meter_bg = QPixmap(30, 125)
		self.meter_bg.load(join(APP_PATH, 'res', 'meter.png'))


class MonoPeakMeter(PeakMeter):
	"""
	Animated peak meter for monophonic plugins / tracks.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		self.__value = 0.0
		self.__display_value = 0.0
		self.anim = QPropertyAnimation(self, b"_display_value")
		self.anim.setEndValue(0.0)
		self.anim.setDuration(self.anim_duration)

	def setValue(self, value):
		if value == self.__value:
			return
		self.__value = value
		if value > self.__display_value:
			self.anim.stop()
			self.__display_value = value
		else:
			self.anim.setEndValue(value)
			self.anim.start()
		self.update()

	@pyqtProperty(float)
	def _display_value(self):
		return self.__display_value

	@_display_value.setter
	def _display_value(self, value):
		self.__display_value = value

	def resizeEvent(self, event):
		self.bar_width = event.size().width()

	def paintEvent(self, _):
		painter = QPainter(self)
		painter.drawPixmap(0, 0, self.meter_bg)
		painter.fillRect(0, 0, self.bar_width, (1.0 - self.__display_value) * self.fixed_height, self.fill_brush)
		painter.end()


class StereoPeakMeter(PeakMeter):
	"""
	Animated peak meter for stereophonic plugins / tracks.
	"""

	def __init__(self, parent):
		super().__init__(parent)
		self.__value_left = 0.0
		self.__display_value_left = 0.0
		self.__value_right = 0.0
		self.__display_value_right = 0.0
		self.anim_left = QPropertyAnimation(self, b"_display_value_left")
		self.anim_left.setEndValue(0.0)
		self.anim_left.setDuration(self.anim_duration)
		self.anim_right = QPropertyAnimation(self, b"_display_value_right")
		self.anim_right.setEndValue(0.0)
		self.anim_right.setDuration(self.anim_duration)

	def setValues(self, left_value, right_value):
		if left_value != self.__value_left:
			self.__value_left = left_value
			if left_value > self.__display_value_left:
				self.anim_left.stop()
				self.__display_value_left = left_value
			else:
				self.anim_left.setEndValue(left_value)
				self.anim_left.start()
			self.update()
		if right_value != self.__value_right:
			self.__value_right = right_value
			if right_value > self.__display_value_right:
				self.anim_right.stop()
				self.__display_value_right = right_value
			else:
				self.anim_right.setEndValue(right_value)
				self.anim_right.start()
			self.update()

	@pyqtProperty(float)
	def _display_value_left(self):
		return self.__display_value_left

	@_display_value_left.setter
	def _display_value_left(self, value):
		self.__display_value_left = value

	@pyqtProperty(float)
	def _display_value_right(self):
		return self.__display_value_right

	@_display_value_right.setter
	def _display_value_right(self, value):
		self.__display_value_right = value

	def resizeEvent(self, event):
		self.bar_width = floor((event.size().width() - 2) / 2)
		self.bar_right_x = self.bar_width + 2

	def paintEvent(self, _):
		painter = QPainter(self)
		painter.drawPixmap(0, 0, self.meter_bg, 0, 0, self.bar_width, 125)
		painter.drawPixmap(self.bar_right_x, 0, self.meter_bg, 0, 0, self.bar_width, 125)
		painter.fillRect(
			0, 0,
			self.bar_width,
			int((1.0 - self.__display_value_left) * self.fixed_height),
			self.fill_brush)
		painter.fillRect(
			self.bar_right_x, 0,
			self.bar_width,
			int((1.0 - self.__display_value_right) * self.fixed_height),
			self.fill_brush)
		painter.end()


# -----------------------------------------------------------------
# Plugin info dialog

class PluginInfoDialog(QDialog):

	fields = [
		('moniker', 'moniker'),
		('plugin Name', 'original_plugin_name'),
		('audio inputs', 'audio_in_count'),
		('audio outputs', 'audio_out_count'),
		('midi inputs', 'midi_in_count'),
		('midi outputs', 'midi_out_count'),
		('parameters in', 'input_parameter_count'),
		('parameters out', 'output_parameter_count'),
		('maker', 'maker'),
		('category', 'category'),
		('label', 'label'),
		('filename', 'filename')
	]

	def __init__(self, plugin):
		super().__init__(plugin)
		lo = QGridLayout(self)
		lo.setSpacing(6)
		row = 0
		for f in self.fields:
			lo.addWidget(QLabel(f[0], self), row, 0)
			lo.addWidget(QLabel(str(getattr(plugin, f[1])), self), row, 1)
			row += 1
		frm = QFrame(self)
		frm.setLayout(lo)
		lo = QVBoxLayout()
		lo.setContentsMargins(8, 4, 8, 14)
		lo.addWidget(frm)
		self.setLayout(lo)



#  end musecbox/gui/plugin_widgets.py
