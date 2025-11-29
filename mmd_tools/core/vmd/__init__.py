# Copyright 2014 MMD Tools authors
# This file is part of MMD Tools.

import collections
import logging
import struct


class InvalidFileError(Exception):
    pass


def _decodeCp932String(byteString):
    r"""Convert a VMD format byte string to a regular string.
    If the first byte is replaced with b"\x00" during encoding, add � at the beginning during decoding
    and replace ? with � to ensure replacement character consistency between UnicodeEncodeError and UnicodeDecodeError.
    - UnicodeEncodeError: Bone/Morph name has characters not supported by cp932 encoding. Default replacement character: ?
    - UnicodeDecodeError: Bone/Morph name was truncated at 15 bytes, breaking character boundaries. Default replacement character: �(U+FFFD)
    Example:
        original = "左带_0_1調整"
        byteString = b"\x00\xb6\x3f\x5f\x30\x5f\x31\x92\xb2\x90\xae\x00\x00\x00\x00"
        decoded = "�ｶ�_0_1調整"
    """
    # Truncate at null terminator (skip first byte) to remove trailing padding
    # Trailing padding may vary across different VMD files. (\x00, \xfd, etc.)
    # Before:
    #     byteString = b"\x00\xb6\x3f\x5f\x30\x5f\x31\x92\xb2\x90\xae\x00\xfd\xfd\xfd"
    # After:
    #     byteString = b"\x00\xb6\x3f\x5f\x30\x5f\x31\x92\xb2\x90\xae"
    if len(byteString) > 1:
        terminator_pos = byteString.find(b"\x00", 1)
        if terminator_pos != -1:
            byteString = byteString[:terminator_pos]

    # If flag indicates encoding error, replace the encoding replacement character from ? to � for consistency,
    # avoiding two different replacement characters appearing in console simultaneously
    # The first character masked by flag is also represented with replacement character
    if byteString[:1] == b"\x00":
        decoded = "\ufffd" + byteString[1:].decode("cp932", errors="replace").replace("?", "\ufffd")
    else:
        decoded = byteString.decode("cp932", errors="replace")
    return decoded


def _encodeCp932String(string):
    """Convert a regular string to a VMD format byte string."""
    try:
        return string.encode("cp932")
    except UnicodeEncodeError:
        # Match MikuMikuDance's behavior: replace first byte with b"\x00" to indicate encoding failures
        return b"\x00" + string.encode("cp932", errors="replace")[1:]


class Header:
    VMD_SIGN = b"Vocaloid Motion Data 0002"

    def __init__(self):
        self.signature = None
        self.model_name = ""

    def load(self, fin):
        (self.signature,) = struct.unpack("<30s", fin.read(30))
        if self.signature[: len(self.VMD_SIGN)] != self.VMD_SIGN:
            raise InvalidFileError(f'File signature "{self.signature}" is invalid.')
        self.model_name = _decodeCp932String(struct.unpack("<20s", fin.read(20))[0])

    def save(self, fin):
        fin.write(struct.pack("<30s", self.VMD_SIGN))
        fin.write(struct.pack("<20s", _encodeCp932String(self.model_name)))

    def __repr__(self):
        return f"<Header model_name {self.model_name}>"


class BoneFrameKey:
    """
    VMD bone keyframe data structure.

    TODO: Optimize this bottleneck. Large VMD files may instantiate millions of BoneFrameKey objects, significantly impacting performance.
    """

    # Use __slots__ for better performance
    __slots__ = ("frame_number", "location", "rotation", "interp")

    def __init__(self):
        self.frame_number = 0
        self.location = []
        self.rotation = []
        self.interp = []

    def load(self, fin):
        (self.frame_number,) = struct.unpack("<L", fin.read(4))
        self.location = tuple(struct.unpack("<fff", fin.read(4 * 3)))
        self.rotation = tuple(struct.unpack("<ffff", fin.read(4 * 4)))
        if not any(self.rotation):
            self.rotation = (0, 0, 0, 1)
        self.interp = tuple(struct.unpack("<64b", fin.read(64)))

    def save(self, fin):
        fin.write(struct.pack("<L", self.frame_number))
        fin.write(struct.pack("<fff", *self.location))
        fin.write(struct.pack("<ffff", *self.rotation))
        fin.write(struct.pack("<64b", *self.interp))

    def __repr__(self):
        return f"<BoneFrameKey frame {str(self.frame_number)}, loa {str(self.location)}, rot {str(self.rotation)}>"


class ShapeKeyFrameKey:
    # Use __slots__ for better performance
    __slots__ = ("frame_number", "weight")

    def __init__(self):
        self.frame_number = 0
        self.weight = 0.0

    def load(self, fin):
        (self.frame_number,) = struct.unpack("<L", fin.read(4))
        (self.weight,) = struct.unpack("<f", fin.read(4))

    def save(self, fin):
        fin.write(struct.pack("<L", self.frame_number))
        fin.write(struct.pack("<f", self.weight))

    def __repr__(self):
        return f"<ShapeKeyFrameKey frame {str(self.frame_number)}, weight {str(self.weight)}>"


