from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, validator

from opennem.schema.core import BaseConfig
from opennem.schema.time import TimeIntervalAPI, TimePeriodAPI


class ScadaInterval(object):
    date: datetime
    value: Optional[float]

    def __init__(self, date: datetime, value: Optional[float] = None):
        self.date = date
        self.value = value


class ScadaReading(Tuple[datetime, Optional[float]]):
    pass


class UnitScadaReading(BaseModel):
    code: str
    data: List[ScadaReading]


class StationScadaReading(BaseModel):
    code: str
    facilities: Dict[str, UnitScadaReading]


class OpennemDataHistory(BaseConfig):
    start: Union[datetime, date]
    last: Union[datetime, date]
    interval: str
    data: Optional[List[Optional[float]]]
    history: Optional[List[Optional[float]]]

    @validator("data")
    def validate_data(cls, data_value):
        data_value = list(
            map(lambda x: round(x, 2) if x else None, data_value)
        )

        return data_value

    @validator("history")
    def validate_history(cls, data_value):
        data_value = list(
            map(lambda x: round(x, 2) if x else None, data_value)
        )

        return data_value


class OpennemData(BaseConfig):
    region: Optional[str]
    fuel_tech: Optional[str]

    network: str
    data_type: str
    code: str = ""
    units: str
    history: OpennemDataHistory


class OpennemDataSet(BaseConfig):
    network: str = ""
    code: str
    region: Optional[str]
    interval: TimeIntervalAPI
    period: TimePeriodAPI

    data: List[OpennemData]


class DataQueryResult(BaseConfig):
    interval: datetime
    result: Union[float, int, None, Decimal]
    group_by: Optional[str]
