"""ONVIF control channel for Tapo IP cameras.

Handles non-video communication: device identity, stream discovery, and PTZ.
Tapo exposes ONVIF on port 2020 rather than the usual 80.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from types import TracebackType

from onvif import ONVIFCamera

logger = logging.getLogger(__name__)

DEFAULT_ONVIF_PORT = 2020


@dataclass(frozen=True)
class DeviceInfo:
    """Identity reported by the camera."""

    manufacturer: str
    model: str
    firmware_version: str
    serial_number: str
    hardware_id: str


class TapoOnvifClient:
    """Thin ONVIF wrapper exposing the operations this POC needs."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = DEFAULT_ONVIF_PORT,
        wsdl_dir: str | None = None,
    ) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._port = port
        self._wsdl_dir = wsdl_dir
        self._camera: ONVIFCamera | None = None
        self._media = None
        self._ptz = None
        self._profile_token: str | None = None

    def __enter__(self) -> "TapoOnvifClient":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def connect(self) -> None:
        """Open the ONVIF session and cache the first media profile."""
        if self._camera is not None:
            return

        logger.info("Opening ONVIF session to %s:%d", self._host, self._port)
        kwargs = {"wsdl_dir": self._wsdl_dir} if self._wsdl_dir else {}
        self._camera = ONVIFCamera(
            self._host, self._port, self._username, self._password, **kwargs
        )
        self._media = self._camera.create_media_service()

        profiles = self._media.GetProfiles()
        if not profiles:
            raise RuntimeError(f"Camera {self._host} reported no ONVIF media profiles")
        self._profile_token = profiles[0].token

    def close(self) -> None:
        self._camera = None
        self._media = None
        self._ptz = None
        self._profile_token = None

    def _require_media(self):
        if self._media is None or self._profile_token is None:
            raise RuntimeError("ONVIF session is not open; call connect() first")
        return self._media

    def device_info(self) -> DeviceInfo:
        """Return manufacturer, model, and firmware details."""
        if self._camera is None:
            raise RuntimeError("ONVIF session is not open; call connect() first")

        info = self._camera.devicemgmt.GetDeviceInformation()
        return DeviceInfo(
            manufacturer=info.Manufacturer,
            model=info.Model,
            firmware_version=info.FirmwareVersion,
            serial_number=info.SerialNumber,
            hardware_id=info.HardwareId,
        )

    def stream_uri(self) -> str:
        """Ask the camera for its RTSP URI instead of assuming the path."""
        media = self._require_media()
        request = media.create_type("GetStreamUri")
        request.ProfileToken = self._profile_token
        request.StreamSetup = {
            "Stream": "RTP-Unicast",
            "Transport": {"Protocol": "RTSP"},
        }
        return media.GetStreamUri(request).Uri

    def snapshot_uri(self) -> str:
        """Return the still-image URI, useful for cheap liveness checks."""
        media = self._require_media()
        request = media.create_type("GetSnapshotUri")
        request.ProfileToken = self._profile_token
        return media.GetSnapshotUri(request).Uri

    def _ptz_service(self):
        if self._camera is None or self._profile_token is None:
            raise RuntimeError("ONVIF session is not open; call connect() first")
        if self._ptz is None:
            self._ptz = self._camera.create_ptz_service()
        return self._ptz

    def get_position(self) -> tuple[float, float]:
        """Return the current (pan, tilt) in the -1.0 to 1.0 space.

        Record this before moving; continuous moves are not reversible by
        issuing an equal move in the opposite direction, because the axis may
        hit an end stop partway through.
        """
        ptz = self._ptz_service()
        position = ptz.GetStatus({"ProfileToken": self._profile_token}).Position
        return float(position.PanTilt.x), float(position.PanTilt.y)

    def goto_position(self, pan: float, tilt: float, *, settle_s: float = 4.0) -> None:
        """Move to an absolute (pan, tilt) and wait for the motion to finish.

        A long sweep needs several seconds; reading the position too early
        reports an intermediate value.
        """
        for name, value in (("pan", pan), ("tilt", tilt)):
            if not -1.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between -1.0 and 1.0")

        ptz = self._ptz_service()
        request = ptz.create_type("AbsoluteMove")
        request.ProfileToken = self._profile_token
        request.Position = {"PanTilt": {"x": pan, "y": tilt}}
        ptz.AbsoluteMove(request)
        time.sleep(settle_s)

    def move(self, pan: float, tilt: float, duration_s: float = 0.5) -> None:
        """Pan/tilt at the given velocities (-1.0 to 1.0) then stop.

        Raises if the model has no PTZ hardware, such as the fixed C100/C110.
        """
        for name, value in (("pan", pan), ("tilt", tilt)):
            if not -1.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between -1.0 and 1.0")

        ptz = self._ptz_service()
        request = ptz.create_type("ContinuousMove")
        request.ProfileToken = self._profile_token
        request.Velocity = {"PanTilt": {"x": pan, "y": tilt}}

        ptz.ContinuousMove(request)
        try:
            time.sleep(duration_s)
        finally:
            ptz.Stop({"ProfileToken": self._profile_token})
