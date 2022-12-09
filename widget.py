#!/usr/bin/env python
# -*- coding: utf-8 -*-


from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtWidgets import QMessageBox, QLabel, QGridLayout, QWidget, QPushButton, QToolBar, QApplication, QHBoxLayout, QSpinBox, QVBoxLayout, QFileDialog, QLabel, QErrorMessage, QTabWidget
from PyQt6.QtGui import QPixmap, QImage, QAction, QScreen

import numpy as np
import random
import sys
import settings
import Phase_pattern
import opticalElement


SLM_size_X = 600
SLM_size_Y = 500


class ImageWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScaledContents(True)

    def hasHeightForWidth(self):
        return self.pixmap() is not None

    def heightForWidth(self, w):
        if self.pixmap():
            try:
                return int(w * (self.pixmap().height() / self.pixmap().width()))
            except ZeroDivisionError:
                return 0

class SLMWindow(QWidget):
    """
    This "window" is a QWidget. If it has no parent, it
    will appear as a free-floating window as we want.
    """
    def __init__(self,resX,resY,window):
        super().__init__(parent=None)
        layout = QVBoxLayout()
        self.setLayout(layout)
        #self.setWindowFlag(QtCore.Qt.WindowType.FramelessWindowHint)
        self.Change_window(window)
        #monitors = QScreen.virtualSiblings(self.screen())
        # If the user selected a monitor that doesn't exist, use the primary monitor
        #monitor = monitors[window].availableGeometry()

        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(QSize(resX,resY))
        self.pattern_image = ImageWidget()
        self.lbl = QLabel(self)
        self.lbl.move(0, 0)
        self.setStyleSheet("background-color: black;")

    # Resize pattern window size
    def Change_window(self,window):
        monitors = QScreen.virtualSiblings(self.screen())
        # If the user selected a monitor that doesn't exist, use the primary monitor
        if len(monitors) <= window:
            window = 0
        monitor = monitors[window].availableGeometry()
        self.move(monitor.left(), monitor.top())

    def ResizeWindow(self,resX,resY):
        self.setFixedSize(QSize(resX,resY))

    def UpdatePattern(self,pixmap):
        self.lbl.setPixmap(pixmap)
        self.lbl.resize(pixmap.width(), pixmap.height())
        self.update()

class HologramsManager():
    def __init__(self, SLMwindow, settings_manager, pattern_generator,tabwidget):
        self.optical_elements = {}
        self.SLMWindow = SLMwindow
        self.settings_manager = settings_manager
        self.pattern_generator = pattern_generator
        self.tabwidget = tabwidget
        self.pattern = None

    def addElementToList(self, id, elem):
        self.optical_elements[id] = elem

    def getElementsList(self):
        return self.optical_elements

    def isListEmpty(self):
        return len(self.optical_elements) == 0

    def removeAll(self):
        todelete = []
        for el in self.optical_elements:
            if el is not None:
                todelete.append(el)
        for el in todelete:
            self.optical_elements[el].__del__()

    def removeElementFromList(self, id):
        del self.optical_elements[id]


    def closeSLMWindow(self):
        pass #Hide SLM window

    def __del__(self):
        self.SLMWindow = None
        self.optical_elements = None

    # This function is used to render a pattern generated from an algorithm, 
    # bypassing the active optical elements
    def renderAlgorithmPattern(self, pattern, others):
        if self.pattern is None:
            self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern = pattern
        if others == True:
            self.getPatterns()
        self.renderPattern()

    #This part corrects for the non-linearities of the SLM
    #For each wavelenght the maximum phase value is given by the company
    #e.g. at 760nm 255 ---> 226
    #So we need to renormalize the hologram such that value%226
    def RenormalizePattern(self):
        self.pattern = self.pattern%(self.settings_manager.get_phase_correction()+1)

    # This function gets all the patterns from the active elements and sums them up
    def getPatterns(self):
         for el in self.optical_elements:
            if el is not None:
                if self.optical_elements[el].is_active():
                    pattern_from_el = self.optical_elements[el].get_pattern()
                    if (pattern_from_el.shape[1] != self.settings_manager.get_X_res()) or (pattern_from_el.shape[0] != self.settings_manager.get_Y_res()) :
                        dlg = QMessageBox(self.tabwidget)
                        dlg.setIcon(QMessageBox.Icon.Warning)
                        dlg.setWindowTitle("WARNING!")
                        dlg.setText("One of the optical elements don't match with the SLM resolution. Please check the settings.")
                        button = dlg.exec()
                        if button == QMessageBox.StandardButton.Ok:
                            return	
                    self.pattern += pattern_from_el

    # This function does the actual render of the phase pattern. Updates the QPixmap used on the SLM window
    def renderPattern(self):
        self.RenormalizePattern()
        q_img = QImage(self.pattern, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res(), self.settings_manager.get_X_res(), QImage.Format.Format_Grayscale8)
#        label = QLabel(self)
        pixmap = QPixmap(q_img)
        self.SLMWindow.ResizeWindow(self.settings_manager.get_X_win_size(),self.settings_manager.get_Y_win_size())
        self.SLMWindow.UpdatePattern(pixmap)

    # Function to update the SLM window when a new pattern is generated
    def updateSLMWindow(self):
        self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.getPatterns()
        self.renderPattern()
        


