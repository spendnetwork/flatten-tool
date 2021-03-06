Getting Started
===============

Prerequisites
-------------

You will need Python 3.5 or later, including the venv module.

Generally the venv module should come with your default Python install, but not on Ubuntu.  On Ubuntu run:

.. code-block:: bash

   sudo apt-get install python3 python3-venv

Installation
------------

.. code-block:: bash

    git clone https://github.com/OpenDataServices/flatten-tool.git
    cd flatten-tool
    python3 -m venv .ve
    source .ve/bin/activate
    pip install -r requirements_dev.txt

Usage
-----

.. code-block:: bash

    flatten-tool -h

will print general help information.

.. code-block:: bash

    flatten-tool {create-template,flatten,unflatten} -h

will print help information specific to that sub-command.

Python Version Support
----------------------

This code supports Python 2.7 and Python 3.5 (and later). Python 3 is
strongly preferred. Only severe Python 2 specific bugs will be fixed, see the
`python2-wontfix <https://github.com/OpenDataServices/flatten-tool/issues?q=is%3Aissue+label%3Apython2-wontfix+is%3Aclosed>`_
label on GitHub for known minor issues.

Python 2.6 and earlier are not supported at all because our code makes use new
language constructs introduced in Python 3 and 2.7. Python 3.4 (and earlier Python 3 versions) is not supported, because one of the dependencies (openpyxl) does not
support it.
