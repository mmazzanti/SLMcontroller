.. _how-to:

How to
*********

After starting the app the following screen will appear:

.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/12940b5a5612849118dabec2827f9234863ffdce/Documentation/Img/main.png
   :width: 400px
   :align: center

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


.. raw:: html

   <script data-name="BMC-Widget" data-cfasync="false" src="https://cdnjs.buymeacoffee.com/1.0.0/widget.prod.min.js" data-id="mmazzanti" data-description="Support me on Buy me a coffee!" data-message="Hey there! If you like my software consider buying me a coffee :)" data-color="#BD5FFF" data-position="Right" data-x_margin="18" data-y_margin="18">
   </script>

.. |2pi| replace:: :math:`{2\pi}`