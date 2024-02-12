#!/usr/bin/env python

"""Phase_pattern.py: Generates phase patterns for the SLM."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2023, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-

import numpy as np
import numba as nb
import math as math


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
    precomp_scaling = 255/pxl
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
    lens = (mask*phi*255)#%256
    return lens

LOOKUP_TABLE = np.array([
    1, 1, 2, 6, 24, 120, 720, 5040, 40320,
    362880, 3628800, 39916800, 479001600,
    6227020800, 87178291200, 1307674368000,
    20922789888000, 355687428096000, 6402373705728000,
    121645100408832000, 2432902008176640000], dtype='int64')

# This part to speed up Zernike polynomial generation
@nb.jit(nopython = True, cache = True, fastmath = True)
def _fast_factorial(n):
    if n > 20:
        raise ValueError
    return LOOKUP_TABLE[n]

## Zernike polynomials generation
# This function determines the radial Zernike polynomials
@nb.jit(nopython = True, cache = True, fastmath = True)
def _radialfunc(n, m1, rho):
    if( m1 < 0  ):
        m = -m1
    else:
        m = m1
    val_i = int((n-m)/2);
    val_j = int((n+m)/2);

    #rad = 0.0;
    rad = np.zeros_like(rho)

    for k in (range(0, val_i+1)):
        rad += ( ((-1)**k * _fast_factorial(n - k) ) / (_fast_factorial(k)*_fast_factorial(val_j - k)*_fast_factorial(val_i - k) ) )* rho**(n-2*k) 

    return rad

# Zernike Polynomial function, generates the corresponding polynomial for each given n,m 
# along the cartesian (pixel) coordinates x,y
@nb.jit(nopython = True, cache = True, fastmath = True)
def _ZernikePolynomial(n, m, x, y):
    # theta is the azimuthal angle between 0 and 2pi; rho is the radial distance between 0 and 1
    
    rho =  np.sqrt(x**2 + y**2)
    theta = np.arctan2(x,y) 
    radial = _radialfunc(n, m , rho)
    
    if( m > 0):
        z_all = radial* np.cos( m * theta) * np.sqrt(2*n+2)
    elif(m == 0):
        z_all = radial * np.sqrt(n+1)
    else :
        z_all = radial* np.sin( m * theta) * np.sqrt(2*n+2)
    return (z_all) #renormalization?

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

        return _generateLens(self.X, self.Y, x_offset, y_offset, wl, focus, pixel_pitch)
    
    def GenerateZernike(self, coefficients, res_X, res_Y, x_offset, y_offset):
        """Generates a Zernike pattern.

        Args:
            coefficients (list): List of coefficients for the Zernike polynomial.
            res_X (int): SLM X resolution.
            res_Y (int): SLM Y resolution.

        Returns:
            np.array: Zernike pattern.
        """

        self.generate_mesh(res_X, res_Y)
        Zernike = np.zeros((res_Y, res_X))
        n = 0
        m = -n
        for order in range(len(coefficients)):
            while (n*(n+2)+m)/2 <= order:
                Zernike +=  coefficients[order] * _ZernikePolynomial(n, m, -x_offset + self.X + int(res_X/2), self.Y - int(res_Y/2) + y_offset )
                m += 2
                if m > n:
                    n += 1
                    m = -n 
        # As the Zernike pattern is a sum of various patterns it needs renormalization
        return (Zernike*255)#%256

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

