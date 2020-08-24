class Field:

    default = None
    ignore = False

    def __init__(self, default=None, ignore=None):
        if default is not None:
            self.default = default
        if ignore is not None:
            self.ignore = ignore

    def decode(self, stream):
        pass

    def encode(self, stream, value):
        pass

class Optional(Field):

    def __init__(self, field):
        self.field = field

    def decode(self, stream):
        x = stream.next(peek=True)
        if x == 0:
            stream.next()
            return None
        return self.field.decode(stream)

    def encode(self, stream, v):
        if v is None:
            stream.write(0)
        else:
            self.field.encode(stream, v)

    @property
    def default(self):
        return self.field.default

    @property
    def ignore(self):
        return self.field.ignore

class AnyReserved(Field):
    
    ignore = True

    def decode(self, stream):
        stream.next()

    def encode(self, stream, v):
        stream.write(0)

class Constant(Field):

    ignore = True

    def __init__(self, v, **kwargs):
        super().__init__(**kwargs)
        self.v = v

    def decode(self, stream):
        v = stream.next()
        if v != self.v:
            raise ValueError(f"Expected {self.v}, found {v}")

    def encode(self, stream, v):
        if v is not None and v != self.v:
            raise ValueError(f"Expected {self.v}, found {v}")
        stream.write(self.v)

class Value(Field):

    def decode(self, stream):
        return stream.next()

    def encode(self, stream, v):
        stream.write(v)

class IntValue(Field):

    def decode(self, stream):
        return stream.nextint()

    def encode(self, stream, v):
        stream.write(v)

class BoolValue(Field):

    def decode(self, stream):
        return stream.next() == 1

    def encode(self, stream, v):
        stream.write(v and 1 or 0)

class EnumValue(Field):

    def __init__(self, enum):
        self.enum = enum

    def decode(self, stream):
        return self.enum(stream.next())
    
    def encode(self, stream, v):
        stream.write(v)

class RecordMeta(type):

    def __new__(cls, name, bases, attrs):
        fields = [a for a in attrs.items() if isinstance(a[1], Field)]
        for n,f in fields:
            attrs[n] = f.default
        attrs["fields"] = fields
        return type.__new__(cls, name, bases, attrs)

class Record(metaclass=RecordMeta):

    def encode(self, stream):
        for name,f in self.fields:
            f.encode(stream, getattr(self, name, None))

    def to_floats(self):
        out = FpStream()
        self.encode(out)
        return out.buf

    def to_json(self):
        return dict((n,getattr(self,n)) for n,_ in self.visible_fields if getattr(self,n) is not None)

    @classmethod
    def decode(cls, stream, fields=None):
        r = cls()
        for name,f in fields or r.fields:
            try:
                v = f.decode(stream)
            except Exception as e:
                raise ValueError(f"Failed to decode {f} field {name}") from e
            if v is not None:
                setattr(r, name, v)
        return r

    @classmethod
    def from_floats(cls, args, fields=None):
        return cls.decode(FpStream(args), fields=fields)

    @classmethod
    def from_json(cls, d):
        r = cls()
        for name,_ in r.fields:
            if name in d:
                setattr(r, name, d[name])
        return r

    @property
    def visible_fields(self):
        return [(n,f) for n,f in self.fields if not f.ignore]

    def __repr__(self):
        return repr(self.to_json())

class FpStream:

    def __init__(self, buf=None):
        self.buf = buf or []

    def next(self, peek=False):
        if len(self.buf) > 0:
            v = self.buf[0]
            if not peek:
                self.buf = self.buf[1:]
            return v
        raise ValueError("Buffer overrun")

    def nextint(self, peek=False):
        f = self.next(peek)
        i = int(f)
        if f != i:
            raise ValueError(f"Non-integer floating point: {f}")
        return i

    def write(self, f):
        self.buf.append(float(f))

    def writebuf(self, buf):
        self.buf.extend(buf)
