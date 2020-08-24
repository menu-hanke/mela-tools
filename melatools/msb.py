import struct
import math
from melatools.rsd import RsdInitialDataRecord

# MELA Standard Binary (MSB)
# For documentation see MELA manual: MELA Standard Binary records (MSB format)

class MsbError(Exception): pass
class MsbEof(MsbError): pass

class MsbFormat:

    def __init__(self, uid_type="d", float_type="f", int_type="I"):
        self.uid_type = uid_type
        self.float_type = float_type
        self.int_type = int_type

# the format is machine-dependent.
# this is for the current machine.
default_format = MsbFormat()

class MsbStream:

    def __init__(self, fp, fmt=default_format):
        self.fp = fp
        self.fmt = fmt

    def close(self):
        self.fp.close()

    # -------------------

    def _read(self, sz):
        buf = self.fp.read(sz)
        if len(buf) < sz:
            raise MsbEof
        return buf

    def _unpack(self, fmt):
        return struct.unpack(fmt, self._read(struct.calcsize(fmt)))

    def read_uid(self):
        return self._unpack(self.fmt.uid_type)[0]

    def read_float(self):
        f = self._unpack(self.fmt.float_type)[0]
        if not math.isfinite(f):
            raise MsbError(f"Non-finite floating point: {f}")
        return f

    def read_fpint(self):
        f = self.read_float()
        i = int(f)
        if i != f:
            raise MsbError(f"Unexpected non-integer floating point: {f}")
        return i

    def read_fpbuf(self, n):
        buf = self._read(struct.calcsize(self.fmt.float_type) * n)
        return (f for (f, ) in struct.iter_unpack(self.fmt.float_type, buf))

    def read_int(self):
        return self._unpack(self.fmt.int_type)[0]

    # Note: this is not the same format as described in MELA manual
    # (turns out the actual format is different than the one in the manual)
    # This format reads blocks of the format:
    #
    #     length in bytes    : int
    #     uid                : double
    #     total num values   : int
    #         record type    : float
    #         num values     : float
    #         payload        : [float]
    #     length again       : int       (same as first length)
    #
    # where the data types are dependent on the fortran compiler and machine that produced
    # the msb file...
    def read_physical_record(self):
        try:
            length = self.read_int()
        except MsbEof:
            return None

        uid = self.read_uid()
        nv = self.read_int()
        nr = 0
        records = []

        while nr < nv:
            typ = self.read_fpint()
            sz = self.read_fpint()
            records.append(MsbLogicalRecord.from_floats(typ, list(self.read_fpbuf(sz))))
            nr += sz + 2 # count also typ and sz

        length2 = self.read_int()

        if length2 != length:
            raise MsbError(f"Length mismatch: {length2} != {length}")

        return MsbPhysicalRecord(uid, records)

    # -------------------

    def _pack(self, fmt, *args):
        self.fp.write(struct.pack(fmt, *args))

    def write_uid(self, uid):
        self._pack(self.fmt.uid_type, uid)

    def write_float(self, f):
        if not math.isfinite(f):
            raise MsbError(f"Non-finite floating point: {f}")
        self._pack(self.fmt.float_type, f)

    def write_fpbuf(self, buf):
        for f in buf:
            self.write_float(f)

    def write_int(self, i):
        self._pack(self.fmt.int_type, i)

    def write_physical_record(self, rec):
        records = [r.to_floats() for r in rec.records]

        length = struct.calcsize(self.fmt.uid_type) # uid
        length += len(records) * struct.calcsize(self.fmt.int_type) # total numv
        length += sum(2 + len(r) for r in records) * struct.calcsize(self.fmt.float_type) # type, numv, payload

        self.write_int(length)
        self.write_uid(rec.uid)
        self.write_int(sum(2 + len(r) for r in records))

        for r, buf in zip(rec.records, records):
            self.write_float(r.record_type)
            self.write_float(len(buf))
            self.write_fpbuf(buf)

        self.write_int(length)

def logical_record(typ, x):
    if typ == 1:
        return RsdInitialDataRecord(x)

    # unimplemented, return as plain buffer
    return MsbLogicalRecord(typ, x)

class MsbPhysicalRecord:

    def __init__(self, uid=None, records=None):
        self.uid = uid
        self.records = records

    def to_json(self):
        return {
            "uid": self.uid,
            "records": [r.to_json() for r in self.records]
        }

    @classmethod
    def from_json(cls, d):
        return cls(
            uid = d["uid"],
            records = [MsbLogicalRecord.from_json(x) for x in d["records"]]
        )

class MsbLogicalRecord:

    def to_floats(self):
        return self.buf

    def to_json(self):
        return { "record_type": self.record_type, "buf": self.buf }

    @staticmethod
    def from_floats(typ, args):
        if typ == 1:
            return RsdInitialDataRecord.from_floats(args)
        return MsbLogicalRecord(typ, args)

    @staticmethod
    def from_json(args):
        if args["record_type"] == 1:
            return RsdInitialDataRecord.from_json(args)
        return MsbLogicalRecord(args["record_type"], args["buf"])

# ---- msb reading & writing ----------------------------------------

def read_msb(fp, fmt=default_format):
    stream = MsbStream(fp, fmt)

    while True:
        rec = stream.read_physical_record()
        if rec is None:
            return
        yield rec

def write_msb(fp, records, fmt=default_format):
    stream = MsbStream(fp, fmt)

    for r in records:
        stream.write_physical_record(r)
