# Copyright 2017 MMD Tools authors
# This file is part of MMD Tools.


class InvalidFileError(Exception):
    pass


class VpdBone:
    def __init__(self, bone_name, location, rotation):
        self.bone_name = bone_name
        self.location = location
        self.rotation = rotation if any(rotation) else [0, 0, 0, 1]

    def __repr__(self):
        return f"<VpdBone {self.bone_name}, loc {str(self.location)}, rot {str(self.rotation)}>"


class VpdMorph:
    def __init__(self, morph_name, weight):
        self.morph_name = morph_name
        self.weight = weight

    def __repr__(self):
        return f"<VpdMorph {self.morph_name}, weight {self.weight:f}>"


class File:
    def __init__(self):
        self.filepath = ""
        self.osm_name = None
        self.bones = []
        self.morphs = []  # MikuMikuMoving

    def __repr__(self):
        return f"<File {self.filepath}, osm {self.osm_name}, bones {len(self.bones)}, morphs {len(self.morphs)}>"

    def load(self, **args):
        path = args["filepath"]

        encoding = "cp932"
        with open(path, encoding=encoding, errors="replace") as fin:
            self.filepath = path
            if not fin.readline().startswith("Vocaloid Pose Data file"):
                raise InvalidFileError

            fin.readline()
            self.osm_name = fin.readline().split(";")[0].strip()
            bone_counts = int(fin.readline().split(";")[0].strip())
            fin.readline()

            for line in fin:
                if line.startswith("Bone"):
                    bone_name = line.split("{")[-1].strip()

                    location = [float(x) for x in fin.readline().split(";")[0].strip().split(",")]
                    if len(location) != 3:
                        raise InvalidFileError

                    rotation = [float(x) for x in fin.readline().split(";")[0].strip().split(",")]
                    if len(rotation) != 4:
                        raise InvalidFileError

                    if not fin.readline().startswith("}"):
                        raise InvalidFileError

                    self.bones.append(VpdBone(bone_name, location, rotation))

                elif line.startswith("Morph"):
                    morph_name = line.split("{")[-1].strip()
                    weight = float(fin.readline().split(";")[0].strip())

                    if not fin.readline().startswith("}"):
                        raise InvalidFileError

                    self.morphs.append(VpdMorph(morph_name, weight))

            if len(self.bones) != bone_counts:
                raise InvalidFileError

    def save(self, **args):
        path = args.get("filepath", self.filepath)

        encoding = "cp932"
        with open(path, "w", encoding=encoding, errors="replace", newline="") as fout:
            self.filepath = path
            fout.write("Vocaloid Pose Data file\r\n")

            fout.write("\r\n")
            fout.write(f"{self.osm_name};\t\t// 親ファイル名\r\n")
            fout.write(f"{len(self.bones)};\t\t\t\t// 総ポーズボーン数\r\n")
            fout.write("\r\n")

            for i, b in enumerate(self.bones):
                fout.write(f"Bone{i}{{{b.bone_name}\r\n")
                x, y, z = b.location
                fout.write(f"  {x},{y},{z};\t\t\t\t// trans x,y,z\r\n")
                x, y, z, w = b.rotation
                fout.write(f"  {x},{y},{z},{w};\t\t// Quaternion x,y,z,w\r\n")
                fout.write("}\r\n")
                fout.write("\r\n")

            for i, m in enumerate(self.morphs):
                fout.write(f"Morph{i}{{{m.morph_name}\r\n")
                fout.write(f"  {m.weight:f};\t\t\t\t// weight\r\n")
                fout.write("}\r\n")
                fout.write("\r\n")
