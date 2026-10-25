"""Run once in Pythonista on the phone, with the phone in LIGHT mode (Settings > Display),
so a failed dark override shows. It answers the Veil look's device questions that the
headless fake ui (tools/fakeui) cannot:

  1. does forcing dark work, from which thread, and is window() set right after present?
  2. is the keyboard dark when a field in the forced-dark view is edited?
  3. does a disabled ui.Button draw its title in its tint (#7a7874) or in a system grey?
  4. Iowan's line height against the app's 1.3 x size text rects: does text clip or vanish?
  5. does touch_ended arrive (phase 'cancelled') when a scroll view steals a touch?

Read the printed lines in the console after closing (the X at the top left)."""
import ui
from objc_util import ObjCInstance, ObjCClass, on_main_thread

print("system ui style:", ui.get_ui_style())
for name in ("IowanOldStyle-Roman", "IowanOldStyle-Bold", "IowanOldStyle-Italic"):
    print("%-22s 'Hg' line height at 100 pt: %.1f  (app rects: 130, tiles 135)"
          % (name, ui.measure_string("Hg", 0, (name, 100))[1]))
for s in u"7♥♠♦♣⚝⛏︎♜☘︎\U0001d11e✓✗":
    print("  %r IowanOldStyle-Bold 100 pt -> %s" % (s, ui.measure_string(s, 0, ("IowanOldStyle-Bold", 100))))


def find_native(view, cls_name):
    k = ObjCClass(cls_name)
    stack = [ObjCInstance(view)]
    while stack:
        o = stack.pop()
        if o.isKindOfClass_(k):
            return o
        stack.extend(list(o.subviews()))
    return None


class TextProbe(ui.View):
    """'7♥', 'Hg' and the class glyphs in rects 1.3, 1.2 and 1.1 em tall (outlined):
    look for glyphs cut at the rect's edge or missing altogether."""

    def draw(self):
        size = 34.0
        samples = [u"7♥", u"Hg", u"⚝⛏︎", u"♜☘︎\U0001d11e"]
        for i, k in enumerate((1.3, 1.2, 1.1)):
            for j, text in enumerate(samples):
                x, y = 6 + i * 124, 6 + j * 52
                ui.set_color("#555555")
                ui.Path.rect(x, y, 116, size * k).stroke()
                ui.draw_string(text, (x, y, 116, size * k), ("IowanOldStyle-Bold", size), "white", ui.ALIGN_CENTER)
                ui.draw_string("%.1f" % k, (x + 2, y + size * k - 12, 30, 12), ("<system>", 9), "#888888")


class TouchProbe(ui.View):
    def touch_began(self, t):
        print("probe touch_began", t.phase)

    def touch_moved(self, t):
        pass

    def touch_ended(self, t):
        print("probe touch_ended, phase =", t.phase, "(hold still 0.5 s on the grey box, then drag to scroll)")


root = ui.View(frame=(0, 0, 390, 700), background_color="#060606", name="Veil probe")
root.add_subview(TextProbe(frame=(0, 0, 390, 212), background_color="#060606"))

box = ui.View(frame=(16, 222, 358, 36), background_color="#0b0b0b", border_width=1, border_color="#353533",
              corner_radius=4)
tf = ui.TextField(frame=(8, 0, 342, 36))
tf.bordered = False
tf.background_color = None
tf.text_color = "#e2dfd9"
tf.tint_color = "#e2dfd9"
tf.font = ("IowanOldStyle-Roman", 16)
tf.text = "Player 1  (tap: is the keyboard dark? does P sit 8pt in?)"
box.add_subview(tf)
root.add_subview(box)

on_b = ui.Button(frame=(16, 270, 170, 40), title="Enabled #7a7874", tint_color="#7a7874", background_color="#0b0b0b")
off_b = ui.Button(frame=(204, 270, 170, 40), title="Disabled #7a7874", tint_color="#7a7874",
                  background_color="#0b0b0b")
off_b.enabled = False
for b in (on_b, off_b):
    b.font = ("IowanOldStyle-Bold", 15)
    root.add_subview(b)
root.add_subview(ui.Label(frame=(16, 312, 358, 20), text="same grey = tint is used when disabled",
                          text_color="#888888", font=("<system>", 11)))

sv = ui.ScrollView(frame=(16, 340, 358, 200), background_color="#111111")
sv.content_size = (358, 900)
sv.add_subview(TouchProbe(frame=(20, 20, 318, 120), background_color="#444444"))
root.add_subview(sv)


def report(sender):
    o = ObjCInstance(root)
    print("view override:", o.overrideUserInterfaceStyle(), " view style now:", o.traitCollection().userInterfaceStyle(),
          "(2 = dark)")
    w = o.window()
    print("window:", w is not None, " window override:", w.overrideUserInterfaceStyle() if w is not None else "-")
    t = find_native(tf, "UITextField")
    print("UITextField found:", t is not None, " keyboardAppearance:", t.keyboardAppearance() if t is not None else "-",
          " style:", t.traitCollection().userInterfaceStyle() if t is not None else "-")
    print("ObjCInstance(tf) is", ObjCInstance(tf))
    btn = find_native(off_b, "UIButton")
    if btn is not None:
        print("disabled UIButton title colour:", btn.titleColorForState_(2), " alpha:", btn.alpha())


root.add_subview(ui.Button(frame=(16, 552, 358, 40), title="Print report (after trying the field)",
                           action=report, tint_color="white", background_color="#222222"))


@on_main_thread
def force_dark(view):
    ObjCInstance(view).setOverrideUserInterfaceStyle_(2)


force_dark(root)                      # before present, on the main thread, the view only
root.present("fullscreen")
w = ObjCInstance(root).window()
print("window() right after present (interpreter thread):", w is not None)
