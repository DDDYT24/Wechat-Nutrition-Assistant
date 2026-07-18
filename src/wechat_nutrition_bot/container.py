from __future__ import annotations

from dataclasses import dataclass

from .catalog import FoodCatalog
from .config import Settings, get_settings
from .deepseek import DeepSeekClient
from .nutrition import NutritionCalculator
from .parser import MealParser
from .profile_parser import ProfileParser
from .repository import Repository
from .service import NutritionService


@dataclass
class Components:
    settings: Settings
    catalog: FoodCatalog
    repository: Repository
    deepseek: DeepSeekClient
    parser: MealParser
    profile_parser: ProfileParser
    calculator: NutritionCalculator
    service: NutritionService


def build_components(settings: Settings | None = None) -> Components:
    resolved = settings or get_settings()
    catalog = FoodCatalog(resolved.food_catalog_path)
    repository = Repository(resolved.database_path, resolved.user_hmac_secret)
    deepseek = DeepSeekClient(
        api_key=resolved.deepseek_api_key,
        base_url=resolved.deepseek_base_url,
        model=resolved.deepseek_model,
        timeout_seconds=resolved.deepseek_timeout_seconds,
    )
    parser = MealParser(catalog, deepseek)
    profile_parser = ProfileParser(deepseek)
    calculator = NutritionCalculator(catalog)
    service = NutritionService(catalog, calculator, parser, repository)
    return Components(
        settings=resolved,
        catalog=catalog,
        repository=repository,
        deepseek=deepseek,
        parser=parser,
        profile_parser=profile_parser,
        calculator=calculator,
        service=service,
    )
