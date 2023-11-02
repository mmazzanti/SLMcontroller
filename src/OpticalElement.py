# This Python file uses the following encoding: utf-8
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QMessageBox, QLineEdit, QGridLayout, QGroupBox, QComboBox, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSlider, QCheckBox, QSpinBox , QPushButton
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QPoint
from PyQt6.QtGui import QImage, QPainter


import numpy as np
import gmsh
import src.utils as utils
import src.Lens as Lens


#import src.Phase_pattern as Phase_pattern

import cv2
import os
import threading

class opticalElement(QDialog):
    def __init__(self, elements_map, parent = None):
        super().__init__(parent)
        self.set_attributes()
        self.generate_selection_window(elements_map)
    def __del__(self):
        pass

    def set_attributes(self):
        """
        Set attributes to the settings dialog.
        """
        self.setWindowTitle("Choose optical element")

    def generate_selection_window(self,elements_map):
        """Create groups of radio buttons as settings elements."""
        grid = QGridLayout()
        groupBox = QGroupBox("Which element you want to add ?")
        self.opt_elem_list = QComboBox()
        slayout = QVBoxLayout()
        for el in elements_map:
            self.opt_elem_list.addItem(el)

        slayout.addWidget(self.opt_elem_list)
        _buttons = QDialogButtonBox.StandardButton
        self.button_box = QDialogButtonBox(_buttons.Ok | _buttons.Cancel)

        slayout.addWidget(self.button_box)
        self.setLayout(slayout)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.accepted.connect(self.return_element)

    def return_element(self):
        self.choosen = self.opt_elem_list.currentIndex()

    def get_selected(self):
        return self.choosen
