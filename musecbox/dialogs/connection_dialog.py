#  musecbox/dialogs/connection_dialog.py
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
Provides a dialog which shows Jack connections relevant to the current project.
"""
import logging
from os.path import join, dirname
from itertools import chain
from qt_extras import SigBlock, ShutUpQT

from PyQt5 import 			uic
from PyQt5.QtCore import	Qt, pyqtSlot, QPointF
from PyQt5.QtGui import		QBrush, QPen, QIcon, QPainter, QColor, QLinearGradient, QPainterPath
from PyQt5.QtWidgets import	QGraphicsScene, QGraphicsView, \
							QGraphicsItem, QGraphicsItemGroup, \
							QGraphicsPathItem, QGraphicsSimpleTextItem, \
							QDialog, QListWidgetItem

from simple_carla import SystemPatchbayClient
from musecbox.gui.track_widget import LiquidSFZ

MARGIN = 80
CELL_SPACING_X = 40
CELL_PADDING_X = 8
CELL_PADDING_Y = 2
FONT_HEIGHT = 13
ROW_HEIGHT = 30
NOT_SELECTED = 0
SELECTED = 1
SELECTED_FIRST = 2


class ConnectionsDialog(QDialog):

	def __init__(self, parent):
		super().__init__(parent)
		with ShutUpQT():
			uic.loadUi(join(dirname(__file__), 'connection_dialog.ui'), self)
		self.restore_geometry()
		self.finished.connect(self.save_geometry)

		Cell.setup_class_vars()

		self.port_graphics = [ PortCell(
			port_widget.channel_splitter,
			f'Port {port_widget.port}'
		) for port_widget in self.parent().port_layout ]

		columns_needed = max(cell.columns_needed() for cell in self.port_graphics)
		rows_needed = sum(cell.rows_needed() for cell in self.port_graphics)

		row = 0
		for cell in self.port_graphics:
			cell.set_row(row)
			cell.set_column(0)
			row += cell.rows_needed()

		widths = [ 0 for column in range(columns_needed) ]
		for cell in self.iterate_cells():
			widths[cell.column] = max(widths[cell.column], cell.width)
		lefts = [ 0 for i in range(len(widths)) ]
		for i in range(1, len(widths)):
			lefts[i] = sum(widths[:i]) + CELL_SPACING_X * i

		self.scene = QGraphicsScene(0, 0,
			sum(widths) + (columns_needed - 1) * CELL_SPACING_X,
			rows_needed * ROW_HEIGHT,
			self
		)

		added_cells = []
		for cell in self.iterate_cells():
			if not cell in added_cells:
				cell.setPos(lefts[cell.column], cell.row * ROW_HEIGHT)
				self.scene.addItem(cell)
				added_cells.append(cell)
				for connector in cell.out_connectors:
					self.scene.addItem(connector)

		for cell in self.iterate_cells():
			for connector in cell.out_connectors:
				connector.reposition()

		self.view = ZoomingView(self.scene, self)
		self.view.setRenderHint(QPainter.Antialiasing)
		self.view.setMinimumWidth(int(self.scene.sceneRect().width() + MARGIN))
		self.view.setMinimumHeight(int(self.scene.sceneRect().height() + MARGIN))
		self.view.ensureVisible(self.scene.sceneRect())
		self.lo_right.replaceWidget(self.view_placeholder, self.view)
		self.view_placeholder.setVisible(False)
		self.view_placeholder.deleteLater()
		del self.view_placeholder

		self.lo_right.setStretch(0, 100)
		self.lo_right.setStretch(1, 1)

		self.first_selected_cell = None
		self.selected_cells = set()

		self.lst_connections.itemSelectionChanged.connect(self.slot_list_selection_changed)

	def iterate_cells(self):
		for cell in self.port_graphics:
			yield from cell.iterate_cells()

	def cell_press_event(self, cell, _):
		if cell.selected_state == SELECTED_FIRST:
			self.clear_selections()
		elif cell.selected_state == SELECTED:
			self.selected_cells.remove(cell)
			cell.set_selected(NOT_SELECTED)
			self.update_selections()
		elif self.first_selected_cell is None:
			cell.set_selected(SELECTED_FIRST)
			self.first_selected_cell = cell
			self.lbl_client.setText(self.first_selected_cell.label.text())
			self.lbl_client.setStyleSheet("""
				background: qlineargradient(
				x1:0, y1:0, x2:0, y2:1,
				stop: 0 #FDF0AF, stop: 1 #FFFDE6);
			""")
			self.lst_connections.clear()
			for client in self.first_selected_cell.client.input_clients():
				cell = Cell.cell_containing_client(client)
				if cell:
					item = QListWidgetItem(self.lst_connections)
					item.setText(cell.label.text())
					item.setIcon(QIcon.fromTheme('go-previous'))
					item.setData(Qt.UserRole, cell)
			for client in self.first_selected_cell.client.output_clients():
				cell = Cell.cell_containing_client(client)
				item = QListWidgetItem(self.lst_connections)
				item.setText(cell.label.text())
				item.setIcon(QIcon.fromTheme('go-next'))
				item.setData(Qt.UserRole, cell)
		else:
			cell.set_selected(SELECTED)
			self.selected_cells.add(cell)
			self.update_selections()

	def clear_selections(self):
		self.first_selected_cell.set_selected(NOT_SELECTED)
		for cell in self.selected_cells:
			cell.set_selected(NOT_SELECTED)
		self.first_selected_cell = None
		self.selected_cells = set()
		self.lbl_client.setText('[None selected]')
		self.lbl_client.setStyleSheet('')
		with SigBlock(self.lst_connections):
			self.lst_connections.clear()
		self.b_disconnect_connector.setEnabled(False)
		self.b_connect.setEnabled(False)

	def update_selections(self):
		"""
		Called from cell_press_event when a cell moves to / from SELECTED,
		and when the connection selection list changes.
		Note: first_selected_cell is always set when this is called.
		"""
		connected = set( cell for cell in self.selected_cells \
			if cell.client.is_connected_to(self.first_selected_cell.client) )
		self.b_disconnect_connector.setEnabled(bool(connected))
		self.b_connect.setEnabled(bool(self.selected_cells - connected))
		for conn in self.first_selected_cell.out_connectors:
			if conn.target_cell in connected:
				conn.set_selected(SELECTED)
		for conn in self.first_selected_cell.in_connectors:
			if conn.source_cell in connected:
				conn.set_selected(SELECTED)

	@pyqtSlot()
	def slot_list_selection_changed(self):
		self.b_disconnect_listitem.setEnabled(len(self.lst_connections.selectedItems()))
		for row in range(self.lst_connections.count()):
			item = self.lst_connections.item(row)
			cell = item.data(Qt.UserRole)
			if item.isSelected():
				cell.set_selected(SELECTED)
				self.selected_cells.add(cell)
			elif cell.selected_state == SELECTED:
				cell.set_selected(NOT_SELECTED)
				self.selected_cells.remove(cell)
		self.update_selections()

	def connector_press_event(self, connector, event):
		pass

	def mousePressEvent(self, event):
		super().mousePressEvent(event)
		if self.first_selected_cell:
			self.clear_selections()


class ZoomingView(QGraphicsView):

	def __init__(self, scene, parent):
		super().__init__(scene, parent)
		self.zoom_in_step = 1.05
		self.zoom_out_step = 1.0 / self.zoom_in_step
		self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
		self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

	def wheelEvent(self, event):
		ctrl = event.modifiers() & Qt.ControlModifier
		shift = event.modifiers() & Qt.ShiftModifier
		if ctrl and not shift:
			if event.angleDelta().y() > 0:
				self.scale(self.zoom_in_step, self.zoom_in_step)
			else:
				self.scale(self.zoom_out_step, self.zoom_out_step)


class Cell(QGraphicsItemGroup):

	# Instance vars:
	client = None
	column = None
	row = None

	# Class vars:
	instances = []
	corner_radius = 4
	pen_width = 0.0
	pen_color = QColor(80, 80, 80)
	gradient_colors = (
		QColor(255, 255, 255),
		QColor(210, 210, 210)
	)
	pen_color_selected = QColor(80, 80, 120)
	gradient_colors_selected = (
		QColor(240, 240, 255),
		QColor(210, 210, 245)
	)
	pen_color_first_selected = QColor(120, 110, 80)
	gradient_colors_first_selected = (
		QColor(255, 253, 230),
		QColor(253, 240, 175)
	)

	def __new__(cls, client, moniker):
		"""
		Keeps a list of all Cell instances and ensures that only one
		Cell is instantiated per client.
		"""
		cell = cls.cell_containing_client(client)
		if cell is None:
			cell = super().__new__(cls, client, moniker)
			cls.instances.append(cell)
		return cell

	@classmethod
	def setup_class_vars(cls):
		__class__.font = QGraphicsSimpleTextItem(__class__.__name__).font()
		__class__.font.setPixelSize(FONT_HEIGHT)
		outline_height = FONT_HEIGHT + CELL_PADDING_Y * 2

		gradient = QLinearGradient(0, 0, 0, outline_height)
		gradient.setColorAt(0, __class__.gradient_colors[0])
		gradient.setColorAt(1, __class__.gradient_colors[1])
		__class__.brush = QBrush(gradient)
		__class__.pen = QPen(__class__.pen_color)
		__class__.pen.setWidthF(__class__.pen_width)

		gradient = QLinearGradient(0, 0, 0, outline_height)
		gradient.setColorAt(0, __class__.gradient_colors_selected[0])
		gradient.setColorAt(1, __class__.gradient_colors_selected[1])
		__class__.brush_selected = QBrush(gradient)
		__class__.pen_selected = QPen(__class__.pen_color_selected)
		__class__.pen_selected.setWidthF(__class__.pen_width)

		gradient = QLinearGradient(0, 0, 0, outline_height)
		gradient.setColorAt(0, __class__.gradient_colors_first_selected[0])
		gradient.setColorAt(1, __class__.gradient_colors_first_selected[1])
		__class__.brush_first_selected = QBrush(gradient)
		__class__.pen_first_selected = QPen(__class__.pen_color_first_selected)
		__class__.pen_first_selected.setWidthF(__class__.pen_width)


	@classmethod
	def cell_containing_client(cls, client):
		for cell in cls.instances:
			if cell.client is client:
				return cell
		return None

	def __init__(self, client, moniker):
		if self.client is None:
			super().__init__()
			self.client = client
			self.setZValue(1)
			self.label = QGraphicsSimpleTextItem(moniker)
			self.label.setFont(__class__.font)
			self.width = self.label.boundingRect().width() + CELL_PADDING_X * 2
			self.height = self.label.boundingRect().height() + CELL_PADDING_Y * 2
			self.selected_state = NOT_SELECTED
			path = QPainterPath()
			path.addRoundedRect(
				0, 0, self.width, self.height,
				__class__.corner_radius, __class__.corner_radius)
			self.outline = QGraphicsPathItem(path)
			self.outline.setPen(__class__.pen)
			self.outline.setBrush(__class__.brush)
			self.addToGroup(self.outline)
			self.addToGroup(self.label)
			self.label.setPos(CELL_PADDING_X, CELL_PADDING_Y)
			self.setFlag(QGraphicsItem.ItemIsMovable)
			self.out_connectors = []
			self.in_connectors = []
			self.create_downstream_cells()
			for target_cell in self.downstream_cells:
				Connector(self, target_cell)

	def create_downstream_cells(self):
		self.downstream_cells = [] \
			if isinstance(self.client, SystemPatchbayClient) \
			else [ Cell(client, client.moniker) \
			for client in self.client.output_clients() ]

	def iterate_cells(self):
		yield self
		for cell in self.downstream_cells:
			yield from cell.iterate_cells()

	def rows_needed(self):
		"""
		This cell will need one row for each immediate downstream client.
		"""
		return max(1, sum(cell.rows_needed() for cell in self.downstream_cells)) \
			if self.downstream_cells else 1

	def columns_needed(self):
		"""
		This cell will need the maximum number of columns of all possible client paths.
		"""
		return max(cell.columns_needed() for cell in self.downstream_cells) + 1 \
			if self.downstream_cells else 1

	def set_row(self, row):
		if self.row is None:
			self.row = row
		else:
			row = self.row
		for cell in self.downstream_cells:
			cell.set_row(row)
			row += 1

	def set_column(self, column):
		if self.column is None:
			self.column = column
		else:
			self.column = max(self.column, column)
		column += 1
		for cell in self.downstream_cells:
			cell.set_column(column)

	def input_connection_point(self):
		return self.mapToScene(QPointF(0, self.boundingRect().center().y()))

	def output_connection_point(self):
		return self.mapToScene(QPointF(self.boundingRect().right(), self.boundingRect().center().y()))

	def mousePressEvent(self, event):
		super().mousePressEvent(event)
		self.scene().parent().cell_press_event(self, event)

	def mouseMoveEvent(self, event):
		super().mouseMoveEvent(event)
		for connector in chain(self.out_connectors, self.in_connectors):
			connector.reposition()

	def set_selected(self, state):
		self.selected_state = state
		if self.selected_state == SELECTED_FIRST:
			self.outline.setBrush(__class__.brush_first_selected)
			self.outline.setPen(__class__.pen_first_selected)
		elif self.selected_state == SELECTED:
			self.outline.setBrush(__class__.brush_selected)
			self.outline.setPen(__class__.pen_selected)
		else:
			self.outline.setBrush(__class__.brush)
			self.outline.setPen(__class__.pen)
			for connector in chain(self.out_connectors, self.in_connectors):
				connector.set_selected(NOT_SELECTED)


class PortCell(Cell):

	def create_downstream_cells(self):
		self.downstream_cells = [ Cell(
			client,
			client.track_widget().moniker if isinstance(client, LiquidSFZ) else client.moniker
		) for client in self.client.output_clients() ]


class Connector(QGraphicsPathItem):

	pen_width = 1.0
	pen_color = QColor(80, 80, 80)
	pen_width_selected = 2.3
	pen_color_selected = QColor(80, 80, 255)
	pen = None
	pen_selected = None
	control_point_shift = None

	def __init__(self, source_cell, target_cell):
		super().__init__()
		if __class__.pen is None:
			__class__.pen = QPen(__class__.pen_color)
			__class__.pen.setWidthF(__class__.pen_width)
			__class__.pen_selected = QPen(__class__.pen_color_selected)
			__class__.pen_selected.setWidthF(__class__.pen_width_selected)
			__class__.control_point_shift = QPointF(CELL_SPACING_X, 0)
		self.source_cell = source_cell
		self.target_cell = target_cell
		self.source_cell.out_connectors.append(self)
		self.target_cell.in_connectors.append(self)
		self.selected_state = NOT_SELECTED
		self.setPen(__class__.pen)

	def reposition(self):
		out_point = self.source_cell.output_connection_point()
		path = QPainterPath(out_point)
		in_point = self.target_cell.input_connection_point()
		path.cubicTo(
			out_point + __class__.control_point_shift,
			in_point - __class__.control_point_shift,
			in_point
		)
		self.setPath(path)

	def set_selected(self, state):
		self.selected_state = state
		self.setPen(__class__.pen_selected \
			if self.selected_state == SELECTED \
			else __class__.pen)

	def mousePressEvent(self, event):
		super().mousePressEvent(event)
		self.scene().parent().connector_press_event(self, event)


#  end musecbox/dialogs/connection_dialog.py
