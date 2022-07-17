bl_info = {
    "name": "Import Minema AE Tracking Date",
    "author": "InformationKiller from MiaoNLI",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "File > Import > Minema AE Tracking Data",
    "description": "Import the After Effect Frames exported by Minema",
    "category": "Import-Export",
}

from math import radians, pi
import traceback
import bpy
from bpy.types import Camera
from bpy.props import (
    IntProperty,
    StringProperty,
    BoolProperty,
    EnumProperty
)
from bpy_extras.io_utils import (
    ImportHelper,
    path_reference_mode,
)

class ImportTxt(bpy.types.Operator, ImportHelper):
    """Load a Minema AE Tracking Data File"""
    bl_idname = "import_minema.txt"
    bl_label = "Import Minema"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".txt"
    path_mode = path_reference_mode
    check_extension = True

    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})
    fps: IntProperty(name="FPS", default=60, min=1, max=240) # Because it includes motion blur tracking datas, my bad
    coord: EnumProperty(name="Axis", default='YZX', items=[('XYZ', 'Minecraft', 'Equals the game.'), ('YZX', 'Blender', 'Convert XYZ to YZX.')])
    delta: BoolProperty(name="Delta Transform", default=False)

    def execute(self, context):
        lines = []
        with open(self.properties.filepath, 'r') as fd:
            lines = fd.readlines()
            for i in range(len(lines)):
                lines[i] = lines[i].rstrip('\n').rstrip('\r').rstrip()
        try:
            if lines[0] != 'Adobe After Effects 8.0 Keyframe Data':
                raise Exception('Illegal After Effects Keyframe Data.')
            state = -1 # -1 - Unknown 0 - AE 1 - Zoom 2 - Rot 3 - Pos 4 - Scale
            data_fps = -1
            height = -1
            pos = {}
            rot = {}
            scale = {}
            fov = {}
            frame = False
            for line in lines:
                data = line.split('\t')
                if not data:
                    continue

                if data[0]:
                    state = -1
                    if data[0] == 'Adobe After Effects 8.0 Keyframe Data':
                        state = 0
                    elif data[0] == 'Camera Options' and data[1] == 'Zoom':
                        state = 1
                        frame = False
                    elif data[0] == 'Transform':
                        frame = False
                        if data[1] == 'Orientation':
                            state = 2
                        elif data[1] == 'Position':
                            state = 3
                        elif data[1] == 'Scale':
                            state = 4
                    elif data[0] == 'Expression Data':
                        skip = True
                    elif data[0] == 'End of Keyframe Data':
                        break
                elif state >= 0 and len(data) > 1:
                    if state == 0:
                        if data[1] == 'Units Per Second':
                            blurframes = round(float(data[2])) / self.properties.fps
                        elif data[1] == 'Source Height':
                            height = int(data[2])
                    else:
                        if state > 0 and not frame and data[1] != 'Frame':
                            raise Exception('Illegal After Effects Keyframe Data.')
                        if data[1] == 'Frame':
                            frame = True
                        else:
                            f = 0
                            if data[1]:
                                f = int(int(data[1]) // blurframes)
                            if state == 1:
                                if not f in fov: # Just ignore motion blur frames, they only take very short time.
                                    fov[f] = float(data[2])
                            elif state == 2:
                                if not f in rot:
                                    rot[f] = (float(data[2]), float(data[3]), float(data[4]))
                            elif state == 3:
                                if not f in pos:
                                    pos[f] = (float(data[2]), float(data[3]), float(data[4]))
                            elif state == 4:
                                if not f in scale:
                                    scale[f] = (float(data[2]) / 100.0, float(data[3]) / 100.0, float(data[4]) / 100.0)
            
            obj = context.selected_objects[0]
            base = context.scene.frame_current # I didn't use blender so I'm not sure which frame means the begin of a movie.

            isCamera = isinstance(obj.data, Camera)

            for f in pos:
                p = pos[f]
                if self.properties.coord == 'YZX':
                    # Minecraft XYZ -> Blender YZX
                    p = (pos[f][2], pos[f][0], pos[f][1])

                if self.properties.delta:
                    obj.delta_location = p
                    obj.keyframe_insert(data_path='delta_location', frame=base+f)
                else:
                    obj.location = p
                    obj.keyframe_insert(data_path='location', frame=base+f)

            if self.properties.coord == 'YZX':
                obj.rotation_mode = 'ZXY'
            else:
                obj.rotation_mode = 'ZYX'

            for f in rot:
                # Matrix = rotX(rx) * rotY(ry) * rotZ(rz) * rotY(180) * rotZ(180)
                r = (radians(rot[f][0] - 180), radians(-rot[f][1]), radians(-rot[f][2]))
                if self.properties.coord == 'YZX':
                    # Matrix = rotZ(90) * rotX(90) * rotX(rx) * rotY(ry) * rotZ(rz) * rotY(180) * rotZ(180)
                    r = (radians(rot[f][1]), radians(rot[f][0] - 90), radians(90 - rot[f][2]))

                if self.properties.delta:
                    obj.delta_rotation_euler = r
                    obj.keyframe_insert(data_path='delta_rotation_euler', frame=base+f)
                else:
                    obj.rotation_euler = r
                    obj.keyframe_insert(data_path='rotation_euler', frame=base+f)
            
            for f in scale:
                s = scale[f]
                if self.properties.delta:
                    obj.delta_scale = s
                    obj.keyframe_insert(data_path='delta_scale', frame=base+f)
                else:
                    obj.scale = s
                    obj.keyframe_insert(data_path='scale', frame=base+f)                

            if isCamera and fov:
                cam = obj.data
                cam.sensor_fit = 'VERTICAL' # Most OpenGL game use this
                for f in fov:
                    cam.lens = fov[f] / height * cam.sensor_height # After Effects use movie's height as sensor height
                    cam.keyframe_insert(data_path='lens', frame=base+f)
        except:
            traceback.print_exc()
            self.report({'ERROR'}, 'Unable to import this data file.')
            return {'CANCELLED'}
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'fps')
        layout.prop(operator, 'coord')
        layout.prop(operator, 'delta')

def menu_func_import(self, context):
    if context.selected_objects:
        if isinstance(context.selected_objects[0].data, Camera):
            self.layout.operator(ImportTxt.bl_idname, text="Minema AE Camera Tracking Data (.txt)")
        else:
            self.layout.operator(ImportTxt.bl_idname, text="Minema AE Object Tracking Data (.txt)")

def register():
    bpy.utils.register_class(ImportTxt)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ImportTxt)

if __name__ == "__main__":
    register()
