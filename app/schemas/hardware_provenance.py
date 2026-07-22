"""Hardware provenance emitted at the locked ETL-to-AI boundary."""

from pydantic import BaseModel


class HardwareProvenance(BaseModel):
    """Firmware, hardware, and protocol identity for one ETL session."""

    firmware_revision: str
    hardware_revision: str
    protocol_version: str
