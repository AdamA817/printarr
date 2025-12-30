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

## v0.1 - Hello World (Deployable from Day 1) ✅
**Goal**: Prove the stack works together, deployable on Unraid

### Scope
- [x] FastAPI backend with health endpoint
- [x] React frontend with basic layout (sidebar, header)
- [x] SQLite database with one table (Channels)
- [x] Docker container that runs both (multi-stage build)
- [x] docker-compose.yml for local development
- [x] Basic Unraid template for deployment
- [x] Proper volume mounts (/config, /data, /library, etc.)
- [x] Can add/view channels in UI (no Telegram yet)

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
- [x] Telegram authentication flow (phone, code, 2FA)
- [x] Session persistence across restarts
- [x] Resolve channel from t.me link
- [x] Fetch last 10 messages from a channel (display raw in UI)

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
**Goal**: Parse messages, detect design candidates, and enrich with Thangs metadata

### Scope
- [ ] Store TelegramMessage records
- [ ] Parse attachments (detect file types)
- [ ] Identify "design posts" (has STL/3MF/archive)
- [ ] Create Design records from detected posts
- [ ] Basic backfill (last N messages per channel)
- [ ] **Thangs URL detection** in captions (auto-link with confidence=1.0)
- [ ] **Thangs metadata fetch** (designer, title) for auto-linked designs
- [ ] ExternalMetadataSource table for storing Thangs links

### Success Criteria
- Add a channel with 3D designs
- Run backfill
- See Designs appear in database
- View design list in UI (basic table)
- Designs with thangs.com URLs show enriched metadata

### Not Included
- Full catalog UI
- Downloads
- Deduplication
- Manual Thangs search (v0.4)

---

## v0.4 - Catalog UI
**Goal**: Radarr-style browsing experience with Thangs integration

### Scope
- [ ] Design grid view with cards
- [ ] Design list view
- [ ] Filter sidebar (status, channel, file type)
- [ ] Design detail page (sources, files, metadata)
- [ ] Pagination and sorting
- [ ] **Thangs status badge** on design detail (Linked / Not Linked)
- [ ] **Thangs search modal** for manual linking
- [ ] **Link by URL** action (paste thangs.com URL)
- [ ] **Unlink Thangs** action
- [ ] Metadata provenance display (Telegram / Thangs / User)

### Success Criteria
- Browse designs like Radarr
- Filter by channel, see results update
- Click design to see details
- Can manually search and link designs to Thangs
- Thangs metadata visible with clear provenance

### Not Included
- Downloads
- Preview images
- Tagging
- Thangs image caching (v0.7)

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
**Goal**: Visual browsing, organization, and full Thangs enrichment

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
- [ ] **Thangs image caching** (download and cache preview images locally)
- [ ] **Thangs tag import** (import tags from Thangs to local design)
- [ ] **Metadata refresh** for linked designs (re-fetch from Thangs)
- [ ] ExternalImage table for cached Thangs images

### Success Criteria
- Design cards show preview images (Telegram + Thangs)
- Click to see full gallery
- Designs have auto-generated tags (from captions + Thangs)
- Can manually edit tags and filter by them
- Thangs-linked designs show cached preview images

### Not Included
- On-demand render for undownloaded
- Deduplication
- Geometry-based Thangs matching (future)

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
- **Thangs geometry search** (upload model to find matches)
- **Printables/Thingiverse adapters** (additional metadata sources)

---

## Current Status

**Active Version**: v0.3 (next)

**Last Updated**: 2025-12-30

---

## Version History

| Version | Focus | Status | Notes |
|---------|-------|--------|-------|
| v0.1 | Hello World | ✅ Complete | Foundation + Docker/Unraid |
| v0.2 | Telegram | ✅ Complete | Auth + connection |
| v0.3 | Ingestion | 🔜 Next | Parse + detect designs + Thangs auto-link |
| v0.4 | Catalog UI | - | Radarr-style browsing + Thangs search UI |
| v0.5 | Downloads | - | Job queue + library |
| v0.6 | Live Monitoring | - | Continuous ingestion |
| v0.7 | Previews & Metadata | - | Images + tags + Thangs enrichment |
| v0.8 | Deduplication | - | Handle duplicates |
| v1.0 | Production | - | Full release |
