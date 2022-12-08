# This Python file uses the following encoding: utf-8
import numpy as np
import numba as nb

@nb.jit
def _generateGrating(X,Y,pxl,theta):
    grating = (256*(Y/pxl*np.sin(theta)+X/pxl*np.cos(theta)))%256
    return grating.astype(np.uint8)

@nb.jit
def _generateLens(X, Y, x_offset, y_offset, wl, focus, pixel_pitch):
    rN = wl*focus/(2*pixel_pitch)
    r = np.sqrt((X - x_offset)**2 + (Y - y_offset)**2)
    mask = r < rN/pixel_pitch
    gamma = np.pi/(wl*focus)
    phi = gamma*(((X - x_offset)*pixel_pitch)**2+((Y - y_offset)*pixel_pitch)**2)/(2*np.pi)
    lens = (mask*phi*256)%256
    return lens.astype(np.uint8)
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
        # Generate meshgrid if needed
        self.generate_mesh(res_X, res_Y)

        return _generateLens(self.X,self.Y,x_offset, y_offset,wl,focus, pixel_pitch)

    def GenerateGrating(self, wl, pixel_pitch, lmm, theta, res_X, res_Y):
        grating=np.zeros((res_Y, res_X))
        if (lmm == 0 ): return grating.astype(np.uint8)

        # Number of pixel per line
        pixel_pitch = pixel_pitch*1e-6
        pxl = 1e-3/lmm/pixel_pitch
        self.generate_mesh(res_X, res_Y)
        return _generateGrating(self.X,self.Y,pxl,theta)

    def empty_pattern(self,res_X, res_Y):
        return (np.zeros((res_Y, res_X))).astype(np.uint8)

    def generate_mesh(self, res_X, res_Y):
        if self.X is None or self.Y is None:
            x_list = np.linspace(-int(res_X/2),int(res_X/2),res_X)
            y_list = np.linspace(-int(res_Y/2),int(res_Y/2),res_Y)
            self.X, self.Y = np.meshgrid(x_list,y_list)
        elif len(self.X) != res_X or len(self.Y) != res_Y:
            x_list = np.linspace(-int(res_X/2),int(res_X/2),res_X)
            y_list = np.linspace(-int(res_Y/2),int(res_Y/2),res_Y)
            self.X, self.Y = np.meshgrid(x_list,y_list)

    def MakeZernike(self):
        print(1)
        pass
