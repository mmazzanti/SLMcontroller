from PyQt6.QtWidgets import QMessageBox, QLineEdit, QGridLayout, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt

import src.utils as utils
import cv2
import os
import numpy as np

class FlatnessCorrectionTab(QWidget):
    def __init__(self, pattern_generator, settings_manager, hologram_manager):
        super().__init__()
        self.pattern_generator = pattern_generator
        self.settings_manager = settings_manager
        self.hologram_manager = hologram_manager
        self.image_data = None
        self.loaded_file = "none"
        self.scale = 10
        self.script_folder = os.path.realpath(__file__)
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        self.Init_GUI()

    def __del__(self):
        pass

    def Init_GUI(self):
        self.layout = QGridLayout()
        
        self.image_loading_layout = QVBoxLayout()
        self.image_preview_layout = QVBoxLayout()
        self.general_controls = QHBoxLayout()
        
        self.image_path = QLineEdit("deformation_correction_pattern/CAL_LSH0802160_760nm.bmp")
        self.loadimage = QPushButton("Load Flatness Correction Image")
        self.loadimage.clicked.connect(self.update_pattern)

        self.pattern_image = utils.ImageWidget()
        
        self.isactive = QCheckBox("Activate element : ")
        self.isactive.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.image_loading_layout.addWidget(self.image_path)
        self.image_loading_layout.addWidget(self.loadimage)
        self.layout.addLayout(self.image_loading_layout,0,0)

        self.image_preview_layout.addWidget(self.pattern_image)
        self.layout.addLayout(self.image_preview_layout,1,0)

        self.general_controls.addWidget(self.isactive)
        self.layout.addLayout(self.general_controls,2,0)

        #self.mesh_layout.addLayout(self.showmesh_layout)
        self.setLayout(self.layout)



    def update_pattern(self):
        self.SLM_x_res = self.settings_manager.get_X_res()
        self.SLM_y_res = self.settings_manager.get_Y_res()
        if self.loaded_file != self.image_path.text():
            img = cv2.imread(self.image_path.text(), -1)
            if img is None:
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Wrong path to image")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return
            self.pattern = np.array(img)
            print(self.pattern.shape)
            if len(self.pattern.shape) != 2:
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Your image does not use a 8 bits color scheme, check the image and retry")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return	
            if (self.pattern.shape[1] != self.SLM_x_res) or (self.pattern.shape[0] != self.SLM_y_res) :
                dlg = QMessageBox(self)
                dlg.setIcon(QMessageBox.Icon.Warning)
                dlg.setWindowTitle("WARNING!")
                dlg.setText("Image dimensions don't match with SLM size")
                button = dlg.exec()
                if button == QMessageBox.StandardButton.Ok:
                    return	
            self.loaded_file = self.image_path.text()
            self.pattern_image.setImage(self.pattern)

    def get_pattern(self):
        self.update_pattern()
        return self.pattern

    def is_active(self):
        return self.isactive.isChecked()