class CameraKeyFrameKey:
    # Use __slots__ for better performance
    __slots__ = ("frame_number", "distance", "location", "rotation", "interp", "angle", "persp")

    def __init__(self):
        self.frame_number = 0
        self.distance = 0.0
        self.location = []
        self.rotation = []
        self.interp = []
        self.angle = 0.0
        self.persp = True

    def load(self, fin):
        (self.frame_number,) = struct.unpack("<L", fin.read(4))
        (self.distance,) = struct.unpack("<f", fin.read(4))
        self.location = tuple(struct.unpack("<fff", fin.read(4 * 3)))
        self.rotation = tuple(struct.unpack("<fff", fin.read(4 * 3)))
        self.interp = tuple(struct.unpack("<24b", fin.read(24)))
        (self.angle,) = struct.unpack("<L", fin.read(4))
        (self.persp,) = struct.unpack("<b", fin.read(1))
        self.persp = self.persp == 0

    def save(self, fin):
        fin.write(struct.pack("<L", self.frame_number))
        fin.write(struct.pack("<f", self.distance))
        fin.write(struct.pack("<fff", *self.location))
        fin.write(struct.pack("<fff", *self.rotation))
        fin.write(struct.pack("<24b", *self.interp))
        fin.write(struct.pack("<L", self.angle))
        fin.write(struct.pack("<b", 0 if self.persp else 1))

    def __repr__(self):
        return f"<CameraKeyFrameKey frame {str(self.frame_number)}, distance {str(self.distance)}, loc {str(self.location)}, rot {str(self.rotation)}, angle {str(self.angle)}, persp {str(self.persp)}>"


class LightKeyFrameKey:
    # Use __slots__ for better performance
    __slots__ = ("frame_number", "color", "direction")

    def __init__(self):
        self.frame_number = 0
        self.color = []
        self.direction = []

    def load(self, fin):
        (self.frame_number,) = struct.unpack("<L", fin.read(4))
        self.color = tuple(struct.unpack("<fff", fin.read(4 * 3)))
        self.direction = tuple(struct.unpack("<fff", fin.read(4 * 3)))

    def save(self, fin):
        fin.write(struct.pack("<L", self.frame_number))
        fin.write(struct.pack("<fff", *self.color))
        fin.write(struct.pack("<fff", *self.direction))

    def __repr__(self):
        return f"<LightKeyFrameKey frame {str(self.frame_number)}, color {str(self.color)}, direction {str(self.direction)}>"


class SelfShadowFrameKey:
    # Use __slots__ for better performance
    __slots__ = ("frame_number", "mode", "distance")

    def __init__(self):
        self.frame_number = 0
        self.mode = 0  # 0: none, 1: mode1, 2: mode2
        self.distance = 0.0

    def load(self, fin):
        (self.frame_number,) = struct.unpack("<L", fin.read(4))
        (self.mode,) = struct.unpack("<b", fin.read(1))
        if self.mode not in range(3):
            logging.warning(" * Invalid self shadow mode %d at frame %d", self.mode, self.frame_number)
            raise struct.error
        (distance,) = struct.unpack("<f", fin.read(4))
        self.distance = 10000 - distance * 100000
        logging.info("    %s", self)

    def save(self, fin):
        fin.write(struct.pack("<L", self.frame_number))
        fin.write(struct.pack("<b", self.mode))
        distance = (10000 - self.distance) / 100000
        fin.write(struct.pack("<f", distance))

    def __repr__(self):
        return f"<SelfShadowFrameKey frame {str(self.frame_number)}, mode {str(self.mode)}, distance {str(self.distance)}>"


class PropertyFrameKey:
    # Use __slots__ for better performance
    __slots__ = ("frame_number", "visible", "ik_states")

    def __init__(self):
        self.frame_number = 0
        self.visible = True
        self.ik_states = []  # list of (ik_name, enable/disable)

    def load(self, fin):
        (self.frame_number,) = struct.unpack("<L", fin.read(4))
        (self.visible,) = struct.unpack("<b", fin.read(1))
        (count,) = struct.unpack("<L", fin.read(4))
        for i in range(count):
            ik_name = _decodeCp932String(struct.unpack("<15s", fin.read(20)[:15])[0])  # MMD format: only the first 15 bytes are valid
            (state,) = struct.unpack("<b", fin.read(1))
            self.ik_states.append((ik_name, state))

    def save(self, fin):
        fin.write(struct.pack("<L", self.frame_number))
        fin.write(struct.pack("<b", 1 if self.visible else 0))
        fin.write(struct.pack("<L", len(self.ik_states)))
        for ik_name, state in self.ik_states:
            fin.write(struct.pack("<20s", _encodeCp932String(ik_name)))
            fin.write(struct.pack("<b", 1 if state else 0))

    def __repr__(self):
        return f"<PropertyFrameKey frame {str(self.frame_number)}, visible {str(self.visible)}, ik_states {str(self.ik_states)}>"


