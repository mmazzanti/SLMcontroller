Settings
*********

Clicking on the |settings|_ menu of SLMcontroller allows to set the following parameters:

- **SLM ID**: the name of the SLM device to be used. This setting is still under development. The program will be extended to control multiple SLMs at the same time.
- **Screen number**: number of the screen on which the SLM is displayed. I advice you to use at least two screens (one to run the control software and one to display the SLM). If you use only one screen, the SLM will be displayed on the same screen as the control software.
- **Laser wavelength**: wavelength of the laser in use.
- **SLM resolution**: resolution of the SLM in use.
- **SLM pixel pitch**: pixel pitch of the SLM in use.
- **SLM phase correction**: Phase correction value for |2pi|  phase shift. This value can be found in the calibration sheet of the SLM (provided by the vendor). Or measured with the calibration procedure (see :ref:`examples`)
- **Pattern size**: size of the pattern that needs to be rendered on the SLM. Notice that its size might differ from the SLM resolution as an SLM might use a higher display resolution that number of pixels available. The extra pixels will appear black.
- **IP address & port**: IP address and port on which to listen for network connections. The software will accepts controls coming from any IP address. If you want to limit the IP addresses that can control the SLM, you can use a firewall. I strongly advice to use the software on a private network (this not for security reasons but to reduce the probability of incoming connections from other computers during sentive operations).


.. image:: https://raw.githubusercontent.com/mmazzanti/SLMcontroller/master/Documentation/Img/settings.png
   :width: 400px
   :align: center





.. |settings| replace:: :mod:`Settings`
.. |slmcontroller| replace:: :mod:`SLM controller`
.. _slmcontroller: https://github.com/mmazzanti/SLM_controller
.. |2pi| replace:: :math:`{2\pi}`