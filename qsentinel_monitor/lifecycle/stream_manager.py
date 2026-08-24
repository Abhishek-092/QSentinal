"""
Phase 10 Monitoring Stream & Epoch Lifecycle Manager for QSENTINEL.

Manages creation of monitoring streams, multi-detector monitoring epochs,
explicit calibration context binding, and clean epoch renewals.
"""
import uuid
import json
from typing import Any

from qsentinel_monitor.persistence.database import get_connection, transaction_scope
from qsentinel_monitor.persistence.repositories import (
    StreamRepository,
    EpochRepository,
    ArtifactRepository,
)
from qsentinel_monitor.persistence.models import (
    StreamRecord,
    EpochRecord,
    CryptographicIntegrityError,
)
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.stage2_calibration_loader import Stage2CalibrationArtifact
from qsentinel_monitor.changepoint_calibration_loader import ChangePointCalibrationArtifact


class StreamLifecycleManager:
    """Manages long-lived monitoring streams and bounded sequential multi-detector epochs."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def create_stream(self, stream_id: str, description: str = "") -> StreamRecord:
        """Creates a new monitoring stream."""
        return StreamRepository.create_stream(self.db_path, stream_id, description)

    def create_epoch(
        self,
        stream_id: str,
        calibration_context: dict[str, Any],
        stage1_artifact: CalibrationArtifact | None = None,
        stage2_artifact: Stage2CalibrationArtifact | None = None,
        changepoint_artifact: ChangePointCalibrationArtifact | None = None,
    ) -> EpochRecord:
        """
        Creates a new multi-detector monitoring epoch bound to explicit artifacts and calibration context.
        FAILS if required calibration context (e.g. calibration_p) is missing.
        """
        if "calibration_p" not in calibration_context:
            raise ValueError("Explicit calibration_p operating point required in calibration_context.")

        # Save & verify artifacts in DB repository
        st1_hash = (
            ArtifactRepository.save_artifact(
                self.db_path, "STAGE1", stage1_artifact.__dict__
            )
            if stage1_artifact
            else None
        )
        st2_hash = (
            ArtifactRepository.save_artifact(
                self.db_path, "STAGE2", stage2_artifact.__dict__
            )
            if stage2_artifact
            else None
        )
        cp_hash = (
            ArtifactRepository.save_artifact(
                self.db_path, "CHANGEPOINT", changepoint_artifact.__dict__
            )
            if changepoint_artifact
            else None
        )

        latest_epoch = EpochRepository.get_latest_epoch(self.db_path, stream_id)
        next_index = 1 if latest_epoch is None else latest_epoch.epoch_index + 1
        epoch_id = f"{stream_id}-epoch-{next_index}-{uuid.uuid4().hex[:8]}"

        return EpochRepository.create_epoch(
            db_path=self.db_path,
            epoch_id=epoch_id,
            stream_id=stream_id,
            epoch_index=next_index,
            calibration_context=calibration_context,
            stage1_artifact_hash=st1_hash,
            stage2_artifact_hash=st2_hash,
            changepoint_artifact_hash=cp_hash,
        )

    def renew_epoch(
        self,
        stream_id: str,
        calibration_context: dict[str, Any],
        termination_reason: str = "EXPLICIT_RENEWAL",
        stage1_artifact: CalibrationArtifact | None = None,
        stage2_artifact: Stage2CalibrationArtifact | None = None,
        changepoint_artifact: ChangePointCalibrationArtifact | None = None,
    ) -> EpochRecord:
        """
        Closes current active epoch and spawns a clean Epoch (index + 1) bound to new/updated artifacts.
        """
        active_epoch = EpochRepository.get_latest_epoch(self.db_path, stream_id)
        if active_epoch and active_epoch.status in ("ACTIVE", "ELEVATED", "EXPIRED"):
            EpochRepository.update_epoch_status(
                self.db_path, active_epoch.epoch_id, "CLOSED", termination_reason
            )

        return self.create_epoch(
            stream_id=stream_id,
            calibration_context=calibration_context,
            stage1_artifact=stage1_artifact,
            stage2_artifact=stage2_artifact,
            changepoint_artifact=changepoint_artifact,
        )
