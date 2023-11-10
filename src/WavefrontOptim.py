from PyQt6.QtWidgets import QMessageBox, QLineEdit, QComboBox, QLabel, QSlider, QDoubleSpinBox, QVBoxLayout, QGroupBox, QHBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt, QThread, QMutex, QWaitCondition, QThreadPool
from PyQt6 import QtCore

from multiprocessing import Process, Condition, Event , Queue
import threading

import src.utils as utils
import gmsh
import numpy as np

from numba import jit
from numba.typed import List



class SpotOptimTab_ext(QWidget):
    def __del__(self):
        self.stop_algo()
        self.close_mesh()
        
    def __init__(self, pattern_generator, settings_manager, hologram_manager, meshing_process):
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

        # --- Concurrency part ---

        # Parse mesh has to be done in a synchronized way. The main process cannot proceed without the mesh being generated
        #self.parseMesh = Condition()

        # Events for signaling the meshing GUI process
        # self.genMesh = Event()
        # self.generalEvent = Event()
        # self.parseMesh = Event()

        # self.showGUI = Event()
        # self.queue = Queue()

        #self.process = MeshingHandler(self.generalEvent, self.showGUI, self.genMesh ,self.parseMesh,self.queue, self.SLM_x_res, self.SLM_y_res, 0 , self.meshF)
        self.meshProcess = meshing_process

        self.mutex = QMutex() # Mutex needs to be given from the controlling thread
        self.waitCond = QWaitCondition()
        self.theOptimizer = OptimizerAlgorithm(self.hologram_manager,self.pattern_generator, self.settings_manager,self.mutex,self.waitCond)

    def setEventsHandlers(self,genMesh, parseMesh, generalEvent, showGUI, closeGUI, parsingCond, queue):
        # Called after initializing the class, here we give the object control over the mutex to control the second process
        self.genMesh = genMesh
        self.generalEvent = generalEvent
        self.parseMesh = parseMesh
        self.showGUI = showGUI
        self.closeGUI = closeGUI
        self.queue = queue
        self.parsingCond = parsingCond
        # Wake up the dormant process
        #self.putVariablesInQueue(queue, self.generalEvent, self.generalEvent)


    def init_GUI(self):
        self.mesh_layout = QVBoxLayout()
        self.showmesh_layout = QHBoxLayout()
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

        self.mesh_layout.addWidget(self.generatemeshbutton)

        self.mesh_layout.addWidget(self.showmeshbutton)
        self.mesh_layout.addWidget(self.closemeshbutton)

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
        
        #self.mesh_layout.addLayout(self.grating_layout)


        #self.mesh_layout.addLayout(self.grating_angle_layout)

        self.mesh_layout.addLayout(self.showmesh_layout)
        self.mesh_layout.addWidget(self.parseMeshButton)



        self.zones_ref_combobox = QComboBox()
        self.zones_prob_combobox = QComboBox()

        self.zones_ref_combobox.currentIndexChanged.connect(self.setRefZone)
        self.zones_prob_combobox.currentIndexChanged.connect(self.setProbZone)
        
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

    def setRefZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_ref_combobox.count() <=0:
            self.ref_zone = 0.
        else:
            self.ref_zone = int(self.zones_ref_combobox.currentText())

    def setProbZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_prob_combobox.count() <=0:
            self.prob_zone = 0.
        else:
            self.prob_zone = int(self.zones_prob_combobox.currentText())


    def populate_zone_selector(self):
        self.zones_ref_combobox.clear()
        self.zones_prob_combobox.clear()
        for el in self.ids_list:
            self.zones_ref_combobox.addItem(str(el))
            self.zones_prob_combobox.addItem(str(el))

    def is_active(self):
        return False
    
    # This part for setting the grating parameters needed for generating constructing/distructive interference

    def make_lmm_slider(self, lmm_layout, spin_lmm, lmm_slider):
        #self.lmm_layout = QVBoxLayout()
        lmm = 100
        #self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        spin_lmm.setSuffix(' l/mm')
        #spin_lmm.valueChanged.connect(lambda : self.update_lmm_slide(lmm, spin_lmm))
            
        spin_lmm.setKeyboardTracking(False)
        spin_lmm.setSingleStep(0.1)
        spin_lmm.setMaximum(self.maxlmm)
        spin_lmm.setMinimum(self.minlmm)

        #lmm_slider = DoubleSlider()
        lmm_slider.setGeometry(50,50, 200, 50)
        lmm_slider.setMinimum(0)
        lmm_slider.setMaximum(self.maxlmm)
        lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        lmm_slider.setTickInterval(3000)
        #lmm_slider.valueChanged.connect(lambda _, lmm: self.update_lmm_slide(lmm, lmm_slider))
        #lmm_slider.valueChanged.connect(lambda : self.update_lmm_slide(lmm, lmm_slider))

        lmm_layout.addWidget(spin_lmm)
        lmm_layout.addWidget(lmm_slider)

    def make_angle_slider(self, angle_layout, spin_angle, angle_slider):
        #angle_layout = QVBoxLayout()

        #spin_angle = QDoubleSpinBox(text="Grating angle")
        spin_angle.setSuffix(' π')
        #spin_angle.valueChanged.connect(lambda: self.update_angle_slide(angle, spin_angle))
        spin_angle.setKeyboardTracking(False)
        spin_angle.setSingleStep(0.1)

        #angle_slider = DoubleSlider()
        angle_slider.setGeometry(50,50, 200, 50)
        angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        angle_slider.setMaximum(2.)
        angle_slider.setTickInterval(100)
        angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        #angle_slider.valueChanged.connect(lambda: self.update_angle_spin(angle, angle_slider))

        angle_layout.addWidget(spin_angle)
        angle_layout.addWidget(angle_slider)

    def triggerNextStep(self):
        self.waitCond.wakeAll()

    def update_grating_lmm_slide(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_slider.setValue(self.lmm_grating)
    def update_grating_lmm_spin(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_spin.setValue(self.lmm_grating)

    def update_interf_grating_lmm_slide(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_slider.setValue(self.lmm_interf_grating) 
    def update_interf_grating_lmm_spin(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_spin.setValue(self.lmm_interf_grating)

    def update_grating_angle_slide(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_slider.setValue(self.angle_grating)
    def update_grating_angle_spin(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_spin.setValue(self.angle_grating)
    def update_interf_grating_angle_slide(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_slider.setValue(self.angle_interf_grating) 
    def update_interf_grating_angle_spin(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_spin.setValue(self.angle_interf_grating)

    def load_zones(self):
        # Activate probe and reference zones
        for id, zone in enumerate(self.ids_list):
            if zone == self.prob_zone or zone == self.ref_zone:
                self.active_zones[id] = 1

    def stop_algo(self):
        print("Stopping optimization")
        self.theOptimizer.stop()
        self.waitCond.wakeAll()
        print("Done")
    
    # def change_mesh_algo(self,algorithm):
    #     gmsh.option.setNumber("Mesh.Algorithm", algorithm)

    def putVariablesInQueue(self, queue, event, notify):
        # Tells the second process the type of event
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
        self.showGUI.set()
        
    def close_mesh(self):
        self.closeGUI.set()
        # To be implemented, second thread of second process has to stop main

    def generate_mesh(self,F):
        self.putVariablesInQueue(self.queue, self.genMesh, self.generalEvent)
        # Waiting for second process to generate the Mesh
        #print("aked to generate")

    def load_mesh_ids(self):
        # Tell the second process to start parsing the mesh
        #self.mutex.lock()
        print("Now parsing, please wait...")
        #self.parsingCond.acquire()
        self.parseMesh.set()
        self.generalEvent.set()
        with self.parsingCond:
            self.parsingCond.wait()

        self.mesh = self.queue.get()
        self.ids_list = self.queue.get()

        print(self.ids_list)
        self.populate_zone_selector()
        # Set mesh and ID list also in optimizer algorith
        self.theOptimizer.setMesh(self.mesh)
        self.theOptimizer.setIdsList(self.ids_list)
        #print(self.ids_list)


    def start_algo(self):
        if self.theOptimizer.isThreadRunning():
            self.waitCond.wakeAll()
            return
        
        # Check that the grating parameter were initialized  
        if self.lmm_grating == 0 or self.lmm_interf_grating == 0:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid grating settings!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        #Generate grating mesh, this will be used for splitting the 0th order from the interference zone

        if self.ref_zone == self.prob_zone or self.prob_zone > np.max(self.ids_list) or self.prob_zone < np.min(self.ids_list) or self.ref_zone > np.max(self.ids_list) or self.ref_zone < np.min(self.ids_list):
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid probe or reference zones!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return


        self.theOptimizer.setProbefZone(self.prob_zone)
        self.theOptimizer.setRefZone(self.ref_zone)
        # TODO : For now hardcoded a step of 20, to be user-selectable
        self.theOptimizer.setPhaseStep(self.settings_manager.get_phase_correction()/10)

        # TODO: Reactivate this part once the thread will be automatized

        # if self.theOptimizer.isThreadRunning():
        #     dlg = QMessageBox(self)
        #     dlg.setIcon(QMessageBox.Icon.Warning)
        #     dlg.setWindowTitle("WARNING!")
        #     dlg.setText("An optimization is already in process!")
        #     button = dlg.exec()
        #     if button == QMessageBox.StandardButton.Ok:
        #         return

        if not self.theOptimizer.isThreadReady():
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Mesh is not ready!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        # TODO : Let user choose a starting phase
        self.theOptimizer.setPhase(0)
        self.theOptimizer.activate(self.lmm_grating, self.angle_grating, self.lmm_interf_grating,self.angle_interf_grating)
        self.theOptimizer.start()




class OptimizerAlgorithm(QThread):
    def __init__(self,hologram_manager, pattern_generator, settings_manager,mutex,waitCond):
            QThread.__init__(self)
            self.pattern = None
            self.frequencies = None
            self.pattern_generator = pattern_generator
            self.settings_manager = settings_manager
            self.times = None
            self.mesh = None
            self.freqs = None
            self.SLM_x_res = None
            self.SLM_y_res = None
            self.ids_list = None
            self.phaseStep = None
            self.probZoneID = None
            self.refZoneID = None

            self.hologram_manager = hologram_manager
            self._active = True
            self.isPhaseReady = False
            self.trigger = mutex

            self._active = False
            self.waitCond = waitCond

            # Save last grating parameters to avoid re-generating the grating
            self.grating_lastvals = np.array([])
            self.interf_grating_lastvals = np.array([])

    def activate(self,grating_lmm, grating_angle,interf_grating_lmm,interf_grating_angle):
        self.setGrating(grating_lmm, grating_angle)
        self.setInterfGrating(interf_grating_lmm,interf_grating_angle)

    def run(self):
        if self.phase is None:
           self.setPhase(0)
        self.initPattern()
        self._active = True
        while self._active:
            self.next_step()
            if self.phase > self.settings_manager.get_phase_correction() :
                self._active = False
                break
            self.trigger.lock()
            self.waitCond.wait(self.trigger)
            self.trigger.unlock()
        self.stop()

    def stop(self):
        self._active=False
        # TODO : Here we should save the data
        # And re-init important local variables
        self.phase = None

    def next_step(self):
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         tmp = self.mesh[i,j]
        #         if tmp == self.refZoneID:
        #             self.pattern[i,j] = self.interf_grating_pattern[i,j]
        #         elif tmp == self.probZoneID:
        #             self.pattern[i,j] = (self.interf_grating_pattern[i,j] + self.phase)%256
        #         else:
        #             self.pattern[i,j] = self.grating_pattern[i,j]
        self.pattern = next_step_fast(self.SLM_x_res, self.SLM_y_res, self.mesh, self.interf_grating_pattern, self.probZoneID, self.pattern, self.phase)
        print("Phase offset at this step: ", self.phase)
        self.phase = self.phase + self.phaseStep
        self.hologram_manager.renderAlgorithmPattern(self.pattern, True)
        


    def setInterfGrating(self,interf_grating_lmm,interf_grating_angle):
        self.interf_grating_lmm = interf_grating_lmm
        self.interf_grating_angle = interf_grating_angle

    def setGrating(self, grating_lmm, grating_angle):
        self.grating_lmm = grating_lmm
        self.grating_angle = grating_angle
    
    def setMesh(self, mesh):
        self.mesh = mesh

    # This to be used only when forcing the algorithm to start at a previous phase
    def setPhase(self, phase):
        self.phase = phase

    def setPhaseStep(self, phaseStep):
        self.phaseStep = phaseStep

    def setProbefZone(self,probZoneID):
        self.probZoneID = probZoneID

    def setRefZone(self,refZoneID):
        self.refZoneID = refZoneID

    def setIdsList(self, ids_list):
        self.ids_list = ids_list

    def isThreadReady(self):
        return self.mesh is not None or self.settings_manager is not None or self.ids_list is not None or self.probZoneID is not None or self.refZoneID is not None
    def isThreadRunning(self):
        return self._active
    

    def initPattern(self):
        print("Initializating ... ")
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.pattern = np.zeros((self.SLM_y_res,self.SLM_x_res))
        if not np.array_equal(self.grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])) and not np.array_equal(self.interf_grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])):
            print("remeshing")
            self.grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.interf_grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
            self.interf_grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
        self.pattern = load_pattern(self.mesh, self.grating_pattern,self.interf_grating_pattern,self.phase,self.SLM_x_res,self.SLM_y_res,self.refZoneID,self.probZoneID)
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         tmp = self.ids_list.index(self.mesh[i,j])
        #         if tmp == self.refZoneID:
        #             self.pattern[i,j] = self.interf_grating_pattern[i,j]
        #         elif tmp == self.probZoneID:
        #             self.pattern[i,j] = (self.interf_grating_pattern[i,j] + self.phase)%256
        #         else:
        #             self.pattern[i,j] = self.grating_pattern[i,j]
        print("... done")


@jit(nopython=True)
def next_step_fast(SIZEX, SIZEY, mesh, interf_grating, probZoneID, pattern, phase):
    for i in range(0,SIZEY):
        for j in range(0,SIZEX):
            tmp = mesh[i,j]
            # if tmp == self.refZoneID:
            #     self.pattern[i,j] = self.interf_grating_pattern[i,j]
            if tmp == probZoneID:
                pattern[i,j] = (interf_grating[i,j] + phase)%256
    return pattern



@jit(nopython=True) # Set "nopython" mode for best performance, equivalent to @njit
def load_pattern(mesh, grating, interf_grating, phase, SIZEX, SIZEY, refZoneID, probZoneID):
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



















'''
class SpotOptimTab_ext(QWidget):
    def __del__(self):
        self.close_mesh()
    
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
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

        self.scaling_x = 0
        self.scaling_y = 0

        self.minlmm = 0
        self.maxlmm = 1e-3/(2*self.settings_manager.get_pixel_pitch()*1e-6)
        self.lmm_grating = 0.
        self.angle_grating = 0.

        self.lmm_interf_grating = 0.
        self.angle_interf_grating = 0.

        self.init_GMESH()
        self.init_GUI()
        self.visualizer = None #utils.MeshVisualizer(self)
        self.threadpool = QThreadPool()
        # Mesh data matrix

        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        self.ids_list = []
        self.phases = []
        self.active_zones = []
        self.step_phase = 0
        self.ref_zone = 0
        self.prob_zone = 0
        self.increment_phase_step = 25

        # Concurrency part
        self.mutex = QMutex() # Mutex needs to be given from the controlling thread
        self.waitCond = QWaitCondition()
        self.theOptimizer = OptimizerAlgorithm(self.hologram_manager,self.pattern_generator, self.settings_manager,self.mutex,self.waitCond)


    def init_GMESH(self):

        if not self.wasINIT:
            gmsh.initialize()
        self.wasINIT = True
        gmsh.model.add("SLM Meshing")
        lc = 0.5*max(self.SLM_x_res,self.SLM_y_res)
        self.scaling_x = self.SLM_x_res
        self.scaling_y = self.SLM_y_res
        self.points[0]=gmsh.model.geo.addPoint(0, 0, 0, meshSize = lc)# lc, 1)
        self.points[1]=gmsh.model.geo.addPoint(self.scaling_x, 0, 0, meshSize = lc)# lc, 2)
        self.points[2]=gmsh.model.geo.addPoint(self.scaling_x, self.scaling_y, 0, meshSize = lc)# lc, 3)
        self.points[3]=gmsh.model.geo.addPoint(0, self.scaling_y, 0, meshSize = lc)# lc, 4)

        self.lines[0] = gmsh.model.geo.addLine(1, 2, 1)
        self.lines[1] = gmsh.model.geo.addLine(3, 2, 2)
        self.lines[2] = gmsh.model.geo.addLine(3, 4, 3)
        self.lines[3] = gmsh.model.geo.addLine(4, 1, 4)

        self.contour = gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

        self.pl = gmsh.model.geo.addPlaneSurface([1], 1)

        gmsh.model.geo.synchronize()
        self.field = gmsh.model.mesh.field
        # self.threshold = gmsh.model.mesh.field.add("Threshold")
        # gmsh.model.mesh.field.setNumber(self.threshold , "InField", 1)
        # gmsh.model.mesh.field.setNumber(self.threshold , "SizeMin", lc / 150)
        # gmsh.model.mesh.field.setNumber(self.threshold , "SizeMax", lc)
        # gmsh.model.mesh.field.setNumber(self.threshold , "DistMin", 1)
        # gmsh.model.mesh.field.setNumber(self.threshold , "DistMax", lc)

        self.mathModel = gmsh.model.mesh.field.add("MathEval")

    def start_algo(self):

        if self.theOptimizer.isThreadRunning():
            self.waitCond.wakeAll()
            return
        
        # Check that the grating parameter were initialized  
        if self.lmm_grating == 0 or self.lmm_interf_grating == 0:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid grating settings!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        #Generate grating mesh, this will be used for splitting the 0th order from the interference zone

        if self.ref_zone == self.prob_zone or self.prob_zone > np.max(self.ids_list) or self.prob_zone < np.min(self.ids_list) or self.ref_zone > np.max(self.ids_list) or self.ref_zone < np.min(self.ids_list):
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid probe or reference zones!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
            
        #self.update_grating_pattern()

        # self.theOptimizer.setGrating(self.grating_lmm,self.grating_angle)
        # self.theOptimizer.setInterfGrating(self.interf_grating_lmm,self.interf_grating_angle)

        self.theOptimizer.setProbefZone(self.prob_zone)
        self.theOptimizer.setRefZone(self.ref_zone)
        # TODO : For now hardcoded a step of 20, to be user-selectable
        self.theOptimizer.setPhaseStep(self.settings_manager.get_phase_correction()/10)

        # TODO: Reactivate this part once the thread will be automatized

        # if self.theOptimizer.isThreadRunning():
        #     dlg = QMessageBox(self)
        #     dlg.setIcon(QMessageBox.Icon.Warning)
        #     dlg.setWindowTitle("WARNING!")
        #     dlg.setText("An optimization is already in process!")
        #     button = dlg.exec()
        #     if button == QMessageBox.StandardButton.Ok:
        #         return

        if not self.theOptimizer.isThreadReady():
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Mesh is not ready!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        # TODO : Let user choose a starting phase
        self.theOptimizer.setPhase(0)
        self.theOptimizer.activate(self.lmm_grating, self.angle_grating, self.lmm_interf_grating,self.angle_interf_grating)
        self.theOptimizer.start()



    def load_zones(self):
        # Activate probe and reference zones
        for id, zone in enumerate(self.ids_list):
            if zone == self.prob_zone or zone == self.ref_zone:
                self.active_zones[id] = 1

    def stop_algo(self):
        self.theOptimizer.stop()
        self.waitCond.wakeAll()
    
    def change_mesh_algo(self,algorithm):
        gmsh.option.setNumber("Mesh.Algorithm", algorithm)

    def generate_mesh(self,F):
       
        #gmsh.model.geo.synchronize()

    def redo_GMESH(self):
        

    def load_mesh_ids(self):
        



    def init_GUI(self):
        self.mesh_layout = QVBoxLayout()
        self.showmesh_layout = QHBoxLayout()
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

        self.mesh_layout.addWidget(self.generatemeshbutton)

        self.mesh_layout.addWidget(self.showmeshbutton)
        self.mesh_layout.addWidget(self.closemeshbutton)

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
        
        #self.mesh_layout.addLayout(self.grating_layout)


        #self.mesh_layout.addLayout(self.grating_angle_layout)

        self.mesh_layout.addLayout(self.showmesh_layout)
        self.mesh_layout.addWidget(self.parseMeshButton)



        self.zones_ref_combobox = QComboBox()
        self.zones_prob_combobox = QComboBox()

        self.zones_ref_combobox.currentIndexChanged.connect(self.setRefZone)
        self.zones_prob_combobox.currentIndexChanged.connect(self.setProbZone)
        
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

    # Wanted to highlight the selected zones but seems is not possible/IDK how to do it
    def highlight_zone(self):
        self.visualizer.highlight_zone(self.zones_prob_combobox.currentIndex,self.zones_ref_combobox.currentIndex)

    def setRefZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_ref_combobox.count() <=0:
            self.ref_zone = 0.
        else:
            self.ref_zone = int(self.zones_ref_combobox.currentText())

    def setProbZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_prob_combobox.count() <=0:
            self.prob_zone = 0.
        else:
            self.prob_zone = int(self.zones_prob_combobox.currentText())


    def populate_zone_selector(self):
        self.zones_ref_combobox.clear()
        self.zones_prob_combobox.clear()
        for el in self.ids_list:
            self.zones_ref_combobox.addItem(str(el))
            self.zones_prob_comboox.addItem(str(el))

    def is_active(self):
        return False




# This part for setting the grating parameters needed for generating constructing/distructive interference

    def make_lmm_slider(self, lmm_layout, spin_lmm, lmm_slider):
        #self.lmm_layout = QVBoxLayout()
        lmm = 100
        #self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        spin_lmm.setSuffix(' l/mm')
        #spin_lmm.valueChanged.connect(lambda : self.update_lmm_slide(lmm, spin_lmm))
            
        spin_lmm.setKeyboardTracking(False)
        spin_lmm.setSingleStep(0.1)
        spin_lmm.setMaximum(self.maxlmm)
        spin_lmm.setMinimum(self.minlmm)

        #lmm_slider = DoubleSlider()
        lmm_slider.setGeometry(50,50, 200, 50)
        lmm_slider.setMinimum(0)
        lmm_slider.setMaximum(self.maxlmm)
        lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        lmm_slider.setTickInterval(10)
        #lmm_slider.valueChanged.connect(lambda _, lmm: self.update_lmm_slide(lmm, lmm_slider))
        #lmm_slider.valueChanged.connect(lambda : self.update_lmm_slide(lmm, lmm_slider))

        lmm_layout.addWidget(spin_lmm)
        lmm_layout.addWidget(lmm_slider)

    def make_angle_slider(self, angle_layout, spin_angle, angle_slider):
        #angle_layout = QVBoxLayout()

        #spin_angle = QDoubleSpinBox(text="Grating angle")
        spin_angle.setSuffix(' π')
        #spin_angle.valueChanged.connect(lambda: self.update_angle_slide(angle, spin_angle))
        spin_angle.setKeyboardTracking(False)
        spin_angle.setSingleStep(0.1)

        #angle_slider = DoubleSlider()
        angle_slider.setGeometry(50,50, 200, 50)
        angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        angle_slider.setMaximum(2.)
        angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        #angle_slider.valueChanged.connect(lambda: self.update_angle_spin(angle, angle_slider))

        angle_layout.addWidget(spin_angle)
        angle_layout.addWidget(angle_slider)

    def triggerNextStep(self):
        self.waitCond.wakeAll()

    def update_grating_lmm_slide(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_slider.setValue(self.lmm_grating)
    def update_grating_lmm_spin(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_spin.setValue(self.lmm_grating)

    def update_interf_grating_lmm_slide(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_slider.setValue(self.lmm_interf_grating) 
    def update_interf_grating_lmm_spin(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_spin.setValue(self.lmm_interf_grating)

    def update_grating_angle_slide(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_slider.setValue(self.angle_grating)
    def update_grating_angle_spin(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_spin.setValue(self.angle_grating)
    def update_interf_grating_angle_slide(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_slider.setValue(self.angle_interf_grating) 
    def update_interf_grating_angle_spin(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_spin.setValue(self.angle_interf_grating)









----------

    def init_GUI(self):
        self.mesh_layout = QVBoxLayout()
        self.showmesh_layout = QHBoxLayout()
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

        self.mesh_layout.addWidget(self.generatemeshbutton)

        self.mesh_layout.addWidget(self.showmeshbutton)
        self.mesh_layout.addWidget(self.closemeshbutton)

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
        
        #self.mesh_layout.addLayout(self.grating_layout)


        #self.mesh_layout.addLayout(self.grating_angle_layout)

        self.mesh_layout.addLayout(self.showmesh_layout)
        self.mesh_layout.addWidget(self.parseMeshButton)



        self.zones_ref_combobox = QComboBox()
        self.zones_prob_combobox = QComboBox()

        self.zones_ref_combobox.currentIndexChanged.connect(self.setRefZone)
        self.zones_prob_combobox.currentIndexChanged.connect(self.setProbZone)
        
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

    # Wanted to highlight the selected zones but seems is not possible/IDK how to do it
    def highlight_zone(self):
        self.visualizer.highlight_zone(self.zones_prob_combobox.currentIndex,self.zones_ref_combobox.currentIndex)

    def setRefZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_ref_combobox.count() <=0:
            self.ref_zone = 0.
        else:
            self.ref_zone = int(self.zones_ref_combobox.currentText())

    def setProbZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_prob_combobox.count() <=0:
            self.prob_zone = 0.
        else:
            self.prob_zone = int(self.zones_prob_combobox.currentText())



    def populate_zone_selector(self):
        self.zones_ref_combobox.clear()
        self.zones_prob_combobox.clear()
        for el in self.ids_list:
            self.zones_ref_combobox.addItem(str(el))
            self.zones_prob_combobox.addItem(str(el))

    def is_active(self):
        return False
    
    # This part for setting the grating parameters needed for generating constructing/distructive interference

    def make_lmm_slider(self, lmm_layout, spin_lmm, lmm_slider):
        #self.lmm_layout = QVBoxLayout()
        lmm = 100
        #self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        spin_lmm.setSuffix(' l/mm')
        #spin_lmm.valueChanged.connect(lambda : self.update_lmm_slide(lmm, spin_lmm))
            
        spin_lmm.setKeyboardTracking(False)
        spin_lmm.setSingleStep(0.1)
        spin_lmm.setMaximum(self.maxlmm)
        spin_lmm.setMinimum(self.minlmm)

        #lmm_slider = DoubleSlider()
        lmm_slider.setGeometry(50,50, 200, 50)
        lmm_slider.setMinimum(0)
        lmm_slider.setMaximum(self.maxlmm)
        lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        lmm_slider.setTickInterval(10)
        #lmm_slider.valueChanged.connect(lambda _, lmm: self.update_lmm_slide(lmm, lmm_slider))
        #lmm_slider.valueChanged.connect(lambda : self.update_lmm_slide(lmm, lmm_slider))

        lmm_layout.addWidget(spin_lmm)
        lmm_layout.addWidget(lmm_slider)

    def make_angle_slider(self, angle_layout, spin_angle, angle_slider):
        #angle_layout = QVBoxLayout()

        #spin_angle = QDoubleSpinBox(text="Grating angle")
        spin_angle.setSuffix(' π')
        #spin_angle.valueChanged.connect(lambda: self.update_angle_slide(angle, spin_angle))
        spin_angle.setKeyboardTracking(False)
        spin_angle.setSingleStep(0.1)

        #angle_slider = DoubleSlider()
        angle_slider.setGeometry(50,50, 200, 50)
        angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        angle_slider.setMaximum(2.)
        angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        #angle_slider.valueChanged.connect(lambda: self.update_angle_spin(angle, angle_slider))

        angle_layout.addWidget(spin_angle)
        angle_layout.addWidget(angle_slider)

    def triggerNextStep(self):
        self.waitCond.wakeAll()

    def update_grating_lmm_slide(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_slider.setValue(self.lmm_grating)
    def update_grating_lmm_spin(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_spin.setValue(self.lmm_grating)

    def update_interf_grating_lmm_slide(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_slider.setValue(self.lmm_interf_grating) 
    def update_interf_grating_lmm_spin(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_spin.setValue(self.lmm_interf_grating)

    def update_grating_angle_slide(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_slider.setValue(self.angle_grating)
    def update_grating_angle_spin(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_spin.setValue(self.angle_grating)
    def update_interf_grating_angle_slide(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_slider.setValue(self.angle_interf_grating) 
    def update_interf_grating_angle_spin(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_spin.setValue(self.angle_interf_grating)




class OptimizerAlgorithm(QThread):
    def __init__(self,hologram_manager, pattern_generator, settings_manager,mutex,waitCond):
            QThread.__init__(self)
            self.pattern = None
            self.frequencies = None
            self.pattern_generator = pattern_generator
            self.settings_manager = settings_manager
            self.times = None
            self.mesh = None
            self.freqs = None
            self.SLM_x_res = None
            self.SLM_y_res = None
            self.ids_list = None
            self.phaseStep = None
            self.probZoneID = None
            self.refZoneID = None

            self.hologram_manager = hologram_manager
            self._active = True
            self.isPhaseReady = False
            self.trigger = mutex

            self._active = False
            self.waitCond = waitCond

            # Save last grating parameters to avoid re-generating the grating
            self.grating_lastvals = np.array([])
            self.interf_grating_lastvals = np.array([])

    def activate(self,grating_lmm, grating_angle,interf_grating_lmm,interf_grating_angle):
        self.setGrating(grating_lmm, grating_angle)
        self.setInterfGrating(interf_grating_lmm,interf_grating_angle)

    def run(self):
        if self.phase is None:
           self.setPhase(0)
        self.initPattern()
        self._active = True
        while self._active:
            self.next_step()
            if self.phase > self.settings_manager.get_phase_correction() :
                self._active = False
                break
            self.waitCond.wait(self.trigger)
        self.trigger.unlock()
        self.stop()

    def stop(self):
        self._active=False
        # TODO : Here we should save the data
        # And re-init important local variables
        self.phase = None

    def next_step(self):
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         tmp = self.mesh[i,j]
        #         if tmp == self.refZoneID:
        #             self.pattern[i,j] = self.interf_grating_pattern[i,j]
        #         elif tmp == self.probZoneID:
        #             self.pattern[i,j] = (self.interf_grating_pattern[i,j] + self.phase)%256
        #         else:
        #             self.pattern[i,j] = self.grating_pattern[i,j]
        self.pattern = next_step_fast(self.SLM_x_res, self.SLM_y_res, self.mesh, self.interf_grating_pattern, self.probZoneID, self.pattern, self.phase)
        print("Phase offset at this step: ", self.phase)
        self.phase = self.phase + self.phaseStep
        self.hologram_manager.renderAlgorithmPattern(self.pattern, True)
        


    def setInterfGrating(self,interf_grating_lmm,interf_grating_angle):
        self.interf_grating_lmm = interf_grating_lmm
        self.interf_grating_angle = interf_grating_angle

    def setGrating(self, grating_lmm, grating_angle):
        self.grating_lmm = grating_lmm
        self.grating_angle = grating_angle
    
    def setMesh(self, mesh):
        self.mesh = mesh

    # This to be used only when forcing the algorithm to start at a previous phase
    def setPhase(self, phase):
        self.phase = phase

    def setPhaseStep(self, phaseStep):
        self.phaseStep = phaseStep

    def setProbefZone(self,probZoneID):
        self.probZoneID = probZoneID

    def setRefZone(self,refZoneID):
        self.refZoneID = refZoneID

    def setIdsList(self, ids_list):
        self.ids_list = ids_list

    def isThreadReady(self):
        return self.mesh is not None or self.settings_manager is not None or self.ids_list is not None or self.probZoneID is not None or self.refZoneID is not None
    def isThreadRunning(self):
        return self._active
    

    def initPattern(self):
        print("Initializating ... ")
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.pattern = np.zeros((self.SLM_y_res,self.SLM_x_res))
        if not np.array_equal(self.grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])) and not np.array_equal(self.interf_grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])):
            print("remeshing")
            self.grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.interf_grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
            self.interf_grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
        self.pattern = load_pattern(self.mesh, self.grating_pattern,self.interf_grating_pattern,self.ids_list,self.phase,self.SLM_x_res,self.SLM_y_res,self.refZoneID,self.probZoneID)
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         tmp = self.ids_list.index(self.mesh[i,j])
        #         if tmp == self.refZoneID:
        #             self.pattern[i,j] = self.interf_grating_pattern[i,j]
        #         elif tmp == self.probZoneID:
        #             self.pattern[i,j] = (self.interf_grating_pattern[i,j] + self.phase)%256
        #         else:
        #             self.pattern[i,j] = self.grating_pattern[i,j]
        print("... done")


@jit(nopython=True)
def next_step_fast(SIZEX, SIZEY, mesh, interf_grating, probZoneID, pattern, phase):
    for i in range(0,SIZEY):
        for j in range(0,SIZEX):
            tmp = mesh[i,j]
            # if tmp == self.refZoneID:
            #     self.pattern[i,j] = self.interf_grating_pattern[i,j]
            if tmp == probZoneID:
                pattern[i,j] = (interf_grating[i,j] + phase)%256
    return pattern



@jit(nopython=True) # Set "nopython" mode for best performance, equivalent to @njit
def load_pattern(mesh, grating, interf_grating, phase, SIZEX, SIZEY, refZoneID, probZoneID):
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







class SpotOptimTab_ext(QWidget):
    def __del__(self):
        self.close_mesh()
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
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

        # --- Concurrency part ---

        # Parse mesh has to be done in a synchronized way. The main process cannot proceed without the mesh being generated
        self.parseMesh = Condition()

        # Events for signaling the meshing GUI process
        self.genMesh = Event()
        self.generalEvent = Event()
        self.parseMesh = Event()

        self.showGUI = Event()
        self.queue = Queue()

        self.process = MeshingHandler(genMesh,parseMesh,queue)


        self.mutex = QMutex() # Mutex needs to be given from the controlling thread
        self.waitCond = QWaitCondition()
        self.theOptimizer = OptimizerAlgorithm(self.hologram_manager,self.pattern_generator, self.settings_manager,self.mutex,self.waitCond)
    
    
    
    def load_zones(self):
        # Activate probe and reference zones
        for id, zone in enumerate(self.ids_list):
            if zone == self.prob_zone or zone == self.ref_zone:
                self.active_zones[id] = 1

    def stop_algo(self):
        self.theOptimizer.stop()
        self.waitCond.wakeAll()
    
    # def change_mesh_algo(self,algorithm):
    #     gmsh.option.setNumber("Mesh.Algorithm", algorithm)

    def putVariablesInQueue(self, queue, event, notify):
        # Tells the second process the type of event
        event.set()
        queue.put(self.SLM_size_X)
        queue.put(self.SLM_size_Y)
        queue.put(self.algorithm)
        queue.put(self.function)
        # Notifies the second process that data is ready
        notify.set()


    def generate_mesh(self,F):
        self.putVariablesInQueue(self.queue, self.genMesh, self.generalEvent)

    def load_mesh_ids(self):
        # Tell the second process to start parsing the mesh
        self.generalEvent.set()
        self.parseMesh.set()
        #Wait for second process to finish parsing the mesh
        with self.waitCond:
            self.waitCond.wait()
        self.mesh = self.queue.get()
        self.ids_list = self.queue.get()


    def start_algo(self):
        if self.theOptimizer.isThreadRunning():
            self.waitCond.wakeAll()
            return
        
        # Check that the grating parameter were initialized  
        if self.lmm_grating == 0 or self.lmm_interf_grating == 0:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid grating settings!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        #Generate grating mesh, this will be used for splitting the 0th order from the interference zone

        if self.ref_zone == self.prob_zone or self.prob_zone > np.max(self.ids_list) or self.prob_zone < np.min(self.ids_list) or self.ref_zone > np.max(self.ids_list) or self.ref_zone < np.min(self.ids_list):
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid probe or reference zones!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return


        self.theOptimizer.setProbefZone(self.prob_zone)
        self.theOptimizer.setRefZone(self.ref_zone)
        # TODO : For now hardcoded a step of 20, to be user-selectable
        self.theOptimizer.setPhaseStep(self.settings_manager.get_phase_correction()/10)

        # TODO: Reactivate this part once the thread will be automatized

        # if self.theOptimizer.isThreadRunning():
        #     dlg = QMessageBox(self)
        #     dlg.setIcon(QMessageBox.Icon.Warning)
        #     dlg.setWindowTitle("WARNING!")
        #     dlg.setText("An optimization is already in process!")
        #     button = dlg.exec()
        #     if button == QMessageBox.StandardButton.Ok:
        #         return

        if not self.theOptimizer.isThreadReady():
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Mesh is not ready!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        # TODO : Let user choose a starting phase
        self.theOptimizer.setPhase(0)
        self.theOptimizer.activate(self.lmm_grating, self.angle_grating, self.lmm_interf_grating,self.angle_interf_grating)
        self.theOptimizer.start()





class SpotOptimTab_ext(QWidget):
    def __del__(self):
        self.close_mesh()
    
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
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

        self.scaling_x = 0
        self.scaling_y = 0

        self.minlmm = 0
        self.maxlmm = 1e-3/(2*self.settings_manager.get_pixel_pitch()*1e-6)
        self.lmm_grating = 0.
        self.angle_grating = 0.

        self.lmm_interf_grating = 0.
        self.angle_interf_grating = 0.

        self.init_GMESH()
        self.init_GUI()
        self.visualizer = None #utils.MeshVisualizer(self)
        self.threadpool = QThreadPool()
        # Mesh data matrix

        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        self.ids_list = []
        self.phases = []
        self.active_zones = []
        self.step_phase = 0
        self.ref_zone = 0
        self.prob_zone = 0
        self.increment_phase_step = 25

        # Concurrency part
        self.mutex = QMutex() # Mutex needs to be given from the controlling thread
        self.waitCond = QWaitCondition()
        self.theOptimizer = OptimizerAlgorithm(self.hologram_manager,self.pattern_generator, self.settings_manager,self.mutex,self.waitCond)


    def init_GMESH(self):

        if not self.wasINIT:
            gmsh.initialize()
        self.wasINIT = True
        gmsh.model.add("SLM Meshing")
        lc = 0.5*max(self.SLM_x_res,self.SLM_y_res)
        self.scaling_x = self.SLM_x_res
        self.scaling_y = self.SLM_y_res
        self.points[0]=gmsh.model.geo.addPoint(0, 0, 0, meshSize = lc)# lc, 1)
        self.points[1]=gmsh.model.geo.addPoint(self.scaling_x, 0, 0, meshSize = lc)# lc, 2)
        self.points[2]=gmsh.model.geo.addPoint(self.scaling_x, self.scaling_y, 0, meshSize = lc)# lc, 3)
        self.points[3]=gmsh.model.geo.addPoint(0, self.scaling_y, 0, meshSize = lc)# lc, 4)

        self.lines[0] = gmsh.model.geo.addLine(1, 2, 1)
        self.lines[1] = gmsh.model.geo.addLine(3, 2, 2)
        self.lines[2] = gmsh.model.geo.addLine(3, 4, 3)
        self.lines[3] = gmsh.model.geo.addLine(4, 1, 4)

        self.contour = gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

        self.pl = gmsh.model.geo.addPlaneSurface([1], 1)

        gmsh.model.geo.synchronize()
        self.field = gmsh.model.mesh.field
        # self.threshold = gmsh.model.mesh.field.add("Threshold")
        # gmsh.model.mesh.field.setNumber(self.threshold , "InField", 1)
        # gmsh.model.mesh.field.setNumber(self.threshold , "SizeMin", lc / 150)
        # gmsh.model.mesh.field.setNumber(self.threshold , "SizeMax", lc)
        # gmsh.model.mesh.field.setNumber(self.threshold , "DistMin", 1)
        # gmsh.model.mesh.field.setNumber(self.threshold , "DistMax", lc)

        self.mathModel = gmsh.model.mesh.field.add("MathEval")

    def start_algo(self):

        if self.theOptimizer.isThreadRunning():
            self.waitCond.wakeAll()
            return
        
        # Check that the grating parameter were initialized  
        if self.lmm_grating == 0 or self.lmm_interf_grating == 0:
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid grating settings!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        #Generate grating mesh, this will be used for splitting the 0th order from the interference zone

        if self.ref_zone == self.prob_zone or self.prob_zone > np.max(self.ids_list) or self.prob_zone < np.min(self.ids_list) or self.ref_zone > np.max(self.ids_list) or self.ref_zone < np.min(self.ids_list):
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("ERROR!")
            dlg.setText("Invalid probe or reference zones!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
            
        #self.update_grating_pattern()

        # self.theOptimizer.setGrating(self.grating_lmm,self.grating_angle)
        # self.theOptimizer.setInterfGrating(self.interf_grating_lmm,self.interf_grating_angle)

        self.theOptimizer.setProbefZone(self.prob_zone)
        self.theOptimizer.setRefZone(self.ref_zone)
        # TODO : For now hardcoded a step of 20, to be user-selectable
        self.theOptimizer.setPhaseStep(self.settings_manager.get_phase_correction()/10)

        # TODO: Reactivate this part once the thread will be automatized

        # if self.theOptimizer.isThreadRunning():
        #     dlg = QMessageBox(self)
        #     dlg.setIcon(QMessageBox.Icon.Warning)
        #     dlg.setWindowTitle("WARNING!")
        #     dlg.setText("An optimization is already in process!")
        #     button = dlg.exec()
        #     if button == QMessageBox.StandardButton.Ok:
        #         return

        if not self.theOptimizer.isThreadReady():
            dlg = QMessageBox(self)
            dlg.setIcon(QMessageBox.Icon.Warning)
            dlg.setWindowTitle("WARNING!")
            dlg.setText("Mesh is not ready!")
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return
        # TODO : Let user choose a starting phase
        self.theOptimizer.setPhase(0)
        self.theOptimizer.activate(self.lmm_grating, self.angle_grating, self.lmm_interf_grating,self.angle_interf_grating)
        self.theOptimizer.start()



    def load_zones(self):
        # Activate probe and reference zones
        for id, zone in enumerate(self.ids_list):
            if zone == self.prob_zone or zone == self.ref_zone:
                self.active_zones[id] = 1

    def stop_algo(self):
        self.theOptimizer.stop()
        self.waitCond.wakeAll()
    
    def change_mesh_algo(self,algorithm):
        gmsh.option.setNumber("Mesh.Algorithm", algorithm)

    def generate_mesh(self,F):
        self.redo_GMESH()
        self.change_mesh_algo(self.algorithms[self.list_algorithms.currentIndex()])
        
        #gmsh.model.mesh.unpartition()
        gmsh.model.mesh.field.setString(self.mathModel, "F", F)
        self.field.setAsBackgroundMesh(self.mathModel)
        #gmsh.model.mesh.setRecombine(2, self.pl)
        # To make quadrangles instead of triangles
        gmsh.model.mesh.setRecombine(2,self.pl)
        gmsh.model.mesh.generate(2)
        gmsh.model.mesh.createEdges()
        gmsh.model.mesh.createFaces()
        #gmsh.model.geo.synchronize()

    def redo_GMESH(self):
        if self.wasINIT: 
            self.SLM_x_res = self.settings_manager.get_X_res()
            self.SLM_y_res = self.settings_manager.get_Y_res()
            gmsh.model.remove_entity_name("SLM Meshing")
            gmsh.model.geo.remove([[1,self.points[0]],[1,self.points[1]],[1,self.points[2]],[1,self.points[3]]],recursive=True)
            gmsh.model.geo.remove([[1,self.lines[0]],[1,self.lines[1]],[1,self.lines[2]],[1,self.lines[3]]],recursive=True)
            #gmsh.model.geo.remove([2,self.contour])
            #gmsh.model.mesh.field.remove(self.threshold)
            gmsh.model.mesh.field.remove(self.mathModel)
            self.mathModel = None
            self.threshold=None
            gmsh.model.mesh.clear()
            self.init_GMESH()
            # gmsh.model.geo.remove([2,self.pl])
            #gmsh.model.geo.remove([2,self.contour])

    def load_mesh_ids(self):
        self.ids_list = []
        self.mesh = np.zeros((self.SLM_y_res, self.SLM_x_res))
        for i in range(0,self.SLM_y_res):
            for j in range(0,self.SLM_x_res):  
                tmp = gmsh.model.mesh.getElementsByCoordinates(j, self.SLM_y_res-i, 0,dim=2)[0]
                self.mesh[i,j] = tmp
                self.ids_list.append(tmp)
        self.ids_list = [*set(self.ids_list)]
        self.populate_zone_selector()
        # Set mesh and ID list also in optimizer algorith
        self.theOptimizer.setMesh(self.mesh)
        self.theOptimizer.setIdsList(self.ids_list)



    def init_GUI(self):
        self.mesh_layout = QVBoxLayout()
        self.showmesh_layout = QHBoxLayout()
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

        self.mesh_layout.addWidget(self.generatemeshbutton)

        self.mesh_layout.addWidget(self.showmeshbutton)
        self.mesh_layout.addWidget(self.closemeshbutton)

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
        
        #self.mesh_layout.addLayout(self.grating_layout)


        #self.mesh_layout.addLayout(self.grating_angle_layout)

        self.mesh_layout.addLayout(self.showmesh_layout)
        self.mesh_layout.addWidget(self.parseMeshButton)



        self.zones_ref_combobox = QComboBox()
        self.zones_prob_combobox = QComboBox()

        self.zones_ref_combobox.currentIndexChanged.connect(self.setRefZone)
        self.zones_prob_combobox.currentIndexChanged.connect(self.setProbZone)
        
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

    # Wanted to highlight the selected zones but seems is not possible/IDK how to do it
    def highlight_zone(self):
        self.visualizer.highlight_zone(self.zones_prob_combobox.currentIndex,self.zones_ref_combobox.currentIndex)

    def setRefZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_ref_combobox.count() <=0:
            self.ref_zone = 0.
        else:
            self.ref_zone = int(self.zones_ref_combobox.currentText())

    def setProbZone(self):
        # Check if we don't have elements in the ComboBox, a mesh update will empty the list
        # Emptying the list will trigger a value update that will try to do int('') crashing
        if self.zones_prob_combobox.count() <=0:
            self.prob_zone = 0.
        else:
            self.prob_zone = int(self.zones_prob_combobox.currentText())



    def populate_zone_selector(self):
        self.zones_ref_combobox.clear()
        self.zones_prob_combobox.clear()
        for el in self.ids_list:
            self.zones_ref_combobox.addItem(str(el))
            self.zones_prob_combobox.addItem(str(el))

    def is_active(self):
        return False

    def show_mesh(self):
        # self.th_active = True
        # self.vis_th = threading.Thread(target=self.thread_gmsh_visualizer, args=())
        # self.vis_th.start()
        #gmsh.fltk.initialize()
        self.visualizer = utils.MeshVisualizer(self)
        self.threadpool.start(self.visualizer)
        #self.visualizer.start()
        
    def close_mesh(self):
        self.visualizer.stop()
        self.visualizer = None
        # self.th_active = False
        # 



# This part for setting the grating parameters needed for generating constructing/distructive interference

    def make_lmm_slider(self, lmm_layout, spin_lmm, lmm_slider):
        #self.lmm_layout = QVBoxLayout()
        lmm = 100
        #self.spin_lmm = QDoubleSpinBox(text="l/mm ")
        spin_lmm.setSuffix(' l/mm')
        #spin_lmm.valueChanged.connect(lambda : self.update_lmm_slide(lmm, spin_lmm))
            
        spin_lmm.setKeyboardTracking(False)
        spin_lmm.setSingleStep(0.1)
        spin_lmm.setMaximum(self.maxlmm)
        spin_lmm.setMinimum(self.minlmm)

        #lmm_slider = DoubleSlider()
        lmm_slider.setGeometry(50,50, 200, 50)
        lmm_slider.setMinimum(0)
        lmm_slider.setMaximum(self.maxlmm)
        lmm_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        lmm_slider.setTickInterval(10)
        #lmm_slider.valueChanged.connect(lambda _, lmm: self.update_lmm_slide(lmm, lmm_slider))
        #lmm_slider.valueChanged.connect(lambda : self.update_lmm_slide(lmm, lmm_slider))

        lmm_layout.addWidget(spin_lmm)
        lmm_layout.addWidget(lmm_slider)

    def make_angle_slider(self, angle_layout, spin_angle, angle_slider):
        #angle_layout = QVBoxLayout()

        #spin_angle = QDoubleSpinBox(text="Grating angle")
        spin_angle.setSuffix(' π')
        #spin_angle.valueChanged.connect(lambda: self.update_angle_slide(angle, spin_angle))
        spin_angle.setKeyboardTracking(False)
        spin_angle.setSingleStep(0.1)

        #angle_slider = DoubleSlider()
        angle_slider.setGeometry(50,50, 200, 50)
        angle_slider.setMinimum(0)
        # Maximum number of lines per mm is limited by the pixel pitch of the SLM (better even avoiding getting closer to this limit)
        angle_slider.setMaximum(2.)
        angle_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        #angle_slider.valueChanged.connect(lambda: self.update_angle_spin(angle, angle_slider))

        angle_layout.addWidget(spin_angle)
        angle_layout.addWidget(angle_slider)

    def triggerNextStep(self):
        self.waitCond.wakeAll()

    def update_grating_lmm_slide(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_slider.setValue(self.lmm_grating)
    def update_grating_lmm_spin(self):
        self.lmm_grating = self.sender().value()
        self.grating_lmm_spin.setValue(self.lmm_grating)

    def update_interf_grating_lmm_slide(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_slider.setValue(self.lmm_interf_grating) 
    def update_interf_grating_lmm_spin(self):
        self.lmm_interf_grating = self.sender().value()
        self.interf_grating_lmm_spin.setValue(self.lmm_interf_grating)

    def update_grating_angle_slide(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_slider.setValue(self.angle_grating)
    def update_grating_angle_spin(self):
        self.angle_grating = self.sender().value()
        self.grating_angle_spin.setValue(self.angle_grating)
    def update_interf_grating_angle_slide(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_slider.setValue(self.angle_interf_grating) 
    def update_interf_grating_angle_spin(self):
        self.angle_interf_grating = self.sender().value()
        self.interf_grating_angle_spin.setValue(self.angle_interf_grating)

    

    # def update_grating_pattern(self):
    #     self.grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())
    #     self.interf_grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.settings_manager.get_X_res(), self.settings_manager.get_Y_res())

        #self.lastvals = [self.angle,self.lmm,self.settings_manager.get_wavelength(),self.settings_manager.get_pixel_pitch(),self.settings_manager.get_X_res(),self.settings_manager.get_Y_res()]



class OptimizerAlgorithm(QThread):
    def __init__(self,hologram_manager, pattern_generator, settings_manager,mutex,waitCond):
            QThread.__init__(self)
            self.pattern = None
            self.frequencies = None
            self.pattern_generator = pattern_generator
            self.settings_manager = settings_manager
            self.times = None
            self.mesh = None
            self.freqs = None
            self.SLM_x_res = None
            self.SLM_y_res = None
            self.ids_list = None
            self.phaseStep = None
            self.probZoneID = None
            self.refZoneID = None

            self.hologram_manager = hologram_manager
            self._active = True
            self.isPhaseReady = False
            self.trigger = mutex

            self._active = False
            self.waitCond = waitCond

            # Save last grating parameters to avoid re-generating the grating
            self.grating_lastvals = np.array([])
            self.interf_grating_lastvals = np.array([])

    def activate(self,grating_lmm, grating_angle,interf_grating_lmm,interf_grating_angle):
        self.setGrating(grating_lmm, grating_angle)
        self.setInterfGrating(interf_grating_lmm,interf_grating_angle)

    def run(self):
        if self.phase is None:
           self.setPhase(0)
        self.initPattern()
        self._active = True
        while self._active:
            self.next_step()
            if self.phase > self.settings_manager.get_phase_correction() :
                self._active = False
                break
            self.waitCond.wait(self.trigger)
        self.trigger.unlock()
        self.stop()

    def stop(self):
        self._active=False
        # TODO : Here we should save the data
        # And re-init important local variables
        self.phase = None

    def next_step(self):
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         tmp = self.mesh[i,j]
        #         if tmp == self.refZoneID:
        #             self.pattern[i,j] = self.interf_grating_pattern[i,j]
        #         elif tmp == self.probZoneID:
        #             self.pattern[i,j] = (self.interf_grating_pattern[i,j] + self.phase)%256
        #         else:
        #             self.pattern[i,j] = self.grating_pattern[i,j]
        self.pattern = next_step_fast(self.SLM_x_res, self.SLM_y_res, self.mesh, self.interf_grating_pattern, self.probZoneID, self.pattern, self.phase)
        print("Phase offset at this step: ", self.phase)
        self.phase = self.phase + self.phaseStep
        self.hologram_manager.renderAlgorithmPattern(self.pattern, True)
        


    def setInterfGrating(self,interf_grating_lmm,interf_grating_angle):
        self.interf_grating_lmm = interf_grating_lmm
        self.interf_grating_angle = interf_grating_angle

    def setGrating(self, grating_lmm, grating_angle):
        self.grating_lmm = grating_lmm
        self.grating_angle = grating_angle
    
    def setMesh(self, mesh):
        self.mesh = mesh

    # This to be used only when forcing the algorithm to start at a previous phase
    def setPhase(self, phase):
        self.phase = phase

    def setPhaseStep(self, phaseStep):
        self.phaseStep = phaseStep

    def setProbefZone(self,probZoneID):
        self.probZoneID = probZoneID

    def setRefZone(self,refZoneID):
        self.refZoneID = refZoneID

    def setIdsList(self, ids_list):
        self.ids_list = ids_list

    def isThreadReady(self):
        return self.mesh is not None or self.settings_manager is not None or self.ids_list is not None or self.probZoneID is not None or self.refZoneID is not None
    def isThreadRunning(self):
        return self._active
    

    def initPattern(self):
        print("Initializating ... ")
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.pattern = np.zeros((self.SLM_y_res,self.SLM_x_res))
        if not np.array_equal(self.grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])) and not np.array_equal(self.interf_grating_lastvals,np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])):
            print("remeshing")
            self.grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.interf_grating_pattern = self.pattern_generator.GenerateGrating(self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res)
            self.grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.grating_lmm, self.grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
            self.interf_grating_lastvals = np.array([self.settings_manager.get_wavelength(), self.settings_manager.get_pixel_pitch(), self.interf_grating_lmm, self.interf_grating_angle*np.pi, self.SLM_x_res, self.SLM_y_res])
        self.pattern = load_pattern(self.mesh, self.grating_pattern,self.interf_grating_pattern,self.ids_list,self.phase,self.SLM_x_res,self.SLM_y_res,self.refZoneID,self.probZoneID)
        # for i in range(0,self.SLM_y_res):
        #     for j in range(0,self.SLM_x_res):
        #         tmp = self.ids_list.index(self.mesh[i,j])
        #         if tmp == self.refZoneID:
        #             self.pattern[i,j] = self.interf_grating_pattern[i,j]
        #         elif tmp == self.probZoneID:
        #             self.pattern[i,j] = (self.interf_grating_pattern[i,j] + self.phase)%256
        #         else:
        #             self.pattern[i,j] = self.grating_pattern[i,j]
        print("... done")


@jit(nopython=True)
def next_step_fast(SIZEX, SIZEY, mesh, interf_grating, probZoneID, pattern, phase):
    for i in range(0,SIZEY):
        for j in range(0,SIZEX):
            tmp = mesh[i,j]
            # if tmp == self.refZoneID:
            #     self.pattern[i,j] = self.interf_grating_pattern[i,j]
            if tmp == probZoneID:
                pattern[i,j] = (interf_grating[i,j] + phase)%256
    return pattern



@jit(nopython=True) # Set "nopython" mode for best performance, equivalent to @njit
def load_pattern(mesh, grating, interf_grating, phase, SIZEX, SIZEY, refZoneID, probZoneID):
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
    
    '''