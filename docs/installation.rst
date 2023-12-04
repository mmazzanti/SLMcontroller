.. _installation:

Installation
============

From PyPI (recommended)
------------------------
You can install directly |slmcontroller|_ from PyPI using the following command:

.. code-block:: python
   
   pip install SLMcontroller

afterwards you can run the following command to start the software:

.. code-block:: python
   
   python3 -m SLMcontroller

or 

.. code-block:: python
   
   SLMcontroller

From source
-----------

Download the latest stable release `here`_.
You can use either the precompiled binaries or compile the source code yourself.

Once downloaded move the folder ``SLMcontroller`` to a location of your choice.
I will refer to this location as ``<INSTALLATION_PATH>``.

First step is to install all the necessary dependencies (see below).
Do so by running the following command:

.. code-block:: python
   
   pip3 install -r <INSTALLATION_PATH>/SLMcontroller/requirements.txt

Then, you can run the following command to start the software:

.. code-block:: python
   
   python3 <INSTALLATION_PATH>/SLMcontroller/SLMcontroller.py

The following GUI should appear on your screen:

.. image:: _static/main.png
  :width: 300
  :alt: GUI
  :align: center

See the :ref:`how-to` section for more information on how to use the software.

Dependencies
------------

The following dependencies are required to run |slmcontroller|_:

- `Flask <https://flask.palletsprojects.com/>`_: Used for remote control of the SLM.
- `PyQt6 <https://www.riverbankcomputing.com/software/pyqt/>`_: Used for the GUI.
- `Gmsh <https://pygmsh.readthedocs.io/en/latest/index.html>`_: Used for meshing the SLM surface.
- `Numba <https://numba.pydata.org/>`_: Used for accelerating the computation of the phase patterns.
- `NumPy <https://numpy.org/>`_: Handling mathematical operations.
- `OpenCV <https://opencv.org/>`_: Used for image processing (when optimizing for aberration using a camera).
- `Pillow <https://pillow.readthedocs.io/en/stable/>`_: Used to show remotely the phase patterns of the SLM.


You can use ``pip install -r docs/requirements.txt`` to install all the required dependencies directly.

.. raw:: html

   <script data-name="BMC-Widget" data-cfasync="false" src="https://cdnjs.buymeacoffee.com/1.0.0/widget.prod.min.js" data-id="mmazzanti" data-description="Support me on Buy me a coffee!" data-message="Hey there! If you like my software consider buying me a coffee :)" data-color="#BD5FFF" data-position="Right" data-x_margin="18" data-y_margin="18">
   </script>


.. |slmcontroller| replace:: :mod:`SLM controller`
.. _slmcontroller: https://github.com/mmazzanti/SLM_controller
.. _here: https://github.com/mmazzanti/SLM_controller
