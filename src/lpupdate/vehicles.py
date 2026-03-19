from __future__ import annotations

from typing import Final

FUND_I: Final[str] = 'BuenTrip Ventures Fund I'
FUND_II: Final[str] = 'BuenTrip Ventures Fund II'
KRIPTOS_LLC: Final[str] = 'BuenTrip Ventures Kriptos LLC'
KRIPTOS_SEED: Final[str] = 'BTV Kriptos Series Seed LLC'
ALTSCORE_SERIES_A: Final[str] = 'BTV AltScore Series A'
FAMILIFY_SEED_EXTENSION: Final[str] = 'BTV Familify Seed Extension LLC'

COMPANY_VEHICLES: Final[dict[str, list[str]]] = {
    'Airpals': [FUND_I],
    'Altscore': [FUND_I, ALTSCORE_SERIES_A],
    'Autority': [FUND_I],
    'Databits': [FUND_I],
    'Familify': [FUND_I, FAMILIFY_SEED_EXTENSION],
    'Kriptos': [FUND_I, KRIPTOS_LLC, KRIPTOS_SEED],
    'Leasy': [FUND_I],
    'Mercately': [FUND_I],
    'MOX': [FUND_I],
    'Nuvocargo': [FUND_I],
    'Pardux': [FUND_I],
    'Picker': [FUND_I],
    'Pronto': [FUND_I],
    'Rampa': [FUND_I],
    'Reliv': [FUND_I],
    'Shippify': [FUND_I],
    'Taxo': [FUND_I],
    'Aloja': [FUND_II],
    'Bem': [FUND_II],
    'Birdie': [FUND_II],
    'Conductor': [FUND_II],
    'Construct AI': [FUND_II],
    'Finnecto': [FUND_II],
    'Neta AI': [FUND_II],
    'Paymon': [FUND_II],
    'Publifyer': [FUND_II],
    'Synthera AI': [FUND_II],
    'Vertebra': [FUND_II],
    'Wava': [FUND_II],
    'Xmonitoring': [FUND_II],
}

CANONICAL_COMPANY_NAMES: Final[dict[str, str]] = {name.casefold(): name for name in COMPANY_VEHICLES}


def canonicalize_company_name(company_name: str | None) -> str | None:
    if not company_name:
        return None
    cleaned = ' '.join(str(company_name).split()).strip()
    return CANONICAL_COMPANY_NAMES.get(cleaned.casefold(), cleaned)


def vehicles_for_company(company_name: str | None) -> list[str]:
    canonical_name = canonicalize_company_name(company_name)
    if not canonical_name:
        return []
    return list(COMPANY_VEHICLES.get(canonical_name, []))


def company_vehicle_type(vehicle_name: str) -> str:
    if vehicle_name in {FUND_I, FUND_II}:
        return 'fund'
    return 'spv'
