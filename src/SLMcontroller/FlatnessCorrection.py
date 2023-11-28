#!/usr/bin/env python

"""FlatnessCorrection.py: Generates a tab used to load an optical flatness correction element (this is usually a 8bit image given by the SLM producer)."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QMessageBox, QLineEdit, QGridLayout, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt


import SLMcontroller.utils as utils
import cv2
import os
import numpy as np

class FlatnessCorrectionTab(QWidget):
    """Generates a tab used to load an optical flatness correction element (this is usually a 8bit image given by the SLM producer).
    Attributes:
        pattern (:numpy.ndarray:): Array containing the loaded flatness correction image.
        pattern_generator (:Pattern_generator:): Pattern generator object used to generate the flatness correction image.
        settings_manager (:SettingsManager:): Settings manager object used to get the SLM resolution.
        hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        image_data (:numpy.ndarray:): Array containing the loaded flatness correction image.
        loaded_file (str): Path to the loaded flatness correction image.
        scale (int): Scale used to display the flatness correction image.
        script_folder (str): Path to the folder containing the script.
        SLM_x_res (int): SLM X resolution.
        SLM_y_res (int): SLM Y resolution.
    """
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        """Constructor for the FlatnessCorrectionTab class.

        Args:
            pattern_generator (:Pattern_generator:): Pattern generator object. Added for consistency with other classes (not used here)
            settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
            hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        """
        super().__init__()
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.image_data = None
        self.loaded_file = "none"
        self.scale = 10
        self.script_folder = os.path.realpath(__file__)
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.Init_GUI()

    def __del__(self):
        """Destructor for the FlatnessCorrectionTab class.

        Todo:
            Implement this?
        """
        pass

    def Init_GUI(self):
        """Generates the GUI elements of the tab.

        The tab contains:
        - A text field to enter the path to the flatness correction image.
        - A button to load the flatness correction image.
        - A checkbox to activate the flatness correction.
        - An image preview of the flatness correction image.
        """
        self.layout = QGridLayout()
        
        self.image_loading_layout = QVBoxLayout()
        self.image_preview_layout = QVBoxLayout()
        self.general_controls = QHBoxLayout()
        
        self.image_path = QLineEdit("deformation_correction_pattern/CAL_LSH0802160_760nm.bmp")
        self.loadimage = QPushButton("Load Flatness Correction Image")
        self.loadimage.clicked.connect(self.update_pattern)

        self.pattern_image = utils.ImageWidget()
        
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.image_loading_layout.addWidget(self.image_path)
        self.image_loading_layout.addWidget(self.loadimage)
        self.layout.addLayout(self.image_loading_layout,0,0)

        self.image_preview_layout.addWidget(self.pattern_image)
        self.layout.addLayout(self.image_preview_layout,1,0)

        self.general_controls.addWidget(self.isactive)
        self.layout.addLayout(self.general_controls,2,0)

        #self.mesh_layout.addLayout(self.showmesh_layout)
        self.setLayout(self.layout)



    def update_pattern(self):
        """Updates the flatness correction image loading it from a file
        """
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        if self.loaded_file != self.image_path.text():
            img = cv2.imread(self.image_path.text(), -1)
            if img is None:
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Wrong path to image")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return
            self.pattern = np.array(img)
            print(self.pattern.shape)
            if len(self.pattern.shape) != 2:
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Your image does not use a 8 bits color scheme, check the image and retry")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return	
            if (self.pattern.shape[1] != self.SLM_x_res) or (self.pattern.shape[0] != self.SLM_y_res) :
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Image dimensions don't match with SLM size")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return	
            self.loaded_file = self.image_path.text()
            self.pattern_image.setImage(self.pattern)

    def get_pattern(self):
        """Returns the flatness correction image.

        Returns:
            :numpy.ndarray: Array containing the flatness correction image.
        """
        self.update_pattern()
        return self.pattern

    def is_active(self):
        """Checks if the flatness correction element is active.

        Returns:
            bool: True if the flatness correction element is active, False otherwise.
        """
        return self.isactive.isChecked()

