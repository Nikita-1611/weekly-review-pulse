from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

class ProductConfig(BaseModel):
    id: str
    name: str
    app_store_id: str
    play_store_package: str
    google_doc_id: str
    stakeholder_emails: List[str]

class YamlSettings(BaseModel):
    rolling_window_weeks: int = 10
    environment: str = "development"
    products: List[ProductConfig] = Field(default_factory=list)

class Settings(BaseSettings):
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

import os

def load_products_yaml(path: Optional[str] = None) -> YamlSettings:
    if path is None:
        path = os.environ.get("PULSE_CONFIG_PATH", "config.yaml")
    
    if not os.path.exists(path):
        # Return empty settings if file doesn't exist (helpful for testing)
        return YamlSettings()

    with open(path, "r") as f:
        data = yaml.safe_load(f)
    
    # If the YAML is just a list, treat it as the 'products' list
    if isinstance(data, list):
        return YamlSettings(products=data)
    
    # If it's empty, return defaults
    if data is None:
        return YamlSettings()
        
    return YamlSettings(**data)

# Global instances
env_settings = Settings()
yaml_settings = load_products_yaml()
