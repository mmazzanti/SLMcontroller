#!/usr/bin/env python

"""Remote_control.py: Generates a remote control for the SLM."""

__author__ = "Matteo Mazzanti"
__copyright__ = "Copyright 2022, Matteo Mazzanti"
__license__ = "GNU GPL v3"
__maintainer__ = "Matteo Mazzanti"

# -*- coding: utf-8 -*-
from flask import Flask, jsonify, abort, request, make_response, send_file


host_name = "127.0.0.1"
port = 50000

class NetworkManager(object):
    """Class used to manage the remote control of the SLM.
    Remote control is done through an HTTP server trying to be as RESTful as possible (but so far, miserably failing)
    Based on Flask.

    Attributes:
        app (Flask): Flask app used to manage the remote control.
    """
    def __init__(self, app, **configs, ):
        """Constructor for the NetworkManager class.

        Args:
            app (Flask): Flask app used to manage the remote control.
        """
        self.app = app
        self.configs(**configs)

    def configs(self, **configs):
        """Sets the configuration of the Flask app.
        """
        for config, value in configs:
            self.app.config[config.upper()] = value

    def before_request(self, address = '127.0.0.1'):
        """Decorator used to limit the access to the server to a specific IP address.

        Args:
            address (str, optional): Allowed IP address for connection. Defaults to '127.0.0.1'.

        Returns:
            abort(403): If the IP address is not the allowed one.
        """
        def limit_remote_addr(self):
            if request.remote_addr != address:
                abort(403)  # Forbidden

    def send_image(self, image, name):
        """Sends an image to the client. Used for remote check of the hologram.

        Args:
            image (image/PNG): Image to send.
            name (string): Filename of the image.

        Returns:
            send_file: HTTP response containing the image.
        """
        return send_file(image, mimetype='image/PNG', as_attachment=False, download_name=name)

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods=['GET'], *args, **kwargs):
        """Adds an endpoint to the Flask app.

        Args:
            endpoint (str, optional): Endpoint to add. Defaults to None.
            endpoint_name (str, optional): Name of the endpoint. Defaults to None.
            handler (function, optional): Function to call when the endpoint is called. Defaults to None.
            methods (list, optional): Allowed methods for the endpoint. Defaults to ['GET'].
        """
        self.app.add_url_rule(endpoint, endpoint_name, handler, methods=methods, *args, **kwargs)


    def run(self, **kwargs):
        """Runs the Flask app.
        """
        self.app.run(**kwargs)

# flask_app = Flask(__name__)
# app = NetworkManager(flask_app)
