#  musecbox/dialogs/copy_sfz_paths_dialog.py
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
import logging
from PyQt5.QtCore import	Qt, pyqtSlot, QSize
from PyQt5.QtWidgets import	QApplication, QDialog, QHBoxLayout, QVBoxLayout, QSizePolicy, \
							QLabel, QPushButton, QSpacerItem
from PyQt5.QtGui import		QIcon
from musecbox import set_application_style, LOG_FORMAT


class CopySFZPathsDialog(QDialog):

	def __init__(self, parent, text):
		super().__init__(parent)
		self.setObjectName("sfz_paths_dialog")
		sz = QSize(636, 320)
		self.resize(sz)
		self.setMinimumSize(sz)
		lo = QHBoxLayout(self)
		lo.setContentsMargins(20, 10, 20, 24)
		lo.setSpacing(12)
		self.lbl_list = QLabel(self)
		self.lbl_list.setWordWrap(True)
		self.lbl_list.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignTop)
		self.lbl_list.setText(text)
		lo.addWidget(self.lbl_list)
		vlo = QVBoxLayout()
		b_copy = QPushButton('&Copy', self)
		b_copy.setFixedSize(QSize(100, 40))
		b_copy.setIcon(QIcon.fromTheme("edit-copy"))
		b_copy.setIconSize(QSize(24, 24))
		b_copy.clicked.connect(self.accept)
		vlo.addWidget(b_copy)
		vlo.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
		lo.addLayout(vlo)
		self.setLayout(lo)

	@pyqtSlot()
	def accept(self):
		QApplication.instance().clipboard().setText(self.lbl_list.text())
		super().accept()


if __name__ == "__main__":
	logging.basicConfig(level = logging.DEBUG, format = LOG_FORMAT)
	app = QApplication([])
	set_application_style()
	dlg = CopySFZPathsDialog(None, """/path/to/file1.sfz
/path/to/file2.sfz
/path/to/file3.sfz
/path/to/file4.sfz""")
	dlg.exec()


#  end musecbox/dialogs/copy_sfz_paths_dialog.py
