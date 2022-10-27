# This Python file uses the following encoding: utf-8
import numpy as np


class Patter_generator:
    def __init__(self):
        self.X = None
        self.Y = None
        pass

    def GenerateLens(self,focus, wl, pixel_pitch, res_X, res_Y):
        # TODO : Put the offset as extra parameter from user
        x_offset, y_offset= 0.0, 0.0

        lens=np.zeros((res_Y, res_X))
        # Convert everything to meters
        focus = focus * 1e-3
        wl = wl * 1e-9
        pixel_pitch = pixel_pitch*1e-6
        # Generate meshgrid
        if self.X is None or self.Y is None:
            self.generate_mesh(res_X, res_Y)

        # Lens scaling parameter
        gamma = np.pi/(wl*focus)
        # Lens maximum radius (limited by the pixel pitch)
        rN = wl*focus/(2*pixel_pitch)
        # Generate maks to cut lens values outside this range
        r = np.sqrt((self.X - x_offset)**2 + (self.Y - y_offset)**2)
        mask = r < rN/pixel_pitch

        # Generate grid if not already done
        
        # Generate lens pattern
        #phi = ((1+np.cos(gamma*(((X - x_offset)*pixel_pitch)**2+((Y - y_offset)*pixel_pitch)**2)))/2)
        phi = gamma*(((self.X - x_offset)*pixel_pitch)**2+((self.Y - y_offset)*pixel_pitch)**2)/(2*np.pi)
  
        lens = (mask*phi*255)%255

        return lens.astype(np.uint8)

    def GenerateGrating(self, wl, pixel_pitch, lmm, theta, res_X, res_Y):
        grating=np.zeros((res_Y, res_X))
        if (lmm == 0 ): return grating.astype(np.uint8)

        # Number of pixel per line
        pixel_pitch = pixel_pitch*1e-6
        pxl = 1e-3/lmm/pixel_pitch

        # x_list = np.linspace(-int(res_X/2),int(res_X/2),res_X)
        # y_list = np.linspace(-int(res_Y/2),int(res_Y/2),res_Y)
        # X, Y = np.meshgrid(x_list,y_list)
        if self.X is None or self.Y is None:
            self.generate_mesh(res_X, res_Y)
        grating = (255*(self.Y/pxl*np.sin(theta)+self.X/pxl*np.cos(theta)))%255

        # for n in range(0,res_Y):
        #     for m in range(0,res_X):
        #         grating[n,m] = (255*(n/pxl*np.sin(theta)+m/pxl*np.cos(theta)))%255
        return grating.astype(np.uint8)

    def empty_pattern(self,res_X, res_Y):
        return (np.zeros((res_Y, res_X))).astype(np.uint8)

    def generate_mesh(self, res_X, res_Y):
        x_list = np.linspace(-int(res_X/2),int(res_X/2),res_X)
        y_list = np.linspace(-int(res_Y/2),int(res_Y/2),res_Y)
        self.X, self.Y = np.meshgrid(x_list,y_list)

    def MakeZernike(self):
        print(1)
        pass
