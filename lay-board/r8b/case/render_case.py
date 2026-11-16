# -*- coding: utf-8 -*-
"""Two shaded renders of the case STL files (VTK, off screen): assembled from the back corner, exploded from the I/O corner.
The PCB is drawn as a plain 40 x 40 x 1.2 slab.

usage: render_case.py <case_stl_dir> <out_dir>
"""
import json
import os
import sys

import vtk

D, OUT = sys.argv[1], sys.argv[2]
sp = json.load(open(os.path.join(D, 'case_spec.json'), encoding='utf-8'))
st = sp['stack']
H = sp['envelope'][2]
ANT = dict(sp['antenna'], thread=6.35)
COLOR = {'tray': (0.20, 0.20, 0.23), 'lid': (0.26, 0.26, 0.30), 'plate': (0.80, 0.81, 0.83), 'sma_thread': (0.85, 0.68, 0.25), 'sma_nut': (0.85, 0.68, 0.25), 'pcb': (0.10, 0.50, 0.22)}


def actor(k, dz):
    cyl = None
    if k == 'pcb':
        src = vtk.vtkCubeSource()
        src.SetBounds(-20, 20, -20, 20, st['z_bot'], st['z_top'])
    elif k.startswith('sma'):   # the SMA jack's thread and nut outside the -x wall (drawn, not a case part)
        src = vtk.vtkCylinderSource()
        r, ln = (ANT['thread'] / 2, 9.0) if k == 'sma_thread' else (4.4, 2.2)
        src.SetRadius(r)
        src.SetHeight(ln)
        src.SetResolution(6 if k == 'sma_nut' else 40)
        cyl = (-sp['envelope'][0] / 2 - ln / 2, ANT['y'], ANT['z'])
    else:
        src = vtk.vtkSTLReader()
        src.SetFileName(os.path.join(D, f'mf_kvm_{k}.stl'))
    nrm = vtk.vtkPolyDataNormals()
    nrm.SetInputConnection(src.GetOutputPort())
    nrm.SetFeatureAngle(35)
    m = vtk.vtkPolyDataMapper()
    m.SetInputConnection(nrm.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(m)
    a.GetProperty().SetColor(*COLOR[k])
    a.GetProperty().SetSpecular(0.25)
    a.SetPosition(0, 0, dz)
    if cyl:
        a.RotateZ(90)
        a.SetPosition(cyl[0], cyl[1], cyl[2] + dz)
    return a


def render(path, offsets, eye, label):
    ren = vtk.vtkRenderer()
    ren.SetBackground(1, 1, 1)
    for k, dz in offsets.items():
        ren.AddActor(actor(k, dz))
    txt = vtk.vtkTextActor()
    txt.SetInput(label)
    txt.GetTextProperty().SetColor(0, 0, 0)
    txt.GetTextProperty().SetFontSize(16)
    txt.SetPosition(12, 12)
    ren.AddViewProp(txt)
    cam = ren.GetActiveCamera()
    zc = (H + max(offsets.values())) / 2
    cam.SetFocalPoint(0, 0, zc)
    cam.SetPosition(eye[0], eye[1], zc + eye[2])
    cam.SetViewUp(0, 0, 1)
    ren.ResetCamera()
    cam.Zoom(1.15)
    win = vtk.vtkRenderWindow()
    win.SetOffScreenRendering(1)
    win.SetSize(1000, 1000)
    win.AddRenderer(ren)
    win.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(win)
    grab.Update()
    w = vtk.vtkPNGWriter()
    w.SetFileName(path)
    w.SetInputConnection(grab.GetOutputPort())
    w.Write()


render(os.path.join(OUT, 'render_assembled.png'), {'tray': 0, 'plate': 0, 'lid': 0, 'sma_thread': 0, 'sma_nut': 0}, (-110, 60, 55),
       f"MF KVM r8b {sp['envelope'][0]:g} x {sp['envelope'][1]:g} x {H:g} mm, back left corner: SMA jack (gold, drawn) in the -x wall")
render(os.path.join(OUT, 'render_exploded.png'), {'tray': 0, 'sma_thread': 0, 'sma_nut': 0, 'pcb': 8, 'plate': 18, 'lid': 28}, (-70, -110, 70),
       'r8b exploded, from the I/O face (-y): tray with SMA jack, PCB slab, plate, lid')
print('wrote', os.path.join(OUT, 'render_assembled.png'), os.path.join(OUT, 'render_exploded.png'))
