#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2016, James Cammarata <jimi@sngx.net>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

import hashlib
import socket
import time

try:
    import json
    HAS_JSON = True
except ImportError:
    HAS_JSON = False

DOCUMENTATION = '''
---
module: hue_scan
version_added: "2.0"
author: "James Cammarata (@jimi-c)"
short_description: Scans for new Hue lights
description:
- "This module scans for new Hue lights and adds them to the Hue bridge configuration for use".
notes:
- "A maximum 10 lights may be specified at once, per the API documentation."
requirements: []
options:
  bridge:
    required: true
    description:
    - "The address of the Hue hub or controller"
  serial_numbers:
    required: true
    description:
    - "A list of Hue light serial numbers to scan add add to the bridge configuration."
'''

EXAMPLES = '''
# Scan and add new lights
- hue_scan:
    bridge: 192.168.0.1
    serial_numbers:
    - 000001
    - 000002
'''

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

    def search_for_lights(self, serial_numbers):
        url = 'http://%s/api/%s/lights' % (self.bridge, self.token)
        data = dict(deviceid=serial_numbers)
        res = open_url(url, data=json.dumps(data), method='POST')
        return json.load(res)

    def add_new_lights(self, timeout=120):
        url = 'http://%s/api/%s/lights/new' % (self.bridge, self.token)
        time_left = timeout
        while time_left > 0:
            res = open_url(url, method='GET', timeout=5)
            data = json.load(res)
            if 'lastscan' in data and data.get('lastscan') == 'active':
                time.sleep(1)
                time_left -= 1
                continue
            else:
                return data

        return None

def main():

    module = AnsibleModule(
        argument_spec = dict(
            bridge=dict(required=True, type='str'),
            serial_numbers=dict(required=True, type='list'),
        ),
        supports_check_mode=False,
    )

    if not HAS_JSON:
        module.fail_json(msg="The python-hue library is not installed")

    # create our custom Hue() object and validate we're talking to it
    try:
        hue = Hue(bridge=module.params['bridge'])
        hue_config = hue.get_config()
    except Exception, e:
        module.fail_json(msg="Failed to connect to the Hue bridge. Make sure you've registered with it first using the hue_register module. Error was: %s" % str(e))

    try:
        res = hue.search_for_lights(module.params['serial_numbers'])
        if not hue.check_success(res):
            raise Exception("Failed to initiate the search for new lights")

        res = hue.add_new_lights()
        if res is None:
            raise Exception("Failed to add new lights after the scan completed (or the scan took too long)")

        hue_config = hue.get_config()
        module.exit_json(changed=True, msg="Search completed successfully", config=hue_config)
    except Exception, e:
        module.fail_json(msg="Failed to scan/add new lights. Error was: %s" % str(e))

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
main()

