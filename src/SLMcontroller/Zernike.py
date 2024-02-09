#!/usr/bin/env python

"""Zernike.py: Generates a tab used to generate Zernike polinomials phase patterns."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2023, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QCheckBox, QSpinBox,QTableWidget,QStyledItemDelegate, QMessageBox, QLineEdit, QComboBox, QLabel, QSlider, QDoubleSpinBox,QGridLayout, QVBoxLayout, QGroupBox, QHBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtCore import Qt

import SLMcontroller.utils as utils
import numpy as np

from numba import jit
from numba.typed import List

from PIL import Image
from io import BytesIO

from flask import jsonify, send_file, abort


class ZernikeTab(QWidget):
    """Generates a tab used to generate Zernike polinomials phase patterns.
    """
    def __del__(self):
        """Destructor for the SpotOptimTab_ext class. Stops the optimization thread and closes the mesh GUI process.
        """
        pass
        
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager

        self.pattern = None
        self.lastvals = np.array([])

        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()

        # Define widgets
        self.centerX = QSpinBox(text="Zernike Center X")
        self.centerX.setMinimum(0)
        self.centerX.setMaximum(self.SLM_x_res)
        self.centerY = QSpinBox(text="Zernike Center Y")
        self.centerY.setMinimum(0)
        self.centerY.setMaximum(self.SLM_y_res)
        self.ZernikeOrders = 1

        # Create Zernike table
        self.ZernikeTable = QTableWidget(1, self.ZernikeOrders)
        delegate = NumericDelegate(self.ZernikeTable)
        self.ZernikeTable.setItemDelegate(delegate)
        
        # Sub layout for adding/removing Zernike orders
        self.add_remove_Zernike = QHBoxLayout()
        # Add button
        self.addOrder = QPushButton("Add order")
        self.addOrder.clicked.connect(self.add_Zernike)
        # Remove button
        self.removeOrder = QPushButton("Remove order")
        self.removeOrder.clicked.connect(self.remove_Zernike)
        # Add buttons to layout
        self.add_remove_Zernike.addWidget(self.addOrder)
        self.add_remove_Zernike.addWidget(self.removeOrder)

        # Activate/disable element
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        

        self.ZernikeLayout = QVBoxLayout()
        self.ZernikeLayout.addWidget(self.make_group("Zernike Center", self.centerX,self.centerY))
        self.ZernikeLayout.addWidget(self.make_group("Polynomials coefficients", self.ZernikeTable))
    
        
        self.ZernikeLayout.addLayout(self.add_remove_Zernike)

        self.make_image_preview()
        self.ZernikeLayout.addLayout(self.image_preview_layout)

        # self.testingbutton = QPushButton("Test")
        # self.testingbutton.clicked.connect(self.readZernikeTable)
        # self.ZernikeLayout.addWidget(self.make_group("Testing", self.testingbutton))
        self.ZernikeLayout.addWidget(self.make_group("Activate", self.isactive))
        self.setLayout(self.ZernikeLayout)

    def make_group(self, group_name, *widgets):
        groupBox = QGroupBox(group_name)
        hbox = QHBoxLayout()
        for widget in widgets:
            hbox.addWidget(widget)
        groupBox.setLayout(hbox)
        return groupBox
    
    def remove_Zernike(self):
        """Removes the last Zernike order from the table.
        """
        if self.ZernikeOrders > 1:
            self.ZernikeOrders -= 1
        self.ZernikeTable.setRowCount(self.ZernikeOrders)

    def add_Zernike(self):
        """Adds a new Zernike order to the table.
        """
        self.ZernikeOrders += 1
        self.ZernikeTable.setRowCount(self.ZernikeOrders)

    def readZernikeTable(self):
        """Reads the Zernike table and returns a list of coefficients.
        """
        coefficients = np.array([])
        for i in range(self.ZernikeOrders):
            item = self.ZernikeTable.item(i,0)
            if item is not None:
                coefficients = np.append(coefficients, float(item.text()))
            else :
                coefficients = np.append(coefficients, 0)
        return coefficients
    
    def update_pattern(self):
        """Updates the Zernike phase pattern.
        """
        self.SLM_last_params = []

        # No need to re-read the SLM resolution here as it was just checked (needs_updates)
        self.lastvals = np.concatenate((np.array([self.SLM_x_res, self.SLM_y_res,self.centerX.value(),self.centerY.value()]),self.readZernikeTable()))
        # for order in range(self.ZernikeOrders):
        #     if order == 0:
        #         n,m = 0,0
        #     else:
        #         n = int(np.floor(np.sqrt(4/np.sqrt(3)*order))-1)
        #         m = n+2+2*(order-np.round(np.sqrt(3)/4*n**2))
        #     self.lastvals[order]
        self.pattern = self.pattern_generator.GenerateZernike(self.readZernikeTable(), self.SLM_x_res, self.SLM_y_res, self.centerX.value(), self.centerY.value())
        self.pattern_image.setImage(self.pattern)
        
    def make_image_preview(self):
        """Generates the image preview of the Zernike pattern.
        """
        self.image_preview_layout = QVBoxLayout()
        self.pattern_image = utils.ImageWidget()
        self.image_preview_layout.addWidget(self.pattern_image)
    
    def needs_updates(self):
        """Checks if the lens needs to be updated.

        Returns:
            bool: True if the lens needs to be updated, False otherwise.
        """
        # Reload the SLM resolution (user might have changed it)
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()

        news_vals = np.concatenate((np.array([self.SLM_x_res, self.SLM_y_res,self.centerX.value(),self.centerY.value()]),self.readZernikeTable()))
        if len(self.lastvals) != len(news_vals):
            return True
        for i in range(len(self.lastvals)):
            self.lastvals[i] != news_vals[i]
            return True
        return False

    def get_pattern(self):
        """Returns the lens pattern.

        Returns:
            :numpy.ndarray: Array containing the lens pattern.
        """
        if self.pattern is None or self.needs_updates():
            self.update_pattern()
        return self.pattern
    
    def is_active(self):
        """Checks if the lens is active (should be added to the rendered holograms)

        Returns:
            bool: True if the lens is active, False otherwise.
        """
        return self.isactive.isChecked()


# Class for checking user input in the Zernike table
# Should be numerical or in scientific notation

class NumericDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super(NumericDelegate, self).createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            reg_ex = QRegularExpression("[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?")
            validator = QRegularExpressionValidator(reg_ex, editor)
            editor.setValidator(validator)
        return editor