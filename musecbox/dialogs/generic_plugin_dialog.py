#  musecbox/dialogs/generic_plugin_dialog.py
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
Provides a generic dialogue with which plugin parameters can be changed.
"""
import logging, re
from math import floor, ceil
from qt_extras import SigBlock
from qt_extras.list_button import QtListButton

# PyQt5 imports
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer, QVariant
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QDialog, QWidget, QSizePolicy, QHBoxLayout, QVBoxLayout, QFormLayout, \
							QFrame, QLabel, QCheckBox, QSlider, QShortcut

from musecbox import main_window, set_application_style, LAYOUT_COMPLETE_DELAY


class PluginDialog(QDialog):

	sig_closed = pyqtSignal()

	def __init__(self, parent):
		"""
		"parent" is an instance of PluginWidget, satisfying Qt's requirement for a
		parent QtWidget. It is also a Plugin, with parameters, ports, etc.
		"""
		super().__init__(parent)
		self.setWindowTitle(parent.moniker)
		self.finished.connect(self.finished_event)
		sc = QShortcut(QKeySequence('F5'), self)
		sc.activated.connect(set_application_style)
		self.setSizeGripEnabled(False)
		self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

		lo = QVBoxLayout()

		self.input_group = ParameterGroup(self, "Inputs", parent.input_parameters())
		self.output_group = ParameterGroup(self, "Outputs", parent.output_parameters())
		if self.input_group.count() > 0:
			lbl = QLabel('Inputs:')
			lbl.setObjectName('param_category')
			lo.addWidget(lbl)
			lo.addWidget(self.input_group)
		if self.output_group.count() > 0:
			lbl = QLabel('Outputs:')
			lbl.setObjectName('param_category')
			lo.addWidget(lbl)
			lo.addWidget(self.output_group)
		self.setLayout(lo)
		self.parameter_widgets = { widget.param.parameter_id : widget \
			for widget in self.iter_parameter_widgets() }
		QTimer.singleShot(LAYOUT_COMPLETE_DELAY, self.layout_complete)

	@pyqtSlot()
	def layout_complete(self):
		for widget in self.parameter_widgets.values():
			widget.internal_value_changed(widget.param.value)

	def iter_parameter_widgets(self):
		yield from self.input_group.iter_parameter_widgets()
		yield from self.output_group.iter_parameter_widgets()

	@pyqtSlot(int)
	def finished_event(self, _):
		self.close()

	def closeEvent(self, _):
		self.sig_closed.emit()

	def parameter_internal_value_changed(self, parameter, value):
		self.parameter_widgets[parameter.parameter_id].internal_value_changed(value)


class ParameterGroup(QFrame):

	max_widget_rows = 12

	def __init__(self, parent, name, parameters):
		super().__init__(parent)
		self.name = name
		self.parameter_widgets = []
		self.groups = {}
		for param in parameters:
			if param.groupName:
				logging.debug('Parameter has group name: %s', param.groupName)
				_, group_name = param.groupName.split(":", 1)
				if group_name in self.groups:
					self.groups[group_name].append_parameter(param)
				else:
					self.groups = ParameterGroup(self, group_name, [param])
			else:
				self.append_parameter(param)

		bool_widgets = [ widget for widget in self.parameter_widgets \
			if isinstance(widget, ParamWidgetBool) ]
		var_widgets = [ widget for widget in self.parameter_widgets \
			if not isinstance(widget, ParamWidgetBool) ]

		self.lo = QHBoxLayout()
		self.lo.setSpacing(18)
		self.lo.setContentsMargins(10,2,10,14)

		if len(self.groups) > 0:
			for group in self.groups:
				group_lo = QHBoxLayout()
				group_lo.addWidget(QLabel(group.name))
				group_lo.addWidget(group)
				self.lo.addItem(group_lo)
		if len(bool_widgets) > 0:
			self.layout_widget_group(bool_widgets)
		if len(var_widgets) > 0:
			self.layout_widget_group(var_widgets)
		self.setLayout(self.lo)

	def layout_widget_group(self, widgets):
		columns = ceil(len(widgets) / self.max_widget_rows)
		rows = ceil(len(widgets) / columns)
		for col in range(columns):
			form_layout = QFormLayout()
			form_layout.setHorizontalSpacing(10)
			form_layout.setVerticalSpacing(5)
			start_index = col * rows
			end_index = (col + 1) * rows
			col_widgets = widgets[start_index:end_index]
			for widget in col_widgets:
				form_layout.addRow(widget.param.name, widget)
			self.lo.addItem(form_layout)

	def append_parameter(self, param):
		if param.uses_scalepoints:
			widget = ParamWidgetSelect(self, param)
		else:
			smallest_step = min(param.step, param.stepSmall)
			divisions = floor(param.range / smallest_step)
			if divisions == 1:
				widget = ParamWidgetBool(self, param)
			elif divisions <= 8:
				widget = ParamWidgetSelect(self, param)
			else:
				widget = ParamWidgetSlider(self, param)
		self.parameter_widgets.append(widget)

	def iter_parameter_widgets(self):
		yield from self.parameter_widgets
		for group in self.groups:
			yield from group.iter_parameter_widgets()

	def count(self):
		return len(list(self.iter_parameter_widgets()))


class ParamWidgetBool(QCheckBox):

	def __init__(self, parent, param):
		super().__init__(parent)
		self.param = param
		self.checked = False
		self.stateChanged.connect(self.state_changed)

	def internal_value_changed(self, value):
		with SigBlock(self):
			self.checked = value != 0.0

	@pyqtSlot(int)
	def state_changed(self, state):
		self.param.value = state == Qt.Checked
		main_window().set_dirty()


class ParamWidgetSelect(QtListButton):

	def __init__(self, parent, param):
		super().__init__(parent)
		self.param = param
		if param.uses_scalepoints:
			for lbl, float_val in param.scale_points:
				self.addItem(lbl, float_val)
		else:
			step = min(param.step, param.stepSmall)
			m = re.match(r'.*\.0*[^0]', f'{step:f}')
			if m:
				fmt = f'%.{m.span()[1]-2}f'
			else:
				fmt = '%.0f'
			float_val = param.min
			while float_val <= param.max:
				self.addItem(fmt % float_val, float_val)
				float_val += step
		self.sig_item_selected.connect(self.item_selected)

	def internal_value_changed(self, value):
		with SigBlock(self):
			try:
				self.select_data(value)
			except IndexError:
				pass

	@pyqtSlot(str, QVariant)
	def item_selected(self, _, data):
		self.param.value = data
		main_window().set_dirty()


class ParamWidgetSlider(QWidget):

	gradation = 1000

	def __init__(self, parent, param):
		super().__init__(parent)
		self.param = param
		self._scaling = self.gradation / param.range
		if param.range >= 100:
			self.fmt = '%.0f'
		elif param.range >= 10:
			self.fmt = '%.1f'
		else:
			self.fmt = '%.2f'
		self.slider = QSlider(self)
		self.slider.setOrientation(Qt.Horizontal)
		self.slider.setMinimum(0)
		self.slider.setMaximum(self.gradation)
		self.lbl_value = QLabel(self)
		self.lbl_value.setText(self.fmt % param.min)
		self.setFixedWidth(164)
		self.slider.setFixedWidth(116)
		self.lbl_value.setFixedWidth(46)
		self.setLayout(QHBoxLayout(self))
		self.layout().setContentsMargins(0,0,0,0)
		self.layout().setSpacing(4)
		self.layout().addWidget(self.slider)
		self.layout().addWidget(self.lbl_value)
		self.slider.valueChanged.connect(self.slider_value_changed)

	def internal_value_changed(self, value):
		with SigBlock(self):
			self.slider.setValue(round((value - self.param.min) * self._scaling))

	@pyqtSlot(int)
	def slider_value_changed(self, value):
		value = value / self._scaling + self.param.min
		self.lbl_value.setText(self.fmt % value)
		self.param.value = value
		main_window().set_dirty()


#  end musecbox/dialogs/generic_plugin_dialog.py
