#!/usr/bin/env python3
"""trackpad-config: read or change the built-in trackpad settings in ~/.config/hypr/trackpad.lua.

The .lua file is generated from a JSON state line at its top. Every write reloads Hyprland and
checks `hyprctl configerrors`; on an error the previous file is put back and the exit code is 1.

  trackpad-config get                         # effective settings as JSON
  trackpad-config set natural_scroll=true scroll_factor=0.6
  trackpad-config reset                       # remove trackpad.lua and the loader block

On the first write a marked block is appended to ~/.config/hypr/input.lua that loads trackpad.lua,
unless input.lua already loads it.
"""
import json, os, re, subprocess, sys, tempfile

TARGET = os.path.expanduser("~/.config/hypr/trackpad.lua")
INPUT = os.path.expanduser("~/.config/hypr/input.lua")
PLUGIN_ID = "io.github.2strange.trackpad"
MARK_BEGIN = f"-- >>> {PLUGIN_ID} >>>"
MARK_END = f"-- <<< {PLUGIN_ID} <<<"
LOADER = f"""
{MARK_BEGIN}
-- Trackpad bar plugin: loads the settings it writes. Removed by `trackpad-config.py reset`.
local trackpad_settings = os.getenv("HOME") .. "/.config/hypr/trackpad.lua"
local trackpad_file = io.open(trackpad_settings)
if trackpad_file then
  trackpad_file:close()
  dofile(trackpad_settings)
end
{MARK_END}
"""
# Built-in trackpads: Apple (bcm5974, applespi) and everything libinput names a touchpad.
DEVICE_HINTS = ("bcm5974", "applespi", "touchpad", "trackpad")
STATE_PREFIX = "-- state: "

# key -> (type, live hyprctl option or None, fallback)
SPEC = {
    "natural_scroll":       (bool,  "input:touchpad:natural_scroll", False),
    "scroll_factor":        (float, "input:touchpad:scroll_factor", 0.4),
    "sensitivity":          (float, None, 0.0),
    "tap_to_click":         (bool,  "input:touchpad:tap-to-click", True),
    "tap_and_drag":         (bool,  "input:touchpad:tap-and-drag", True),
    "clickfinger_behavior": (bool,  "input:touchpad:clickfinger_behavior", True),
    "disable_while_typing": (bool,  "input:touchpad:disable_while_typing", True),
    "swipe_use_r":          (bool,  "gestures:workspace_swipe_use_r", False),
    "swipe_invert":         (bool,  "gestures:workspace_swipe_invert", True),
    "swipe_end":            (str,   None, "new"),   # at the last workspace: "stop", "new" or "wrap" (around)
    "swipe_fingers":        (int,   None, 3),       # fingers for the workspace swipe; 0 = the plugin adds no gesture
}
SWIPE_ENDS = ("stop", "new", "wrap")


def hyprctl(*args):
    return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=5).stdout


def live(option, typ):
    try:
        data = json.loads(hyprctl("getoption", "-j", option))
    except (ValueError, subprocess.SubprocessError):
        return None
    for k in ("bool", "float", "int"):
        if k in data:
            return typ(data[k])
    return None


def touchpad_device():
    """Name of the built-in trackpad as Hyprland knows it, or None."""
    try:
        mice = json.loads(hyprctl("devices", "-j")).get("mice", [])
    except (ValueError, subprocess.SubprocessError, AttributeError):
        return None
    for mouse in mice:
        name = str(mouse.get("name", ""))
        if any(hint in name.lower() for hint in DEVICE_HINTS):
            return name
    return None


def saved():
    try:
        with open(TARGET) as f:
            first = f.readline()
    except FileNotFoundError:
        return {}
    if first.startswith(STATE_PREFIX):
        try:
            return json.loads(first[len(STATE_PREFIX):])
        except ValueError:
            pass
    return {}


