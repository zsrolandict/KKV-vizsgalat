"""Validated, versioned assessment input. Percentages are 0..100; money is HUF."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)


Percent = Decimal
Category = Literal['micro', 'small', 'medium', 'large']


class Company(Model):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    registration: str = Field(default='', max_length=80)
    country: str = Field(default='HU', max_length=3)
    kind: Literal['company', 'public', 'investor'] = 'company'
    activity: str = Field(default='', max_length=2000)
    founded: date | None = None
    ceased: date | None = None
    investor_exception: bool = False
    exception_reason: str = Field(default='', max_length=2000)


class Person(Model):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    notes: str = Field(default='', max_length=2000)


class Ownership(Model):
    id: str = Field(min_length=1, max_length=80)
    owner: str
    company: str
    capital: Decimal = Field(ge=0, le=100, max_digits=16, decimal_places=10)
    votes: Decimal = Field(ge=0, le=100, max_digits=16, decimal_places=10)
    start: date | None = None
    end: date | None = None
    control: bool = False
    reason: str = Field(default='', max_length=3000)
    source: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def dates(self):
        if self.start and self.end and self.end < self.start:
            raise ValueError('A kapcsolat vége nem előzheti meg a kezdetét.')
        if self.owner == self.company:
            raise ValueError('Önmagára mutató tulajdoni kapcsolat nem adható meg.')
        return self


class Family(Model):
    id: str
    first: str
    second: str
    relationship: str = Field(min_length=1, max_length=150)
    source: str = Field(default='', max_length=1000)


class Decision(Model):
    id: str
    first: str
    second: str
    relation: Literal['linked', 'partner', 'independent', 'unresolved']
    percent: Decimal = Field(default=0, ge=0, le=100, max_digits=16, decimal_places=10)
    basis: Literal['ownership', 'control', 'persons', 'expert'] = 'expert'
    reason: str = Field(default='', max_length=4000)
    market: str = Field(default='', max_length=2000)
    acting_together: str = Field(default='', max_length=2000)
    source: str = Field(default='', max_length=1000)
    confirmed: bool = False
    start: date | None = None
    end: date | None = None

    @model_validator(mode='after')
    def valid(self):
        if self.first == self.second:
            raise ValueError('Kapcsolati döntéshez két külön vállalkozás szükséges.')
        if self.relation == 'partner' and self.percent == 0:
            raise ValueError('A partner beszámítási aránya nem lehet nulla.')
        if self.start and self.end and self.end < self.start:
            raise ValueError('A döntés időszaka hibás.')
        return self


class Financial(Model):
    company: str
    year: int = Field(ge=1990, le=2100)
    employees: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=8)
    turnover: Decimal | None = Field(default=None, ge=0, max_digits=28, decimal_places=8)
    balance: Decimal | None = Field(default=None, ge=0, max_digits=28, decimal_places=8)
    currency: Literal['HUF', 'EUR'] = 'HUF'
    start: date | None = None
    end: date | None = None
    accepted: date | None = None
    employment_method: Literal['annual', 'AWU', 'estimate'] = 'annual'
    source: str = Field(default='', max_length=1000)
    consolidated: bool = False
    included: list[str] = Field(default_factory=list, max_length=250)
    estimated: bool = False
    annualized: bool = False

    @model_validator(mode='after')
    def dates(self):
        if self.start and self.end and self.end < self.start:
            raise ValueError('A beszámoló időszaka hibás.')
        if self.end and self.accepted and self.accepted < self.end:
            raise ValueError('A beszámoló elfogadása nem előzheti meg az év végét.')
        if self.included and not self.consolidated:
            raise ValueError('Beszámolóba bevont cégek csak konszolidált adatnál adhatók meg.')
        return self


class Rate(Model):
    year: int = Field(ge=1990, le=2100)
    date: date
    quoted: date | None = None
    value: Decimal = Field(gt=0, max_digits=18, decimal_places=8)
    source: str = Field(default='', max_length=1000)
    confirmed: bool = False


class Event(Model):
    id: str
    date: date
    kind: Literal['founding', 'acquisition', 'merger', 'split', 'control', 'other']
    description: str = Field(min_length=1, max_length=3000)
    resolution: str = Field(default='', max_length=3000)
    confirmed: bool = False
    immediate: bool = False


class AggregationOverride(Model):
    year: int
    company: str
    percent: Decimal = Field(ge=0, le=100, max_digits=16, decimal_places=10)
    reason: str = Field(min_length=1, max_length=3000)
    confirmed: bool = False


class PublicReview(Model):
    capital: Decimal = Field(default=0, ge=0, le=100)
    votes: Decimal = Field(default=0, ge=0, le=100)
    exception: bool = False
    reason: str = Field(default='', max_length=3000)
    confirmed: bool = False


class Assessment(Model):
    schema_version: int = 1
    title: str = Field(min_length=1, max_length=200)
    client: str = Field(default='', max_length=200)
    purpose: str = Field(default='KKV-minősítés', max_length=1000)
    as_of: date
    law_date: date | None = None
    law_source: str = Field(default='', max_length=3000)
    law_applicability: str = Field(default='', max_length=3000)
    profile: Literal['HU', 'EU'] = 'HU'
    structure_basis: Literal['period_end', 'assessment'] = 'period_end'
    root: str
    years: list[int] = Field(min_length=1, max_length=10)
    previous_category: Category | None = None
    previous_date: date | None = None
    companies: list[Company] = Field(default_factory=list, max_length=250)
    persons: list[Person] = Field(default_factory=list, max_length=500)
    ownerships: list[Ownership] = Field(default_factory=list, max_length=2000)
    families: list[Family] = Field(default_factory=list, max_length=1000)
    decisions: list[Decision] = Field(default_factory=list, max_length=2000)
    financials: list[Financial] = Field(default_factory=list, max_length=2500)
    rates: list[Rate] = Field(default_factory=list, max_length=10)
    events: list[Event] = Field(default_factory=list, max_length=100)
    overrides: list[AggregationOverride] = Field(default_factory=list, max_length=200)
    public_review: PublicReview = Field(default_factory=PublicReview)
    assumptions: str = Field(default='', max_length=10000)
    conclusion_notes: str = Field(default='', max_length=10000)

    @model_validator(mode='after')
    def references(self):
        ids = [c.id for c in self.companies] + [p.id for p in self.persons]
        if len(ids) != len(set(ids)):
            raise ValueError('A szereplők azonosítói nem lehetnek ismétlődők.')
        cids = {c.id for c in self.companies}
        pids = {p.id for p in self.persons}
        if self.root not in cids:
            raise ValueError('A vizsgált vállalkozás hiányzik a cégek közül.')
        if len(self.years) != len(set(self.years)):
            raise ValueError('Egy év csak egyszer szerepelhet.')
        for o in self.ownerships:
            if o.owner not in set(ids) or o.company not in cids:
                raise ValueError('Tulajdoni kapcsolat ismeretlen szereplőre mutat.')
        for f in self.families:
            if f.first not in pids or f.second not in pids or f.first == f.second:
                raise ValueError('Rokonsági kapcsolat csak két ismert személy között lehet.')
        for d in self.decisions:
            if d.first not in cids or d.second not in cids:
                raise ValueError('Kapcsolati döntés ismeretlen vállalkozásra mutat.')
        keys = [(f.company, f.year) for f in self.financials]
        if len(keys) != len(set(keys)):
            raise ValueError('Egy vállalkozás és év pénzügyi adata csak egyszer szerepelhet.')
        for f in self.financials:
            if f.company not in cids or not set(f.included) <= cids:
                raise ValueError('A beszámoló ismeretlen vállalkozást tartalmaz.')
        if len({r.year for r in self.rates}) != len(self.rates):
            raise ValueError('Egy évhez csak egy vizsgálati árfolyam tartozhat.')
        for o in self.overrides:
            if o.company not in cids:
                raise ValueError('Az összeszámítási döntés cége ismeretlen.')
        if len({(o.year, o.company) for o in self.overrides}) != len(self.overrides):
            raise ValueError('Ismétlődő összeszámítási döntés.')
        for collection in [self.ownerships, self.families, self.decisions, self.events]:
            if len({x.id for x in collection}) != len(collection):
                raise ValueError('Ismétlődő kapcsolati vagy eseményazonosító.')
        return self
