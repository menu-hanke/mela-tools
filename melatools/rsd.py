from melatools.record import FpStream, Record, Value, IntValue, Optional, Constant, AnyReserved

class RsdSamplePlot(Record):
    id                        = IntValue() # 1
    year                      = IntValue() # 2
    area                      = Value() # 3
    area_weight               = Value() # 4
    X                         = Value() # 5
    Y                         = Value() # 6
    stand_id                  = Optional(Value()) # 7
    height                    = Value() # 8
    dd                        = Value() # 9
    owner_category            = IntValue() # 10
    land_use_category         = IntValue() # 11
    soil_category             = IntValue() # 12
    site_type_category        = IntValue() # 13
    taxation_class            = IntValue() # 14
    fftcsfc                   = IntValue() # Finnish forest taxation class or site fertility category, 15
    drainage_category         = IntValue() # 16
    drainage_feasibility      = IntValue() # 17
    _18                       = Constant(0) # 18
    last_drainage_year        = IntValue() # 19
    last_fertilization_year   = IntValue() # 20
    last_ssp_year             = IntValue() # soil surface preparation, 21
    natural_regen_feasibility = IntValue() # 22
    last_cleaning_year        = IntValue() # 23
    development_class         = Optional(Value()) # 24
    last_artif_regen_year     = IntValue() # 25
    last_tending_young_year   = IntValue() # 26
    last_pruning_year         = IntValue() # 27
    last_cutting_year         = IntValue() # 28
    forestry_center           = IntValue() # 29
    management_category       = IntValue() # 30
    last_cutting_method       = IntValue() # 31
    municipality              = IntValue() # 32
    _33                       = AnyReserved() # 33
    _34                       = AnyReserved() # 34

class RsdTree(Record):
    f                         = Value() # 1
    spe                       = IntValue() # 2
    d                         = Value() # 3
    h                         = Value() # 4
    age                       = Value() # 5
    bio_age                   = Value() # 6
    rmswl                     = Optional(Value()) # Reduction to model-based saw log volume, 7
    prune_year                = Optional(Value()) # 8
    age_13_10                 = Optional(Value()) # Age at 1.3 m height when reached 10 cm diameter at breast height, 9
    origin                    = Optional(IntValue()) # 10
    sample_id                 = Optional(IntValue()) # 11
    orig_angle                = Optional(Value()) # 12
    orig_dist                 = Optional(Value()) # 13
    orig_hdif                 = Optional(Value()) # 14
    h_low_branch              = Optional(Value()) # 15
    management_category       = Optional(IntValue()) # 16
    _17                       = AnyReserved() # 17

class RsdInitialDataRecord:

    record_type = 1

    def __init__(self, plot=None, trees=None):
        self.plot = plot or RsdSamplePlot()
        self.trees = trees or []

    def to_floats(self):
        return [
            len(RsdSamplePlot.fields),
            *self.plot.to_floats(),
            len(self.trees),
            len(RsdTree.fields),
            *(f for t in self.trees for f in t.to_floats())
        ]

    def to_json(self):
        return {
            "record_type": self.record_type,
            **self.plot.to_json(),
            "trees": [t.to_json() for t in self.trees]
        }

    @classmethod
    def from_floats(cls, buf):
        stream = FpStream(buf)
        nv = stream.nextint()
        if nv > len(RsdSamplePlot.fields):
            raise ValueError(f"Given {nv} sample plot fields but only have {len(RsdSamplePlot.fields)}")

        plot = RsdSamplePlot.decode(stream, fields=RsdSamplePlot.fields[:nv])

        nt = stream.nextint()
        ntv = stream.nextint()

        trees = [RsdTree.decode(stream, fields=RsdTree.fields[:ntv]) for _ in range(nt)]
        return cls(plot, trees)

    @classmethod
    def from_json(cls, src):
        plot = RsdSamplePlot.from_json(src)
        trees = [RsdTree.from_json(t) for t in src["trees"]]
        return cls(plot, trees)
