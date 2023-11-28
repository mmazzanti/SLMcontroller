#!/usr/bin/env python

"""MainGUI.py: Main GUI window of the SLM controller. 
This file contains the main window of the GUI and the SLM window."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, QSize, QWaitCondition
from PyQt6.QtWidgets import QMessageBox, QLabel, QGridLayout, QWidget, QPushButton, QToolBar, QApplication, QHBoxLayout, QSpinBox, QVBoxLayout, QFileDialog, QLabel, QErrorMessage, QTabWidget
from PyQt6.QtGui import QPixmap, QImage, QAction, QScreen

import numpy as np
import SLMcontroller.settings as settings
import SLMcontroller.camera.camera as camera
import SLMcontroller.Phase_pattern as Phase_pattern
import SLMcontroller.OpticalElement as opticalElement
import SLMcontroller.Lens as Lens
import SLMcontroller.Grating as Grating
import SLMcontroller.FourierWavefrontOptim as FourierWavefrontOptim
import SLMcontroller.WavefrontOptim as WavefrontOptim
import SLMcontroller.FlatnessCorrection as FlatnessCorrection
import SLMcontroller.Meshing_process as Meshing_process
import SLMcontroller.Remote_control as Remote_control
import SLMcontroller.utils as utils

from multiprocessing import RLock, Event, Queue, Process, Condition, freeze_support
import threading

from PIL import Image
from io import BytesIO


class SLMWindow(QWidget):
    """SLM window. The window is used to display the phase pattern generated by the optical elements.

    Attributes:
        lbl (QLabel): QLabel for pattern image rendering.
    """
    def __init__(self,resX,resY,SLMmonitor):
        """Initializes the SLM pattern window

        Args:
            resX (int): Window width
            resY (int): Window height
            window (int): Monitor number to display the window on

        Returns:
            QWidget: QWidget of the SLM window
        """
        super().__init__(parent=None)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.Change_window(SLMmonitor)

        """ Set necessary flags for the window to be on top of the GUI """
        self.setWindowFlags(Qt.WindowType.BypassWindowManagerHint | Qt.WindowType.X11BypassWindowManagerHint | QtCore.Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.ResizeWindow(resX,resY)

        self.lbl = QLabel(self)
        """ Move QLabel at the top left corner of the SLM screen """
        self.lbl.move(0, 0)
        """ Set QLabel background color to black 
        (this is useful the SLM resolution doesn't match the usable number of pixels on the SLM) """
        self.setStyleSheet("background-color: black;")

    # Resize pattern window size
    def Change_window(self,SLMmonitor):
        """Moves the SLM window to the selected monitor

        Args:
            SLMmonitor (int): Monitor identifier
        """
        monitors = QScreen.virtualSiblings(self.screen())
        # If the user selected a monitor that doesn't exist, use the primary monitor
        if len(monitors) <= SLMmonitor:
            SLMmonitor = 0
        monitor = monitors[SLMmonitor].availableGeometry()
        self.move(monitor.left(), monitor.top())

    def ResizeWindow(self,resX,resY):
        """Resize the SLM window to the selected resolution

        Args:
            resX (int): Window width
            resY (int): Window height
        """
        self.setFixedSize(QSize(resX,resY))

    def UpdatePattern(self,pixmap):
        """Updates the SLM window with the new phase pattern

        Args:
            pixmap (QPixmap): QPixmap of the new phase pattern
        """
        self.lbl.setPixmap(pixmap)
        self.lbl.resize(pixmap.width(), pixmap.height())
        self.update()

class HologramsManager():
    """Class in charge of handling the rendering of the optical elements patterns on the SLM window.

    Attributes:
        SLMWindow (QWidget): QWidget used to render the complete hologram on the SLM.
        settings_manager (:SettingsManager:): Settings manager class used to retrieve the SLM settings.
        pattern_generator (:Pattern_generator:): Pattern generator class used to generate the phase patterns.
        tabwidget (QTabWidget): QTabWidget parent object. Used to locate the parent object in the screen and open warnings/errors on top of that.

    """
    def __init__(self, SLMwindow, settings_manager, pattern_generator,tabwidget):
        """Initializes the HologramsManager class

        Args:
            optical_elements (dict): Dictionary of active optical elements.
            SLMwindow (QWidget): QWidget used to render the complete hologram on the SLM.
            settings_manager (:SettingsManager:): Settings manager class used to retrieve the SLM settings.
            pattern_generator (:Pattern_generator:): Pattern generator class used to generate the phase patterns.
            tabwidget (QTabWidget): QTabWidget parent object. Used to locate the parent object in the screen and open warnings/errors on top of that.
            pattern (np.array): Phase pattern currently being rendered on the SLM.
        """
        self.optical_elements = {}
        self.SLMWindow = SLMwindow
        self.settings_manager = settings_manager
        self.pattern_generator = pattern_generator
        self.tabwidget = tabwidget
        self.pattern = None

    def addElementToList(self, id, elem):
        """Adds an optical element to the list of active optical elements

        Args:
            id (int): Optical element identifier
            elem (OpticalElement, QWidget): Optical element object (usually a QWidget)
        """
        self.optical_elements[id] = elem

    def getElementsList(self):
        """Returns the list of active optical elements

        Returns:
            dict: Dictionary of active optical elements
        """
        return self.optical_elements

    def isListEmpty(self):
        """Checks if the list of active optical elements is empty

        Returns:
            Bool: True if the list is empty, False otherwise
        """
        return len(self.optical_elements) == 0

    def removeAll(self):
        """Removes all the active optical elements from the list
        """
        todelete = []
        for el in self.optical_elements:
            if el is not None:
                todelete.append(el)
        for el in todelete:
            self.optical_elements[el].__del__()

    def removeElementFromList(self, id):
        """Removes an optical element from the list of active optical elements

        Args:
            id (int): Optical element identifier
        """
        del self.optical_elements[id]


    def closeSLMWindow(self):
        """Closes the SLM window

        Todo:
            This function is still to be implemented (did not see it's usage so far)
        """
        pass #Hide SLM window

    def __del__(self):
        """Destructor of the HologramsManager class. Empties the list of active optical elements and closes the SLM window.
        """
        self.removeAll()
        self.SLMWindow = None
        self.optical_elements = None

    # This function is used to render a pattern generated from an algorithm, 
    # bypassing the active optical elements
    def renderAlgorithmPattern(self, pattern, others):
        """Renders a phase pattern generated from an algorithm, bypassing the active optical elements

        Args:
            pattern (np.array): Phase pattern to be rendered on the SLM
            others (bool): If True, the other active optical elements will be rendered on the SLM as well
        """
        print("rendering")
        if self.pattern is None:
            self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.pattern = np.copy(pattern)
        if others == True:
            self.getPatterns()
        self.renderPattern()

    def getPhasePatternIMG(self):
        """Returns the phase pattern currently being rendered on the SLM in PNG image format for remote clients.
            Calls the NetworkManager.send_image which sends the contents of a file to the client.
        """
        if self.pattern is None:
            return 404
        img = Image.fromarray(self.pattern.astype('uint8'))
        file_object = BytesIO()
        img.save(file_object, 'PNG')
        file_object.seek(0)
        return self.app.send_image(file_object,'pattern.png')

    #This part corrects for the non-linearities of the SLM
    #For each wavelenght the maximum phase value is given by the company
    #e.g. at 760nm 255 ---> 226
    #So we need to renormalize the hologram such that value%226
    def RenormalizePattern(self):
        """Corrects for the non-linearities of the SLM. 
        For each wavelenght the maximum uint8 phase value is usually given by the company but can also be measured
        e.g. at 760nm 255(2pi) ---> 226(new 2pi value)
        So we need to renormalize the hologram such that value%226
        """
        self.pattern = ((self.pattern%256)*(self.settings_manager.get_phase_correction())/255).astype(np.uint8)


    def getPatterns(self):
        """This function gets all the patterns from the active elements and combines them
        """
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
                            return	4444
                    self.pattern += pattern_from_el

    def renderPattern(self):
        """This function does the actual render of the phase pattern. Updates the QPixmap used on the SLM window
        """
        self.RenormalizePattern()
        q_img = QImage(self.pattern, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res(), self.settings_manager.get_X_res(), QImage.Format.Format_Grayscale8)
#        label = QLabel(self)
        pixmap = QPixmap(q_img)
        self.SLMWindow.ResizeWindow(self.settings_manager.get_X_win_size(),self.settings_manager.get_Y_win_size())
        self.SLMWindow.UpdatePattern(pixmap)

    def updateSLMWindow(self):
        """This function updates the SLM window when a new pattern is generated
        """
        self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.getPatterns()
        self.renderPattern()
        


class First(QtWidgets.QMainWindow):
    """Main window of the GUI. This class is used to initialize the GUI and the SLM window.

    Attributes:
        settings_manager (:SettingsManager:): Settings manager class used to retrieve the SLM settings.
        pattern_generator (:Pattern_generator:): Pattern generator class used to generate the phase patterns.
        pattern (np.array): Phase pattern currently being rendered on the SLM.
        tabwidget (QTabWidget): QTabWidget parent object. Used to locate the parent object in the screen and open warnings/errors on top of that.
        cameraWindow (QWidget): QWidget used to display the camera feed.
        holograms_manager (:HologramsManager:): HologramsManager class used to render the optical elements patterns on the SLM window.
        possible_optical_elements (list): List of possible optical elements that can be added to the GUI.
        tabs_constructors (list): List of functions used to generate the optical elements tabs.
        SLMWindow (QWidget): QWidget used to render the complete hologram on the SLM.
        mesh_process (Process): Process used to handle the meshing of the optical elements.
    """
    def __init__(self, mesh_process, flaskApp, queue, eventsDict, conditionsDict, parent=None):
        """Initializes the main window of the GUI

        Args:
            mesh_process (Process): Process used to handle the meshing of the optical elements.
            parent (_type_, optional): Parent class. Defaults to None.
        """
        super(First, self).__init__(parent)
        self.setMinimumSize(QSize(400, 700))
        #centerPoint = QGuiApplication.primaryScreen().availableGeometry()
        self.setWindowTitle("SLM hologram control")
        self.settings_manager = settings.SettingsManager()
        self.pattern_generator = Phase_pattern.Patter_generator()
        self.pattern = None
        #self.tabwidget = 
        self.tabwidget = QTabWidget()
        self.tabwidget.setTabBar(utils.OpticalTabBar(self))
        self.tabwidget.setUsesScrollButtons(True)
        self.tabwidget.setTabsClosable(True)
        self.cameraWindow = None
        self.tabwidget.tabCloseRequested.connect(self.closeTab)
        self.mesh_process = mesh_process

        self.SLMWindow = SLMWindow(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res(),self.settings_manager.get_SLM_window())
        self.holograms_manager = HologramsManager(self.SLMWindow, self.settings_manager, self.pattern_generator,self.tabwidget)

        self.possible_optical_elements = ["Lens", "Grating", "Flatness correction", "Zernike", "LUT", "Spot optimization", "Spot optimization (ext)"]
        self.tabs_constructors = [self.lens_tab, self.grating_tab, self.flatness_correction_tab, self.zernike_tab, self.LUT_tab, self.Spot_optim, self.Spot_optim_ext]

        wid = QtWidgets.QWidget(self)
        self.setCentralWidget(wid)

        buttons = {}
        self.InitButtons(buttons)

        menu = self.menuBar()
        toolbar = QToolBar("Quick actions")
        grid = QGridLayout()

        # Flask app for remote control
        self.flaskApp = flaskApp
        # Queue used to communicate with the meshing process
        self.queue = queue
        # Events and conditions used to synchronize the meshing process with the GUI
        self.eventsDict, self.conditionsDict = eventsDict, conditionsDict

        self.InitMenu(menu,buttons)
        self.InitToolbar(toolbar,buttons)
        self.addToolBar(toolbar)
        self.InitLayout(grid,buttons)

        flask_thread = threading.Thread(target=lambda: self.flaskApp.run(host=self.settings_manager.get_IPclient(), port=self.settings_manager.get_Portclient(), debug=True, use_reloader=False))
        flask_thread.daemon = True
        flask_thread.start()
        self.flaskApp.add_endpoint('/phasePattern', 'phasePattern', self.holograms_manager.getPhasePatternIMG, methods=['GET'])


        wid.setLayout(grid)
        self.show()

    def closeTab(self,index):
        """Closes the selected tab

        Args:
            index (int): Index of the tab to be closed
        """
        widget = self.tabwidget.widget(index)
        if widget is not None:
            widget.deleteLater()
        self.tabwidget.removeTab(index)
        self.holograms_manager.removeElementFromList(id(widget))

    def lens_tab(self):
        """Creates a new Lens tab and adds it to the tabwidget
        """
        tab = Lens.LensTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Lens")
        self.holograms_manager.addElementToList(id(tab), tab)

    def grating_tab(self):
        """Creates a new Grating tab and adds it to the tabwidget
        """
        tab = Grating.GratingTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Grating")
        self.holograms_manager.addElementToList(id(tab), tab)

    def flatness_correction_tab(self):
        """Creates a new Flatness Correction tab and adds it to the tabwidget
        """
        tab = FlatnessCorrection.FlatnessCorrectionTab(self.pattern_generator, self.settings_manager, self.holograms_manager)
        self.tabwidget.addTab(tab,"Flatness Correction")
        self.holograms_manager.addElementToList(id(tab), tab)

    def zernike_tab(self):
        """Creates a new Zernike tab and adds it to the tabwidget.
            Todo: 
                Implement Zernike tab
        """
        pass
    def LUT_tab(self):
        """Creates a new LUT tab and adds it to the tabwidget.
            Todo:
                Implement LUT tab
        """
        pass
    def Spot_optim(self):
        """Creates a new SpotOptimTab tab and adds it to the tabwidget.
        The spot optimization algorithm used in the SpotOptimTab is based on https://www.frontiersin.org/articles/10.3389/fnano.2022.998656/full
        This algorithm relies on a camera to measure the spot intensity where aberrations should be reduced.
        """
        if self.cameraWindow is None:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Initialize camera first!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        tab = FourierWavefrontOptim.SpotOptimTab(self.pattern_generator, self.settings_manager, self.holograms_manager,self.cameraWindow)
        self.tabwidget.addTab(tab,"Optimizer (camera)")
        self.holograms_manager.addElementToList(id(tab), tab)

    def Spot_optim_ext(self):
        """Creates a new SpotOptimTab_ext tab and adds it to the tabwidget.
        The spot optimization algorithm used in the SpotOptimTab_ext is based on https://www.nature.com/articles/nphoton.2010.85
        The algorithm relies on an external feedback for the spot intensity measurement.
        The algorithm steps and parameters can be controlled remotely on the network using the following endpoints:
        - /optimiser/start : starts the algorithm (if already running, triggers a next step)
        - /optimiser/nextStep : triggers the next step of the algorithm (once scaned till the end of the phase pattern, this will return phase = null)
        - /optimiser/refzone : returns the current reference zone
        - /optimiser/refzone/<refzone> : sets the reference zone to <refzone>
        - /optimiser/probzone : returns the current probe zone
        - /optimiser/probzone/<probzone> : sets the probe zone to <probzone>
        - /optimiser/phase : returns the current phase
        - /optimiser/phase/<phase> : sets the phase to <phase>
        - /optimiser/phaseStep/<phaseStep> : sets the phase step to <phaseStep>
        - /optimiser/IDsList : returns the list of IDs of the active optical elements
        - /optimiser/phasePattern : returns the current phase pattern
        """
        tab = WavefrontOptim.SpotOptimTab_ext(self.pattern_generator, self.settings_manager, self.holograms_manager, self.mesh_process)
        tab.setEventsHandlers(self.eventsDict, self.conditionsDict, self.queue)
        self.tabwidget.addTab(tab,"Optimizer (ext)")
        self.holograms_manager.addElementToList(id(tab), tab)
        self.add_endpoint_connections(tab)

    def edit_SLM_settings(self):
        """Opens the settings dialog
            Todo: 
                Resizing of the SLM pattern to match the SLM resolution
        """
        dlg = settings.SettingsDialog(self.settings_manager, self)
        dlg.exec()
        # Update where the SLM window is (TODO: IS IT GOOD TO DO THIS HERE ??)
        self.SLMWindow.Change_window(self.settings_manager.get_SLM_window())
    
    def start_camera(self):
        """Starts the camera feed
        """
        self.cameraWindow = camera.CameraWindow()
        self.cameraWindow.show()

    def closeEvent(self,event):
        """Closes the SLM window and the GUI
        At the closing event remove all tabs in memory calling their destructor
        """
        self.holograms_manager.removeAll()
        print("Closing Hologram window")
        QApplication.instance().quit()
    
    def add_endpoint_connections(self,tab):
        """Adds the endpoints connections to the Flask app

        Args:
            tab (WavefrontOptim.SpotOptimTab_ext): SpotOptimTab_ext object (for now the only tab that uses the endpoints)
        """
        self.flaskApp.add_endpoint('/optimiser/start', 'optimiser/start', tab.start_algo_rem, methods=['GET'])

        self.flaskApp.add_endpoint('/optimiser/nextStep', 'optimiser/nextStep', tab.triggerNextStep, methods=['GET'])

        self.flaskApp.add_endpoint('/optimiser/refzone', 'optimiser/refzone', tab.getProbRefZone, methods=['GET'])
        self.flaskApp.add_endpoint('/optimiser/refzone/<refzone>', 'optimiser/refzone/<int:refzone>', tab.setRefZone, methods=['GET'])

        self.flaskApp.add_endpoint('/optimiser/probzone', 'optimiser/probzone', tab.getProbRefZone, methods=['GET'])
        self.flaskApp.add_endpoint('/optimiser/probzone/<probzone>', 'optimiser/probzone/<int:probzone>', tab.setProbZone, methods=['GET'])

        self.flaskApp.add_endpoint('/optimiser/phase', 'optimiser/phase', tab.getProbRefZone, methods=['GET'])
        self.flaskApp.add_endpoint('/optimiser/phase/<phase>', 'optimiser/phase/<float:phase>', tab.setPhase, methods=['GET'])
        self.flaskApp.add_endpoint('/optimiser/phaseStep/<float:phaseStep>', 'optimiser/phaseStep/<phaseStep>', tab.setPhaseStep, methods=['GET'])

        self.flaskApp.add_endpoint('/optimiser/IDsList', 'optimiser/IDsList', tab.getIdsList, methods=['GET'])
        self.flaskApp.add_endpoint('/optimiser/phasePattern', 'optimiser/phasePattern', tab.getPhasePatternIMG, methods=['GET'])
        self.flaskApp.add_endpoint('/optimiser/phasePatternData', 'optimiser/phasePatternData', tab.getPhasePattern, methods=['GET'])

    def on_pushButton_clicked(self):
        """Updates the SLM window with the new phase pattern. Connected to the "Show Hologram/Update" button.
        """
        self.SLMWindow.show()
        # Initialize empty pattern. WARNING! Resolution of SLM must be already defined!!
        if self.pattern is None:
            self.pattern = self.pattern_generator.empty_pattern(self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
        self.update_pattern()

    def InitLayout(self,grid,buttons):
        """Initializes the GUI layout

        Args:
            grid (QGridLayout): QGridLayout of the GUI
            buttons (Dict): Dictionary of buttons used in the GUI
        """
        grid.addWidget(buttons["SLM_hologram_window"], 1, 0)
        grid.addWidget(buttons["Add_optical_elem"], 2, 0)
        grid.addWidget(self.tabwidget,0,0)

    def AddOpticalElement(self):
        """Adds a new optical element to the GUI
        """
        if self.holograms_manager.isListEmpty() and self.tabwidget== None:
            # If the user still didn't choose any optical element generate the tabs layout ?
            pass
        inputter = opticalElement.opticalElement(self.possible_optical_elements, self)
        if inputter.exec():
            self.tabs_constructors[inputter.get_selected()]()

    def InitButtons(self,buttons):
        """Initializes the GUI buttons

        Args:
            buttons (dict): Dictionary of buttons used in the GUI
        """
        button_exit = QAction("Exit", self)
        button_exit.setStatusTip("Exit")
        button_exit.triggered.connect(QApplication.instance().quit)
        button_exit.setCheckable(True)
        buttons["Exit"] = button_exit


        button_camera = QAction("Start Camera", self)
        button_camera.triggered.connect(self.start_camera)
        buttons["Start Camera"] = button_camera

        button_settings = QAction("Settings", self)
        button_settings.triggered.connect(self.edit_SLM_settings)
        buttons["Settings"] = button_settings

        SLM_hologram_window = QPushButton("Show Hologram/Update")
        SLM_hologram_window.clicked.connect(self.on_pushButton_clicked)
        buttons["SLM_hologram_window"] = SLM_hologram_window

        AddOpticalElement = QPushButton("Add new optical element")
        AddOpticalElement.clicked.connect(self.AddOpticalElement)
        buttons["Add_optical_elem"] = AddOpticalElement

    def InitToolbar(self,toolbar,buttons):
        """Initializes the GUI toolbar

        Args:
            toolbar (QToolBar): QToolBar of the GUI
            buttons (dict): Dictionary of buttons used in the GUI
        """
        toolbar.setIconSize(QSize(16, 16))
        toolbar.addSeparator()
        toolbar.addAction(buttons["Settings"])
        toolbar.addAction(buttons["Start Camera"])
        toolbar.addAction(buttons["Exit"])

    def InitMenu(self,menu,buttons):
        """Initializes the GUI menu

        Args:
            menu (QGridLayout): QGridLayout of the GUI
            buttons (dict): Dictionary of buttons used in the GUI
        """
        file_menu = menu.addMenu("&File")
        file_menu.addAction(buttons["Settings"])
        file_menu.addAction(buttons["Exit"])

    def update_pattern(self):
        """Updates the SLM window with the new phase pattern
        """
        self.holograms_manager.updateSLMWindow()


# def closeSecondProcess(eventsDict):
#     """Closes the GMSH GUI process
#     """
#     eventsDict['terminate'].set()
#     eventsDict['generalEvent'].set()
