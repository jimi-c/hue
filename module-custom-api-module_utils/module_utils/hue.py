import hashlib
import socket
import time

try:
    import json
    HAS_JSON = True
except ImportError:
    HAS_JSON = False

class Hue(object):
    def __init__(self, bridge):
        self.bridge = bridge

        # the token code here is copied from python-hue
        # https://github.com/issackelly/python-hue/blob/master/hue/hue.py
        self.token = hashlib.md5("ph-%s" % socket.getfqdn()).hexdigest()

    def check_success(self, result):
        for status in result:
            if 'failed' in status.keys():
                return False
        return True

    def get_config(self):
        url = 'http://%s/api/%s' % (self.bridge, self.token)
        res = open_url(url, method='GET', timeout=5)
        return json.load(res)

    def get_state(self, target):
        real_target = target[1:]
        if target.startswith('l'):
            url = 'http://%s/api/%s/lights/%s' % (self.bridge, self.token, real_target)
        elif target.startswith('g'):
            url = 'http://%s/api/%s/groups/%s' % (self.bridge, self.token, real_target)
        else:
            raise Exception("Invalid target: %s" % target)

        res = open_url(url, method='GET', timeout=5)
        return json.load(res)

    def set_state(self, target, state):
        real_target = target[1:]
        if target.startswith('l'):
            url = 'http://%s/api/%s/lights/%s/state' % (self.bridge, self.token, real_target)
        elif target.startswith('g'):
            url = 'http://%s/api/%s/groups/%s/action' % (self.bridge, self.token, real_target)
        else:
            raise Exception("Invalid target: %s" % target)

        res = open_url(url, data=json.dumps(state), method='PUT', timeout=5)
        return json.load(res)

