from enum import IntEnum
from collections import defaultdict
from melatools.var import get_var
from melatools.sym import finnish
from melatools.record import Record, Value, IntValue, BoolValue, Constant

class ParError(Exception):
    pass

class Par:

    def __init__(self):
        self.events = {}
        self.includes = []
        self.years = None
        self.output = None
        self.control = None

    def add_event(self, ev):
        if ev.id in self.events:
            raise ParError(f"Duplicate event: {ev.id}")
        self.events[ev.id] = ev

    def emit(self, out):
        if self.years is not None:
            out.command("VUODET", *self.years)
            out.newline()

        if self.output is not None:
            out.command("TULOSTUS", *self.output.to_floats())
            out.newline()

        if self.control is not None:
            out.command("SIMULOINNIN_OHJAUS", *self.control.to_floats())
            out.newline()

        for e in self.events.values():
            e.emit(out)
            out.newline()

        for i in self.includes:
            out.command("LUE", i)

    def tostring(self, sym=finnish, line_wrap=130):
        out = ParWriter(sym, line_wrap)
        self.emit(out)
        return str(out)

    def to_json(self):
        out = {}
        if self.events:
            out["events"] = dict((id,e.to_json()) for id,e in self.events.items())
        if self.includes:
            out["includes"] = self.includes
        if self.years is not None:
            out["years"] = self.years
        if self.output is not None:
            out["output"] = self.output.to_json()
        if self.control is not None:
            out["control"] = self.control.to_json()
        return out

    @classmethod
    def from_json(cls, d):
        par = cls()
        links = ParEventLinks()

        if "events" in d:
            for id, e in d["events"].items():
                ev = Event.from_json(id, e)
                par.add_event(ev)
                if "comparable_events" in e:
                    links.comparable[ev.id].extend(e["comparable_events"])
                if "feasible_precedessors" in e:
                    links.precedessors[ev.id].extend(e["feasible_precedessors"])

        links.link_events(par)

        if "includes" in d:
            par.includes.extend(d["includes"])
        if "years" in d:
            par.years = d["years"]
        if "output" in d:
            par.output = Output.from_json(d["output"])
        if "control" in d:
            par.control = Control.from_json(d["control"])

        return par

class ParEventLinks:

    def __init__(self):
        self.comparable = defaultdict(list)
        self.precedessors = defaultdict(list)

    def link_events(self, par):
        for id, comp in self.comparable.items():
            if id in par.events:
                par.events[id].comparable_events = [
                        par.events[eid] if eid in par.events else EventRef(eid) for eid in comp]
        for id, prec in self.precedessors.items():
            if id in par.events:
                par.events[id].feasible_precedessors = [
                        par.events[eid] if eid in par.events else EventRef(eid) for eid in prec]

class ParWriter:

    def __init__(self, sym, line_wrap=130):
        self.sym = sym
        self.line_wrap = line_wrap
        self.buf = []

    def command(self, name, *params):
        self.emit(self.sym[name], *params, kind="command")

    def string(self, *s):
        self.emit(*s, kind="string")

    def comment(self, *s):
        self.emit(*s, kind="comment")

    def newline(self):
        self.buf.append("\n")

    def emit(self, *params, kind="command"):
        line = []
        remain = self.line_wrap
        first = None

        if kind == "string":
            remain -= 1
            first = "#"
        elif kind == "comment":
            remain -= 1
            first = "*"

        for p in map(str, params):
            if remain - 1 - len(p) <= 0:
                if not line:
                    raise ParError(f"Parameter is too long to be line-wrapped: {p}")

                if first:
                    self.buf.append(first)
                self.buf.extend(line)
                self.buf.append("\n")

                remain = self.line_wrap
                line = []

                if kind == "command":
                    remain -= 4
                    first = "    "
                elif kind == "string":
                    remain -= 4
                    first = "#>> "
                elif kind == "comment":
                    remain -= 1
                    first = "*"

            if line:
                line.append(' ')
                remain -= 1

            line.append(p)
            remain -= len(p)

        if line:
            if first:
                self.buf.append(first)
            self.buf.extend(line)
            self.buf.append("\n")


    def __str__(self):
        return ''.join(self.buf)

def write_par(fp, par, **kwargs):
    fp.write(par.tostring(**kwargs).encode("utf8"))

##-- events ----------------------------------------

class EventMixin:

    def __init__(self):
        self.years = None
        self.probability = None
        self.branching = None
        self.condition = None
        self.min_intervals = None
        self.comparable_events = None
        self.feasible_precedessors = None
        self.repeat_interval = None

    def emit(self, out):
        years = []
        if self.years:
            years.extend(self.years)
        if self.repeat_interval is not None:
            years.append(self.repeat_interval)
        if years:
            out.string(out.sym["TAPAHTUMAVUODET"], *years)

        if self.branching:
            out.string(out.sym["HAARAUTUMINEN"], *self.branching)

        if self.probability:
            out.string(out.sym["TODENNAKOISYYS"], *self.probability)

        if self.condition:
            out.string(out.sym["METSIKKOEHDOT"], *self.condition.to_floats())

        if self.min_intervals:
            out.string(out.sym["LYHIMMAT_TOTEUTUSVALIT"], *self.min_intervals)

        if self.comparable_events:
            out.string(out.sym["VASTAAVAT_TAPAHTUMAT"], *(e.id for e in self.comparable_events))

        if self.feasible_precedessors:
            out.string(out.sym["SALLITUT_EDELTAJAT"], *(e.id for e in self.feasible_precedessors))

    def to_json(self):
        out = {}

        if self.years:
            out["years"] = self.years

        if self.repeat_interval is not None:
            out["repeat_interval"] = self.repeat_interval

        if self.branching:
            out["branching"] = self.branching

        if self.probability:
            out["probability"] = self.probability

        if self.condition:
            out["condition"] = self.condition.to_json()

        if self.min_intervals:
            out["min_intervals"] = self.min_intervals

        if self.comparable_events:
            out["comparable_events"] = [e.id for e in self.comparable_events]

        if self.feasible_precedessors:
            out["feasible_precedessors"] = [e.id for e in self.feasible_precedessors]

        return out

    def from_json(self, d):
        self.years = d.get("years")
        self.repeat_interval = d.get("repeat_interval")
        self.branching = d.get("branching")
        self.probability = d.get("probability")
        self.min_intervals = d.get("min_intervals")
        
        if "condition" in d:
            self.condition = DNFCondition.from_json(d["condition"])

