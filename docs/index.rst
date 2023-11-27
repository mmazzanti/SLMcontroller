.. SLM controller documentation master file, created by
   sphinx-quickstart on Mon Nov 27 14:46:58 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to SLM controller's documentation!
==========================================

|SLM controller|_ is a python Qt based app for controlling spatial light modulators (SLM).
It allows to control a SLM connected to a second monitor. Phase patterns of optical elements can be added and tuned from the GUI.
The software allows for aberration correction using algorithms described in [1]_ and [2]_.


.. toctree::
   :maxdepth: 1
   :caption: Getting Started
   installation
   how to

   :caption: User Guide:
   examples
   settings
   calibration


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |SLM controller| replace:: :mod:`SLM controller`
.. _SLMcontroller: https://github.com/mmazzanti/SLM_controller
.. _[1]: https://www.nature.com/articles/nphoton.2010.85
.. _[2]: https://www.frontiersin.org/articles/10.3389/fnano.2022.998656/full