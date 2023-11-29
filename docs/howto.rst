.. _how-to:

How to
*********

After starting the app the following screen will appear:

.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/12940b5a5612849118dabec2827f9234863ffdce/Documentation/Img/main.png
   :width: 400px
   :align: center

Setting things up
-----------------

You can set the parameters of the SLM by clicking on the "Settings" button. The following screen will appear:

.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/12940b5a5612849118dabec2827f9234863ffdce/Documentation/Img/settings.png
   :width: 400px
   :align: center

The available parameters are:

- **SLM ID**: ID of the SLM in use. At the moment this variable is not used. In the following versions it will be used to identify the SLM in use and to automatically load the correct calibration file.
- **Screen number**: number of the screen on which the SLM is displayed. I advice you to use at least two screens (one to run the control software and one to display the SLM). If you use only one screen, the SLM will be displayed on the same screen as the control software.
- **Laser wavelength**: wavelength of the laser in use.
- **SLM resolution**: resolution of the SLM in use.
- **SLM pixel pitch**: pixel pitch of the SLM in use.
- **SLM phase correction**: Phase correction value for |2pi|  phase shift. This value can be found in the calibration sheet of the SLM (provided by the vendor). Or measured with the calibration procedure (see :ref:`examples`)
- **Pattern size**: size of the pattern that needs to be rendered on the SLM. Notice that its size might differ from the SLM resolution as an SLM might use a higher display resolution that number of pixels available. The extra pixels will appear black.
- **IP address & port**: IP address and port on which to listen for network connections. The software will accepts controls coming from any IP address. If you want to limit the IP addresses that can control the SLM, you can use a firewall. I strongly advice to use the software on a private network (this not for security reasons but to reduce the probability of incoming connections from other computers during sentive operations).


Adding patterns
---------------

It is possible to add multiple optical elements phase patterns to the SLM. Each pattern will appear as a separate tab where it is possible to modify its parameters.
Besides optical elements some tabs are used for iterative algorithms that can be used to compensate for optical aberrations (see :ref:`examples`).

Between the available optical elements there are:

- **Lens**: a lens with a given focal length (used to focus/defocus the beam).
- **Grating**: a grating phase pattern with a given pitch and angle (used to steer the beam).
- **Flatness correction**: a phase pattern used to correct for the flatness of the SLM.

& more to come.

In the center of the tab will be shown a small preview of the phase pattern that will be rendered on the SLM.
Each optical elemnt tab has a checkbox to activate/deactivate the element.
Active elements will be rendered on the SLM (summed up and rendered). Inactive elements will be ignored.

The "live update" checkbox will enable/disable the live update of the phase pattern on the SLM. If the checkbox is not selected, the phase pattern will be updated only when the "Show hologram/update" button is pressed.

Phase lenses
-------------------------
If the user selects "Lens" after clicking on "Add new optical element" the following tab will be created:

.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/12940b5a5612849118dabec2827f9234863ffdce/Documentation/Img/lens.png
   :width: 400px
   :align: center

Activating the element will render a phase pattern on the SLM that will focus/defocus the beam. The focal length of the lens can be set by changing the value of the focus using the scrollbox or the slider in the tab. The focal length is expressed in mm. The focal length can be positive or negative. A positive focal length will focus the beam, a negative focal length will defocus the beam.

Phase grating
-------------------------
Selecting "Grating" after clicking on "Add new optical element" will create a new grating tab that appears as follows:

.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/12940b5a5612849118dabec2827f9234863ffdce/Documentation/Img/grating.png
   :width: 400px
   :align: center

Using the scrollbox or the slider it is possible to set the pitch of the grating and its angle. The pitch is expressed in lines/mm. The angle is expressed in radians.
Similar to the lens, the grating can be activated/deactivated using the checkbox in the tab.

Flatness correction
-------------------------
Selecting "Flatness correction" after clicking on "Add new optical element" will create a new flatness correction tab that appears as follows:

.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/12940b5a5612849118dabec2827f9234863ffdce/Documentation/Img/flatness_correction.png
   :width: 400px
   :align: center

The flatness correction pattern is usually provided by the company as a bmp image. It is possible to load the image by pasting its path in the text box.
"Load Flatness Correction Image" will then load the image as a phase pattern. Be sure that the flatness correction image is a 8bit grayscale bmp image.


.. |2pi| replace:: :math:`{2\pi}`