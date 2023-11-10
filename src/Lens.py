# This Python file uses the following encoding: utf-8
from PyQt6.QtWidgets import QDoubleSpinBox, QGridLayout, QVBoxLayout, QWidget, QSlider, QCheckBox
from PyQt6.QtCore import Qt


import src.utils as utils


class LensTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
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
        pass

    def init_GUI(self):
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
        #self.layout.addWidget(self.label,1,0)

        self.setLayout(self.layout)

    # def removeme(self):
    #     self.hologram_manager.removeElementFromList(id(self), self)
    #     passpattern

    def make_image_preview(self):
        self.image_preview_layout = QVBoxLayout()
        self.pattern_image = utils.ImageWidget()
        self.image_preview_layout.addWidget(self.pattern_image)

    def update_lens_spin(self):
        self.focus = self.sender().value()
        #self.focus_slider.setValue(self.focus)
        if self.spin_focus.value() != self.focus:
            self.spin_focus.setValue(self.focus)
        #self.spin_focus.setValue(self.focus)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_lens_slide(self):
        self.focus = self.sender().value()
        #self.focus_slider.setValue(self.focus)
        if self.focus_slider.value() != self.focus:
            self.focus_slider.setValue(self.focus)
        #self.spin_focus.setValue(self.focus)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_pattern(self):
        self.pattern = self.pattern_generator.GenerateLens(self.focus, self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern_image.setImage(self.pattern)
        self.lastvals = [self.focus,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
    
    def needs_updates(self):
        news_vals = [self.focus,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]
        for i in range(len(self.lastvals)):
            self.lastvals[i] != news_vals[i]
            return True
        return False

    def get_pattern(self):
        if self.pattern is None or self.needs_updates():
            self.update_pattern()
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()