#!/usr/bin/python

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
module: hue_register
version_added: "2.0"
author: "James Cammarata (@jimi-c)"
short_description: Register with a Philips Hue hub.
description:
- Registers with the Phillips Hue hub, so that the python-hue library can interract with it using the REST API.
requirements: []
options:
  bridge:
    required: true
    description:
    - "The address of the Hue hub or controller"
  retries:
    default: 6
    description:
    - "The number of registration attempts to try before giving up."
  retry_time:
    default: 5
    descript:
    - "The time in seconds to wait before attempting the next retry after failure to authenticate."
'''

EXAMPLES = '''
# Register with the Hue hub (after pressing the button on the hub)
- hue_register:
    bridge: 192.168.0.1

'''

class Hue(object):
    def __init__(self, bridge):
        self.bridge = bridge

        # the token code here is copied from python-hue
        # https://github.com/issackelly/python-hue/blob/master/hue/hue.py
        self.token = hashlib.md5("ph-%s" % socket.getfqdn()).hexdigest()

    def get_config(self):
        url = 'http://%s/api/%s' % (self.bridge, self.token)
        res = open_url(url, method='GET', timeout=5)
        return json.load(res)

    def create_user(self):
        url = 'http://%s/api' % (self.bridge,)
        data = dict(devicetype="python-hue", username=self.token)
        res = open_url(url, data=json.dumps(data), method='POST', timeout=5)
        return json.load(res)

def main():

    module = AnsibleModule(
        argument_spec = dict(
            bridge=dict(required=True, type='str'),
            retries=dict(default=6, type='int'),
            retry_time=dict(default=5, type='int'),
        ),
        supports_check_mode=False,
    )

    if not HAS_JSON:
        module.fail_json(msg="The python-hue library is not installed")

    # create our custom Hue() object and validate we're talking to it
    changed = False
    try:
        hue = Hue(bridge=module.params['bridge'])
        hue_config = hue.get_config()
        if isinstance(hue_config, list) and 'error' in hue_config[0]:
            raise Exception("")
        message = "Already authenticated"
    except:
        num_retries = module.params.get('retries')
        retry_time  = module.params.get('retry_time')
        while num_retries >= 0:
            try:
                res = hue.create_user()
                if isinstance(res, list) and 'error' in res[0]:
                    raise Exception("Error result: %s" % res)
                hue_config = hue.get_config()
                message = "Hue bridge authentication successful."
                changed = True
                break
            except Exception, e:
                if num_retries > 0:
                    time.sleep(retry_time)
                num_retries -= 1
                continue

        if not changed:
            module.fail_json(msg="Failed to connect to the Hue bridge. Make sure you've registered with it first using the hue_register module.")

    module.exit_json(changed=changed, msg=message, config=hue_config)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
main()