class First(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(First, self).__init__(parent)
        self.setMinimumSize(QSize(400, 600))
        self.setWindowTitle("SLM hologram control")
        self.settings_manager = settings.SettingsManager()
        self.pattern_generator = Phase_pattern.Patter_generator()
        self.pattern = None
        self.tabwidget = QTabWidget()
        self.tabwidget.setTabsClosable(True)
        self.tabwidget.tabCloseRequested.connect(self.closeTab)

        self.w = SLMWindow(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res(),self.settings_manager.get_SLM_window())
        self.holograms_manager = HologramsManager(self.w, self.settings_manager, self.pattern_generator,self.tabwidget)

        
        self.possible_optical_elements = ["Lens", "Grating", "Flatness correction", "Zernike", "LUT", "Spot optimization"]
        self.tabs_constructors = [self.lens_tab, self.grating_tab, self.flatness_correction_tab, self.zernike_tab, self.LUT_tab, self.Spot_optim]

        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)

        buttons = {}
        self.InitButtons(buttons)

        menu = self.menuBar()
        toolbar = QToolBar("Quick actions")
        grid = QGridLayout()

        self.InitMenu(menu,buttons)
        self.InitToolbar(toolbar,buttons)
        self.addToolBar(toolbar)
        self.InitLayout(grid,buttons)


        wid.setLayout(grid)
        self.show()

    def closeTab(self,index):
        widget = self.tabwidget.widget(index)
        if widget is not None:
            widget.deleteLater()
        self.tabwidget.removeTab(index)
        self.holograms_manager.removeElementFromList(id(widget))

    def lens_tab(self):
        tab = opticalElement.LensTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Lens")
        self.holograms_manager.addElementToList(id(tab), tab)

    def grating_tab(self):
        tab = opticalElement.GratingTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Grating")
        self.holograms_manager.addElementToList(id(tab), tab)

    def flatness_correction_tab(self):
        tab = opticalElement.FlatnessCorrectionTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Flatness Correction")
        self.holograms_manager.addElementToList(id(tab), tab)
    def zernike_tab(self):
        pass
    def LUT_tab(self):
        pass
    def Spot_optim(self):
        tab = opticalElement.SpotOptimTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Optimizer")
        self.holograms_manager.addElementToList(id(tab), tab)

    def edit_SLM_settings(self):
        dlg = settings.SettingsDialog(self.settings_manager, self)
        dlg.exec()
        # Update where the SLM window is (TODO: IS IT GOOD TO DO THIS HERE ??)
        self.w.Change_window(self.settings_manager.get_SLM_window())
        # TODO: ADD HERE RESIZING OF SLM PATTERN TO MATCH RESOLUTION

    def closeEvent(self, event):
        self.holograms_manager.removeAll()
        print("Closing Hologram window")
        QApplication.instance().quit()
#        del self.holograms_manager
#        self.w = None



    def on_pushButton_clicked(self):
        self.w.show()
        #self.pattern = self.pattern_generator.GenerateLens(100, 800, self.settings_manager.get_pixel_pitch(), self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        # Initialize empty pattern. WARNING! Resolution of SLM must be already defined!!
        if self.pattern is None:
            self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.update_pattern()

    def InitLayout(self,grid,buttons):
        grid.addWidget(buttons["SLM_hologram_window"], 1, 0)
        grid.addWidget(buttons["Add_optical_elem"], 2, 0)
        grid.addWidget(self.tabwidget,0,0)

    def AddOpticalElement(self):
        if self.holograms_manager.isListEmpty() and self.tabwidget== None:
            # If the user still didn't choose any optical element generate the tabs layout ?
            pass
        inputter = opticalElement.opticalElement(self.possible_optical_elements, self)
        if inputter.exec():
            self.tabs_constructors[inputter.get_selected()]()

    def InitButtons(self,buttons):
        button_exit = QAction("Exit", self)
        button_exit.setStatusTip("Exit")
        button_exit.triggered.connect(QApplication.instance().quit)
        button_exit.setCheckable(True)
        buttons["exit"] = button_exit

        button_settings = QAction("Settings", self)
        button_settings.triggered.connect(self.edit_SLM_settings)
        buttons["settings"] = button_settings

        SLM_hologram_window = QPushButton("Show Hologram/Update")
        SLM_hologram_window.clicked.connect(self.on_pushButton_clicked)
        buttons["SLM_hologram_window"] = SLM_hologram_window

        AddOpticalElement = QPushButton("Add new optical element")
        AddOpticalElement.clicked.connect(self.AddOpticalElement)
        buttons["Add_optical_elem"] = AddOpticalElement

    def InitToolbar(self,toolbar,buttons):
        toolbar.setIconSize(QSize(16, 16))
        toolbar.addSeparator()
        toolbar.addAction(buttons["settings"])
        toolbar.addAction(buttons["exit"])

    def InitMenu(self,menu,buttons):
        file_menu = menu.addMenu("&File")
        file_menu.addAction(buttons["settings"])
        file_menu.addAction(buttons["exit"])

    def update_pattern(self):
        self.holograms_manager.updateSLMWindow()


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('macos')
    main = First()

    main.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
