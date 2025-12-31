"""Tests for AutoDownloadService."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Channel,
    Design,
    DesignSource,
    DesignStatus,
    DownloadMode,
    Job,
    JobStatus,
    JobType,
    TelegramMessage,
)
from app.services.auto_download import AutoDownloadService


def unique_peer_id() -> str:
    """Generate a unique telegram_peer_id for tests."""
    return f"test_{uuid.uuid4().hex[:12]}"


class TestAutoDownloadCheckAndQueue:
    """Tests for check_and_queue_design method."""

    @pytest.mark.asyncio
    async def test_manual_mode_no_download(self, test_session: AsyncSession):
        """Test that MANUAL mode doesn't trigger downloads."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Manual Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.flush()

        design = Design(
            canonical_title="Test Design",
            status=DesignStatus.DISCOVERED,
        )
        test_session.add(design)
        await test_session.flush()

        service = AutoDownloadService(test_session)
        result = await service.check_and_queue_design(design, channel)

        assert result is False

    @pytest.mark.asyncio
    async def test_download_all_new_queues_new_design(self, test_session: AsyncSession):
        """Test that DOWNLOAD_ALL_NEW mode queues new designs."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Auto New Channel",
            download_mode=DownloadMode.DOWNLOAD_ALL_NEW,
            download_mode_enabled_at=datetime.utcnow() - timedelta(hours=1),
        )
        test_session.add(channel)
        await test_session.flush()

        design = Design(
            canonical_title="New Design",
            status=DesignStatus.DISCOVERED,
            created_at=datetime.utcnow(),  # Created after mode enabled
        )
        test_session.add(design)
        await test_session.flush()

        service = AutoDownloadService(test_session)
        result = await service.check_and_queue_design(design, channel)
        await test_session.commit()

        assert result is True

        # Verify job was created
        jobs = await test_session.execute(
            select(Job).where(Job.design_id == design.id)
        )
        job = jobs.scalar_one_or_none()
        assert job is not None
        assert job.type == JobType.DOWNLOAD_DESIGN
        assert job.status == JobStatus.QUEUED

        # Verify design status updated
        await test_session.refresh(design)
        assert design.status == DesignStatus.WANTED

    @pytest.mark.asyncio
    async def test_download_all_new_skips_old_design(self, test_session: AsyncSession):
        """Test that DOWNLOAD_ALL_NEW mode skips designs created before mode enabled."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Auto New Channel",
            download_mode=DownloadMode.DOWNLOAD_ALL_NEW,
            download_mode_enabled_at=datetime.utcnow(),  # Just now
        )
        test_session.add(channel)
        await test_session.flush()

        design = Design(
            canonical_title="Old Design",
            status=DesignStatus.DISCOVERED,
            created_at=datetime.utcnow() - timedelta(hours=1),  # Created before mode enabled
        )
        test_session.add(design)
        await test_session.flush()

        service = AutoDownloadService(test_session)
        result = await service.check_and_queue_design(design, channel)

        assert result is False

    @pytest.mark.asyncio
    async def test_download_all_queues_design(self, test_session: AsyncSession):
        """Test that DOWNLOAD_ALL mode queues designs."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Download All Channel",
            download_mode=DownloadMode.DOWNLOAD_ALL,
        )
        test_session.add(channel)
        await test_session.flush()

        design = Design(
            canonical_title="Any Design",
            status=DesignStatus.DISCOVERED,
        )
        test_session.add(design)
        await test_session.flush()

        service = AutoDownloadService(test_session)
        result = await service.check_and_queue_design(design, channel)
        await test_session.commit()

        assert result is True

    @pytest.mark.asyncio
    async def test_skips_non_discovered_status(self, test_session: AsyncSession):
        """Test that non-DISCOVERED designs are not queued."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Auto Channel",
            download_mode=DownloadMode.DOWNLOAD_ALL,
        )
        test_session.add(channel)
        await test_session.flush()

        design = Design(
            canonical_title="Already Downloaded",
            status=DesignStatus.DOWNLOADED,  # Already downloaded
        )
        test_session.add(design)
        await test_session.flush()

        service = AutoDownloadService(test_session)
        result = await service.check_and_queue_design(design, channel)

        assert result is False


class TestBulkDownload:
    """Tests for bulk download functionality."""

    @pytest.mark.asyncio
    async def test_bulk_download_dry_run(self, test_session: AsyncSession):
        """Test bulk download preview (dry run)."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Bulk Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.flush()

        # Create some designs for this channel
        for i in range(3):
            design = Design(
                canonical_title=f"Design {i}",
                status=DesignStatus.DISCOVERED,
            )
            test_session.add(design)
            await test_session.flush()

            # Create message for the design source
            message = TelegramMessage(
                channel_id=channel.id,
                telegram_message_id=1000 + i,
                date_posted=datetime.utcnow(),
            )
            test_session.add(message)
            await test_session.flush()

            source = DesignSource(
                design_id=design.id,
                channel_id=channel.id,
                message_id=message.id,
                source_rank=1,
            )
            test_session.add(source)

        await test_session.commit()

        service = AutoDownloadService(test_session)
        result = await service.trigger_bulk_download(channel, dry_run=True)

        assert result["count"] == 3
        assert result["queued"] == 0

        # Verify no jobs were created
        jobs = await test_session.execute(
            select(Job).where(Job.channel_id == channel.id)
        )
        assert jobs.scalars().first() is None

    @pytest.mark.asyncio
    async def test_bulk_download_execute(self, test_session: AsyncSession):
        """Test bulk download execution."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Bulk Channel",
            download_mode=DownloadMode.DOWNLOAD_ALL,
        )
        test_session.add(channel)
        await test_session.flush()

        # Create some designs for this channel
        designs = []
        for i in range(2):
            design = Design(
                canonical_title=f"Bulk Design {i}",
                status=DesignStatus.DISCOVERED,
            )
            test_session.add(design)
            await test_session.flush()
            designs.append(design)

            # Create message for the design source
            message = TelegramMessage(
                channel_id=channel.id,
                telegram_message_id=2000 + i,
                date_posted=datetime.utcnow(),
            )
            test_session.add(message)
            await test_session.flush()

            source = DesignSource(
                design_id=design.id,
                channel_id=channel.id,
                message_id=message.id,
                source_rank=1,
            )
            test_session.add(source)

        await test_session.commit()

        service = AutoDownloadService(test_session)
        result = await service.trigger_bulk_download(channel, dry_run=False)
        await test_session.commit()

        assert result["count"] == 2
        assert result["queued"] == 2

        # Verify jobs were created
        jobs_result = await test_session.execute(
            select(Job).where(Job.channel_id == channel.id)
        )
        jobs = jobs_result.scalars().all()
        assert len(jobs) == 2


