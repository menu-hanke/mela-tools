# PAR file parsing, separate from par.py because of the lark dependency

import sys
import re
import lark
from melatools.par import Par, ParError, ParEventLinks, Event, EventDefaults, DNFCondition,\
        RoutineCall, Control, Output
from melatools.sym import finnish

# XXX: the include syntax is a hack and won't work for other syms.
# blame MELA.
grammar = r"""
    start         : expr+
    ?expr         : sysexpr | userexpr | include
    sysexpr       : SYS_NAME parameter*
    userexpr      : USER_NAME parameter*
    include       : ("LUE" | "INCLUDE") /.+$/m
    ?parameter    : string | number
    string        : string_first string_cont*
    number        : SIGNED_NUMBER
    ?string_first : "#" /[^#\n]+/
    ?string_cont  : "#>>" /[^#\n]+/
    SYS_NAME      : /^[a-z]\w*/im
    USER_NAME     : /^ [a-z]\w*/im
    COMMENT.2     : /^[^ #a-z].*$/im

    %import common.SIGNED_NUMBER
    %import common.WS
    %ignore WS
    %ignore COMMENT
"""

class ParCmd:

    def __init__(self, type, name, params):
        self.type = type
        self.name = name
        self.params = params

    def __str__(self):
        return "%s %s" % (self.name, self.params)

class ParTransformer(lark.Transformer):
    start = list
    sysexpr = lark.v_args(inline=True)(lambda self, name, *params: ParCmd("system", name, params))
    userexpr = lark.v_args(inline=True)(lambda self, name, *params: ParCmd("user", name[1:], params))
    include = lark.v_args(inline=True)(lambda self, fname: ParCmd("system", "LUE", [fname]))
    string = lambda self, x: " ".join(x)
    number = lark.v_args(inline=True)(float)

_parse = lark.Lark(grammar, parser="lalr", transformer=ParTransformer()).parse

##-- parsing ----------------------------------------

class Parser:

    def __init__(self, sym):
        self.par = Par()
        self.links = ParEventLinks()
        self.sym = sym

# TODO: autodetect sym
def parse_par(s, sym=finnish):
    parser = Parser(sym)
    for p in _parse(s):
        try:
            cmd = _commands[sym[p.name]]
        except KeyError:
            print(f"warn: skipping unknown command '{p.name}'", file=sys.stderr)
            continue

        cmd(parser, p)

    parser.links.link_events(parser.par)
    return parser.par

def read_par(fp):
    return parse_par(fp.read().decode("utf8"))

##-- commands ----------------------------------------
# Note: finnish names are used as that's what MELA uses internally.
# use a symbol file for english par files.

_commands = {}

def command(name):
    def w(f):
        _commands[name] = f
        return f
    return w

# --------------------

def parse_event_param(p, ev, param):
    args = param.split()
    try:
        name, args = p.sym[args[0]], list(map(float, args[1:]))
    except Exception as e:
        # MELA skips invalid syntax here
        print(f"warn: skipping invalid argument list: {param}", file=sys.stderr)
        return

    if name == "TAPAHTUMAVUODET":
        ev.years = args[:-1]
        ev.repeat_interval = args[-1]
    elif name == "LYHIMMAT_TOTEUTUSVALIT":
        ev.min_intervals = args
    elif name == "HAARAUTUMINEN":
        ev.branching = args
    elif name == "VASTAAVAT_TAPAHTUMAT":
        p.links.comparable[ev.id].extend(map(int, args))
    elif name == "SALLITUT_EDELTAJAT":
        p.links.precedessors[ev.id].extend(map(int, args))
    elif name == "METSIKKOEHDOT":
        ev.condition = DNFCondition.from_floats(args)
    elif name == "TODENNAKOISYYS":
        ev.probability = args
    elif name == "TAPAHTUMAKUTSU":
        ev.calls.append(RoutineCall.from_floats(args))
    else:
        raise ParError(f"Unexpected event parameter '{name}'")

@command("TAPAHTUMA")
@command("TAPAHTUMA_OLETUSARVOT")
def cmd_event(p, cmd):
    params = cmd.params

    if cmd.name == "TAPAHTUMA":
        id, name = params[0].split(maxsplit=1)
        ev = Event(int(id), name)
        params = params[1:]
    else:
        ev = EventDefaults()

    for parm in params:
        try:
            parse_event_param(p, ev, parm)
        except Exception as e:
            raise ParError(f"Parser failed here: {cmd}") from e

    p.par.add_event(ev)

@command("VUODET")
def cmd_years(p, cmd):
    p.par.years = cmd.params

@command("TULOSTUS")
def cmd_output(p, cmd):
    p.par.output = Output.from_floats(cmd.params)

@command("SIMULOINNIN_OHJAUS")
def cmd_control(p, cmd):
    p.par.control = Control.from_floats(cmd.params)

@command("LUE")
def cmd_include(p, cmd):
    p.par.includes.append(cmd.params[0])
