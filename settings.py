# This Python file uses the following encoding: utf-8

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QDoubleSpinBox, QRadioButton, QVBoxLayout, QSpinBox,QLineEdit


class SettingsManager:

    def __init__(self):
        # SLM settings document (contains resolution, name etc.)
        #self.settings = QSettings("SLM_pattern.ini", QSettings.Format.IniFormat)
        self.settings = QSettings("SLM settings2", "settings")
        self.widget_mappers = {
                'QCheckBox': ('checkState', 'setCheckState',bool),
                'QLineEdit': ('text', 'setText',str),
                'QSpinBox': ('value', 'setValue',int),
                'QSpinBox': ('value', 'setValue',int),
                'QDoubleSpinBox': ('value', 'setValue',float),
                'QRadioButton': ('isChecked', 'setChecked',int),
            }

        self.defaults = {'SLM_size_X' : 800,
                         'SLM_size_Y' : 600,
                         'pattern_window_size_X' : 800,
                         'pattern_window_size_Y' : 600,
                         'Laser wavelength':800,
                         'SLM_window': 0,
                         'Phase_correction' : 255
        }

    def save_from_widget(self, settings_widgets):
        # Save settings from values in the widgets
        for name, widget in settings_widgets.items():
                    # Load name of that widget class (eg. QCheckBox)
                    cls = widget.__class__.__name__
                    # Get getter and setter methods, they're defined in our widget_mapper dictionary
                    getter, setter, type = self.widget_mappers.get(cls, (None, None, None))
                    if getter:
                        # Return the widget module getter
                        fn = getattr(widget, getter)
                        value = fn()
                        if value is not None:
                            self.settings.setValue(name, value) # Set the settings.


    def load_to_widget(self, settings_widgets):
        # Load settings to widget
        for name, widget in settings_widgets.items():
            cls = widget.__class__.__name__
            getter, setter, type = self.widget_mappers.get(cls, (None, None, None))
            value = self.settings.value(name)
            if setter and value is not None:
                fn = getattr(widget, setter)
                if isinstance(value, type):
                    fn(value)  # Set the widget.
                else  :
                    fn(type(value))

    # Returns resolution of that SLM from settings
    # TODO : Make it dependent on the SLM name
    def get_X_res(self):
        if self.settings.value("SLM_size_X") is not None:
            return int(self.settings.value("SLM_size_X"))
        else:
            return self.defaults['SLM_size_X']
    def get_Y_res(self):
        if self.settings.value("SLM_size_Y") is not None:
            return int(self.settings.value("SLM_size_Y"))
        else:
            return self.defaults['SLM_size_Y']

    def get_wavelength(self):
        return self.settings.value("Laser wavelength")

    # Returns size of the pattern window
    # WARNING! This might be different than the SLM resolution!
    # TODO : Make it dependent on the SLM name
    def get_X_win_size(self):
        return int(self.settings.value("pattern_window_size_X"))

    def get_Y_win_size(self):
        return int(self.settings.value("pattern_window_size_Y"))

    def get_phase_correction(self):
        return int(self.settings.value("Phase_correction"))

    def get_pixel_pitch(self):
        return float(self.settings.value("SLM_pixel_pitch"))

    def get_SLM_window(self):
        if self.settings.value("SLM_window") is not None:
            return int(self.settings.value("SLM_window"))
        else:
            return int(self.defaults["SLM_window"])

class SettingsDialog(QDialog):
    """Create a settings dialog to edit all the settings of the application."""
    def __init__(self,settings_manager, parent = None):
        super().__init__(parent)
        # Get settings manager from main class
        self.settings_manager = settings_manager
        self.set_attributes()
        self.create_elements()
        self.set_layout()
        self.load_settings()
        self.connect_signals_to_slots()

    def set_attributes(self):
        """
        Set attributes to the settings dialog.
        """
        self.setWindowTitle("SLM Settings")

    def create_elements(self):
        """Create groups of radio buttons as settings elements."""
        self.SLM_name = QLineEdit()
        self.SLM_window = QSpinBox(text="Monitor to which the SLM is connected")
        self.SLM_window.setMinimum(0)
        self.SLM_window.setMaximum(5)

        self.wavelength = QSpinBox(text="Laser wavelength")
        self.wavelength.setSuffix('  nm')
        self.wavelength.setMaximum(2000)
        self.wavelength.setMinimum(0)

        self.correction = QSpinBox(text="Phase correction")
        self.correction.setMaximum(255)
        self.correction.setMinimum(0)

        self.SLM_res_X = QSpinBox(text="X resolution of SLM")
        self.SLM_res_X.setMaximum(10000)
        self.SLM_res_X.setSuffix(' px')
        self.SLM_res_Y = QSpinBox(text="Y resolution of SLM")
        self.SLM_res_Y.setMaximum(10000)
        self.SLM_res_Y.setSuffix(' px')

        self.SLM_winsize_X = QSpinBox(text="Pattern window size X")
        self.SLM_winsize_X.setSuffix(' px')
        self.SLM_winsize_X.setMaximum(10000)
        self.SLM_winsize_Y = QSpinBox(text="Pattern window size Y")
        self.SLM_winsize_Y.setSuffix(' px')
        self.SLM_winsize_Y.setMaximum(10000)

        self.pixel_pitch = QDoubleSpinBox(text="SLM pixel pitch")
        self.pixel_pitch.setSuffix('  μm')
        #self.pixel_pitch.setMaximum(100)

        self.settings_widgets = {
                    'SLM_name': self.SLM_name,
                    'SLM_window' : self.SLM_window,
                    'Laser wavelength': self.wavelength,
                    'Phase_correction': self.correction,
                    'SLM_size_X': self.SLM_res_X,
                    'SLM_size_Y': self.SLM_res_Y,
                    'pattern_window_size_X': self.SLM_winsize_X,
                    'pattern_window_size_Y': self.SLM_winsize_Y,
                    'SLM_pixel_pitch': self.pixel_pitch,
                }
        #self.settings_manager = SettingsManager()
    def make_group(self, group_name, *widgets):
        groupBox = QGroupBox(group_name)
        vbox = QVBoxLayout()
        for widget in widgets:
            vbox.addWidget(widget)
        groupBox.setLayout(vbox)
        return groupBox

    def set_layout(self):
        """Set a layout for the settings elements."""
        grid = QGridLayout()

        #Settings layout
        slayout = QVBoxLayout()
        slayout.addWidget(self.make_group("SLM ID", self.SLM_name,self.SLM_window))
        slayout.addWidget(self.make_group("Laser parameters", self.wavelength))
        slayout.addWidget(self.make_group("SLM resolution", self.SLM_res_X,self.SLM_res_Y))
        slayout.addWidget(self.make_group("SLM pixel pitch", self.pixel_pitch))
        slayout.addWidget(self.make_group("SLM phase correction", self.correction))
        slayout.addWidget(self.make_group("Pattern window size", self.SLM_winsize_X,self.SLM_winsize_Y))

        #Ok/cancel settings buttons
        _buttons = QDialogButtonBox.StandardButton
        self.button_box = QDialogButtonBox(_buttons.Ok | _buttons.Cancel)

        slayout.addWidget(self.button_box)
        self.setLayout(slayout)

    def connect_signals_to_slots(self):
        """Execute the proper action when a signal is emitted."""
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.accepted.connect(self.save_settings)

    def save_settings(self):
        self.settings_manager.save_from_widget(self.settings_widgets)

    def load_settings(self):
        self.settings_manager.load_to_widget(self.settings_widgets)
