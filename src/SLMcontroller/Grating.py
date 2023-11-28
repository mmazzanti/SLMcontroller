#!/usr/bin/env python

"""Grating.py: Generates a tab used to control an optical grating element. The grating can be rotated and its line density can be changed."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QDoubleSpinBox, QGridLayout, QVBoxLayout, QWidget, QSlider, QCheckBox
from PyQt6.QtCore import Qt

import SLMcontroller.utils as utils
import numpy as np

class GratingTab(QWidget):
    """Generates a tab used to control an optical grating element. The grating can be rotated and its line density can be changed. 
    The grating is generated using the GenerateGrating function of the PatternGenerator class. 
    The grating will depend on the selected wavelength and SLM pixel pitch.

    Attributes:
        pattern (:numpy.ndarray:): Array containing the generated grating.
        pattern_generator (:Pattern_generator:): Pattern generator object used to generate the grating.
        settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
        hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        minlmm (float): Minimum number of lines per mm that can be used to generate the grating.
        maxlmm (float): Maximum number of lines per mm that can be used to generate the grating.
        lmm (float): Number of lines per mm used to generate the grating.
        angle (float): Angle of the grating in radians.
        lastvals (list): List containing the last values of the angle, lmm, wavelength, pixel pitch, X resolution and Y resolution used to generate the last grating (used to avoid re-generating gratings). 
    """
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        """Constructor for the GratingTab class.

        Args:
            pattern_generator (:Pattern_generator:): Pattern generator object used to generate the grating.
            settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
            hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        """
        super().__init__()
        self.pattern = None
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.minlmm = 0
        self.maxlmm = 1e-3/(2*self.settings_manager.get_pixel_pitch()*1e-6)
        self.lmm = 0.
        self.angle = 0.
        self.init_GUI()
    def __del__(self):
        """Destructor for the GratingTab class.

        Todo:
            Implement this?
        """
        pass

    def init_GUI(self):
        """Generates the GUI elements of the tab. 
        The tab contains:
        - A slider and a spinbox to control the number of lines per mm of the grating.
        - A slider and a spinbox to control the angle of the grating.
        - A checkbox to activate the grating.
        - A checkbox to enable live updating of the grating.
        - An image preview of the grating.
        """
        self.general_controls_layout = QVBoxLayout()
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.liveupdate = QCheckBox("Live updating : ")
        self.liveupdate.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.general_controls_layout.addWidget(self.isactive)
        self.general_controls_layout.addWidget(self.liveupdate)

        self.make_lmm_slider()
        self.make_angle_slider()

        self.make_image_preview()

        self.layout = QGridLayout()
        self.layout.addLayout(self.lmm_layout,0,0)
        self.layout.addLayout(self.angle_layout,1,0)
        self.layout.addLayout(self.image_preview_layout,2,0)
        self.layout.addLayout(self.general_controls_layout,3,0)
        #self.layout.addWidget(self.label,1,0)

        self.setLayout(self.layout)

    def needs_updates(self):
        """Checks if the grating needs to be re-generated.

        Returns:
            bool: True if the grating needs to be re-generated, False otherwise.
        """
        new_vals = [self.angle,self.lmm,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
        for i in range(len(self.lastvals)):
            self.lastvals[i] != new_vals[i]
            return True
        return False

    def make_image_preview(self):
        """Generates the image preview of the grating.
        """
        self.image_preview_layout = QVBoxLayout()
        self.pattern_image = utils.ImageWidget()
        self.image_preview_layout.addWidget(self.pattern_image)

    def make_lmm_slider(self):
        """Generates the slider and spinbox used to control the number of lines per mm of the grating and adds them to the GUI.
        """
        self.lmm_layout = QVBoxLayout()

        self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        self.spin_lmm.setSuffix(' l/mm')
        self.spin_lmm.valueChanged.connect(self.update_lmm_slide)
        self.spin_lmm.setKeyboardTracking(False)
        self.spin_lmm.setSingleStep(0.01)
        self.spin_lmm.setMaximum(self.maxlmm)
        self.spin_lmm.setMinimum(self.minlmm)

        self.lmm_slider = utils.DoubleSlider()
        self.lmm_slider.setGeometry(50,50, 200, 50)
        self.lmm_slider.setMinimum(0)
        self.lmm_slider.setMaximum(self.maxlmm)
        self.lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.lmm_slider.setTickInterval(3000)
        self.lmm_slider.valueChanged.connect(self.update_lmm_spin)

        self.lmm_layout.addWidget(self.spin_lmm)
        self.lmm_layout.addWidget(self.lmm_slider)

    def make_angle_slider(self):
        """Generates the slider and spinbox used to control the angle of the grating and adds them to the GUI.
        """
        self.angle_layout = QVBoxLayout()

        self.spin_angle = QDoubleSpinBox(text="Grating angle")
        self.spin_angle.setSuffix(' π')
        self.spin_angle.valueChanged.connect(self.update_angle_slide)
        self.spin_angle.setKeyboardTracking(False)
        self.spin_angle.setSingleStep(0.01)

        self.angle_slider = utils.DoubleSlider()
        self.angle_slider.setGeometry(50,50, 200, 50)
        self.angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        self.angle_slider.setMaximum(2.)
        self.angle_slider.setTickInterval(100)
        self.angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.angle_slider.valueChanged.connect(self.update_angle_spin)

        self.angle_layout.addWidget(self.spin_angle)
        self.angle_layout.addWidget(self.angle_slider)

    def update_lmm_spin(self):
        """Updates the number of lines per mm of the grating when the spinbox is changed (usually called from the slider valueChanged signal)
        """
        self.lmm = self.sender().value()
        #self.lmm_slider.setValue(self.lmm)
       
        if self.spin_lmm.value() != self.lmm:
            self.spin_lmm.setValue(self.lmm)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()
    
    def update_lmm_slide(self):
        """Updates the number of lines per mm of the grating when the slider is changed (usually called from the spinbox valueChanged signal)
        """
        self.lmm = self.sender().value()
        if(self.lmm_slider.value() != self.lmm):
            self.lmm_slider.setValue(self.lmm)
        #self.spin_lmm.setValue(self.lmm)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_angle_spin(self):
        """Updates the angle of the grating when the spinbox is changed (usually called from the slider valueChanged signal)
        """
        self.angle = self.sender().value()
        #self.angle_slider.setValue(self.angle)
        self.spin_angle.setValue(self.angle)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_angle_slide(self):
        """Updates the angle of the grating when the slider is changed (usually called from the spinbox valueChanged signal)
        """
        self.angle = self.sender().value()
        self.angle_slider.setValue(self.angle)
        #self.spin_angle.setValue(self.angle)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()


    def update_pattern(self):
        """Updates the grating pattern.
        """
        self.pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.lmm, self.angle*np.pi, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern_image.setImage(self.pattern)
        self.lastvals = [self.angle,self.lmm,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]

    def get_pattern(self):
        """Returns the grating pattern.
        """
        if self.pattern is None or self.needs_updates():
            self.update_pattern()
        return self.pattern

    def is_active(self):
        """Returns the state of the isactive checkbox.
        """
        return self.isactive.isChecked()
