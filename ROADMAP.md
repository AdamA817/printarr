# Printarr Roadmap

This document outlines the versioned development plan from initial prototype to full v1.0 release.

Each version builds incrementally on the previous, allowing for testing and feedback along the way.

---

## Version Philosophy

- **v0.x** - Development milestones, may have rough edges
- **v1.0** - Feature-complete per REQUIREMENTS.md, production-ready

Each version should be:
1. **Deployable** - Can run in Docker
2. **Testable** - Core features work end-to-end
3. **Demonstrable** - Shows clear progress

---

## v0.1 - Hello World (Deployable from Day 1)
**Goal**: Prove the stack works together, deployable on Unraid

### Scope
- [ ] FastAPI backend with health endpoint
- [ ] React frontend with basic layout (sidebar, header)
- [ ] SQLite database with one table (Channels)
- [ ] Docker container that runs both (multi-stage build)
- [ ] docker-compose.yml for local development
- [ ] Basic Unraid template for deployment
- [ ] Proper volume mounts (/config, /data, /library, etc.)
- [ ] Can add/view channels in UI (no Telegram yet)

### Success Criteria
- Deploy on Unraid via Docker template
- Access UI from browser
- Add a channel name via UI, see it in the list
- Data persists across container restarts

### Not Included
- Telegram integration
- Design catalog
- Downloads

---

## v0.2 - Telegram Connection
**Goal**: Connect to Telegram and prove we can read data

### Scope
- [ ] Telegram authentication flow (phone, code, 2FA)
- [ ] Session persistence across restarts
- [ ] Resolve channel from t.me link
- [ ] Fetch last 10 messages from a channel (display raw in UI)

### Success Criteria
- Log in with Telegram account via UI
- Add a real channel link
- See recent messages displayed (just text, no processing)

### Not Included
- Message parsing
- Design detection
- Attachments

---

## v0.3 - Message Ingestion
**Goal**: Parse messages and detect design candidates

### Scope
- [ ] Store TelegramMessage records
- [ ] Parse attachments (detect file types)
- [ ] Identify "design posts" (has STL/3MF/archive)
- [ ] Create Design records from detected posts
- [ ] Basic backfill (last N messages per channel)

### Success Criteria
- Add a channel with 3D designs
- Run backfill
- See Designs appear in database
- View design list in UI (basic table)

### Not Included
- Full catalog UI
- Downloads
- Deduplication

---

## v0.4 - Catalog UI
**Goal**: Radarr-style browsing experience

### Scope
- [ ] Design grid view with cards
- [ ] Design list view
- [ ] Filter sidebar (status, channel, file type)
- [ ] Design detail page (sources, files, metadata)
- [ ] Pagination and sorting

### Success Criteria
- Browse designs like Radarr
- Filter by channel, see results update
- Click design to see details

### Not Included
- Downloads
- Preview images
- Tagging

---

## v0.5 - Downloads & Library
**Goal**: Download files and organize into library

### Scope
- [ ] Job queue system (database-backed)
- [ ] Download worker
- [ ] "Want" / "Download" buttons
- [ ] Download to staging directory
- [ ] Archive extraction (zip, rar, 7z)
- [ ] Import to library with folder structure
- [ ] Activity page (queue, history)

### Success Criteria
- Mark design as "Wanted"
- Watch it download and extract
- Find organized files in library folder

### Not Included
- Auto-download modes
- Preview generation
- Multicolor detection

---

## v0.6 - Live Monitoring
**Goal**: Continuous ingestion of new posts

### Scope
- [ ] Live channel monitoring (polling or subscription)
- [ ] New posts ingested automatically
- [ ] Per-channel download modes (manual, auto-new, auto-all)
- [ ] Dashboard with stats

### Success Criteria
- New post appears in Telegram
- Design appears in Printarr within minutes
- Auto-download mode triggers download

### Not Included
- Suggested channels
- Full backfill options

---

## v0.7 - Previews & Metadata
**Goal**: Visual browsing and organization

### Scope
- [ ] Capture Telegram images from posts
- [ ] Display preview images on cards
- [ ] Extract 3MF embedded thumbnails
- [ ] Preview generation for downloaded models
- [ ] Image gallery in design detail
- [ ] Auto-tagging from captions and filenames
- [ ] Manual tag editing
- [ ] Designer detection/override
- [ ] Multicolor classification
- [ ] Tag filtering in UI

### Success Criteria
- Design cards show preview images
- Click to see full gallery
- Designs have auto-generated tags
- Can manually edit tags and filter by them

### Not Included
- On-demand render for undownloaded
- Deduplication

---

## v0.8 - Deduplication & Reliability
**Goal**: Handle duplicates, improve reliability

### Scope
- [ ] Hash-based deduplication (post-download)
- [ ] Filename/size heuristic matching
- [ ] Merge duplicate designs
- [ ] Multiple sources per design
- [ ] Error handling improvements
- [ ] Rate limiting / backoff for Telegram
- [ ] Job retry logic and failure recovery

### Success Criteria
- Same design from 2 channels shows as one entry
- Preferred source selection works
- System handles Telegram rate limits gracefully
- Failed jobs can be retried

### Not Included
- Suggested channels (future consideration)

---

## v1.0 - Production Ready
**Goal**: Full REQUIREMENTS.md implementation, battle-tested

### Scope
- [ ] All v0.x features polished
- [ ] Full backfill options (all history, last N days)
- [ ] Complete Settings UI
- [ ] Polished Unraid template with all options
- [ ] CI/CD pipeline (auto-build, auto-release)
- [ ] User documentation / README
- [ ] Performance optimization for scale
- [ ] Error recovery and resilience

### Success Criteria
- Monitor 100+ channels reliably
- Manage 10,000+ designs without slowdown
- All features from REQUIREMENTS.md working
- Clean upgrade path from v0.x

---

## Future Considerations (Post v1.0)
- Channel suggestion system
- Printer profile awareness
- Slicer metadata extraction
- Export to slicer-friendly libraries
- Multi-user support

---

## Current Status

**Active Version**: Not started

**Last Updated**: 2024-12-29

---

## Version History

| Version | Focus | Status | Notes |
|---------|-------|--------|-------|
| v0.1 | Hello World | Not Started | Foundation + Docker/Unraid |
| v0.2 | Telegram | - | Auth + connection |
| v0.3 | Ingestion | - | Parse + detect designs |
| v0.4 | Catalog UI | - | Radarr-style browsing |
| v0.5 | Downloads | - | Job queue + library |
| v0.6 | Live Monitoring | - | Continuous ingestion |
| v0.7 | Previews & Metadata | - | Images + tags |
| v0.8 | Deduplication | - | Handle duplicates |
| v1.0 | Production | - | Full release |