class Event(EventMixin):

    def __init__(self, id, name):
        EventMixin.__init__(self)
        self.id = id
        self.name = name
        self.condition = None
        self.calls = []

    @property
    def ident(self):
        return "%d %s" % (self.id, self.name)

    def emit(self, out):
        out.command("TAPAHTUMA")
        out.string(self.ident)
        out.comment("--------------------------------------------------------")

        EventMixin.emit(self, out)

        for c in self.calls:
            out.string(out.sym["TAPAHTUMAKUTSU"], *c.to_floats())

    def to_json(self):
        out = {
            #"id": self.id,
            "name": self.name,
            **EventMixin.to_json(self)
        }

        if self.condition:
            out["condition"] = self.condition.to_json()

        if self.calls:
            out["calls"] = [c.to_json() for c in self.calls]

        return out

    @staticmethod
    def from_json(id, d):
        if id == "default":
            ev = EventDefaults()
        else:
            ev = Event(int(id), d["name"])

            if "calls" in d:
                ev.calls = list(map(RoutineCall.from_json, d["calls"]))

        EventMixin.from_json(ev, d)
        return ev

class EventDefaults(EventMixin):

    id = "default"

    def emit(self, out):
        out.command("TAPAHTUMA_OLETUSARVOT")
        EventMixin.emit(self, out)

class EventRef:

    def __init__(self, id):
        self.id = id

##-- conditions ----------------------------------------

class DNFCondition:

    def __init__(self, groups):
        self.groups = groups

    def to_floats(self):
        if not self.groups:
            return [0]

        out = [x for c in self.groups[0] for x in c.to_floats()]
        for g in self.groups[1:]:
            out.append(0)
            out.extend(x for c in g for x in c.to_floats())

        return out

    def to_json(self):
        return [[c.to_json() for c in g] for g in self.groups]

    @classmethod
    def from_floats(cls, args):
        groups = []

        # the whole dnf
        while len(args) > 0:

            # group
            group = []
            while len(args) > 0:

                # definition
                nv, args = int(args[0]), args[1:]
                if nv == 0:
                    # group separator
                    break

                var, cst = int(args[0]), args[1:nv]
                c = []
                while len(cst) > 0:
                    if len(cst) > 1 and cst[1] < 0:
                        c.append((cst[0], -cst[1]))
                        cst = cst[2:]
                    else:
                        c.append(cst[0])
                        cst = cst[1:]

                args = args[nv:]
                group.append(Constraint(get_var(var), c))

            if group:
                groups.append(group)

        return cls(groups)

    @classmethod
    def from_json(cls, d):
        return cls([[Constraint.from_json(c) for c in g] for g in d])

# logical OR
class Constraint:

    def __init__(self, var, values):
        self.var = var
        self.values = values

    def to_floats(self):
        out = [self.var.id]
        for c in self.values:
            if isinstance(c, (int, float)):
                out.append(c)
            else:
                out.append(c[0])
                out.append(-c[1])
        return [len(out), *out]

    def to_json(self):
        return [self.var.name, *self.values]

    @classmethod
    def from_json(cls, d):
        return cls(get_var(d[0]), list(d[1:]))

##-- routine calls ----------------------------------------

class RoutineCall:

    def __init__(self, routine, args):
        self.routine = routine
        self.args = args

    def to_floats(self):
        return [self.routine, 1, *self.args]

    def to_json(self):
        return self.__dict__

    @staticmethod
    def from_floats(args):
        routine = args[0]
        return RoutineCall(routine, args[2:])

    @staticmethod
    def from_json(d):
        return RoutineCall(**d)

##-- simulation control ----------------------------------------

class Control(Record):
    branch_stop_year = IntValue() # 1
    max_events       = IntValue() # 2
    _3               = Constant(0) # 3
    _4               = Constant(0) # 4
    _5               = Constant(1000) # 5
    _6               = Constant(0) # 6
    _7               = Constant(1) # 7
    max_branches     = IntValue() # 8
    _9               = Constant(0) # 9
    _10              = Constant(0) # 10
    max_plots        = IntValue() # 11
    smr_year         = IntValue() # 12
    _13              = Constant(0) # 13
    _14              = Constant(0) # 14
    force_stop_year  = IntValue() # 15
    land_value_mode  = IntValue() # 16
    sim_mode         = IntValue() # 17

##-- reports ----------------------------------------

class Output(Record):
    msc                  = BoolValue() # 1
    forest_sum           = BoolValue() # 2
    terminal_summary     = Value() # 3
    terminal_data_report = Value() # 4
    unit_sum             = BoolValue() # 5
    _6                   = Constant(0) # 6
    _7                   = Constant(0) # 7
    _8                   = Constant(0) # 8
    smr                  = BoolValue() # 9
    _10                  = Constant(0) # 10
