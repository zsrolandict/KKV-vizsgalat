"""Tao workbench input, independent of the existing KKV assessment format."""
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from .models import Model, Person


class Evidence(Model):
    source: str = Field(default='', max_length=2000)
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1, le=10000)
    quote: str = Field(default='', max_length=4000)


class TaoCompany(Model):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    registration: str = Field(default='', max_length=80)
    registry_reviewed_on: date | None = None
    registry_source: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def review_source(self):
        if self.registry_reviewed_on and not self.registry_source:
            raise ValueError('A cégjegyzéki ellenőrzéshez forrás szükséges.')
        return self


class VotingFact(Model):
    id: str = Field(min_length=1, max_length=80)
    owner: str
    company: str
    capital: Decimal | None = Field(default=None, ge=0, le=100, max_digits=16, decimal_places=10)
    vote_mode: Literal['ownership_default', 'explicit', 'expert', 'unknown'] = 'ownership_default'
    votes: Decimal | None = Field(default=None, ge=0, le=100, max_digits=16, decimal_places=10)
    vote_bound: Literal['exact', 'over_half'] = 'exact'
    valid_from: date | None = None
    valid_to: date | None = None
    reviewed_as_of: date | None = None
    registered_on: date | None = None
    deletion_registered_on: date | None = None
    evidence: Evidence = Field(default_factory=Evidence)
    reason: str = Field(default='', max_length=3000)

    @model_validator(mode='after')
    def validate_fact(self):
        if self.owner == self.company:
            raise ValueError('Önmagára mutató tulajdoni kapcsolat nem adható meg.')
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError('A kizáró végdátumnak a kezdőnap után kell lennie.')
        if self.vote_mode in ('explicit', 'expert'):
            if self.vote_bound == 'exact' and self.votes is None:
                raise ValueError('Pontos szavazati adathoz százalék szükséges.')
            if self.vote_bound == 'over_half' and self.votes is not None:
                raise ValueError('Az 50% feletti jelzéshez nem adható kitalált pontos százalék.')
        elif self.votes is not None or self.vote_bound != 'exact':
            raise ValueError('Külön szavazat explicit vagy szakértői módban adható meg.')
        if self.vote_mode == 'expert' and not self.reason:
            raise ValueError('A szakértői felülbírálat indoka kötelező.')
        return self


class PairDecision(Model):
    first: str
    second: str
    as_of: date
    result: Literal['related', 'not_related', 'undetermined'] = 'undetermined'
    stage: Literal['unreviewed', 'awaiting_declaration', 'missing_data', 'management_review'] = 'unreviewed'
    basis: str = Field(default='', max_length=2000)
    reason: str = Field(default='', max_length=5000)
    evidence: Evidence = Field(default_factory=Evidence)
    assumptions: str = Field(default='', max_length=3000)
    missing: str = Field(default='', max_length=3000)
    confirmed: bool = False
    relevant_grounds_reviewed: bool = False

    @model_validator(mode='after')
    def validate_decision(self):
        if self.first == self.second:
            raise ValueError('Két külön vállalkozás szükséges.')
        if self.result != 'undetermined' and self.confirmed:
            if not all((self.basis, self.reason, self.evidence.source)):
                raise ValueError('Megerősített minősítéshez jogalap, indok és forrás szükséges.')
            if self.result == 'not_related' and not self.relevant_grounds_reviewed:
                raise ValueError('Negatív minősítéshez a releváns jogalapok ellenőrzése szükséges.')
        if self.result == 'undetermined' and self.confirmed and not self.reason:
            raise ValueError('A részleges megállapításhoz a bizonytalanság indoka szükséges.')
        return self


FAMILY_LABELS = {
    'spouse': 'Házastárs', 'lineal': 'Egyeneságbeli rokon',
    'adoptive': 'Örökbefogadó szülő / örökbefogadott gyermek',
    'step': 'Mostohaszülő / mostohagyermek', 'foster': 'Nevelőszülő / nevelt gyermek',
    'sibling': 'Testvér (féltestvér is)', 'partner': 'Élettárs – nem közeli hozzátartozó',
    'other': 'Egyéb hozzátartozó – külön szakértői vizsgálat',
}
CLOSE_FAMILY_TYPES = frozenset(FAMILY_LABELS) - {'partner', 'other'}


class FamilyFact(Model):
    id: str = Field(min_length=1, max_length=80)
    first: str
    second: str
    relationship: Literal['spouse', 'lineal', 'adoptive', 'step', 'foster', 'sibling', 'partner', 'other']
    valid_from: date | None = None
    valid_to: date | None = None
    reviewed_as_of: date | None = None
    evidence: Evidence = Field(default_factory=Evidence)
    confirmed: bool = False

    @model_validator(mode='after')
    def validate_family(self):
        if self.first == self.second:
            raise ValueError('Két külön természetes személy szükséges.')
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError('A kizáró végdátumnak a kezdőnap után kell lennie.')
        if self.confirmed and not self.evidence.source.strip():
            raise ValueError('Igazolt rokonsághoz forrás / nyilatkozat szükséges.')
        return self


CONTROL_LABELS = {
    'appointments': 'Vezető tisztségviselők / felügyelőbizottság többségének megválasztási vagy visszahívási joga',
    'voting_agreement': 'Más tagokkal kötött szavazási megállapodás',
}