def effective():
    state = saved()
    if "swipe_end" not in state and "swipe_create_new" in state:  # settings from version 1.0
        state["swipe_end"] = "new" if state["swipe_create_new"] else "stop"
    if state.get("swipe_end") not in SWIPE_ENDS:
        state.pop("swipe_end", None)
    if state.get("swipe_fingers") not in (0, 3, 4):
        state.pop("swipe_fingers", None)
    if "swipe_fingers" not in state and gesture_conflict(SPEC["swipe_fingers"][2]):
        # input.lua already has a swipe on these fingers (version 1.0 told people to add one):
        # a second one would make Hyprland reject every change, so start with ours off
        state["swipe_fingers"] = 0
    out = {}
    for key, (typ, option, fallback) in SPEC.items():
        value = state.get(key)
        if value is None and option:
            value = live(option, typ)
        out[key] = typ(fallback if value is None else value)
    return out


def lua_string(text):
    out = []
    for ch in text:
        if ch in ('"', "\\"):
            out.append("\\" + ch)
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append("\\%03d" % ord(ch))
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def lua(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return repr(round(v, 4))


def gesture_lua(s):
    """The workspace swipe. Stop and new use Hyprland's own 1:1 swipe; Hyprland cannot wrap
    around, so "wrap" is two discrete gestures that jump to the next or previous open workspace."""
    fingers = int(s["swipe_fingers"])
    if fingers <= 0:
        return ""
    if s["swipe_end"] != "wrap":
        return f'''
-- Workspace swipe with {fingers} fingers (Hyprland's own, follows the fingers).
hl.gesture({{ fingers = {fingers}, direction = "horizontal", action = "workspace" }})
'''
    # natural (invert on): fingers moving left bring in the next workspace
    nxt, prv = ("left", "right") if s["swipe_invert"] else ("right", "left")
    return f'''
-- Workspace swipe with {fingers} fingers, wrapping around at the ends (fires when the swipe ends).
hl.gesture({{ fingers = {fingers}, direction = "{nxt}", action = function() hl.dispatch(hl.dsp.focus({{ workspace = "e+1" }})) end }})
hl.gesture({{ fingers = {fingers}, direction = "{prv}", action = function() hl.dispatch(hl.dsp.focus({{ workspace = "e-1" }})) end }})
'''


GESTURE_RE = re.compile(r"hl\.gesture\s*\(\s*\{(.*?)\}\s*\)", re.S)
HORIZONTAL = ("horizontal", "left", "right", "swipe")


def gesture_conflict(fingers):
    """input.lua (outside our block) has a gesture Hyprland would refuse next to ours:
    same finger count, a horizontal direction and no modifier, whatever its action."""
    if int(fingers) <= 0:
        return False
    text = without_loader(read(INPUT) or "")
    text = re.sub(r"--\[(=*)\[.*?\]\1\]", "", text, flags=re.S)  # block comments
    text = re.sub(r"--[^\n]*", "", text)  # line comments
    for spec in GESTURE_RE.findall(text):
        f = re.search(r"fingers\s*=\s*(\d+)", spec)
        d = re.search(r"direction\s*=\s*[\"']([^\"']+)", spec)
        if f and d and int(f.group(1)) == int(fingers) and d.group(1) in HORIZONTAL and "mods" not in spec:
            return True
    return False


def render(s, device):
    text = f"""{STATE_PREFIX}{json.dumps(s, sort_keys=True)}
-- Generated by the Trackpad bar plugin ({PLUGIN_ID}). Edit through the trackpad menu, not by hand.
-- Loaded from hypr/input.lua.
hl.config({{
  input = {{
    touchpad = {{
      natural_scroll = {lua(s["natural_scroll"])},
      scroll_factor = {lua(s["scroll_factor"])},
      tap_to_click = {lua(s["tap_to_click"])},
      tap_and_drag = {lua(s["tap_and_drag"])},
      clickfinger_behavior = {lua(s["clickfinger_behavior"])},
      disable_while_typing = {lua(s["disable_while_typing"])},
    }},
  }},
  gestures = {{
    workspace_swipe_use_r = {lua(s["swipe_use_r"])},
    workspace_swipe_invert = {lua(s["swipe_invert"])},
    workspace_swipe_create_new = {lua(s["swipe_end"] == "new")},
  }},
}})
"""
    text += gesture_lua(s)
    if device:
        text += f"""
-- Pointer speed for the built-in trackpad only (the mouse keeps its own).
hl.device({{
  name = {lua_string(device)},
  sensitivity = {lua(s["sensitivity"])},
}})
"""
    return text


def parse(key, raw):
    typ = SPEC[key][0]
    if key == "swipe_end":
        if raw not in SWIPE_ENDS:
            raise ValueError(f"{key} wants one of {', '.join(SWIPE_ENDS)}")
        return raw
    if key == "swipe_fingers":
        value = int(raw)
        if value not in (0, 3, 4):
            raise ValueError(f"{key} wants 0, 3 or 4")
        return value
    if typ is bool:
        if raw.lower() not in ("true", "false"):
            raise ValueError(f"{key} wants true/false")
        return raw.lower() == "true"
    value = float(raw)
    if key == "sensitivity":
        value = max(-1.0, min(1.0, value))
    elif key == "scroll_factor":
        value = max(0.05, min(3.0, value))
    return value


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return None


def put(path, text):
    """Atomic write; None removes the file."""
    path = os.path.realpath(path)  # write through a symlink (dotfile managers) instead of replacing it
    if text is None:
        if os.path.exists(path):
            os.remove(path)
        return
    try:
        mode = os.stat(path).st_mode & 0o7777
    except FileNotFoundError:
        mode = 0o644
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".trackpad.", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def without_loader(text):
    if MARK_BEGIN not in text:
        return text
    head, _, rest = text.partition(MARK_BEGIN)
    if MARK_END not in rest:
        return text  # end marker deleted by hand: leave the file alone rather than cut too much
    _, _, tail = rest.partition(MARK_END)
    return head.rstrip("\n") + "\n" + tail.lstrip("\n")


def apply(changes):
    """Write {path: text}, reload Hyprland, and put every file back if it reports errors."""
    old = {path: read(path) for path in changes}
    try:
        before = hyprctl("configerrors").strip()
        for path, text in changes.items():
            put(path, text)
        hyprctl("reload")
        errors = hyprctl("configerrors").strip()
    except Exception as err:  # hyprctl missing or timing out: never leave a half-applied change
        errors, before = f"trackpad-config: {err}", None
    if errors and errors != before:
        for path, text in old.items():
            put(path, text)
        try:
            hyprctl("reload")
        except Exception:
            pass
        print(errors, file=sys.stderr)
        return 3 if "overshadowed by a previous gesture" in errors else 1
    return 0


def write(state):
    changes = {TARGET: render(state, touchpad_device())}
    current = read(INPUT) or ""
    # Leave input.lua alone when it already loads trackpad.lua (marked block or a hand-written one).
    if "trackpad.lua" not in current and "hypr.trackpad" not in current:
        changes[INPUT] = current.rstrip("\n") + "\n" + LOADER
    return apply(changes)


def reset():
    changes = {TARGET: None}
    current = read(INPUT)
    if current and MARK_BEGIN in current:
        changes[INPUT] = without_loader(current)
    return apply(changes)


def main(argv):
    if len(argv) >= 1 and argv[0] == "get":
        out = effective()
        out["gesture_conflict"] = gesture_conflict(out["swipe_fingers"])
        print(json.dumps(out))
        return 0
    if len(argv) == 1 and argv[0] == "reset":
        return reset()
    if len(argv) >= 2 and argv[0] == "set":
        state = effective()
        for pair in argv[1:]:
            key, _, raw = pair.partition("=")
            if key not in SPEC:
                print(f"unknown key: {key}", file=sys.stderr)
                return 2
            try:
                state[key] = parse(key, raw)
            except ValueError as err:
                print(f"bad value for {key}: {err}", file=sys.stderr)
                return 2
        return write(state)
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
