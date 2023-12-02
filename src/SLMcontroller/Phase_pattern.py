#!/usr/bin/env python

"""Phase_pattern.py: Generates phase patterns for the SLM."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

import numpy as np
import numba as nb

@nb.jit(nopython = True, parallel = True, cache = True, fastmath = True)
def _generateGrating(X,Y,pxl,theta):
    """Generates a grating pattern.

    Args:
        X (int): X resolution of the pattern (SLM).
        Y (int): Y resolution of the pattern (SLM).
        pxl (float): pixel size
        theta (float): angle of the grating

    Returns:
        np.array: Grating pattern.
    """
    precomp_sin = np.sin(theta)
    precomp_cos = np.cos(theta)
    precomp_scaling = 256/pxl
    grating = precomp_scaling*(Y*precomp_sin+X*precomp_cos)
    return grating

@nb.jit(nopython = True, parallel = True, cache = True, fastmath = True)
def _generateLens(X, Y, x_offset, y_offset, wl, focus, pixel_pitch):
    """Generates a lens pattern.

    Args:
        X (int): X resolution of the pattern (SLM).
        Y (int): Y resolution of the pattern (SLM).
        x_offset (int): Lens offset from the center of the SLM on the X axis.
        y_offset (int): Lens offset from the center of the SLM on the Y axis.
        wl (float): Wavelength of the laser.
        focus (float): Focus of the lens.
        pixel_pitch (float): Pixel pitch of the SLM.

    Returns:
        np.array: Lens pattern.
    """
    rN = wl*focus/(2*pixel_pitch)
    r = np.sqrt((X - x_offset)**2 + (Y - y_offset)**2)
    mask = r < np.abs(rN/pixel_pitch)
    gamma = np.pi/(wl*focus)
    phi = gamma*(((X - x_offset)*pixel_pitch)**2+((Y - y_offset)*pixel_pitch)**2)/(2*np.pi)
    lens = (mask*phi*256)#%256
    return lens

class Patter_generator:
    """Class for generating phases patterns.

    Attributes:
        X (int): X resolution of the pattern (SLM).
        Y (int): Y resolution of the pattern (SLM).
    """

    def __init__(self):
        """Constructor for the Pattern_generator class.
        """
        self.X = None
        self.Y = None

    def GenerateLens(self,focus, wl, pixel_pitch, res_X, res_Y):
        """Generates a lens pattern.

        Args:
            focus (float): Focus of the lens.
            wl (float): Wavelength of the laser.
            pixel_pitch (float): Pixel pitch of the SLM.
            res_X (int): SLM X resolution.
            res_Y (int): SLM Y resolution.

        Returns:
            np.array: Lens pattern.
        """
        # TODO : Put the offset as extra parameter from user
        x_offset, y_offset= 0.0, 0.0
        # Convert everything to meters
        if focus == 0 :
            focus = 1
        focus = focus * 1e-3
        wl = wl * 1e-9
        pixel_pitch = pixel_pitch*1e-6
        # Generate meshgrid if needed
        self.generate_mesh(res_X, res_Y)

        return _generateLens(self.X,self.Y,x_offset, y_offset,wl,focus, pixel_pitch)

    def GenerateGrating(self, wl, pixel_pitch, lmm, theta, res_X, res_Y):
        """Generates a grating pattern.

        Args:
            wl (float): Wavelength of the laser.
            pixel_pitch (float): Pixel pitch of the SLM.
            lmm (float): Lines per mm of the grating.
            theta (float): Angle of the grating.
            res_X (int): SLM X resolution.
            res_Y (int): SLM Y resolution.

        Returns:
            np.array: Grating pattern.
        """
        if (lmm == 0 ): return np.zeros((res_Y, res_X))

        # Number of pixel per line
        pixel_pitch = pixel_pitch*1e-6
        pxl = 1e-3/lmm/pixel_pitch
        self.generate_mesh(res_X, res_Y)
        return _generateGrating(self.X,self.Y,pxl,theta)

    def empty_pattern(self,res_X, res_Y):
        """Generates an empty pattern.

        Args:
            res_X (int): X resolution of the pattern (SLM).
            res_Y (int): Y resolution of the pattern (SLM).

        Returns:
            np.array: Empty pattern.
        """
        return np.zeros((res_Y, res_X))

    def generate_mesh(self, res_X, res_Y):
        """Generates a meshgrid for the pattern.
        Used to speed up the pattern generation.

        Args:
            res_X (int): X resolution of the pattern (SLM).
            res_Y (int): Y resolution of the pattern (SLM).
        """
        if self.X is None or self.Y is None:
            x_list = np.linspace(-int(res_X/2),int(res_X/2),res_X)
            y_list = np.linspace(-int(res_Y/2),int(res_Y/2),res_Y)
            self.X, self.Y = np.meshgrid(x_list,y_list)
        elif len(self.X) != res_X or len(self.Y) != res_Y:
            x_list = np.linspace(-int(res_X/2),int(res_X/2),res_X)
            y_list = np.linspace(-int(res_Y/2),int(res_Y/2),res_Y)
            self.X, self.Y = np.meshgrid(x_list,y_list)

    def MakeZernike(self):
        """Generates a Zernike pattern.

        Todo: 
            Implement this function.
        """
        print(1)
        pass