class ControlFact(Model):
    id: str = Field(min_length=1, max_length=80)
    owner: str
    company: str
    kind: Literal['appointments', 'voting_agreement']
    membership: Literal['unknown', 'member', 'not_member'] = 'unknown'
    condition: Literal['unknown', 'yes', 'no'] = 'unknown'
    aligned_bound: Literal['exact', 'over_half'] = 'exact'
    aligned_votes: Decimal | None = Field(default=None, ge=0, le=100, max_digits=16, decimal_places=10)
    valid_from: date | None = None
    valid_to: date | None = None
    reviewed_as_of: date | None = None
    reason: str = Field(default='', max_length=4000)
    evidence: Evidence = Field(default_factory=Evidence)
    confirmed: bool = False

    @model_validator(mode='after')
    def validate_control(self):
        if self.owner == self.company:
            raise ValueError('Két külön szereplő szükséges.')
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError('A kizáró végdátumnak a kezdőnap után kell lennie.')
        if self.aligned_bound == 'over_half' and self.aligned_votes is not None:
            raise ValueError('Az 50% feletti megállapodási jelzéshez nem adható pontos százalék.')
        if self.kind == 'appointments' and (self.aligned_votes is not None or self.aligned_bound != 'exact'):
            raise ValueError('Megválasztási joghoz nem adható meg összehangolt szavazati százalék.')
        if self.confirmed and not (self.evidence.source.strip() and self.reason.strip()):
            raise ValueError('Igazolt irányítási tényhez forrás és indok szükséges.')
        return self


class ManagementFact(Model):
    id: str = Field(min_length=1, max_length=80)
    first: str
    second: str
    managers: list[str] = Field(min_length=1, max_length=30)
    common_management: Literal['unknown', 'yes', 'no'] = 'unknown'
    business_control: Literal['unknown', 'yes', 'no'] = 'unknown'
    financial_control: Literal['unknown', 'yes', 'no'] = 'unknown'
    valid_from: date | None = None
    valid_to: date | None = None
    reviewed_as_of: date | None = None
    reason: str = Field(default='', max_length=4000)
    evidence: Evidence = Field(default_factory=Evidence)
    confirmed: bool = False

    @model_validator(mode='after')
    def validate_management(self):
        if self.first == self.second:
            raise ValueError('Két külön vállalkozás szükséges.')
        if len(self.managers) != len(set(self.managers)):
            raise ValueError('A közös vezető nem ismétlődhet.')
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError('A kizáró végdátumnak a kezdőnap után kell lennie.')
        if self.confirmed and not (self.evidence.source.strip() and self.reason.strip()):
            raise ValueError('Igazolt ügyvezetési tényhez forrás és indok szükséges.')
        return self


class TaoAssessment(Model):
    schema_version: Literal[1] = 1
    title: str = Field(min_length=1, max_length=200)
    client: str = Field(default='', max_length=200)
    as_of: date
    purpose: str = Field(default='Tao-kapcsoltság – transzferár előkészítése', max_length=2000)
    scope: str = Field(default='', max_length=5000)
    assumptions: str = Field(default='', max_length=5000)
    law_date: date | None = None
    law_source: str = Field(default='', max_length=3000)
    companies: list[TaoCompany] = Field(min_length=2, max_length=60)
    persons: list[Person] = Field(default_factory=list, max_length=250)
    voting_facts: list[VotingFact] = Field(default_factory=list, max_length=2000)
    family_facts: list[FamilyFact] = Field(default_factory=list, max_length=1000)
    control_facts: list[ControlFact] = Field(default_factory=list, max_length=1000)
    management_facts: list[ManagementFact] = Field(default_factory=list, max_length=1000)
    decisions: list[PairDecision] = Field(default_factory=list, max_length=1770)

    @model_validator(mode='after')
    def validate_references(self):
        cids = {c.id for c in self.companies}
        ids = [c.id for c in self.companies] + [p.id for p in self.persons]
        if len(ids) != len(set(ids)):
            raise ValueError('A szereplők azonosítói nem ismétlődhetnek.')
        for fact in self.voting_facts:
            if fact.owner not in ids or fact.company not in cids:
                raise ValueError('A szavazati tény ismeretlen szereplőre mutat.')
        if len({f.id for f in self.voting_facts}) != len(self.voting_facts):
            raise ValueError('Ismétlődő tényazonosító.')
        person_ids = {p.id for p in self.persons}
        if len({f.id for f in self.family_facts}) != len(self.family_facts):
            raise ValueError('Ismétlődő rokonsági tényazonosító.')
        for fact in self.family_facts:
            if fact.first not in person_ids or fact.second not in person_ids:
                raise ValueError('Rokonság csak rögzített természetes személyek között adható meg.')
        for collection in (self.control_facts, self.management_facts):
            if len({f.id for f in collection}) != len(collection):
                raise ValueError('Ismétlődő irányítási tényazonosító.')
        for fact in self.control_facts:
            if fact.owner not in ids or fact.company not in cids:
                raise ValueError('Az irányítási jog ismeretlen szereplőre mutat.')
        for fact in self.management_facts:
            if fact.first not in cids or fact.second not in cids or any(m not in ids for m in fact.managers):
                raise ValueError('Az ügyvezetési tény ismeretlen szereplőre mutat.')
        keys = []
        for decision in self.decisions:
            if decision.first not in cids or decision.second not in cids:
                raise ValueError('A döntés ismeretlen vállalkozásra mutat.')
            keys.append((tuple(sorted((decision.first, decision.second))), decision.as_of))
        if len(keys) != len(set(keys)):
            raise ValueError('Egy cégpár egy napra csak egy döntést kaphat.')
        return self
