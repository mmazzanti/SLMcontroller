#!/usr/bin/env python

"""__init__.py: Defines main function for the program."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

from PyQt6 import QtWidgets

import sys

import SLMcontroller.MainGUI as MainGUI
import SLMcontroller.Meshing_process as Meshing_process
import SLMcontroller.Remote_control as Remote_control

from multiprocessing import Event, Queue, Condition, freeze_support

def closeSecondProcess(eventsDict):
    """Closes the GMSH GUI process
    """
    eventsDict['terminate'].set()
    eventsDict['generalEvent'].set()


def main():
    freeze_support()

    # Events list for :
    # 0 - Mesh generation request
    # 1 - General event to check user request
    # 2 - Parse mesh request
    # 3 - Show GUI event (opens GMSH GUI)
    # 4 - Close GUI event (closes GMSH GUI)
    # 5 - Terminate meshing handler process
    # 6 - Save meshing file
    # 7 - Load meshing file
    eventsDict = {"genMesh":Event(),"generalEvent":Event(),"parseMesh":Event(),"showGUI":Event(),"closeGUI":Event(),"terminate":Event(), "savefile":Event(), "loadfile":Event()}


    # Conditions list for :
    # 0 - Mesh generation request
    # 1 - Save meshing file
    # 2 - Load meshing file
    conditionsDict = {"parsingCond":Condition(), "savefile":Condition(), "loadfile":Condition()}


    # Flask app for remote control
    flask_app = Remote_control.Flask(__name__)
    app = Remote_control.NetworkManager(flask_app)
    # Queue for inter-processing communication
    queue = Queue()

    # Start meshing process, this will be needed to show GMESH GUI in another process
    mesh_process = Meshing_process.MeshingHandler(eventsDict, conditionsDict, queue, 0, 0, 0 , "")
    mesh_process.start()

    # Start GUI
    GUIapp = QtWidgets.QApplication(sys.argv)
    GUIapp.setStyle('macos')
    main = MainGUI.First(mesh_process,app, queue, eventsDict, conditionsDict)
    main.show()
    retval = GUIapp.exec()

    # Close Gmsh process
    closeSecondProcess(eventsDict)
    
    sys.exit(retval)