class TestUpdateDownloadMode:
    """Tests for update_download_mode method."""

    @pytest.mark.asyncio
    async def test_update_to_download_all_new(self, test_session: AsyncSession):
        """Test changing mode to DOWNLOAD_ALL_NEW."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Mode Change Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.commit()

        service = AutoDownloadService(test_session)
        result = await service.update_download_mode(
            channel, DownloadMode.DOWNLOAD_ALL_NEW
        )
        await test_session.commit()

        assert result["changed"] is True
        assert result["old_mode"] == "MANUAL"
        assert result["new_mode"] == "DOWNLOAD_ALL_NEW"
        assert result["enabled_at"] is not None

        await test_session.refresh(channel)
        assert channel.download_mode == DownloadMode.DOWNLOAD_ALL_NEW
        assert channel.download_mode_enabled_at is not None

    @pytest.mark.asyncio
    async def test_update_back_to_manual(self, test_session: AsyncSession):
        """Test changing mode back to MANUAL clears enabled_at."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Mode Change Channel",
            download_mode=DownloadMode.DOWNLOAD_ALL_NEW,
            download_mode_enabled_at=datetime.utcnow(),
        )
        test_session.add(channel)
        await test_session.commit()

        service = AutoDownloadService(test_session)
        result = await service.update_download_mode(channel, DownloadMode.MANUAL)
        await test_session.commit()

        assert result["changed"] is True
        assert result["enabled_at"] is None

        await test_session.refresh(channel)
        assert channel.download_mode == DownloadMode.MANUAL
        assert channel.download_mode_enabled_at is None

    @pytest.mark.asyncio
    async def test_no_change_same_mode(self, test_session: AsyncSession):
        """Test that setting same mode reports no change."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="No Change Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.commit()

        service = AutoDownloadService(test_session)
        result = await service.update_download_mode(channel, DownloadMode.MANUAL)

        assert result["changed"] is False


class TestDownloadModeAPIEndpoints:
    """Tests for download mode API endpoints."""

    @pytest.mark.asyncio
    async def test_preview_endpoint(self, client, test_session: AsyncSession):
        """Test download mode preview endpoint."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="API Test Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.commit()

        response = client.get(
            f"/api/v1/channels/{channel.id}/download-mode/preview?new_mode=DOWNLOAD_ALL"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_mode"] == "MANUAL"
        assert data["new_mode"] == "DOWNLOAD_ALL"
        assert "designs_to_queue" in data

    @pytest.mark.asyncio
    async def test_update_mode_endpoint(self, client, test_session: AsyncSession):
        """Test download mode update endpoint."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="API Test Channel 2",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.commit()

        response = client.post(
            f"/api/v1/channels/{channel.id}/download-mode",
            json={"download_mode": "DOWNLOAD_ALL_NEW"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["changed"] is True
        assert data["new_mode"] == "DOWNLOAD_ALL_NEW"

    @pytest.mark.asyncio
    async def test_update_mode_requires_confirmation(
        self, client, test_session: AsyncSession
    ):
        """Test that DOWNLOAD_ALL requires confirmation when there are designs."""
        channel = Channel(
            telegram_peer_id=unique_peer_id(),
            title="Confirm Test Channel",
            download_mode=DownloadMode.MANUAL,
        )
        test_session.add(channel)
        await test_session.flush()

        # Create a design for this channel
        design = Design(
            canonical_title="Pending Design",
            status=DesignStatus.DISCOVERED,
        )
        test_session.add(design)
        await test_session.flush()

        # Create message for the design source
        message = TelegramMessage(
            channel_id=channel.id,
            telegram_message_id=3000,
            date_posted=datetime.utcnow(),
        )
        test_session.add(message)
        await test_session.flush()

        source = DesignSource(
            design_id=design.id,
            channel_id=channel.id,
            message_id=message.id,
            source_rank=1,
        )
        test_session.add(source)
        await test_session.commit()

        # Try without confirmation - should fail
        response = client.post(
            f"/api/v1/channels/{channel.id}/download-mode",
            json={"download_mode": "DOWNLOAD_ALL", "confirm_bulk_download": False},
        )
        assert response.status_code == 400
        assert "confirm_bulk_download" in response.json()["detail"]

        # Try with confirmation - should succeed
        response = client.post(
            f"/api/v1/channels/{channel.id}/download-mode",
            json={"download_mode": "DOWNLOAD_ALL", "confirm_bulk_download": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["changed"] is True
        assert data["bulk_download"] is not None
        assert data["bulk_download"]["queued"] >= 1
