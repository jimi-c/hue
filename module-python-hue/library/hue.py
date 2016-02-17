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
module: hue
version_added: "2.0"
author: "James Cammarata (@jimi-c)"
short_description: Control Philips Hue lights
description:
- A module to control Philips Hue lights via the python-hue library.
requirements:
- python-hue
options:
  bridge:
    required: true
    description:
    - "The address of the Hue hub or controller"
  name:
    required: true
    description:
    - "The id of the light or group to be controlled. For lights, the id should be of the form C(lX), 
       and groups should be of the form C(gX) where X is the id of the the item from the API."
    - "The special id C(all) can also be used, which is an alias for the special '0' group, which
       contains all of the lights connected to the bridge"
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
    name: all
    brightness 254
    effect: colorloop

# Turn off the first light
- hue:
    bridge: 192.168.0.1
    name: l1
    on: false

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
    of the given light object from the python-hue library.
    '''
    light_state = dict()

    # set the 'on' state
    light_state['on'] = module.params.get('on')

    # set the brightness
    bri = module.params.get('brightness', None)
    if bri is not None:
        light_state['bri'] = bri

    # set the alert
    alert = module.params.get('alert', None)
    if alert is not None:
        alert = alert.lower()
        if alert not in ('none', 'select', 'lselect'):
            module.fail_json(msg="The alert setting must be one of the following values: none, select or lselect")
        light_state['alert'] = alert

    # set the effect
    effect = module.params.get('effect', None)
    if effect is not None:
        effect = effect.lower()
        if effect not in ('none', 'colorloop'):
            module.fail_json(msg="The effect setting must be one of the following values: none or colorloop")
        light_state['effect'] = effect

    # set the transition time
    transition_time = module.params.get('transition_time', None)
    if transition_time is not None:
        light_state['transitiontime'] = transition_time

    # Figure out which color mode we're using...
    if 'hue' in module.params or 'saturation' in module.params:
        hue = module.params.get('hue', None)
        if hue is not None:
            light_state['hue'] = hue
        sat = module.params.get('saturation', None)
        if sat is not None:
            light_state['sat'] = sat
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

        light_state['xy'] = [x, y]
    elif 'color_temp' in module.params:
        ct = module.params['color_temp']
        if ct < 153 or ct > 500:
            module.warning('The color temperature specified (%d) may be outside of the recommend range (153-500) listed in the Hue API documentation' % ct)
        light_state['ct'] = ct

    # Test to see if any fields changed. We only test those set in
    # the global constant as we don't want to set any fields outside
    # of those        
    changed = False
    for field in STATE_FIELDS:
        if field in light_state and cur_state.get(field) != light_state.get(field):
            changed = True
            break

    return (changed, light_state)

def main():

    module = AnsibleModule(
        argument_spec = dict(
            bridge=dict(required=True, type='str'),
            name=dict(required=True, type='str'),
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
        mutually_exclusive=(('hue', 'xy', 'color_temp', 'rgb'), ('saturation', 'xy', 'color_temp', 'rgb')),
        supports_check_mode=True
    )

    if not HUE_AVAILABLE:
        module.fail_json(msg="The python-hue library is not installed")

    # Connect to the Hue hub
    try:
        h = Hue()
        h.station_ip = module.params['bridge']
        h.get_state()
    except Exception, e:
        module.fail_json(msg="Failed to connect to the Hue hub. Make sure you've registered using the hue_register module first. Error was: %s" % str(e))

    # set initial flags
    changed = False
    failed  = False

    # get the targeted lights name from the module params
    name  = module.params['name']

    # Compile the state (or list of states when using 'all' for the light name).
    # The final_states dict will hold the final state of each light
    target_lights = dict()
    final_states = dict()

    # First we build the list of lights we're going to check
    if name == 'all':
        lights_to_check = list(h.lights.keys())
    else:
        try:
            # For an individual light, we check now to make sure
            # it's valid with the Hue hub
            the_light = h.lights[name]
            lights_to_check = [ name ]
        except KeyError:
            module.fail_json(msg="Failed to find light '%s'. Make sure that the light was turned on." % name)

    # Then, for each light in the list, fetch the current state and build
    # the desired state (assuming the light is reachable)
    for light_name in lights_to_check:
        the_light = h.lights.get(light_name)
        the_light.update_state_cache()
        if not the_light.state.get('state', {}).get('reachable', True):
            final_states[light_name] = the_light.state.copy()
            failed = True
        else:
            state_changed, desired_state = build_state(module, the_light.state)
            changed |= state_changed
            target_lights[light_name] = desired_state

    # Next, we set the state of each light as requested above
    for target_light, target_state in iter(target_lights.items()):
        the_light = h.lights[target_light]
        if not module.check_mode and len(target_state) > 0:
            # get the light and set the state
            the_light = the_light.set_state(target_state)
            the_light.update_state_cache()
            if not the_light.state.get('state', {}).get('reachable', True):
                failed = True

        # save the state for the final module result
        final_states[target_light] = the_light.state.copy()

    # If one or more lights failed, fail the module, otherwise return
    # whether or not we changed. In both cases, we return the state of
    # the lights which were specified.
    if failed:
        if name == 'all':
            module.fail_json(msg="One or more lights failed to update.", light_states=final_states)
        else:
            module.fail_json(msg="The light '%s' failed to update.", light_state=final_states)
    else:
        module.exit_json(changed=changed, light_states=final_states)

# import module snippets
from ansible.module_utils.basic import *
main()

