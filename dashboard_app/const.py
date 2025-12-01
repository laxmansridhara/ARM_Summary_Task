from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class Config:
    DOI_PREFIX: str = "https://doi.org/"
    AUTHORS_ID_PREFIX: str = "at"
    KEYWORDS_ID_PREFIX:str = "kd"
    RESEARCHER_ID_PREFIX:str = "rs"
    
@dataclass(frozen=True)
class PaperTypes(Enum):
    ARTICLE = 1
    JOURNAL = 2
    VOLUME = 3
    UNSTRUCTURED = 4