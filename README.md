# Trackpad

Omarchy bar plugin for the built-in trackpad. Click the trackpad icon in the bar
(tabs: Pointer, Scroll, Click, Swipe) and change scrolling, pointer speed, tapping, clicking and the three-finger
workspace swipe. Every switch applies live; sliders apply when you let go.

![Trackpad menu in the Omarchy bar](preview.png)

## Settings

| Section | Setting | Hyprland option |
| --- | --- | --- |
| Pointer | Tracking speed (trackpad only, a mouse keeps its own) | `device { sensitivity }` |
| Scrolling | Natural scrolling | `input:touchpad:natural_scroll` |
| | Scroll speed | `input:touchpad:scroll_factor` |
| Clicking | Tap to click | `input:touchpad:tap-to-click` |
| | Tap and drag | `input:touchpad:tap-and-drag` |
| | Two-finger click is a right click | `input:touchpad:clickfinger_behavior` |
| | Ignore trackpad while typing | `input:touchpad:disable_while_typing` |
| Workspace swipe | Include empty workspaces | `gestures:workspace_swipe_use_r` |
| | At the last workspace: stop, new one, wrap around | `gestures:workspace_swipe_create_new` / own gestures |
| | Fingers: off, 3, 4 | `hl.gesture` in `trackpad.lua` |
| | Invert swipe direction | `gestures:workspace_swipe_invert` |

The plugin adds the workspace swipe itself (3 fingers by default; 4 fingers or
Off on the Swipe tab). If your `~/.config/hypr/input.lua` defines its own
horizontal `hl.gesture(...)` with the same number of fingers (whatever its
action), Hyprland refuses the second one: remove that line or set Fingers to Off.
The menu warns when both are active, and until then changes are rolled back.

**Upgrading from 1.0:** version 1.0 asked you to enable the swipe in `input.lua`.
If that line is still there, the plugin starts with Fingers set to Off, so your
swipe keeps working; remove the line and pick 3 or 4 fingers to get the new
end-of-row options.

**At the last workspace** you can stop, open a new workspace, or wrap around to
the first one. Stop and New one use Hyprland's own swipe, which follows your
fingers. Hyprland's swipe cannot wrap, so Wrap around uses two gestures that
switch to the next or previous open workspace when the swipe ends. Wrap around
always skips empty workspaces, so Include empty workspaces has no effect there.

## Install

```sh
omarchy plugin add https://github.com/2strange/omarchy-trackpad.git --enable
```

No password and no packages: the plugin only writes files in `~/.config/hypr/`.

## How it works

- The menu calls `trackpad-config.py`, which writes `~/.config/hypr/trackpad.lua`
  from a JSON state line at the top of that file, reloads Hyprland and checks
  `hyprctl configerrors`. If Hyprland reports a new error, every file it touched
  is put back and the menu shows "rolled back". Errors that were already there
  before the change do not block it.
- On the first change it appends one marked block to `~/.config/hypr/input.lua`
  that loads `trackpad.lua`, unless `input.lua` already loads it. Nothing else in
  `input.lua` is modified. The block sits at the end of `input.lua`, so the menu
  wins over touchpad settings earlier in that file. If `input.lua` mentions
  `trackpad.lua` anywhere (even in a comment), the plugin assumes you load it
  yourself and adds nothing.
- The pointer speed is set per device. The plugin picks the first pointer whose
  name contains `bcm5974`, `applespi`, `touchpad` or `trackpad`; without one, the
  speed slider has no effect.
- Settings you never touched follow your current Hyprland values.

From a terminal:

```sh
cd ~/.config/omarchy/plugins/io.github.2strange.trackpad
python3 trackpad-config.py get
python3 trackpad-config.py set natural_scroll=true scroll_factor=0.6
```

## Remove

```sh
python3 ~/.config/omarchy/plugins/io.github.2strange.trackpad/trackpad-config.py reset
omarchy plugin remove io.github.2strange.trackpad
```

`reset` deletes `trackpad.lua` and the marked block in `input.lua`, so Hyprland
falls back to your own or Omarchy's touchpad settings.

Tested on a MacBook Pro 11,3 (bcm5974) with Omarchy 4.0.6.

## License

MIT. See [LICENSE](LICENSE).
