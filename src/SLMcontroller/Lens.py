#!/usr/bin/env python

"""Lens.py: Generates a tab used to control an optical lens element."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QDoubleSpinBox, QGridLayout, QVBoxLayout, QWidget, QSlider, QCheckBox
from PyQt6.QtCore import Qt


import SLMcontroller.utils as utils
import numpy as np

class LensTab(QWidget):
    """Generates a tab used to control an optical lens element.
    The lens is generated using the GenerateLens function of the PatternGenerator class. 
    The lens will depend on the selected wavelength, focus and SLM pixel pitch.
    
    Attributes:
        pattern (:numpy.ndarray:): Array containing the generated lens.
        pattern_generator (:Pattern_generator:): Pattern generator object used to generate the lens.
        settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
        hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        minfocus (float): Minimum focus distance that can be used to generate the lens.
        maxfocus (float): Maximum focus distance that can be used to generate the lens.
        focus (float): Focus distance used to generate the lens.
        lastvals (list): List containing the last values of the focus, wavelength, pixel pitch, X resolution and Y resolution used to generate the last lens (used to avoid re-generating lenses).
    """
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        """Constructor for the LensTab class.

        Args:
            pattern_generator (:Pattern_generator:): Pattern generator object used to generate the lens.
            settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
            hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        """
        super().__init__()
        self.pattern = None
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.minfocus = -2000
        self.maxfocus = 2000
        self.focus = self.minfocus

        self.init_GUI()
        
    def __del__(self):
        """Destructor for the LensTab class.
        """
        pass

    def init_GUI(self):
        """Generates the GUI elements of the tab.

        The tab contains:
            - A slider and a spinbox to control the focus distance of the lens.
            - A checkbox to activate the lens.
            - A checkbox to enable live updating of the lens.
            - An image preview of the lens.
        """
        self.slider_layout = QVBoxLayout()
        self.general_controls_layout = QVBoxLayout()

        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.liveupdate = QCheckBox("Live updating : ")
        self.liveupdate.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.general_controls_layout.addWidget(self.isactive)
        self.general_controls_layout.addWidget(self.liveupdate)

        self.spin_focus = QDoubleSpinBox(text="Focus ")
        self.spin_focus.setSuffix(' mm')
        self.spin_focus.setKeyboardTracking(False)
        self.spin_focus.setSingleStep(0.01)
        self.spin_focus.setMaximum(self.maxfocus)
        self.spin_focus.setMinimum(self.minfocus)
        self.spin_focus.valueChanged.connect(self.update_lens_slide)

        self.focus_slider = utils.DoubleSlider()
        self.focus_slider.setGeometry(50,50, 200, 50)
        self.focus_slider.setMaximum(self.maxfocus)
        self.focus_slider.setMinimum(self.minfocus)
        self.focus_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.focus_slider.setTickInterval(300000)
        self.focus_slider.valueChanged.connect(self.update_lens_spin)

        self.slider_layout.addWidget(self.spin_focus)
        self.slider_layout.addWidget(self.focus_slider)

        self.make_image_preview()

        self.layout = QGridLayout()
        self.layout.addLayout(self.slider_layout,0,0)
        self.layout.addLayout(self.image_preview_layout,1,0)
        self.layout.addLayout(self.general_controls_layout,2,0)
        self.patten = None
        
        self.setLayout(self.layout)


    def make_image_preview(self):
        """Generates the image preview of the lens.
        """
        self.image_preview_layout = QVBoxLayout()
        self.pattern_image = utils.ImageWidget()
        self.image_preview_layout.addWidget(self.pattern_image)

    def update_lens_spin(self):
        """Updates the focus distance of the lens when the slider is moved.
        """
        self.focus = self.sender().value()
        #self.focus_slider.setValue(self.focus)
        if self.spin_focus.value() != self.focus:
            self.spin_focus.setValue(self.focus)
        #self.spin_focus.setValue(self.focus)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_lens_slide(self):
        """Updates the focus distance of the lens when the spinbox is changed.
        """
        self.focus = self.sender().value()
        #self.focus_slider.setValue(self.focus)
        if self.focus_slider.value() != self.focus:
            self.focus_slider.setValue(self.focus)
        #self.spin_focus.setValue(self.focus)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()
            
            

    def update_pattern(self):
        """Updates the lens pattern.
        """
        self.pattern = self.pattern_generator.GenerateLens(self.focus, self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern_image.setImage(self.pattern)
        self.lastvals = [self.focus,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
        
    
    def needs_updates(self):
        """Checks if the lens needs to be updated.

        Returns:
            bool: True if the lens needs to be updated, False otherwise.
        """
        news_vals = [self.focus,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
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