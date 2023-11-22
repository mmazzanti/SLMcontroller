from flask import Flask, jsonify, abort, request, make_response, send_file
import threading
import numpy as np
import time
from PIL import Image
from io import BytesIO

host_name = "127.0.0.1"
port = 23336

class NetworkManager(object):
    def __init__(self, app, **configs, ):
        self.app = app
        self.configs(**configs)

    def configs(self, **configs):
        for config, value in configs:
            self.app.config[config.upper()] = value

    def before_request(self, address = '127.0.0.1'):
        def limit_remote_addr(self):
            if request.remote_addr != address:
                abort(403)  # Forbidden

    def send_image(self, image, name):
        return send_file(image, mimetype='image/PNG', as_attachment=False, download_name=name)

    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods=['GET'], *args, **kwargs):
        self.app.add_url_rule(endpoint, endpoint_name, handler, methods=methods, *args, **kwargs)


    def run(self, **kwargs):
        self.app.run(**kwargs)

flask_app = Flask(__name__)
app = NetworkManager(flask_app)




# Debugging
'''
test = np.random.rand(100,500)

def testaction():
    """ Function which is triggered in flask app """
    return jsonify(test.tolist()) # return
if __name__ == "__main__":
    #app.run(debug=True,ssl_context='adhoc')
    app.add_endpoint('/action', 'action', testaction, methods=['GET'])
    flask_thread = threading.Thread(target=lambda: app.run(host=host_name, port=port, debug=True, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    print("after run")
    time.sleep(10)
    exit(0)
    '''