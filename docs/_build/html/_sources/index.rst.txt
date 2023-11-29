.. SLM controller documentation master file, created by
   sphinx-quickstart on Mon Nov 27 14:46:58 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to SLM controller's documentation!
==========================================

|slmcontroller|_ is a python Qt based app for controlling spatial light modulators (SLM).
It allows to control a SLM connected to a second monitor. Phase patterns of optical elements can be added and tuned from the GUI.
The software allows for aberration correction using algorithms described in [`1`_] and [`2`_].


.. toctree::
   :maxdepth: 1
   :caption: Getting Started
   
   installation
   howto
   
.. toctree::
   :maxdepth: 1
   :caption: User Guide

   examples
   settings
   calibration



.. toctree::
   :maxdepth: 1
   :caption: Modules

   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

Acknowledgements
================

SLMcontroller was built and is maintaned by me (Matteo Mazzanti). 
If you find the software useful, please consider be one of the few `buying me a coffee <https://www.buymeacoffee.com/mmazzanti>`_.

.. raw:: html

   <script data-name="BMC-Widget" data-cfasync="false" src="https://cdnjs.buymeacoffee.com/1.0.0/widget.prod.min.js" data-id="mmazzanti" data-description="Support me on Buy me a coffee!" data-message="Hey there! If you like my software consider buying me a coffee :)" data-color="#BD5FFF" data-position="Right" data-x_margin="18" data-y_margin="18">
   </script>

.. |slmcontroller| replace:: :mod:`SLM controller`
.. _slmcontroller: https://github.com/mmazzanti/SLM_controller
.. _1: https://www.nature.com/articles/nphoton.2010.85
.. _2: https://www.frontiersin.org/articles/10.3389/fnano.2022.998656/full