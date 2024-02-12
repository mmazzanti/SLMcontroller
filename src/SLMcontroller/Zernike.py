#!/usr/bin/env python

"""Zernike.py: Generates a tab used to generate Zernike polinomials phase patterns."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2023, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QHeaderView, QTableWidgetItem, QCheckBox, QSpinBox,QTableWidget,QStyledItemDelegate, QMessageBox, QLineEdit, QComboBox, QLabel, QSlider, QDoubleSpinBox,QGridLayout, QVBoxLayout, QGroupBox, QHBoxLayout, QWidget, QPushButton, QFileDialog
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
        self.centerX.setMinimumWidth(120)
        self.labelX = QLabel('X: ', self)
        self.centerX.setMinimum(0)
        self.centerX.setMaximum(self.SLM_x_res)
        self.centerY = QSpinBox(text="Zernike Center Y")
        self.centerY.setMinimumWidth(120)
        self.labelY = QLabel('Y: ', self)
        self.centerY.setMinimum(0)
        self.centerY.setMaximum(self.SLM_y_res)
        self.ZernikeOrders = 1

        # Create Zernike table
        self.ZernikeTable = QTableWidget(1, self.ZernikeOrders)
        delegate = NumericDelegate(self.ZernikeTable)
        self.ZernikeTable.setItemDelegate(delegate)
        self.ZernikeTable.setItem(0,0, QTableWidgetItem("0"))
        self.ZernikeTable.setHorizontalHeaderLabels(["Coefficient"])
        self.ZernikeTable.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.ZernikeTable.item(0,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ZernikeTable.itemChanged.connect(self.auto_update)

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

        self.loadZernikebutton = QPushButton("Load from file")
        self.saveZernikebutton = QPushButton("Save to file")
        self.loadZernikebutton.clicked.connect(self.loadZernikeFromFile)
        self.saveZernikebutton.clicked.connect(self.saveZernikeToFile)


        # Activate/disable element
        self.isactive = QCheckBox("Activate element: ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.liveupdate = QCheckBox("Live updating: ")
        self.liveupdate.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        

        self.ZernikeLayout = QVBoxLayout()
        self.ZernikeLayout.addWidget(self.make_group("Load/save coefficients", self.loadZernikebutton, self.saveZernikebutton))
        self.ZernikeLayout.addWidget(self.make_group("Zernike Center", self.labelX, self.centerX, self.labelY, self.centerY))
        self.ZernikeLayout.addWidget(self.make_group("Polynomials coefficients (OSA/ANSI)", self.ZernikeTable))
        self.ZernikeLayout.addLayout(self.add_remove_Zernike)
        

        self.make_image_preview()
        self.ZernikeLayout.addLayout(self.image_preview_layout)

        # self.testingbutton = QPushButton("Test")
        # self.testingbutton.clicked.connect(self.readZernikeTable)
        # self.ZernikeLayout.addWidget(self.make_group("Testing", self.testingbutton))
        #self.ZernikeLayout.addWidget(self.make_group("Activate", self.isactive))
        self.ZernikeLayout.addWidget(self.isactive)
        self.ZernikeLayout.addWidget(self.liveupdate)
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
        self.ZernikeTable.setItem(self.ZernikeOrders-1,0, QTableWidgetItem("0"))
        self.ZernikeTable.item(self.ZernikeOrders-1,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def add_zernikeN(self,order,coeff):
        """Adds a new Zernike order to the table. Fills the table with 0 in case lower orders are missing.
        """
        order = int(order)
        coeff = float(coeff)
        print("Adding Zernike order ",order," with coefficient ",coeff)
        if order > self.ZernikeOrders:
            # Fill the table with missing coefficients
            self.ZernikeTable.setRowCount(order)
            print(self.ZernikeOrders," ---- ", order-self.ZernikeOrders)
            for i in range(self.ZernikeOrders,order-1):
                self.ZernikeTable.setItem(i,0, QTableWidgetItem("0"))
                self.ZernikeTable.item(i,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                print(i)
            #print(order," : ",coeff)
            self.ZernikeTable.setItem(order-1,0, QTableWidgetItem(str(coeff)))
            self.ZernikeTable.item(order-1,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ZernikeOrders = order
        else:
            self.ZernikeTable.setItem(order-1,0, QTableWidgetItem(str(coeff)))
            self.ZernikeTable.item(order-1,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return jsonify(coefficients = self.readZernikeTable().tolist())#,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)

        #self.ZernikeOrders += 1
        #self.ZernikeTable.setRowCount(self.ZernikeOrders)
        #self.ZernikeTable.setItem(self.ZernikeOrders-1,0, QTableWidgetItem(str(coeff)))
        #self.ZernikeTable.item(self.ZernikeOrders-1,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        

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

    def saveZernikeToFile(self):
        """Saves Zernike parameters to file.
        """
        # Opens a prompt for the user to select a mesh file
        ZernikeFile = QFileDialog.getSaveFileName(self,"Save File","","Numpy (*.npy);;")
        datadict={'centerX':self.centerX.value(), 'centerY':self.centerY.value(),'coefficients':self.readZernikeTable()}
        np.save(ZernikeFile[0], datadict)
    
    def loadZernikeFromFile(self):
        """Loads Zernike parameters from file.
        """
        # Opens a prompt for the user to select a mesh file
        ZernikeFile = QFileDialog.getOpenFileName(self,"Open File","${HOME}","Numpy (*.npy);;",)
        try:
            data = np.load(ZernikeFile[0], allow_pickle=True)
            self.centerX.setValue(data.item().get('centerX'))
            self.centerY.setValue(data.item().get('centerY'))

            coefficients = data.item().get('coefficients')
            # Clear the table
            self.ZernikeTable.setRowCount(0)
            self.ZernikeTable.setRowCount(len(coefficients))
            for i in range(len(coefficients)):
                self.ZernikeTable.setItem(i,0, QTableWidgetItem(str(coefficients[i])))
                self.ZernikeTable.item(i,0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.ZernikeOrders = len(coefficients)
        except:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("There is an error in the Zernike file, check that all variables are present and correctly formatted")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
    
    def auto_update(self):
        """Updates the Zernike pattern when the table is modified.
        """
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()
            
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
            reg_ex = QRegularExpression("[+\-]?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+\-]?\d+)?")
            validator = QRegularExpressionValidator(reg_ex, editor)
            editor.setValidator(validator)
        return editor