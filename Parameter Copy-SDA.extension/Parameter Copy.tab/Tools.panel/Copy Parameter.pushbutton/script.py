
# -*- coding: utf-8 -*-
"""
pyRevit (Revit 2022 / IronPython 2.7)

COPY PARAMETERS BY NAME (COMMON-ONLY DROPDOWN)

Workflow
1) Pick SOURCE element
2) Pick TARGETS one-by-one (toggle + highlight)
3) Press ESC
4) Dropdown shows ONLY parameters that exist on SOURCE AND on ALL TARGETS
5) Pick parameters -> copies values from source to all targets

Notes
- Skips locked/undesired parameters by name (Bauteilebene, Arbeitsebene)
- Copies Double/Int/String/ElementId with safety checks
"""

from pyrevit import revit, DB, UI, forms
from System.Collections.Generic import List

doc = revit.doc
uidoc = revit.uidoc

# -----------------------------
# CONFIG
# -----------------------------
BLOCKED_NAMES = [
    u"Bauteilebene",
    u"Arbeitsebene",
]

# -----------------------------
# HELPERS
# -----------------------------
def _clean(s):
    try:
        return (s or u"").strip()
    except:
        return u""


def _is_blocked(name):
    n = _clean(name).lower()
    for b in BLOCKED_NAMES:
        if n == _clean(b).lower():
            return True
    return False


def _is_cancel(ex):
    # Revit throws Autodesk.Revit.Exceptions.OperationCanceledException when ESC is pressed
    name = ex.__class__.__name__
    msg = (str(ex) or "").lower()
    return name == "OperationCanceledException" or "aborted the pick operation" in msg


def _set_selection(eids):
    ids = List[DB.ElementId]()
    for eid in eids:
        ids.Add(eid)
    uidoc.Selection.SetElementIds(ids)


def _elem_from_ref(pick_ref):
    try:
        return doc.GetElement(pick_ref.ElementId)
    except:
        return None


def _storage_label(st):
    if st == DB.StorageType.Double:
        return "Double"
    if st == DB.StorageType.Integer:
        return "Integer"
    if st == DB.StorageType.String:
        return "String"
    if st == DB.StorageType.ElementId:
        return "ElementId"
    return "None"


def _param_names_lower(elem):
    """Return set of parameter UI names (lowercase) on an element, excluding blocked names."""
    out = set()
    try:
        for p in elem.Parameters:
            try:
                n = _clean(p.Definition.Name)
                if not n or _is_blocked(n):
                    continue
                out.add(n.lower())
            except:
                pass
    except:
        pass
    return out


def _build_source_param_map(source):
    """
    Map: lower_name -> {name, display}
    Display includes StorageType + RO/RW info for the dropdown.
    """
    m = {}
    try:
        params = source.Parameters
    except:
        params = []

    for p in params:
        try:
            name = _clean(p.Definition.Name)
            if not name or _is_blocked(name):
                continue

            key = name.lower()
            if key in m:
                continue

            ro = "RO" if p.IsReadOnly else "RW"
            st = _storage_label(p.StorageType)
            disp = u"{}   [{} | {}]".format(name, st, ro)

            m[key] = {"name": name, "display": disp}
        except:
            continue
    return m


def _get_param_value(p):
    st = p.StorageType
    if st == DB.StorageType.Double:
        return p.AsDouble()
    if st == DB.StorageType.Integer:
        return p.AsInteger()
    if st == DB.StorageType.String:
        return p.AsString()
    if st == DB.StorageType.ElementId:
        return p.AsElementId()
    return None


def _set_param_value(p, value):
    st = p.StorageType
    if st == DB.StorageType.Double:
        p.Set(value)
        return True
    if st == DB.StorageType.Integer:
        p.Set(value)
        return True
    if st == DB.StorageType.String:
        p.Set(value if value is not None else "")
        return True
    if st == DB.StorageType.ElementId:
        p.Set(value)
        return True
    return False


def _try_copy_by_name(src_elem, dst_elem, pname):
    """Copy a parameter by its UI name from src to dst. Returns (ok, reason)."""
    pname = _clean(pname)
    if not pname or _is_blocked(pname):
        return (False, "blocked/empty")

    sp = src_elem.LookupParameter(pname)
    tp = dst_elem.LookupParameter(pname)

    if not sp or not tp:
        return (False, "missing")
    if tp.IsReadOnly:
        return (False, "read-only")
    if sp.StorageType != tp.StorageType:
        return (False, "type mismatch")

    try:
        val = _get_param_value(sp)

        # ElementId copies can fail across contexts; keep it safe.
        if sp.StorageType == DB.StorageType.ElementId:
            if val and val != DB.ElementId.InvalidElementId:
                if doc.GetElement(val) is None:
                    return (False, "elementid not in doc")

        if _set_param_value(tp, val):
            return (True, "")
        return (False, "unsupported")
    except Exception as e:
        return (False, str(e))


