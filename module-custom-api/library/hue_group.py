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
import re
import socket
import time

try:
    import json
    HAS_JSON = True
except ImportError:
    HAS_JSON = False

DOCUMENTATION = '''
---
module: hue_group
version_added: "2.0"
author: "James Cammarata (@jimi-c)"
short_description: Manage Hue bridge light groups
description:
- "Manages light groups on a Hue bridge."
requirements: []
options:
  bridge:
    required: true
    description:
    - "The address of the Hue hub or controller"
  name:
    required: true
    description:
    - "The group identifier, which mathes the format 'gX' where X is the actual id on the Hue bridge."
  state:
    choices: [present, absent]
    default: present
    description:
    - "The desired state of the group. C(present) creates or updates the group while C(absent) removes the group."
  lights:
    required: true
    description:
    - "A list of lights which should be members of the group. These can be of the form C(X) or C(lX) where C(X) is the id of the light on the Hue bridge."
  group_type:
    default: LightGroup
    choices: [LightGroup, Room, Lightsource, Luminaire]
    description:
    - "The group type. C(LightGroups) and C(Rooms) are functionally equivalent, with the exception that C(LightGroups) can be created with 0 lights. This value is case-sensitive."
  group_class:
    default: Other
    choices: [Living room, Kitchen, Dining, Bedroom, Kids bedroom, Bathroom, Nursery, Recreation, Office, Gym, Hallway, Toilet, Front door, Garage, Terrace, Garden, Driveway, Carport, Other]
    description:
    - "The group class for the group. This value is case-sensitive."
'''

EXAMPLES = '''
# Create a new group with some lights
- hue_group:
    bridge: 192.168.0.1
    name: my_group
    state: present
    lights: [l1, l2, l3]

# Delete a group
- hue_group:
    bridge: 192.168.0.1
    name: my_group
    state: absent

'''

HUE_GROUP_TYPES = [
    "Luminaire", "Lightsource", "LightGroup", "Room",
]

HUE_GROUP_CLASSES = [
    "Living room", "Kitchen", "Dining", "Bedroom", "Kids bedroom", "Bathroom",
    "Nursery", "Recreation", "Office", "Gym", "Hallway", "Toilet", "Front door",
    "Garage", "Terrace", "Garden", "Driveway", "Carport", "Other",
]

STATE_FIELDS = ["name", "lights", "type", "class"]

class Hue(object):
    def __init__(self, bridge):
        self.bridge = bridge

        # the token code here is copied from python-hue
        # https://github.com/issackelly/python-hue/blob/master/hue/hue.py
        self.token = hashlib.md5("ph-%s" % socket.getfqdn()).hexdigest()

    def check_success(self, result):
        for status in result:
            if 'error' in status.keys():
                return False
        return True

    def get_config(self):
        url = 'http://%s/api/%s' % (self.bridge, self.token)
        res = open_url(url, method='GET', timeout=5)
        return json.load(res)

    def get_group_state(self, target):
        url = 'http://%s/api/%s/groups/%s' % (self.bridge, self.token, target)
        res = open_url(url, method='GET', timeout=5)
        return json.load(res)

    def create_group(self, state):
        url = 'http://%s/api/%s/groups' % (self.bridge, self.token)
        res = open_url(url, data=json.dumps(state), method='POST', timeout=5)
        return json.load(res)

    def update_group(self, target, state):
        url = 'http://%s/api/%s/groups/%s' % (self.bridge, self.token, target)
        res = open_url(url, data=json.dumps(state), method='PUT', timeout=5)
        return json.load(res)

    def delete_group(self, target):
        url = 'http://%s/api/%s/groups/%s' % (self.bridge, self.token, target)
        res = open_url(url, method='DELETE', timeout=5)
        return json.load(res)


