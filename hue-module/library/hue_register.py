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

import time

try:
    from hue import Hue
    HUE_AVAILABLE = True
except ImportError:
    HUE_AVAILABLE = False

DOCUMENTATION = '''
---
module: hue_register
version_added: "2.0"
author: "James Cammarata (@jimi-c)"
short_description: Register with a Philips Hue hub.
description:
- Registers with the Phillips Hue hub, so that the python-hue library can interract with it using the REST API.
requirements:
- python-hue
options:
  bridge:
    required: true
    description:
    - "The address of the Hue hub or controller"
'''

EXAMPLES = '''
# Register with the Hue hub (after pressing the button on the hub)
- hue_register:
    bridge: 192.168.0.1

'''

def main():

    module = AnsibleModule(
        argument_spec = dict(
            bridge=dict(required=True, type='str'),
        ),
        supports_check_mode=False,
    )

    if not HUE_AVAILABLE:
        module.fail_json(msg="The python-hue library is not installed")

    # Connect and authenticate to the Hue hub
    try:
        h = Hue()
        h.station_ip = module.params['bridge']
        h.authenticate()
    except Exception, e:
        module.fail_json(msg="Failed to authenticate to the Hue hub. Make sure you've pushed the button on the hub recently. Error was: %s" % str(e))

    module.exit_json(changed=True, msg="Successfully authenticated with the Hue hub")

# import module snippets
from ansible.module_utils.basic import *
main()