# -----------------------------
# 1) PICK SOURCE
# -----------------------------
forms.alert("Pick SOURCE element (reference).", title="Copy Parameters (Common Only)", ok=True)
try:
    src_ref = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, "Pick SOURCE")
except Exception:
    forms.alert("Canceled.", title="Copy Parameters (Common Only)")
    raise SystemExit

source = _elem_from_ref(src_ref)
if not source:
    forms.alert("Could not read source element.", title="Copy Parameters (Common Only)")
    raise SystemExit


# -----------------------------
# 2) PICK TARGETS (TOGGLE + HIGHLIGHT)
# -----------------------------
forms.alert(
    "Pick TARGETS one-by-one.\n\n"
    "• Targets stay highlighted\n"
    "• Click again to REMOVE\n"
    "• Press ESC to CONTINUE\n\n"
    "Next: you will choose parameters to copy.\n"
    "Only parameters common to SOURCE AND ALL TARGETS will be shown.",
    title="Copy Parameters (Common Only)",
    ok=True
)

target_ids = []
while True:
    try:
        r = uidoc.Selection.PickObject(UI.Selection.ObjectType.Element, "Pick TARGET (ESC = Continue)")
        e = doc.GetElement(r.ElementId)
        if not e:
            continue
        if e.Id == source.Id:
            continue

        if e.Id in target_ids:
            target_ids.remove(e.Id)
        else:
            target_ids.append(e.Id)

        _set_selection(target_ids)

    except Exception as ex:
        if _is_cancel(ex):
            break
        raise

if not target_ids:
    forms.alert("No targets selected. Nothing changed.", title="Copy Parameters (Common Only)")
    raise SystemExit


# -----------------------------
# 3) BUILD COMMON PARAM LIST (INTERSECTION)
# -----------------------------
src_map = _build_source_param_map(source)
common_keys = set(src_map.keys())

for tid in target_ids:
    tgt = doc.GetElement(tid)
    if not tgt:
        continue
    common_keys &= _param_names_lower(tgt)

if not common_keys:
    forms.alert(
        "No common parameters found between SOURCE and ALL TARGETS.\n\n"
        "Tip: select targets from the same family/type group (or reduce targets).",
        title="Copy Parameters (Common Only)"
    )
    raise SystemExit

common_keys_sorted = sorted(list(common_keys))
display_items = [src_map[k]["display"] for k in common_keys_sorted]


# -----------------------------
# 4) PICK PARAMETERS (MULTISELECT)
# -----------------------------
picked_display = forms.SelectFromList.show(
    display_items,
    title="Select parameters to copy (COMMON ONLY)",
    multiselect=True,
    button_name="Copy to Targets"
)

if not picked_display:
    forms.alert("No parameters selected. Nothing changed.", title="Copy Parameters (Common Only)")
    raise SystemExit

picked_set = set(picked_display)
picked_names = []
for k in common_keys_sorted:
    if src_map[k]["display"] in picked_set:
        picked_names.append(src_map[k]["name"])

# Optional manual extras
extra = forms.ask_for_string(
    default="",
    prompt="Optional: add more parameter names (comma-separated).\n"
           "They will be attempted too (must exist & be writable on targets).\n\n"
           "Leave empty if not needed.",
    title="Copy Parameters (Common Only)"
)
if extra:
    for x in extra.split(","):
        n = _clean(x)
        if n and (not _is_blocked(n)):
            if n.lower() not in [p.lower() for p in picked_names]:
                picked_names.append(n)


# -----------------------------
# 5) APPLY COPY
# -----------------------------
elem_updated = 0
elem_skipped = 0
sets_ok = 0
sets_fail = 0
fail_samples = []

with revit.Transaction("Copy Parameters (Common Only)"):
    for tid in target_ids:
        tgt = doc.GetElement(tid)
        if not tgt:
            elem_skipped += 1
            continue

        ok_any = False
        for pname in picked_names:
            ok, why = _try_copy_by_name(source, tgt, pname)
            if ok:
                ok_any = True
                sets_ok += 1
            else:
                sets_fail += 1
                if why in ("missing", "read-only", "type mismatch", "elementid not in doc") and len(fail_samples) < 10:
                    fail_samples.append(u"{} -> {}".format(pname, why))

        if ok_any:
            elem_updated += 1
        else:
            elem_skipped += 1

_set_selection(target_ids)


# -----------------------------
# 6) REPORT
# -----------------------------
msg = []
msg.append("Targets: {}".format(len(target_ids)))
msg.append("Elements updated: {}".format(elem_updated))
msg.append("Elements skipped: {}".format(elem_skipped))
msg.append("")
msg.append("Param sets OK: {}".format(sets_ok))
msg.append("Param sets failed: {}".format(sets_fail))
msg.append("")
msg.append("Blocked (always skipped): " + ", ".join(BLOCKED_NAMES))

if fail_samples:
    msg.append("")
    msg.append("Sample failures:")
    for s in fail_samples:
        msg.append("- " + s)

forms.alert("\n".join([str(x) for x in msg]), title="Copy Parameters (Common Only)")

