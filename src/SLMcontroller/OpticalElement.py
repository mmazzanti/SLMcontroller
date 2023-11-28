#!/usr/bin/env python

"""OpticalElement.py: Generates a dialog used to load an optical element."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

# This Python file uses the following encoding: utf-8
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QComboBox, QVBoxLayout


import SLMcontroller.utils as utils
import SLMcontroller.Lens as Lens


class opticalElement(QDialog):
    """Generates a dialog used to load an optical element. 
    The list allows to choose between various optical elements (lens, grating, etc..)
    """
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
        """Create groups of radio buttons as settings elements.

        Args:
            elements_map (list): List of optical elements to choose from.
        """
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
        """Sets the selected optical element when the user selects from the list.
        """
        self.choosen = self.opt_elem_list.currentIndex()

    def get_selected(self):
        """Return the selected optical element.

        Returns:
            int: Index of the selected optical element.
        """
        return self.choosen
