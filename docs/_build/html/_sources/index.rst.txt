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

.. |slmcontroller| replace:: :mod:`SLM controller`
.. _slmcontroller: https://github.com/mmazzanti/SLM_controller
.. _1: https://www.nature.com/articles/nphoton.2010.85
.. _2: https://www.frontiersin.org/articles/10.3389/fnano.2022.998656/full