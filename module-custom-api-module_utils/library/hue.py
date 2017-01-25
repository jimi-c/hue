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

DOCUMENTATION = '''
---
module: hue
version_added: "2.0"
author: "James Cammarata (@jimi-c)"
short_description: Control Philips Hue lights
description:
- A module to control Philips Hue lights via the python-hue library.
requirements: []
options:
  bridge:
    required: true
    description:
    - "The address of the Hue hub or controller"
  id:
    required: true
    description:
    - "The id of the light or group to be controlled. For lights, the id should be of the form C(lX), 
       and groups should be of the form C(gX) where X is the id of the the item from the API."
    - "The special id C(all) can also be used, which is an alias for the special '0' group, which
       contains all of the lights connected to the bridge"
    - "Either C(id) or C(name) must be specified."
  name:
    required: true
    descriptioni:
    - "The name of the light or group to be controlled."
    - "Either C(id) or C(name) must be specified."
  on:
    default: true
    description:
    - "On/Off state of the light. On=true, Off=false, and it defaults to C(true)."
  brightness:
    description:
    - "An integer value from 0 to 254, which controls the brightness of the light."
  hue:
    description:
    - "An integer value from 0 to 65535, which controls the hue of the light."
    - "When setting C(hue)/C(saturation), you should not set C(xy), C(color_temp), or C(rgb)."
  saturation:
    description:
    - "An integer value from 0 to 254, which controls the saturation of the light.""
    - "When setting C(hue)/C(saturation), you should not set C(xy), C(color_temp), or C(rgb)."
  xy:
    description:
    - "The x and y coordinates of a color in CIE color space, specified as an array [x, y]. These values should be between 0.0 and 1.0 (inclusive)."
    - "When setting C(xy), you should not set C(hue)/C(saturation), C(color_temp), or C(rgb)."
  color_temp:
    description:
    - "The Mired Color temperature of the light. 2012 connected lights are capable of 153 (6500K) to 500 (2000K)."
    - "When setting C(color_temp), you should not set C(hue)/C(saturation), C(xy), or C(rgb)."
  rgb:
    description:
    - "The RGB hex string. The leading C(#) is optional, but the full C(RRGGBB) string must always be specified (no shorthand or aliases allowed)."
    - "When setting C(rgb), you should not set C(hue)/C(saturation), C(xy), or C(color_temp)."
  alert:
    choices: ['none', 'select', 'lselect']
    description:
    - "Sets the C(alert) state of the light. C(none) disables the alert, C(select) makes it flash once, and C(lselect) makes it flash for 15 seconds."
  effect:
    choices: ['none', 'colorloop']
    description:
    - "Sets the C(effect) state of the light. C(none) disables effects, and C(colorloop) will cause the light to cycle through all hues using the current brightness and saturation settings."
  transition_time:
    description:
    - "The duration of the transition from the light’s current state to the new state as a multiple of 100ms. The API default is 4 (400ms)."
'''

EXAMPLES = '''
# Turn all of the lights on and make their colors loop
- hue:
    bridge: 192.168.0.1
    id: all
    brightness 254
    effect: colorloop

# Turn off the first light
- hue:
    bridge: 192.168.0.1
    id: l1
    !!str on: false

# Update light group 1
- hue:
    bridge: 192.168.0.1
    name: "Test Group 1"
    rgb: "#ff00ff"
    brightness: 128
'''

STATE_FIELDS = ('on', 'bri', 'hue', 'sat', 'xy', 'ct', 'alert', 'effect',)

def hex2rgb(hex):
    '''
    Converts a hex string to an RGB value.
    '''
    hex = hex.lstrip('#')
    assert len(hex) == 6
    return (int(hex[0:2], 16), int(hex[2:4], 16), int(hex[4:6], 16))

def rgb2xy(r, g, b):
    '''
    Converts an RGB value to xyz coordinates, based on matrix transformations
    of colorspace values here (Wide Gamut RGB):
    http://www.brucelindbloom.com/index.html?Eqn_RGB_XYZ_Matrix.html
    '''
    X = 0.7161046 * r + 0.1009296 * g + 0.1471858 * b
    Y = 0.2581874 * r + 0.7249378 * g + 0.0168748 * b
    Z = 0.0000000 * r + 0.0517813 * g + 0.7734287 * b
    x = X / (X+Y+Z)
    y = Y / (X+Y+Z)
    return [x, y]

