"""Configuración de la app, leída de variables de entorno / archivo .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8",
                                      extra="ignore")

    # Base de la tienda (pedidos, usuarios, zonas, contenido)
    db_tienda_host: str = "167.250.5.60"
    db_tienda_port: int = 3306
    db_tienda_user: str = "iebbbhrt_operador"
    db_tienda_password: str = ""
    db_tienda_name: str = "iebbbhrt_prueba_paginaweb"

    # Base del ERP (catálogo)
    db_erp_host: str = "167.250.5.60"
    db_erp_port: int = 3306
    db_erp_user: str = "iebbbhrt_operador"
    db_erp_password: str = ""
    db_erp_name: str = "iebbbhrt_masorganicos"

    secret_key: str = "dev-inseguro-cambiar"
    img_base_url: str = "/img"
    entorno: str = "development"

    # Si es False, el checkout NO escribe en grupos/transacciones (simula).
    permitir_escribir_pedidos: bool = False

    def url_tienda(self) -> str:
        return (
            f"mysql+pymysql://{self.db_tienda_user}:{self.db_tienda_password}"
            f"@{self.db_tienda_host}:{self.db_tienda_port}/{self.db_tienda_name}?charset=utf8mb4"
        )

    def url_erp(self) -> str:
        return (
            f"mysql+pymysql://{self.db_erp_user}:{self.db_erp_password}"
            f"@{self.db_erp_host}:{self.db_erp_port}/{self.db_erp_name}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