def build_state(module, cur_state):
    '''
    Builds the state based on the module params and the current state
    of the given group object from the Hue bridge..
    '''

    if cur_state is None:
        cur_state = dict()

    group_state = dict()

    name = module.params.get('name')
    if name is not None:
        group_state['name'] = name

    group_type = module.params.get('type')
    if group_type is not None:
        group_state['type'] = group_type

    group_class = module.params.get('class')
    if group_class is not None:
        group_state['class'] = group_class

    lights = module.params.get('lights')
    if lights is not None:
        if not isinstance(lights, list):
            module.fail_json(msg="The lights specified must be a list, instead got a %s" % type(lights))
        final_lights = []
        for light in lights:
           if isinstance(light, int):
               final_lights.append(str(light))
           elif isinstance(light, basestring):
               if light.startswith('l'):
                   final_lights.append(light[1:])
               else:
                   final_lights.append(light)
           else:
               module.fail_json(msg="Invalid light id specified (%s, type %s) in the list of lights" % (light, type(light)))
        group_state['lights'] = final_lights

    # Test to see if any fields changed. We only test those set in
    # the global constant as we don't want to set any fields outside
    # of those        
    changed = False
    for field in STATE_FIELDS:
        if field in group_state and cur_state.get(field) != group_state.get(field):
            changed = True
            break

    return (changed, group_state)

def main():

    module = AnsibleModule(
        argument_spec = dict(
            bridge=dict(required=True, type='str'),
            id=dict(type='str'),
            name=dict(type='str'),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            lights=dict(type='list'),
            group_type=dict(default='LightGroup', choices=HUE_GROUP_TYPES, type='str'),
            group_class=dict(default='Other', choices=HUE_GROUP_CLASSES, type='str'),
        ),
        mutually_exclusive=(('id', 'name'),),
        required_one_of=(('id', 'name'),),
        supports_check_mode=False,
    )

    if not HAS_JSON:
        module.fail_json(msg="This module requires json.")

    # create our custom Hue() object and validate we're talking to it
    try:
        hue = Hue(bridge=module.params['bridge'])
        hue_config = hue.get_config()
    except Exception, e:
        module.fail_json(msg="Failed to connect to the Hue bridge. Make sure you've registered with it first using the hue_register module. Error was: %s" % str(e))

    # set initial flags
    changed = False
    failed  = False

    # Get the targeted lights name from the module params. If no id is specified,
    # we search through the groups for one matching the given group name.
    group_id = module.params['id']
    group_name = module.params['name']
    group_state = None
    if group_id is None:
        for _id, group_config in iter(hue_config.get('groups', {}).items()):
            if group_config.get('name') == group_name:
                group_id = _id
                group_state = group_config
                break
    else:
        matched_group = re.compile(r'^g?([0-9]+)$').match(group_id)
        if not matched_group:
            module.fail_json(msg="Invalid group id '%s' specified. The group id should be of the form 'gX' or 'X' where 'X' is the integer id on the Hue hub" % group_id)
        else:
            group_id = matched_group.group(0)
            group_state = hue_config.get('groups', {}).get(group_id)

    state = module.params['state']

    if state == 'absent':
        if group_state is None:
            message = "The specified group id or name was not found."
        else:
            changed = True
            message = "The specified group id or name was removed successfully."
            if not module.check_mode:
                res = hue.delete_group(group_id)
                failed = not hue.check_success(res)

        if failed:
            module.fail_json(msg="Failed to remove the group '%s'. Delete result was: %s" % (group_id or group_name,), res=res)
        else:
            module.exit_json(msg=message, changed=changed)
    elif state == 'present':
        if group_id is not None and group_name is None and group_state is None:
            module.fail_json(msg="Error, the group was not found but no group name was specified for group creation.")

        changed, desired_state = build_state(module, group_state)
        if group_id is None:
            if 'lights' not in desired_state:
                module.fail_json(msg="Lights must be specified when creating a new group")
            message = "Group created successfully."
            res = hue.create_group(desired_state)
        else:
            message = "Group updated successfully."
            res = hue.update_group(group_id, desired_state)

        failed = not hue.check_success(res)
        if failed:
            module.fail_json(msg="Failed to create/update the group '%s'." % (group_id or group_name,), res=res)
        else:
            if group_id is None:
                group_id = res[0].get('success').get("id")
            group_config = hue.get_group_state(group_id)
            module.exit_json(changed=changed, group=group_config)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
main()