def build_state(module, cur_state):
    '''
    Builds the state based on the module params and the current state
    of the given light object from the Hue bridge.
    '''
    thing_state = dict()

    # set the 'on' state
    thing_state['on'] = module.params.get('on')

    # set the brightness
    bri = module.params.get('brightness', None)
    if bri is not None:
        thing_state['bri'] = bri

    # set the alert
    alert = module.params.get('alert', None)
    if alert is not None:
        alert = alert.lower()
        if alert not in ('none', 'select', 'lselect'):
            module.fail_json(msg="The alert setting must be one of the following values: none, select or lselect")
        thing_state['alert'] = alert

    # set the effect
    effect = module.params.get('effect', None)
    if effect is not None:
        effect = effect.lower()
        if effect not in ('none', 'colorloop'):
            module.fail_json(msg="The effect setting must be one of the following values: none or colorloop")
        thing_state['effect'] = effect

    # set the transition time
    transition_time = module.params.get('transition_time', None)
    if transition_time is not None:
        thing_state['transitiontime'] = transition_time

    # Figure out which color mode we're using...
    if 'hue' in module.params or 'saturation' in module.params:
        hue = module.params.get('hue', None)
        if hue is not None:
            thing_state['hue'] = hue
        sat = module.params.get('saturation', None)
        if sat is not None:
            thing_state['sat'] = sat
    elif 'xy' in module.params or 'rgb' in module.params:
        if 'rgb' in module.params:
            # The Hue doesn't support RGB by default, and python-hue does
            # the conversion internally. So to make sure we can preserve
            # idempotency we do the conversion calculation ourselves
            try:
                x, y = rgb2xyz(hex2rgb(module.params['rgb']))
            except:
                module.fail_json(msg="Invalid RGB hex string: %s" % module.params['rgb'])
        else:
            try:
                x, y = module.params['xy']
                assert isinstance(x, (int, float)) and x >= 0.0 and x <= 1.0
                assert isinstance(y, (int, float)) and y >= 0.0 and y <= 1.0
            except:
                module.fail_json(msg="Invalid xy value. Expected an array of 2 floating point values (0.0 >= [x,y] >= 1.0) but got %s" % (module.params['xy'],))

        thing_state['xy'] = [x, y]
    elif 'color_temp' in module.params:
        ct = module.params['color_temp']
        if ct < 153 or ct > 500:
            module.warning('The color temperature specified (%d) may be outside of the recommend range (153-500) listed in the Hue API documentation' % ct)
        thing_state['ct'] = ct

    # Test to see if any fields changed. We only test those set in
    # the global constant as we don't want to set any fields outside
    # of those        
    changed = False
    for field in STATE_FIELDS:
        if field in thing_state and cur_state.get(field) != thing_state.get(field):
            changed = True
            break

    return (changed, thing_state)

def main():

    module = AnsibleModule(
        argument_spec = dict(
            bridge=dict(required=True, type='str'),
            id=dict(type='str'),
            name=dict(type='str'),
            on=dict(default=True, type='bool'),
            brightness=dict(type='int'),
            hue=dict(type='int'),
            saturation=dict(type='int'),
            xy=dict(type='list'),
            color_temp=dict(type='int'),
            rgb=dict(type='str'),
            alert=dict(type='str', choices=['none', 'select', 'lselect']),
            effect=dict(type='str', choices=['none', 'colorloop']),
            transition_time=dict(type='int'),
        ),
        mutually_exclusive=(('id', 'name'), ('hue', 'xy', 'color_temp', 'rgb'), ('saturation', 'xy', 'color_temp', 'rgb')),
        required_one_of=(('id', 'name'),),
        supports_check_mode=True
    )

    # create our custom Hue() object and validate we're talking to it
    try:
        hue = Hue(bridge=module.params['bridge'])
        hue_config = hue.get_config()
    except Exception, e:
        module.fail_json(msg="Failed to connect to the Hue bridge. Make sure you've registered with it first using the hue_register module. Error was: %s" % str(e))

    # set initial flags
    changed = False
    failed  = False

    # get the targeted lights name from the module params
    thing_id = module.params['id']
    thing_name = module.params['name']
    if thing_id is None and thing_name != 'all':
        # search lights and then groups for something with 'name'
        for light_id, light_config in iter(hue_config.get('lights', {}).items()):
            if light_config.get('name') == thing_name:
                thing_id = "l%s" % light_id
                break
        else:
            for group_id, group_config in iter(hue_config.get('groups', {}).items()):
                if group_config.get('name') == thing_name:
                    thing_id = "g%s" % group_id
                    break
            else:
                module.fail_json(msg="There is no light or group on the Hue bridge named '%s'" % thing_name)

    # Compile the state (or list of states when using 'all' for the light name).
    # The final_states dict will hold the final state of each light
    target_states = dict()
    final_states = dict()

    # First we build the list of lights we're going to check
    if thing_name == 'all' or thing_id == 'g0' or thing_id == 'all':
        ids_to_check = [ "g0" ]
    else:
        real_id = thing_id[1:]
        if thing_id.startswith('l'):
            the_thing = hue_config.get('lights', {}).get(real_id)
        elif thing_id.startswith('g'):
            the_thing = hue_config.get('groups', {}).get(real_id) 
        else:
            module.fail_json(msg="Invalid light or group name: '%s'" % (thing_name or thing_id,))
            
        if the_thing is None:
            module.fail_json(msg="Failed to find light or group '%s'. Make sure that the light was turned on." % (thing_name or thing_id,))
        else:
            ids_to_check = [ thing_id ]

    # Then, for each light in the list, fetch the current state and build
    # the desired state (assuming the light is reachable)
    for _id in ids_to_check:
        thing_state = hue.get_state(_id)
        if not thing_state.get('state', {}).get('reachable', True):
            final_states[_id] = thing_state
            failed = True
        else:
            if _id.startswith('l'):
                thing_state = thing_state.get('state')
            elif _id.startswith('g'):
                thing_state = thing_state.get('action')

            state_changed, desired_state = build_state(module, thing_state)
            changed |= state_changed
            target_states[_id] = desired_state

    # Next, we set the state of each light as requested above
    for target_thing, target_state in iter(target_states.items()):
        if not module.check_mode and len(target_state) > 0:
            # get the light and set the state
            result = hue.set_state(target_thing, target_state)
            failed = not hue.check_success(result)

        # save the state for the final module result
        final_states[target_thing] = hue.get_state(target_thing)

    # If one or more lights failed, fail the module, otherwise return
    # whether or not we changed. In both cases, we return the state of
    # the lights which were specified.
    if failed:
        if thing_name == 'all':
            module.fail_json(msg="One or more lights failed to update.", light_states=final_states)
        else:
            module.fail_json(msg="The light or group '%s' failed to update.", light_states=final_states)
    else:
        module.exit_json(changed=changed, light_states=final_states)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
from ansible.module_utils.hue import *
main()
