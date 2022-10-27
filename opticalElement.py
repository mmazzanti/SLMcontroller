# This Python file uses the following encoding: utf-8
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QGridLayout, QGroupBox, QComboBox, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSlider, QCheckBox, QSpinBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6 import QtCore, QtWidgets

import numpy as np

import Phase_pattern

class opticalElement(QDialog):
    def __init__(self, elements_map, parent = None):
        super().__init__(parent)
        self.set_attributes()
        self.generate_selection_window(elements_map)

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

class LensTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern = None
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.focus = 0
        self.init_GUI()

    def init_GUI(self):
        self.slider_layout = QHBoxLayout()

        self.label = QLabel(self)
        self.label.setText("Focus: 0 mm")

        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.spin_focus = QSpinBox(text="Focus ")


        self.focus_slider = DoubleSlider()
        self.focus_slider.setGeometry(50,50, 200, 50)
        self.focus_slider.setMinimum(0)
        self.focus_slider.setMaximum(2000)
        self.focus_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.focus_slider.setTickInterval(10)
        self.focus_slider.valueChanged.connect(self.update_lens)

        self.slider_layout.addWidget(self.focus_slider)
        self.slider_layout.addWidget(self.label)

        self.layout = QGridLayout()
        self.layout.addLayout(self.slider_layout,0,0)
        self.layout.addWidget(self.isactive,1,0)
        #self.layout.addWidget(self.label,1,0)

        self.setLayout(self.layout)

    def update_lens(self):
        self.focus = self.sender().value()
        self.label.setText("Focus: "+str(self.focus)+" mm")

    def get_pattern(self):
        self.pattern = self.pattern_generator.GenerateLens(self.focus, self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()

class GratingTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern = None
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.lmm = 0.
        self.angle = 0.
        self.init_GUI()

    def init_GUI(self):
        self.general_controls_layout = QVBoxLayout()
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.liveupdate = QCheckBox("Live updating : ")
        self.liveupdate.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.general_controls_layout.addWidget(self.isactive)
        self.general_controls_layout.addWidget(self.liveupdate)

        self.make_lmm_slider()
        self.make_angle_slider()

        self.layout = QGridLayout()
        self.layout.addLayout(self.lmm_layout,0,0)
        self.layout.addLayout(self.angle_layout,1,0)
        self.layout.addLayout(self.general_controls_layout,2,0)
        #self.layout.addWidget(self.label,1,0)

        self.setLayout(self.layout)

    def make_lmm_slider(self):
        self.lmm_layout = QVBoxLayout()

        self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        self.spin_lmm.setSuffix(' l/mm')
        self.spin_lmm.valueChanged.connect(self.update_lmm)
        self.spin_lmm.setKeyboardTracking(False)
        self.spin_lmm.setSingleStep(0.1)

        self.lmm_slider = DoubleSlider()
        self.lmm_slider.setGeometry(50,50, 200, 50)
        self.lmm_slider.setMinimum(0)
        self.lmm_slider.setMaximum(1e-3/(self.settings_manager.get_pixel_pitch()*1e-6))
        self.lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.lmm_slider.setTickInterval(1/10)
        self.lmm_slider.valueChanged.connect(self.update_lmm)

        self.lmm_layout.addWidget(self.spin_lmm)
        self.lmm_layout.addWidget(self.lmm_slider)

    def make_angle_slider(self):
        self.angle_layout = QHBoxLayout()

        self.spin_angle = QDoubleSpinBox(text="Grating angle")
        self.spin_angle.setSuffix(' π')
        self.spin_angle.valueChanged.connect(self.update_angle)
        self.spin_angle.setKeyboardTracking(False)
        self.spin_angle.setSingleStep(0.1)

        self.angle_slider = DoubleSlider()
        self.angle_slider.setGeometry(50,50, 200, 50)
        self.angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        self.angle_slider.setMaximum(2.)
        self.angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.angle_slider.valueChanged.connect(self.update_angle)

        self.angle_layout.addWidget(self.spin_angle)
        self.angle_layout.addWidget(self.angle_slider)

    def update_lmm(self):
        self.lmm = self.sender().value()
        self.lmm_slider.setValue(self.lmm)
        self.spin_lmm.setValue(self.lmm)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()

    def update_angle(self):
        self.angle = self.sender().value()
        self.angle_slider.setValue(self.angle)
        self.spin_angle.setValue(self.angle)
        if self.liveupdate.isChecked():
            self.update_pattern()
            self.hologram_manager.updateSLMWindow()


    def update_pattern(self):
        self.pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.lmm, self.angle*np.pi, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())

    def get_pattern(self):
        self.update_pattern()
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()

class DoubleSlider(QSlider):
    doubleValueChanged = pyqtSignal(float)
    def __init__(self, decimals=3, *args, **kargs):
        super(DoubleSlider, self).__init__(Qt.Orientation.Horizontal,*args, **kargs)
        self._multi = 10 ** decimals

        self.valueChanged.connect(self.emitDoubleValueChanged)

    def emitDoubleValueChanged(self):
        value = float(super(DoubleSlider, self).value())/self._multi
        self.doubleValueChanged.emit(value)

    def value(self):
        return float(super(DoubleSlider, self).value()) / self._multi

    def setMinimum(self, value):
        return super(DoubleSlider, self).setMinimum(value * self._multi)

    def setMaximum(self, value):
        return super(DoubleSlider, self).setMaximum(value * self._multi)

    def setSingleStep(self, value):
        return super(DoubleSlider, self).setSingleStep(value * self._multi)

    def singleStep(self):
        return float(super(DoubleSlider, self).singleStep()) / self._multi

    def setValue(self, value):
        super(DoubleSlider, self).setValue(int(value * self._multi))