class _AnimationBase(collections.defaultdict):
    def __init__(self):
        collections.defaultdict.__init__(self, list)

    @staticmethod
    def frameClass():
        raise NotImplementedError

    def load(self, fin):
        (count,) = struct.unpack("<L", fin.read(4))
        logging.info("loading %s... %d", self.__class__.__name__, count)
        for i in range(count):
            name = _decodeCp932String(struct.unpack("<15s", fin.read(15))[0])
            cls = self.frameClass()
            frameKey = cls()
            frameKey.load(fin)
            self[name].append(frameKey)

    def save(self, fin):
        count = sum(len(i) for i in self.values())
        fin.write(struct.pack("<L", count))
        for name, frameKeys in self.items():
            name_data = struct.pack("<15s", _encodeCp932String(name))
            for frameKey in frameKeys:
                fin.write(name_data)
                frameKey.save(fin)


class _AnimationListBase(list):
    def __init__(self):
        list.__init__(self)

    @staticmethod
    def frameClass():
        raise NotImplementedError

    def load(self, fin):
        (count,) = struct.unpack("<L", fin.read(4))
        logging.info("loading %s... %d", self.__class__.__name__, count)
        for i in range(count):
            cls = self.frameClass()
            frameKey = cls()
            frameKey.load(fin)
            self.append(frameKey)

    def save(self, fin):
        fin.write(struct.pack("<L", len(self)))
        for frameKey in self:
            frameKey.save(fin)


class BoneAnimation(_AnimationBase):
    def __init__(self):
        _AnimationBase.__init__(self)

    @staticmethod
    def frameClass():
        return BoneFrameKey


class ShapeKeyAnimation(_AnimationBase):
    def __init__(self):
        _AnimationBase.__init__(self)

    @staticmethod
    def frameClass():
        return ShapeKeyFrameKey


class CameraAnimation(_AnimationListBase):
    def __init__(self):
        _AnimationListBase.__init__(self)

    @staticmethod
    def frameClass():
        return CameraKeyFrameKey


class LightAnimation(_AnimationListBase):
    def __init__(self):
        _AnimationListBase.__init__(self)

    @staticmethod
    def frameClass():
        return LightKeyFrameKey


class SelfShadowAnimation(_AnimationListBase):
    def __init__(self):
        _AnimationListBase.__init__(self)

    @staticmethod
    def frameClass():
        return SelfShadowFrameKey


class PropertyAnimation(_AnimationListBase):
    def __init__(self):
        _AnimationListBase.__init__(self)

    @staticmethod
    def frameClass():
        return PropertyFrameKey


class File:
    def __init__(self):
        self.filepath = None
        self.header = None
        self.boneAnimation = None
        self.shapeKeyAnimation = None
        self.cameraAnimation = None
        self.lightAnimation = None
        self.selfShadowAnimation = None
        self.propertyAnimation = None

    def load(self, **args):
        path = args["filepath"]

        with open(path, "rb") as fin:
            self.filepath = path
            self.header = Header()
            self.boneAnimation = BoneAnimation()
            self.shapeKeyAnimation = ShapeKeyAnimation()
            self.cameraAnimation = CameraAnimation()
            self.lightAnimation = LightAnimation()
            self.selfShadowAnimation = SelfShadowAnimation()
            self.propertyAnimation = PropertyAnimation()

            self.header.load(fin)
            try:
                self.boneAnimation.load(fin)
                self.shapeKeyAnimation.load(fin)
                self.cameraAnimation.load(fin)
                self.lightAnimation.load(fin)
                self.selfShadowAnimation.load(fin)
                self.propertyAnimation.load(fin)
            except struct.error:
                pass  # no valid camera/light data

    def save(self, **args):
        path = args.get("filepath", self.filepath)

        header = self.header or Header()
        boneAnimation = self.boneAnimation or BoneAnimation()
        shapeKeyAnimation = self.shapeKeyAnimation or ShapeKeyAnimation()
        cameraAnimation = self.cameraAnimation or CameraAnimation()
        lightAnimation = self.lightAnimation or LightAnimation()
        selfShadowAnimation = self.selfShadowAnimation or SelfShadowAnimation()
        propertyAnimation = self.propertyAnimation or PropertyAnimation()

        with open(path, "wb") as fin:
            header.save(fin)
            boneAnimation.save(fin)
            shapeKeyAnimation.save(fin)
            cameraAnimation.save(fin)
            lightAnimation.save(fin)
            selfShadowAnimation.save(fin)
            propertyAnimation.save(fin)
