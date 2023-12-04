#!/usr/bin/env python

"""WavefrontOptim.py: Generates a tab used to control the spot optimization process."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6.QtWidgets import QMessageBox, QLineEdit, QComboBox, QLabel, QSlider, QDoubleSpinBox,QGridLayout, QVBoxLayout, QGroupBox, QHBoxLayout, QWidget, QPushButton, QFileDialog
from PyQt6.QtCore import QThread, QMutex, QWaitCondition



import SLMcontroller.utils as utils
import numpy as np

from numba import jit
from numba.typed import List

from PIL import Image
from io import BytesIO

from flask import jsonify, send_file, abort


class SpotOptimTab_ext(QWidget):
    """Spot optimization tab used to control the spot optimization process.
    The algorithm is based on https://www.nature.com/articles/nphoton.2010.85.

    This code is meant to be controlled remotely from a separate acquisition system that will measure the intensity of the interference between probe and reference zones.
    
    The control is done via Flask. The following endpoints are available:
        - /optimiser/start : starts the algorithm (if already running, triggers a next step).
        - /optimiser/nextStep : triggers the next step of the algorithm (once scaned till the end of the phase pattern, this will return phase = null).
        - /optimiser/refzone : returns the current reference zone
        - /optimiser/refzone/<refzone> : sets the reference zone to <refzone>
        - /optimiser/probzone : returns the current probe zone
        - /optimiser/probzone/<probzone> : sets the probe zone to <probzone>
        - /optimiser/phase : returns the current phase
        - /optimiser/phase/<phase> : sets the phase to <phase>
        - /optimiser/phaseStep/<phaseStep> : sets the phase step to <phaseStep>
        - /optimiser/IDsList : returns the list of IDs of the active optical elements
        - /optimiser/phasePattern : returns the current phase pattern

    --- Setting up the algorithm ---
    First the user has to define the probe and references zones on the SLM. This can be done using gmsh.
    Mesh parameters and algorithms can be choosen in the tab. Once obtaining a satisfactory meshing this can be saved and loaded later.
    The mesh can be visualized using the gmsh GUI. This requires to start the GUI on another process as certain OS do not allow GUI to be started outside the main thread.
    The second process is started at the start of the program and kept dormant if not used.
    
    It allows for an user to choose the parameters for 2 gratings:
        - one to "dump" the 1st order power of the SLM to an unused zone
        - one to that will be assigned to the reference and probe zones in order to scan for their interference

    Once chosen the parameters the code will parse all the zones in the mesh and assign them a tag. 
    The user can then choose the reference and probe zones from the GUI.

    Starting the algorithm will allow to scan the selected reference zone phase offset in a range [0,2pi].

    Attributes:
        pattern_generator (:Pattern_generator:): Pattern generator object used to generate the grating.
        settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
        hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        algorithms (list): List of available meshing algorithms.
        algorithms_names (list): List of names of the available meshing algorithms.
        openmeshvisualizer (bool): Flag to indicate if the mesh visualizer is open or not.
        wasINIT (bool): Flag to indicate if the mesh has been initialized or not.
        th_active (bool): Flag to indicate if the algorithm is running or not.
        process_step (int): Current step of the algorithm.
        points (list): List of points used to define the SLM boundaries in the meshing software.
        lines (list): List of lines used to define the SLM boundaries in the meshing software.
        SLM_x_res (int): SLM X resolution.
        SLM_y_res (int): SLM Y resolution.
        minlmm (float): Minimum number of lines per mm that can be used to generate the grating.
        maxlmm (float): Maximum number of lines per mm that can be used to generate the grating.
        lmm_grating (float): Number of lines per mm used to generate the offset grating.
        angle_grating (float): Angle of the offset grating in radians.
        lmm_interf_grating (float): Number of lines per mm used to generate the grating used for interference.
        angle_interf_grating (float): Angle of the grating in radians used for interference.
        meshProcess (:MeshingProcess:): Meshing process object used to generate and visualize the mesh.
        mutex (:QMutex:): Mutex used to control the second process.
        waitCond (:QWaitCondition:): Wait condition used to control the second process.
        theOptimizer (:OptimizerAlgorithm:): Optimizer algorithm object used to control the second process.
    """
    def __del__(self):
        """Destructor for the SpotOptimTab_ext class. Stops the optimization thread and closes the mesh GUI process.
        """
        self.stop_algo()
        self.close_mesh()
        
    def __init__(self, pattern_generator, settings_manager, hologram_manager, meshing_process):
        """Constructor for the SpotOptimTab_ext class.

        Args:
            pattern_generator (:Pattern_generator:): Pattern generator object used to generate the grating.
            settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
            hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
            meshing_process (:MeshingProcess:): Meshing process object used to generate and visualize the mesh.
        """
        super().__init__()
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.algorithms = [1,2,3,5,6,7,8,9,11]
        self.algorithms_names = ["MeshAdapt", "Automatic", "Initial mesh only", "Delaunay", "Frontal-Delaunay", "BAMG", "Frontal-Delaunay quads", "Packing paralleograms","Quasi-structured Quad"]
        self.openmeshvisualizer = True
        self.wasINIT = False
        self.th_active = True
        self.process_step = 0

        self.points = [0,0,0,0] # 4 points array where to store the points tags
        self.lines = [0,0,0,0] # 4 points array where to store the lines tags
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()

        self.minlmm = 0
        self.maxlmm = 1e-3/(2*self.settings_manager.get_pixel_pitch()*1e-6)
        self.lmm_grating = 0.
        self.angle_grating = 0.

        self.lmm_interf_grating = 0.
        self.angle_interf_grating = 0.

        self.init_GUI()

        # Mesh data matrix

        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        self.ids_list = []
        self.phases = []
        self.active_zones = []
        self.step_phase = 0
        self.ref_zone = 0
        self.prob_zone = 0
        self.increment_phase_step = 25

        self.meshProcess = meshing_process

        self.mutex = QMutex() # Mutex needs to be given from the controlling thread
        self.waitCond = QWaitCondition()
        self.theOptimizer = OptimizerAlgorithm(self.hologram_manager,self.pattern_generator, self.settings_manager,self.mutex,self.waitCond)

    def setEventsHandlers(self,eventsDict, conditionsDict, queue):
        """Sets the events handlers for the class.
         As for the gmsh GUI process, Events and Conditions are generated in __main__ and passed to the class.
         Events are used to trigger actions in the meshProcess process (e.g. generate mesh, load mesh, save mesh, etc.)
         Conditions are used to synchronize the two processes (e.g. wait for the mesh to be generated before loading it)

        Args:
            eventsDict (dict): Dictionary containing the events.
            conditionsDict (dict): Dictionary containing the conditions.
            queue (queue): Queue used to communicate with the gmsh GUI process.
        """
        # Called after initializing the class, here we give the object control over the mutex to control the second process
        self.eventsDict = eventsDict
        self.conditionsDict = conditionsDict
        self.queue = queue


    def init_GUI(self):
        """Generates the GUI elements of the tab.
        """
        self.loadshowmeshlayout =  QGridLayout()
        self.showmesh_layout = QHBoxLayout()
        self.mesh_layout = QVBoxLayout()
        
        self.meshparams_layout = QHBoxLayout()
        self.algo_controls_layout = QHBoxLayout()
        self.algo_zones_layout = QHBoxLayout()
        self.reference_zone_layout = QHBoxLayout()
        self.probe_zone_layout = QHBoxLayout()

        self.interf_groupbox = QGroupBox("Interference zone")
        self.grating_groupbox = QGroupBox("Diffractive grating")

        self.showmeshbutton = QPushButton("Show Mesh")
        self.generatemeshbutton = QPushButton("Generate Mesh")
        self.closemeshbutton = QPushButton("Close Mesh")

        # Load and save mesh buttons
        self.loadmeshbutton = QPushButton("Load mesh file")
        self.savemeshbutton = QPushButton("Save mesh file")
        self.loadmeshbutton.clicked.connect(self.loadMeshFromFile)
        self.savemeshbutton.clicked.connect(self.saveMeshToFile)
        self.loadshowmeshlayout.addWidget(self.loadmeshbutton,1,0)
        self.loadshowmeshlayout.addWidget(self.savemeshbutton,1,1)

        self.parseMeshButton = QPushButton("Parse phases from mesh (slow)")
        self.parseMeshButton.clicked.connect(self.load_mesh_ids)

        self.runAlgorithmButton = QPushButton("Next step (Start)")
        self.runAlgorithmButton.clicked.connect(self.start_algo)

        self.stopAlgorithmButton = QPushButton("Stop optimization")
        self.stopAlgorithmButton.clicked.connect(self.stop_algo)

        self.list_algorithms = QComboBox()
        for elem in self.algorithms_names:
            self.list_algorithms.addItem(elem)

        self.showmeshbutton.clicked.connect(self.show_mesh)
        self.meshF = QLineEdit("2.5*((x-0.5)*(x-0.5)+(y-0.5)*(y-0.5))+ 10")

        self.generatemeshbutton.clicked.connect(lambda: self.generate_mesh(self.meshF.text()))
        self.closemeshbutton.clicked.connect(self.close_mesh)

        
        self.meshparams_layout.addWidget(self.meshF)
        self.meshparams_layout.addWidget(self.list_algorithms)
        self.mesh_layout.addLayout(self.meshparams_layout)

        self.loadshowmeshlayout.addWidget(self.showmeshbutton,0,0)
        self.loadshowmeshlayout.addWidget(self.closemeshbutton,0,1)

        self.mesh_layout.addWidget(self.generatemeshbutton)
        self.mesh_layout.addLayout(self.loadshowmeshlayout)

        # This for the parameters of the grating used for interference
        self.grating_layout = QVBoxLayout()
        self.interf_grating_layout = QVBoxLayout()

        #self.grating_angle_layout = QVBoxLayout()
        #self.interf_grating_angle_layout = QVBoxLayout()

        self.grating_angle_spin = QDoubleSpinBox(text="Grating angle")
        self.interf_grating_angle_spin = QDoubleSpinBox(text="Grating angle")

        self.grating_lmm_spin = QDoubleSpinBox(text="l/mm ")
        self.interf_grating_lmm_spin = QDoubleSpinBox(text="l/mm ")

        self.grating_lmm_slider = utils.DoubleSlider()
        self.interf_grating_lmm_slider = utils.DoubleSlider()

        self.grating_angle_slider = utils.DoubleSlider()
        self.interf_grating_angle_slider = utils.DoubleSlider()

        self.make_lmm_slider(self.grating_layout, self.grating_lmm_spin, self.grating_lmm_slider)
        self.grating_lmm_slider.valueChanged.connect(self.update_grating_lmm_spin)
        self.grating_lmm_spin.valueChanged.connect(self.update_grating_lmm_slide)

        self.make_lmm_slider(self.interf_grating_layout, self.interf_grating_lmm_spin, self.interf_grating_lmm_slider)
        self.interf_grating_lmm_slider.valueChanged.connect(self.update_interf_grating_lmm_spin)
        self.interf_grating_lmm_spin.valueChanged.connect(self.update_interf_grating_lmm_slide)

        self.make_angle_slider(self.grating_layout, self.grating_angle_spin, self.grating_angle_slider)
        self.grating_angle_slider.valueChanged.connect(self.update_grating_angle_spin)
        self.grating_angle_spin.valueChanged.connect(self.update_grating_angle_slide)

        self.make_angle_slider(self.interf_grating_layout, self.interf_grating_angle_spin, self.interf_grating_angle_slider)
        self.interf_grating_angle_slider.valueChanged.connect(self.update_interf_grating_angle_spin)
        self.interf_grating_angle_spin.valueChanged.connect(self.update_interf_grating_angle_slide)


        self.grating_groupbox.setLayout(self.grating_layout)
        self.interf_groupbox.setLayout(self.interf_grating_layout)
        self.mesh_layout.addWidget(self.grating_groupbox)
        self.mesh_layout.addWidget(self.interf_groupbox)

        self.mesh_layout.addWidget(self.parseMeshButton)

        self.zones_ref_combobox = QComboBox()
        self.zones_prob_combobox = QComboBox()

        self.zones_ref_combobox.currentIndexChanged.connect(self.selectRefZone)
        self.zones_prob_combobox.currentIndexChanged.connect(self.selectProbZone)
        
        label_reference_zone = QLabel("Reference zone:", self)
        label_probe_zone = QLabel("Probe zone:", self)
        self.reference_zone_layout.addWidget(label_reference_zone)
        self.reference_zone_layout.addWidget(self.zones_ref_combobox)
        self.probe_zone_layout.addWidget(label_probe_zone)
        self.probe_zone_layout.addWidget(self.zones_prob_combobox)

        self.algo_zones_layout.addLayout(self.reference_zone_layout)
        self.algo_zones_layout.addLayout(self.probe_zone_layout)
        self.mesh_layout.addLayout(self.algo_zones_layout)

        self.algo_controls_layout.addWidget(self.runAlgorithmButton)
        self.algo_controls_layout.addWidget(self.stopAlgorithmButton)

        
        self.mesh_layout.addLayout(self.algo_controls_layout)

        self.setLayout(self.mesh_layout)

    def selectRefZone(self):
        """Updates the reference zone when the user selects a new one from the GUI.
        """
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_ref_combobox.count() <=0:
            self.ref_zone = 0.
        else:
            self.ref_zone = int(self.zones_ref_combobox.currentText())

    def selectProbZone(self):
        """Updates the probe zone when the user selects a new one from the GUI.
        """
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_prob_combobox.count() <=0:
            self.prob_zone = 0.
        else:
            self.prob_zone = int(self.zones_prob_combobox.currentText())

    def loadMeshFromFile(self):
        """Loads a mesh from a file in gmsh .msh format.
        """
        # Opens a prompt for the user to select a mesh file
        name = QFileDialog.getOpenFileName(self,"Open File","${HOME}","GMSH (*.msh);;",)
        self.queue.put(name[0])
        self.putVariablesInQueue(self.queue, self.eventsDict['loadfile'], self.eventsDict['generalEvent'])
        # self.eventsDict['loadfile'].set()
        # self.eventsDict['generalEvent'].set()
        with self.conditionsDict['loadfile']:
            self.conditionsDict['loadfile'].wait()
        outcome = self.queue.get()
        if not outcome:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("There was an error loading the mesh file, check the file and try again")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
    
    def saveMeshToFile(self):
        """Saves the current mesh to a file in gmsh .msh format.
        """
        name = QFileDialog.getSaveFileName(self, "Save File", "","GMSH (*.msh);;")
        self.queue.put(name[0])
        self.eventsDict['savefile'].set()
        self.eventsDict['generalEvent'].set()
        with self.conditionsDict['savefile']:
            self.conditionsDict['savefile'].wait()
        outcome = self.queue.get()
        if not outcome:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("There was an error saving the mesh file, check the file and try again")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return



    def populate_zone_selector(self):
        """Populates the reference and probe zone selection comboboxes once the mesh has been generated
        """
        self.zones_ref_combobox.clear()
        self.zones_prob_combobox.clear()
        for el in self.ids_list:
            self.zones_ref_combobox.addItem(str(el))
            self.zones_prob_combobox.addItem(str(el))

    def is_active(self):
        """Returns the status of the algorithm.
        """
        return False
    
    # This part for setting the grating parameters needed for generating constructing/distructive interference

    def make_lmm_slider(self, lmm_layout, spin_lmm, lmm_slider):
        """Generates the slider to control the offset grating parameters and adds it to the GUI.

        Args:
            lmm_layout (:QVBoxLayout:): Layout to which the slider will be added.
            spin_lmm (:QDoubleSpinBox:): Spinbox to control the offset grating parameters.
            lmm_slider (:utils.DoubleSlider:): Slider to control the offset grating parameters.
        """
        #self.lmm_layout = QVBoxLayout()
        lmm = 100
        #self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        spin_lmm.setSuffix(' l/mm')
        #spin_lmm.valueChanged.connect(lambda : self.update_lmm_slide(lmm, spin_lmm))
            
        spin_lmm.setKeyboardTracking(False)
        spin_lmm.setSingleStep(0.1)
        spin_lmm.setMaximum(self.maxlmm)
        spin_lmm.setMinimum(self.minlmm)

        lmm_slider.setGeometry(50,50, 200, 50)
        lmm_slider.setMinimum(0)
        lmm_slider.setMaximum(self.maxlmm)
        lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        lmm_slider.setTickInterval(3000)

        lmm_layout.addWidget(spin_lmm)
        lmm_layout.addWidget(lmm_slider)

    def make_angle_slider(self, angle_layout, spin_angle, angle_slider):
        """Generates the slider to control the offset grating parameters and adds it to the GUI.

        Args:
            angle_layout (:QVBoxLayout:): Layout to which the slider will be added.
            spin_angle (:QDoubleSpinBox:): Spinbox to control the offset grating parameters.
            angle_slider (:utils.DoubleSlider:): Slider to control the offset grating parameters.
        """
        spin_angle.setSuffix(' π')
        spin_angle.setKeyboardTracking(False)
        spin_angle.setSingleStep(0.1)


        angle_slider.setGeometry(50,50, 200, 50)
        angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        angle_slider.setMaximum(2.)
        angle_slider.setTickInterval(100)
        angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        angle_layout.addWidget(spin_angle)
        angle_layout.addWidget(angle_slider)
    
    def setRefZone(self,refzone):
        """Sets the reference zone.

        Args:
            refzone (int/str): Reference zone to set. Flask will input this as a string.
        """
        refzone = int(refzone)
        if (refzone in self.ids_list) and not(refzone == self.ref_zone):
            # Change ref zone in the GUI
            self.zones_ref_combobox.setCurrentText(str(refzone))
            # Set the new reference zone
            self.ref_zone = int(refzone)
            # Change it also in the algorithm
            self.theOptimizer.refZoneID = int(refzone)
            # Return the value of the new reference zone
            # Used for Flask as a return code to double check everything went fine
        return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)

    def getProbRefZone(self):
        """Returns the zones IDs and optimizer process state (running/not running) zone remotely

        Returns:
             json(Reference zone, Probe zone, Phase, Optimizer status): Returns information on the probe zone, reference zone and current phase in json format for remote clients.
        """
        # If the algorithm is running take the ref_zone from it (more updated)
        if self.theOptimizer.isThreadRunning():
            return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase, Optimizer = self.theOptimizer.isThreadRunning())
        # Otherwise use the one shown in the GUI
        else: 
            return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase, Optimizer = self.theOptimizer.isThreadRunning())

    def setProbZone(self,probzone):
        """Sets the probe zone remotely
         Args:
            probzone (int/str): Probe zone to set. Flask will input this as a string.

        Returns:
            json(Probe zone, Reference zone, Phase): Returns information on the probe zone, reference zone and current phase in json format for remote clients.
        """
        probzone = int(probzone)
        if (probzone in self.ids_list) and not(probzone == self.ref_zone):
            self.zones_prob_combobox.setCurrentText(str(probzone))
            # Set the new reference zone
            self.prob_zone = int(probzone)
            # Change it also in the algorithm
            self.theOptimizer.probZoneID = int(probzone)
            # Return the value of the new reference zone
            # Used for Flask as a return code to double check everything went fine
        return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)

    def setPhase(self,phase):
        """Sets the phase remotely

        Args:
            phase (int/str): Phase to set. Flask will input this as a string.

        Returns:
            json(Probe zone, Reference zone, Phase): Returns information on the probe zone, reference zone and current phase in json format for remote clients.
        """
        phase = float(phase)
        if phase >= 0 and phase <= 255:
            self.theOptimizer.phase = phase
        return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)

    def setPhaseStep(self,phaseStep):
        """Sets the phase step remotely. The phase steps is the amount of phase used to increase the phase of the reference zone at each step of the algorithm.

        Args:
            phaseStep (int/str): Phase step to set. Flask will input this as a string.

        Returns:
            json(Probe zone, Reference zone, Phase, PhaseStep): Returns information on the probe zone, reference zone, current phase and phase steps in json format for remote clients.
        """
        phaseStep = float(phaseStep)
        if phaseStep > 0 and phaseStep < 255:
            self.theOptimizer.phaseStep = phaseStep
        return jsonify(ProbZone = self.theOptimizer.probZoneID,RefZone = self.theOptimizer.refZoneID,Phase = self.theOptimizer.phase ,PhaseStep = self.theOptimizer.phaseStep)
    
    def checkAlgoReady(self):
        if self.lmm_grating == 0 or self.lmm_interf_grating == 0:
            return[500, 'Invalid gratings settings']
        if self.ref_zone == self.prob_zone or self.prob_zone > np.max(self.ids_list) or self.prob_zone < np.min(self.ids_list) or self.ref_zone > np.max(self.ids_list) or self.ref_zone < np.min(self.ids_list):
            return[500, 'Invalid probe/reference zone']
        if not self.theOptimizer.isThreadReady():
            return[500, 'Mesh not ready']
        else:
            return 0


    def start_algo_rem(self):
        """Starts the optimization algorithm remotely. If the algorithm is alredy running, triggers a next step.
        Unfortunately not all OS allow to use the start_algo function (as that will require to open new GUI windows)
        For this reason this is more or less a "Duplicate window" of the start_algo function.
        """
        if self.theOptimizer.isThreadRunning():
            self.waitCond.wakeAll()
            return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)
        errors = self.checkAlgoReady()
        if errors != 0:
            abort(errors[0], errors[1])

        self.theOptimizer.probZoneID = self.prob_zone
        self.theOptimizer.refZoneID = self.ref_zone
        # If the phase step was not set (e.g. first time running the algorithm) set it to 1/10 of the phase range
        if self.theOptimizer.phaseStep == None:
            self.theOptimizer.phaseStep = self.settings_manager.get_phase_correction()/10
        # If the phase was not set (e.g. first time running the algorithm) set it to 0
        if self.theOptimizer.phase == None:
            self.theOptimizer.phase = 0

        self.theOptimizer.activate(self.lmm_grating, self.angle_grating, self.lmm_interf_grating,self.angle_interf_grating)
        self.theOptimizer.start()
        return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)
    
    def getPhasePattern(self):
        if self.theOptimizer.getPhasePattern() is None:
            return abort(404, "No pattern defined")
        return jsonify(PhasePattern = self.theOptimizer.getPhasePattern().tolist())
    
    def getMesh(self):
        if self.theOptimizer.mesh is None:
            return abort(404, "No mesh defined")
        return jsonify(Mesh = self.theOptimizer.mesh.tolist())

    def getPhasePatternIMG(self):
        """Returns the phase pattern

        Returns:
            HTTP Response IMG (Phase pattern): Returns information on the current phase pattern in PNG image format for remote clients.
        """

        if self.theOptimizer.getPhasePattern() is None:
            return abort(404, "No pattern defined")
        img = Image.fromarray(self.theOptimizer.getPhasePattern().astype('uint8'))
        # create file-object in memory
        file_object = BytesIO()
        # write PNG in file-object
        img.save(file_object, 'PNG')
        # move to beginning of file so `send_file()` it will read from start 
        file_object.seek(0)
        return send_file(file_object,mimetype='image/PNG',as_attachment=False,download_name='pattern.png')
    
    def getIdsList(self):
        """Returns the IDs list

        Returns:
            json(IDs list): Returns information on the current IDs list in json format for remote clients.
        """
        print(type(self.theOptimizer.ids_list))
        return jsonify(IDsList = np.array(self.theOptimizer.ids_list).tolist())

    def triggerNextStep(self):
        """Triggers the next step of the algorithm

        Returns:
            json(Phase) : Returns information on the current phase of the probe zone in json format for remote clients.
        """
        self.waitCond.wakeAll()
        return jsonify(RefZone = self.theOptimizer.refZoneID,ProbZone = self.theOptimizer.probZoneID,Phase = self.theOptimizer.phase)

    def update_grating_lmm_slide(self):
        """Updates the offset grating lmm in the slider when the user changes the spin value.
        """
        self.lmm_grating = self.sender().value()
        self.grating_lmm_slider.setValue(self.lmm_grating)

    def update_grating_lmm_spin(self):
        """Updates the offset grating lmm in the spinbox when the user changes the slider value.
        """
        self.lmm_grating = self.sender().value()
        self.grating_lmm_spin.setValue(self.lmm_grating)

    def update_interf_grating_lmm_slide(self):
        """Updates the interference grating lmm in the slider when the user changes the spin value.
        """
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_slider.setValue(self.lmm_interf_grating) 

    def update_interf_grating_lmm_spin(self):
        """Updates the interference grating lmm in the spinbox when the user changes the slider value.
        """
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_spin.setValue(self.lmm_interf_grating)

    def update_grating_angle_slide(self):
        """Updates the offset grating angle in the slider when the user changes the spin value.
        """
        self.angle_grating = self.sender().value()
        self.grating_angle_slider.setValue(self.angle_grating)

    def update_grating_angle_spin(self):
        """Updates the offset grating angle in the spinbox when the user changes the slider value.
        """
        self.angle_grating = self.sender().value()
        self.grating_angle_spin.setValue(self.angle_grating)

    def update_interf_grating_angle_slide(self):
        """Updates the interference grating angle in the slider when the user changes the spin value.
        """
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_slider.setValue(self.angle_interf_grating) 

    def update_interf_grating_angle_spin(self):
        """Updates the interference grating angle in the spinbox when the user changes the slider value.
        """
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_spin.setValue(self.angle_interf_grating)

    def load_zones(self):
        """Loads the reference and probe zones from the GUI.
        """
        # Activate probe and reference zones
        for id, zone in enumerate(self.ids_list):
            if zone == self.prob_zone or zone == self.ref_zone:
                self.active_zones[id] = 1

    def stop_algo(self):
        """Stops the optimization algorithm.
        """
        print("Stopping optimization")
        self.theOptimizer.stop()
        self.waitCond.wakeAll()
        print("Done")
    
    def putVariablesInQueue(self, queue, event, notify):
        """Puts the variables needed to generate the mesh in the queue and notifies the second process.

        Args:
            queue (queue): Queue used to communicate with the gmsh GUI process.
            event (event): Event used to notify the second process what to do (e.g. generate mesh, render mesh etc.).
            notify (event): Event used to notify the second process that data is ready.
        """
        event.set()
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.algorithm = self.list_algorithms.currentIndex()
        self.function = self.meshF.text()
        queue.put(self.SLM_x_res)
        queue.put(self.SLM_y_res)
        queue.put(self.algorithm)
        queue.put(self.function)
        # Notifies the second process that data is ready
        notify.set()

    def show_mesh(self):
        """Notifies the gmsh process to render the mesh in the GUI.
        """
        self.eventsDict['showGUI'].set()
        self.eventsDict['generalEvent'].set()
        
    def close_mesh(self):
        """Notifies the gmsh process to close meshing visualization the GUI.
        """
        self.eventsDict['closeGUI'].set()

    def generate_mesh(self,F):
        """Notifies the meshing process that a new mesh should be generated and which parameter (function) to use.

        Args:
            F (string): Function used to generate the mesh.
        """
        self.putVariablesInQueue(self.queue, self.eventsDict['genMesh'], self.eventsDict['generalEvent'])
        # Waiting for second process to generate the Mesh
        #print("aked to generate")

    def load_mesh_ids(self):
        """Notifies the second process to start parsing the mesh
        """
        print("Now parsing, please wait...")
        self.eventsDict['parseMesh'].set()
        self.eventsDict['generalEvent'].set()
        with self.conditionsDict['parsingCond']:
            self.conditionsDict['parsingCond'].wait()

        self.mesh = self.queue.get()
        self.ids_list = self.queue.get()

        self.populate_zone_selector()
        # Set mesh and ID list also in optimizer algorith
        self.theOptimizer.mesh = self.mesh
        self.theOptimizer.ids_list = self.ids_list


    def start_algo(self):
        """Starts the optimization algorithm. If the algorithm is alredy running, triggers a next step.
        """
        if self.theOptimizer.isThreadRunning():
            self.waitCond.wakeAll()
            return 0
        
        errors = self.checkAlgoReady()
        if errors != 0:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText(errors[1])
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return 500
        self.theOptimizer.probZoneID = self.prob_zone
        self.theOptimizer.refZoneID = self.ref_zone
        # TODO : For now hardcoded a step of ~25 (maxphase (usually ~255)/10), to be user-selectable
        # Default to maxphase/10
        self.theOptimizer.phaseStep = self.settings_manager.get_phase_correction()/10

        # TODO : Let user choose a starting phase. This can be done only remotely ATM
        self.theOptimizer.phase = 0
        self.theOptimizer.activate(self.lmm_grating, self.angle_grating, self.lmm_interf_grating,self.angle_interf_grating)
        self.theOptimizer.start()
        return 




class OptimizerAlgorithm(QThread):
    """Class used to control the optimization algorithm.

    Attributes:
        pattern_generator (:Pattern_generator:): Pattern generator object used to generate the grating.
        settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
        hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        pattern (np.array): Phase pattern used to generate the grating.
        pattern_generator (:Pattern_generator:): Pattern generator object used to generate the grating.
        settings_manager (:SettingsManager:): Settings manager object used to get the wavelength, SLM resolution and SLM pixel pitch.
        _mesh (np.array): Mesh used to generate the grating.
        SLM_x_res (int): SLM X resolution.
        SLM_y_res (int): SLM Y resolution.
        _ids_list (list): List of IDs used to define the zones in the mesh.
        _phaseStep (int): Phase step used to increment the phase of the reference zone at each step of the algorithm.
        _probZoneID (int): Probe zone ID.
        _refZoneID (int): Reference zone ID.
        _prevzones (list): List of the previous probe and reference zones.
        hologram_manager (:HologramsManager:): Hologram manager object used to update the SLM window.
        _active (bool): Flag to indicate if the algorithm is running or not.
        waitCond (:QWaitCondition:): Wait condition used to control the second process.
        trigger (:QMutex:): Mutex used to control the second process.
        phase (int): Current phase of the reference zone.
        grating_lastvals (np.array): Last values of the grating parameters.
        interf_grating_lastvals (np.array): Last values of the grating parameters used for interference.
    """
    def __init__(self,hologram_manager, pattern_generator, settings_manager,mutex,waitCond):
            QThread.__init__(self)
            self.pattern = None
            self.pattern_generator = pattern_generator
            self.settings_manager = settings_manager
            self._mesh = None
            self.SLM_x_res = None
            self.SLM_y_res = None
            self._ids_list = None
            self._phaseStep = None
            self._probZoneID = None
            self._refZoneID = None
            self._prevzones = None

            self.hologram_manager = hologram_manager
            self._active = True
            self.isPhaseReady = False
            self.trigger = mutex
            self._phase = 0

            self._active = False
            self.waitCond = waitCond

            # Save last grating parameters to avoid re-generating the grating
            self.grating_lastvals = np.array([])
            self.interf_grating_lastvals = np.array([])

    def activate(self,grating_lmm, grating_angle,interf_grating_lmm,interf_grating_angle):
        """Activates the algorithm.

        Args:
            grating_lmm (float): l/mm of the offset grating.
            grating_angle (float): Angle of the offset grating.
            interf_grating_lmm (float): l/mm of the interference grating.
            interf_grating_angle (float): Angle of the interference grating.
        """
        self.setGrating(grating_lmm, grating_angle)
        self.setInterfGrating(interf_grating_lmm,interf_grating_angle)

    def run(self):
        """Runs the optimization algorithm. The algorithm will wait for a waitCond signal before proceeding to the next step.
        """
        if self._phase is None:
           self.phase = 0
        self.initPattern()
        self._active = True
        while self._active:
            self.next_step()
            if self._phase > self.settings_manager.get_phase_correction() :
                self._active = False
                self._phase = None
                break
            self.trigger.lock()
            self.waitCond.wait(self.trigger)
            self.trigger.unlock()
        self.stop()

    def stop(self):
        """Stops the optimization algorithm.

        Todo:
            Save the data (meshing zones, phases etc.) somewhere here (not sure if useful). Re-init important local variables
        """
        self._active=False
        self._phase = None

    def next_step(self):
        """Moves to the next step of the optimization algorithm
        Checks that gratings and zones parameters weren't changed (perhaps remotely)
        If they were it needs to regenerate the grating patterns
        """
        self.remeshing()
        # If the user changed the zones call the slower function to reload the gratings patterns on the previous zones
        if not np.array_equal(self._prevzones,[self._refZoneID, self._probZoneID]):
            self.pattern = load_pattern(self._mesh, self.grating_pattern,self.interf_grating_pattern,self._phase,self.SLM_x_res,self.SLM_y_res,self._refZoneID,self._probZoneID)
        self.pattern = next_step_fast(self.SLM_x_res, self.SLM_y_res, self._mesh, self.interf_grating_pattern, self._probZoneID, self.pattern, self._phase)
        print("Phase offset at this step: ", self._phase)
        
        # Increment phase for next step
        self._phase = self._phase + self._phaseStep
        self.hologram_manager.renderAlgorithmPattern(self.pattern, True)
        self._prevzones = [self._refZoneID, self._probZoneID]
        


    def setInterfGrating(self,interf_grating_lmm,interf_grating_angle):
        """Sets the parameters of the interference grating.

        Args:
            interf_grating_lmm (float): l/mm of the interference grating.
            interf_grating_angle (float): Angle of the interference grating.
        """
        self.interf_grating_lmm = interf_grating_lmm
        self.interf_grating_angle = interf_grating_angle

    def setGrating(self, grating_lmm, grating_angle):
        """Sets the parameters of the offset grating.

        Args:
            grating_lmm (float): l/mm of the offset grating.
            grating_angle (float): Angle of the offset grating.
        """
        self.grating_lmm = grating_lmm
        self.grating_angle = grating_angle
    
    @property
    def mesh(self):
        return self._mesh
    
    @mesh.setter
    def mesh(self, mesh):
        """Sets the mesh used to separate the SLM in zones.
        NOTE: This is a bit stupid as we do not clone the mesh here with copy/np.copy.
        This is intended as we want to use the same mesh as the GUI tab object.
        However, what's stupid is to have a private object that is a pointer to an object owned by an object of another class.
        Anyways, this is how it is for now.
        """
        self._mesh = mesh

    # This to be used only when forcing the algorithm to start at a previous phase
    @property
    def phase(self):
        """Returns the phase of the reference zone.

        Returns:
            float: Phase of the reference zone.
        """
        return self._phase

    @phase.setter
    def phase(self, phase):
        """Sets the phase of the reference zone.
        """
        self._phase = phase

    @property
    def phaseStep(self):
        """Returns the phase step used to increment the phase of the reference zone at each step of the algorithm.

        Returns:
            float: Phase step.
        """
        return self._phaseStep
    
    @phaseStep.setter
    def phaseStep(self, phaseStep):
        """Sets the phase step used to increment the phase of the reference zone at each step of the algorithm.

        Args:
            phaseStep (float): Phase step to set.
        """
        self._phaseStep = phaseStep

    @property 
    def probZoneID(self):
        """Returns the probe zone ID.

        Returns:
            int: Probe zone ID.
        """
        return self._probZoneID

    @probZoneID.setter
    def probZoneID(self,probZoneID):
        """Sets the probe zone.

        Args:
            probZoneID (int): Probe zone ID.
        """
        self._probZoneID = probZoneID
    
    @property
    def refZoneID(self):
        """Returns the reference zone ID.

        Returns:
            int: Reference zone ID.
        """
        return self._refZoneID
    
    @refZoneID.setter
    def refZoneID(self,refZoneID):
        """Sets the reference zone.

        Args:
            refZoneID (int): Reference zone ID.
        """
        self._refZoneID = refZoneID
    
    @property
    def ids_list(self):
        """Returns the IDs list (list of available zones)

        Returns:
            list: List of available zones.
        """
        return self._ids_list
    
    @ids_list.setter
    def ids_list(self, ids_list):
        """Sets the IDs list (list of available zones). 
        Here is intendend to don't use np.copy() as we want the optimizer to use the same ID list as the GUI.

        Args:
            ids_list (list): List of available zones.
        """
        self._ids_list = ids_list

    
    def getPhasePattern(self):
        """Returns the phase pattern.

        Returns:
            np.array: Phase pattern.
        """
        return self.pattern

    def isThreadReady(self):
        """Returns True if the algorithm is ready to start.

        Returns:
            bool: True if the algorithm is ready to start.
        """
        return self._mesh is not None or self.settings_manager is not None or self._ids_list is not None or self._probZoneID is not None or self._refZoneID is not None
    
    def isThreadRunning(self):
        """Checks if the algorithm is running.

        Returns:
            bool: True if the algorithm is running.
        """
        return self._active
    
    def remeshing(self):
        """Checks if the grating parameters were changed and if so, regenerates the grating patterns.
        """
        if not np.array_equal(self.grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])) or not np.array_equal(self.interf_grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])):
            print("remeshing")
            self.grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.interf_grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
            self.interf_grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])


    def initPattern(self):
        """Initializes the phase patterns for offset and interference gratings.
        """
        print("Initializating ... ")
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.pattern = np.zeros((self.SLM_y_res,self.SLM_x_res))
        self.remeshing()
        self.pattern = load_pattern(self._mesh, self.grating_pattern,self.interf_grating_pattern,self._phase,self.SLM_x_res,self.SLM_y_res,self._refZoneID,self._probZoneID)
        print("... done")


@jit(nopython=True)
def next_step_fast(SIZEX, SIZEY, mesh, interf_grating, probZoneID, pattern, phase):
    """Generates the next step of the optimization algorithm. Uses jit from numba to speed up the computation.
    This updates only the part of the pattern corresponding to the probe zone.
    In case the probe/reference zones have been changed load_pattern should be used instead.

    Args:
        SIZEX (int): SLM X resolution.
        SIZEY (int): SLM Y resolution.
        mesh (np.array): Mesh used to separate the SLM in zones.
        interf_grating (np.array): Interference grating pattern.
        probZoneID (int): Probe zone ID.
        pattern (np.array): Phase pattern.
        phase (float): Current phase of the reference zone.

    Returns:
        np.array: New phase pattern.
    """
    for i in range(0,SIZEY):
        for j in range(0,SIZEX):
            tmp = mesh[i,j]
            if tmp == probZoneID:
                pattern[i,j] = (interf_grating[i,j] + phase)%256
    return pattern



@jit(nopython=True) # Set "nopython" mode for best performance, equivalent to @njit
def load_pattern(mesh, grating, interf_grating, phase, SIZEX, SIZEY, refZoneID, probZoneID):
    """Loads the phase pattern. Uses jit from numba to speed up the computation.

    Args:
        mesh (np.array): Mesh used to separate the SLM in zones.
        grating (np.array): Offset grating pattern.
        interf_grating (np.array): Interference grating pattern.
        phase (float): Current phase of the reference zone.
        SIZEX (int): SLM X resolution.
        SIZEY (int): SLM Y resolution.
        refZoneID (int): Reference zone ID.
        probZoneID (int): Probe zone ID.

    Returns:
        np.array: Phase pattern.
    """
    pattern = np.zeros((SIZEY,SIZEX))
    for i in range(0,SIZEY):
            for j in range(0,SIZEX):
                tmp = mesh[i,j]
                if tmp == refZoneID:
                    pattern[i,j] = interf_grating[i,j]
                elif tmp == probZoneID:
                    pattern[i,j] = (interf_grating[i,j] + phase)%256
                else:
                    pattern[i,j] = grating[i,j]
    return pattern