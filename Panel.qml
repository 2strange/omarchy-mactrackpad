import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Trackpad settings popup. Every control goes through trackpad-config.py, which regenerates
// ~/.config/hypr/trackpad.lua, reloads Hyprland and rolls back if Hyprland reports errors.
// Switches write on click, sliders on release (each write is a Hyprland reload).
Panel {
  id: root
  moduleName: "io.github.2strange.trackpad"
  ipcTarget: "io.github.2strange.trackpad"
  manageIpc: false

  property var anchorItem: null
  property string tab: "pointer"  // Pointer / Scroll / Click / Swipe
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root

  function open() {
    setCenterHoverRevealSuppressed(false)
    root.controller.show()
    root.refresh()
  }
  function openFromHotkey() {
    root.controller.show()
    root.refresh()
    Qt.callLater(function() { if (root.opened) setCenterHoverRevealSuppressed(true) })
  }
  // Hide first, so the overlay goes away even if anything after this throws.
  function close() {
    root.controller.hide()
    setCenterHoverRevealSuppressed(false)
  }
  function toggle() {
    if (root.opened) root.close()
    else root.openFromHotkey()
  }
  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.barIdentity, direction)
    return false
  }
  function setCenterHoverRevealSuppressed(value) {
    if (root.bar && typeof root.bar.setCenterHoverRevealSuppressed === "function")
      root.bar.setCenterHoverRevealSuppressed(value)
    else if (root.bar && "centerHoverRevealSuppressed" in root.bar)
      root.bar.centerHoverRevealSuppressed = value
  }

  // ---- settings state (flat: key -> value)
  readonly property string helper: decodeURIComponent(Qt.resolvedUrl("trackpad-config.py").toString().replace(/^file:\/\//, ""))
  property var cfg: ({})
  property string errorText: ""
  function val(key, fallback) {
    return cfg[key] === undefined ? fallback : cfg[key]
  }
  function refresh() {
    if (!readProc.running && !writeProc.running) readProc.running = true
  }

  Process {
    id: readProc
    command: ["python3", "-I", root.helper, "get"]
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.cfg = JSON.parse(text) } catch (e) { console.warn("trackpad: bad json", e) }
      }
    }
  }

  // Local state changes first, so a switch never snaps back; the write follows.
  property var pending: ({})
  function set(key, value) {
    var c = Object.assign({}, cfg)
    c[key] = value
    cfg = c
    var p = Object.assign({}, pending)
    p[key] = value
    pending = p
    writeTimer.restart()
  }
  Timer {
    id: writeTimer
    interval: 150
    onTriggered: root.flush()
  }
  function flush() {
    var keys = Object.keys(pending)
    if (keys.length === 0) return
    if (writeProc.running) { writeTimer.restart(); return }
    var args = ["python3", "-I", root.helper, "set"]
    for (var i = 0; i < keys.length; i++) args.push(keys[i] + "=" + String(pending[keys[i]]))
    pending = ({})
    writeProc.command = args
    writeProc.running = true
  }
  Process {
    id: writeProc
    stderr: StdioCollector { id: writeErr }
    onExited: function(code) {
      root.errorText = code === 0 ? "" : code === 1 ? "Hyprland rejected the change, rolled back"
        : code === 3 ? "Another swipe gesture in input.lua blocks this, see the Swipe tab" : "Could not apply the change"
      if (code !== 0) console.warn("trackpad-config failed", code, writeErr.text)
      root.refresh()
    }
  }
  Component.onCompleted: root.refresh()

  readonly property color fg: bar ? bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(fg, 1.4)
  readonly property string fontFam: bar ? bar.fontFamily : Style.font.family

  function fmt(v) { return (Math.round(v * 100) / 100).toString() }

  // ---- a labelled slider row; shows the dragged value, commits on release
  component SliderRow: Column {
    id: row
    property string label: ""
    property real minimum: 0
    property real maximum: 1
    property real step: 0.05
    property real value: 0
    property string suffix: ""
    property real shown: value
    onValueChanged: shown = value
    signal committed(real v)
    width: parent.width
    spacing: Style.space(4)
    function snap(v) {
      var s = Math.round((v - row.minimum) / row.step) * row.step + row.minimum
      s = Math.max(row.minimum, Math.min(row.maximum, s))
      return Math.round(s * 10000) / 10000
    }
    Item {
      width: parent.width
      height: labelText.implicitHeight
      Text { id: labelText; text: row.label; color: root.fg; font.family: root.fontFam; font.pixelSize: Style.font.body; anchors.left: parent.left }
      Text { text: root.fmt(row.shown) + row.suffix; color: root.dim; font.family: root.fontFam; font.pixelSize: Style.font.caption; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter }
    }
    PanelSlider {
      bar: root.bar
      width: parent.width
      minimum: row.minimum
      maximum: row.maximum
      step: row.step
      value: row.value
      onMoved: function(v) { row.shown = row.snap(v) }
      onReleased: function(v) { row.committed(row.snap(v)) }
    }
  }

  // ---- a labelled switch row
  component SwitchRow: Item {
    id: srow
    property string label: ""
    property string description: ""
    property bool checked: false
    signal toggled()
    width: parent.width
    implicitHeight: Math.max(labels.implicitHeight, sw.implicitHeight)
    Column {
      id: labels
      anchors.left: parent.left
      anchors.right: sw.left
      anchors.rightMargin: Style.space(12)
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(2)
      Text { text: srow.label; color: root.fg; font.family: root.fontFam; font.pixelSize: Style.font.body; width: parent.width; elide: Text.ElideRight }
      Text { text: srow.description; visible: text !== ""; color: root.dim; font.family: root.fontFam; font.pixelSize: Style.font.caption; width: parent.width; wrapMode: Text.WordWrap }
    }
    ToggleSwitch {
      id: sw
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      checked: srow.checked
      foreground: root.fg
      onToggled: srow.toggled()
    }
  }

  // A switch bound to one boolean key.
  component KeySwitch: SwitchRow {
    property string key: ""
    property bool fallback: false
    checked: root.val(key, fallback) === true
    onToggled: root.set(key, !(root.val(key, fallback) === true))
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(360))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Column {
        id: column
        anchors.fill: parent
        spacing: Style.space(14)

        // ---------- Hero ----------
        Item {
          width: parent.width
          implicitHeight: Math.max(heroIcon.implicitHeight, heroLabels.implicitHeight)
          Text {
            id: heroIcon
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: String.fromCodePoint(0xF07F8)
            color: root.fg
            font.family: root.fontFam
            font.pixelSize: Style.font.display
          }
          Column {
            id: heroLabels
            anchors.left: heroIcon.right
            anchors.leftMargin: Style.space(14)
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(2)
            Text { text: "Trackpad"; color: root.fg; font.family: root.fontFam; font.pixelSize: Style.font.title; font.bold: true; width: parent.width; elide: Text.ElideRight }
            Text { text: (root.errorText !== "" ? root.errorText : "Applies live").toUpperCase(); color: root.dim; font.family: root.fontFam; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1.2; width: parent.width; elide: Text.ElideRight }
          }
        }

        PanelSeparator { width: parent.width; foreground: root.fg }

        ButtonGroup {
          width: parent.width
          options: [
            { value: "pointer", label: "Pointer" },
            { value: "scroll", label: "Scroll" },
            { value: "click", label: "Click" },
            { value: "swipe", label: "Swipe" }
          ]
          value: root.tab
          foreground: root.fg
          fontFamily: root.fontFam
          fontSize: Style.font.caption
          focusable: false
          onChanged: function(v) { root.tab = v }
        }

        Column {
          width: parent.width
          spacing: Style.space(14)
          visible: root.tab === "pointer"
          // ---------- Pointer ----------
          PanelSectionHeader { text: "POINTER"; foreground: root.fg; fontFamily: root.fontFam }
          SliderRow {
            label: "Tracking speed"
            minimum: -1; maximum: 1; step: 0.05
            value: root.val("sensitivity", 0)
            onCommitted: function(v) { root.set("sensitivity", v) }
          }
        }

        Column {
          width: parent.width
          spacing: Style.space(14)
          visible: root.tab === "scroll"
          // ---------- Scrolling ----------
          PanelSectionHeader { text: "SCROLLING"; foreground: root.fg; fontFamily: root.fontFam }
          KeySwitch {
            key: "natural_scroll"
            label: "Natural scrolling"
            description: "Content follows the fingers"
          }
          SliderRow {
            label: "Scroll speed"
            minimum: 0.1; maximum: 2; step: 0.05
            suffix: "×"
            value: root.val("scroll_factor", 0.4)
            onCommitted: function(v) { root.set("scroll_factor", v) }
          }
        }

        Column {
          width: parent.width
          spacing: Style.space(14)
          visible: root.tab === "click"
          // ---------- Clicking ----------
          PanelSectionHeader { text: "CLICKING"; foreground: root.fg; fontFamily: root.fontFam }
          KeySwitch {
            key: "tap_to_click"; fallback: true
            label: "Tap to click"
          }
          KeySwitch {
            key: "tap_and_drag"; fallback: true
            label: "Tap and drag"
            description: "Double-tap and hold to drag"
          }
          KeySwitch {
            key: "clickfinger_behavior"; fallback: true
            label: "Two-finger click is a right click"
            description: "Off: right-click in the lower-right corner"
          }
          KeySwitch {
            key: "disable_while_typing"; fallback: true
            label: "Ignore trackpad while typing"
          }
        }

        Column {
          width: parent.width
          spacing: Style.space(14)
          visible: root.tab === "swipe"
          // ---------- Gestures ----------
          PanelSectionHeader { text: "WORKSPACE SWIPE"; foreground: root.fg; fontFamily: root.fontFam }
          Column {
            width: parent.width
            spacing: Style.space(6)
            Text { text: "Fingers"; color: root.fg; font.family: root.fontFam; font.pixelSize: Style.font.body }
            ButtonGroup {
              width: parent.width
              options: [{ value: "0", label: "Off" }, { value: "3", label: "3 fingers" }, { value: "4", label: "4 fingers" }]
              value: String(root.val("swipe_fingers", 3))
              foreground: root.fg; fontFamily: root.fontFam; fontSize: Style.font.caption; focusable: false
              onChanged: function(v) { root.set("swipe_fingers", parseInt(v)) }
            }
          }
          Text {
            width: parent.width
            visible: root.val("gesture_conflict", false) === true
            text: "~/.config/hypr/input.lua defines its own swipe gesture as well. Remove that line, or set Fingers to Off here."
            color: Color.urgent
            font.family: root.fontFam; font.pixelSize: Style.font.caption; wrapMode: Text.WordWrap
          }
          Column {
            width: parent.width
            spacing: Style.space(6)
            Text { text: "At the last workspace"; color: root.fg; font.family: root.fontFam; font.pixelSize: Style.font.body }
            ButtonGroup {
              width: parent.width
              options: [{ value: "stop", label: "Stop" }, { value: "new", label: "New one" }, { value: "wrap", label: "Wrap around" }]
              value: String(root.val("swipe_end", "new"))
              foreground: root.fg; fontFamily: root.fontFam; fontSize: Style.font.caption; focusable: false
              onChanged: function(v) { root.set("swipe_end", v) }
            }
          }
          KeySwitch {
            key: "swipe_use_r"
            label: "Include empty workspaces"
            description: "Workspaces 1-5 always count, like in the bar. Off: only open ones"
          }
          KeySwitch {
            key: "swipe_invert"; fallback: true
            label: "Invert swipe direction"
          }
        }

        Text {
          width: parent.width
          text: "Writes ~/.config/hypr/trackpad.lua"
          color: root.dim
          font.family: root.fontFam
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }
}
