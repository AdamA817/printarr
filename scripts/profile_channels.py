#!/usr/bin/env python3
"""
Channel Profiling Script

Analyzes Telegram channels from TEST_CHANNELS.md and generates profiles
showing what features each channel has (file types, external links,
multi-part patterns, channel references, etc.)

Usage:
    python scripts/profile_channels.py [options]

Options:
    --channels-file     Path to channels file (default: TEST_CHANNELS.md)
    --output-dir        Output directory (default: channel_profiles/)
    --messages          Number of messages to sample (default: 100)
    --channels          Specific channel(s) to profile (comma-separated usernames)
    --skip-existing     Skip channels that already have profiles

Requirements:
    - Telegram session must be authenticated (run the app first)
    - Run from project root directory
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from telethon import TelegramClient
from telethon.tl.types import (
    Channel,
    DocumentAttributeFilename,
    Message,
    MessageFwdHeader,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerChannel,
)

# File extension categories
DESIGN_EXTENSIONS = {".stl", ".3mf", ".obj", ".step", ".stp"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar.gz", ".tgz"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# URL patterns (from thangs.py)
THANGS_PATTERNS = [
    re.compile(r"thangs\.com/([^/]+)/([^/\s]+)-(\d+)", re.IGNORECASE),
    re.compile(r"thangs\.com/m/(\d+)", re.IGNORECASE),
    re.compile(r"thangs\.com/model/(\d+)", re.IGNORECASE),
]
PRINTABLES_PATTERN = re.compile(r"printables\.com/model/(\d+)", re.IGNORECASE)
THINGIVERSE_PATTERN = re.compile(r"thingiverse\.com/thing:(\d+)", re.IGNORECASE)

# Channel reference patterns
CHANNEL_MENTION_PATTERN = re.compile(r"@([a-zA-Z][a-zA-Z0-9_]{3,31})")
CHANNEL_LINK_PATTERN = re.compile(r"t\.me/([a-zA-Z][a-zA-Z0-9_]{3,31})")

# Multi-part archive patterns
MULTIPART_PATTERN = re.compile(r"(.+?)\.part(\d+)\.rar", re.IGNORECASE)
IMAGE_SUFFIX_PATTERN = re.compile(r"\(Images?\)", re.IGNORECASE)
FILES_SUFFIX_PATTERN = re.compile(r"\((?:Non[ -]?Supported|Files?|STL)\)", re.IGNORECASE)


def extract_filename(message: Message) -> str | None:
    """Extract filename from message media."""
    if not message.media:
        return None
    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if doc and doc.attributes:
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    return attr.file_name
    return None


def get_extension(filename: str | None) -> str | None:
    """Get lowercase extension from filename."""
    if not filename:
        return None
    lower = filename.lower()
    if lower.endswith(".tar.gz"):
        return ".tar.gz"
    if lower.endswith(".tgz"):
        return ".tgz"
    dot_idx = filename.rfind(".")
    if dot_idx > 0:
        return filename[dot_idx:].lower()
    return None


def detect_external_urls(text: str) -> dict[str, list[str]]:
    """Detect external platform URLs in text."""
    if not text:
        return {"thangs": [], "printables": [], "thingiverse": []}

    thangs = []
    for pattern in THANGS_PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groups()
            model_id = groups[2] if len(groups) == 3 else groups[0]
            url = f"https://thangs.com/m/{model_id}"
            if url not in thangs:
                thangs.append(url)

    printables = []
    for match in PRINTABLES_PATTERN.finditer(text):
        url = f"https://printables.com/model/{match.group(1)}"
        if url not in printables:
            printables.append(url)

    thingiverse = []
    for match in THINGIVERSE_PATTERN.finditer(text):
        url = f"https://thingiverse.com/thing:{match.group(1)}"
        if url not in thingiverse:
            thingiverse.append(url)

    return {"thangs": thangs, "printables": printables, "thingiverse": thingiverse}


def detect_channel_references(text: str) -> dict[str, list[str]]:
    """Detect channel mentions and links in text."""
    if not text:
        return {"mentions": [], "links": []}

    mentions = list(set(CHANNEL_MENTION_PATTERN.findall(text)))
    links = list(set(CHANNEL_LINK_PATTERN.findall(text)))

    return {"mentions": mentions, "links": links}


def detect_multipart(filename: str | None) -> dict | None:
    """Check if filename is part of a multi-part archive."""
    if not filename:
        return None
    match = MULTIPART_PATTERN.match(filename)
    if match:
        return {"base_name": match.group(1), "part": int(match.group(2))}
    return None


def detect_image_file_pattern(text: str | None) -> str | None:
    """Check if text matches image/files suffix pattern."""
    if not text:
        return None
    if IMAGE_SUFFIX_PATTERN.search(text):
        return "images"
    if FILES_SUFFIX_PATTERN.search(text):
        return "files"
    return None


async def profile_channel(
    client: TelegramClient,
    channel_input: str,
    message_limit: int = 100,
) -> dict[str, Any]:
    """Profile a single channel."""

    print(f"  Fetching channel info...")

    # Get channel entity
    try:
        entity = await client.get_entity(channel_input)
    except Exception as e:
        return {"error": str(e), "channel_input": channel_input}

    if not isinstance(entity, Channel):
        return {"error": "Not a channel", "channel_input": channel_input}

    # Basic channel info
    profile: dict[str, Any] = {
        "channel": {
            "title": entity.title,
            "username": entity.username,
            "peer_id": entity.id,
            "is_private": entity.username is None,
            "member_count": getattr(entity, "participants_count", None),
        },
        "activity": {
            "messages_sampled": 0,
            "date_range": {"oldest": None, "newest": None},
            "posts_per_week": 0.0,
            "last_post_date": None,
            "days_since_last_post": None,
        },
        "file_types": {
            "stl": 0, "3mf": 0, "obj": 0, "step": 0,
            "zip": 0, "rar": 0, "7z": 0, "tar_gz": 0,
            "images": 0, "other": 0,
        },
        "design_detection": {
            "messages_with_design_files": 0,
            "messages_with_archives": 0,
            "messages_with_only_images": 0,
            "messages_with_no_media": 0,
            "total_attachments": 0,
        },
        "external_links": {
            "thangs": {"count": 0, "examples": []},
            "printables": {"count": 0, "examples": []},
            "thingiverse": {"count": 0, "examples": []},
        },
        "channel_references": {
            "forwarded_from": {"count": 0, "channels": {}},
            "mentioned_channels": {"count": 0, "channels": {}},
            "linked_channels": {"count": 0, "channels": {}},
        },
        "multipart_detection": {
            "split_archives": {"count": 0, "patterns": {}},
            "image_file_pairs": {"count": 0, "image_posts": 0, "file_posts": 0},
        },
        "caption_analysis": {
            "messages_with_captions": 0,
            "total_caption_length": 0,
            "messages_with_hashtags": 0,
            "hashtags": Counter(),
        },
        "samples": {
            "thangs_link_example": None,
            "split_archive_example": None,
            "forwarded_example": None,
        },
    }

    print(f"  Fetching {message_limit} messages...")

    # Fetch messages
    messages: list[Message] = []
    async for msg in client.iter_messages(entity, limit=message_limit):
        if isinstance(msg, Message):
            messages.append(msg)

    profile["activity"]["messages_sampled"] = len(messages)

    if not messages:
        return profile

    # Analyze date range
    dates = [m.date for m in messages if m.date]
    if dates:
        newest = max(dates)
        oldest = min(dates)
        profile["activity"]["date_range"]["newest"] = newest.isoformat()
        profile["activity"]["date_range"]["oldest"] = oldest.isoformat()
        profile["activity"]["last_post_date"] = newest.isoformat()

        days_range = (newest - oldest).days or 1
        profile["activity"]["posts_per_week"] = round(len(messages) / days_range * 7, 1)

        days_since = (datetime.now(newest.tzinfo) - newest).days
        profile["activity"]["days_since_last_post"] = days_since

    print(f"  Analyzing {len(messages)} messages...")

    # Analyze each message
    for msg in messages:
        # Caption analysis
        caption = msg.message or ""
        if caption:
            profile["caption_analysis"]["messages_with_captions"] += 1
            profile["caption_analysis"]["total_caption_length"] += len(caption)

            # Hashtags
            hashtags = re.findall(r"#(\w+)", caption)
            if hashtags:
                profile["caption_analysis"]["messages_with_hashtags"] += 1
                profile["caption_analysis"]["hashtags"].update(hashtags)

            # External URLs
            urls = detect_external_urls(caption)
            for platform in ["thangs", "printables", "thingiverse"]:
                if urls[platform]:
                    profile["external_links"][platform]["count"] += len(urls[platform])
                    # Store first 3 examples
                    if len(profile["external_links"][platform]["examples"]) < 3:
                        profile["external_links"][platform]["examples"].extend(urls[platform][:3])
                    # Sample message
                    if platform == "thangs" and not profile["samples"]["thangs_link_example"]:
                        profile["samples"]["thangs_link_example"] = {
                            "message_id": msg.id,
                            "caption": caption[:500],
                            "urls": urls["thangs"],
                        }

            # Channel references in caption
            refs = detect_channel_references(caption)
            for username in refs["mentions"]:
                profile["channel_references"]["mentioned_channels"]["channels"][username] = \
                    profile["channel_references"]["mentioned_channels"]["channels"].get(username, 0) + 1
                profile["channel_references"]["mentioned_channels"]["count"] += 1
            for username in refs["links"]:
                profile["channel_references"]["linked_channels"]["channels"][username] = \
                    profile["channel_references"]["linked_channels"]["channels"].get(username, 0) + 1
                profile["channel_references"]["linked_channels"]["count"] += 1

            # Image/file suffix pattern
            pattern_type = detect_image_file_pattern(caption)
            if pattern_type == "images":
                profile["multipart_detection"]["image_file_pairs"]["image_posts"] += 1
            elif pattern_type == "files":
                profile["multipart_detection"]["image_file_pairs"]["file_posts"] += 1

        # Forwarded messages
        if msg.fwd_from and isinstance(msg.fwd_from, MessageFwdHeader):
            fwd = msg.fwd_from
            if fwd.from_id and isinstance(fwd.from_id, PeerChannel):
                fwd_channel_id = fwd.from_id.channel_id
                fwd_name = fwd.from_name or str(fwd_channel_id)
                profile["channel_references"]["forwarded_from"]["channels"][fwd_name] = \
                    profile["channel_references"]["forwarded_from"]["channels"].get(fwd_name, 0) + 1
                profile["channel_references"]["forwarded_from"]["count"] += 1

                if not profile["samples"]["forwarded_example"]:
                    profile["samples"]["forwarded_example"] = {
                        "message_id": msg.id,
                        "from_channel": fwd_name,
                        "from_id": fwd_channel_id,
                    }

        # Media analysis
        if not msg.media:
            profile["design_detection"]["messages_with_no_media"] += 1
            continue

        filename = extract_filename(msg)
        ext = get_extension(filename)

        if isinstance(msg.media, MessageMediaPhoto):
            profile["file_types"]["images"] += 1
            profile["design_detection"]["total_attachments"] += 1
        elif isinstance(msg.media, MessageMediaDocument):
            profile["design_detection"]["total_attachments"] += 1

            if ext:
                # Categorize by extension
                if ext in DESIGN_EXTENSIONS:
                    if ext == ".stl":
                        profile["file_types"]["stl"] += 1
                    elif ext == ".3mf":
                        profile["file_types"]["3mf"] += 1
                    elif ext == ".obj":
                        profile["file_types"]["obj"] += 1
                    elif ext in {".step", ".stp"}:
                        profile["file_types"]["step"] += 1
                    profile["design_detection"]["messages_with_design_files"] += 1

                elif ext in ARCHIVE_EXTENSIONS:
                    if ext == ".zip":
                        profile["file_types"]["zip"] += 1
                    elif ext == ".rar":
                        profile["file_types"]["rar"] += 1
                    elif ext == ".7z":
                        profile["file_types"]["7z"] += 1
                    elif ext in {".tar.gz", ".tgz"}:
                        profile["file_types"]["tar_gz"] += 1
                    profile["design_detection"]["messages_with_archives"] += 1

                    # Check for multi-part
                    multipart = detect_multipart(filename)
                    if multipart:
                        base = multipart["base_name"]
                        profile["multipart_detection"]["split_archives"]["patterns"][base] = \
                            profile["multipart_detection"]["split_archives"]["patterns"].get(base, [])
                        profile["multipart_detection"]["split_archives"]["patterns"][base].append(multipart["part"])
                        profile["multipart_detection"]["split_archives"]["count"] += 1

                        if not profile["samples"]["split_archive_example"]:
                            profile["samples"]["split_archive_example"] = {
                                "message_id": msg.id,
                                "filename": filename,
                                "base_name": base,
                                "part": multipart["part"],
                            }

                elif ext in IMAGE_EXTENSIONS:
                    profile["file_types"]["images"] += 1
                else:
                    profile["file_types"]["other"] += 1

    # Post-process
    # Convert Counter to list of tuples for JSON serialization
    profile["caption_analysis"]["hashtags"] = [
        {"tag": tag, "count": count}
        for tag, count in profile["caption_analysis"]["hashtags"].most_common(20)
    ]

    # Calculate average caption length
    if profile["caption_analysis"]["messages_with_captions"] > 0:
        profile["caption_analysis"]["avg_caption_length"] = round(
            profile["caption_analysis"]["total_caption_length"] /
            profile["caption_analysis"]["messages_with_captions"]
        )
    else:
        profile["caption_analysis"]["avg_caption_length"] = 0
    del profile["caption_analysis"]["total_caption_length"]

    # Count image/file pairs
    profile["multipart_detection"]["image_file_pairs"]["count"] = min(
        profile["multipart_detection"]["image_file_pairs"]["image_posts"],
        profile["multipart_detection"]["image_file_pairs"]["file_posts"],
    )

    # Sort channel references by count
    for ref_type in ["forwarded_from", "mentioned_channels", "linked_channels"]:
        channels = profile["channel_references"][ref_type]["channels"]
        profile["channel_references"][ref_type]["channels"] = [
            {"name": name, "count": count}
            for name, count in sorted(channels.items(), key=lambda x: -x[1])[:20]
        ]

    # Sort split archive patterns
    patterns = profile["multipart_detection"]["split_archives"]["patterns"]
    profile["multipart_detection"]["split_archives"]["patterns"] = [
        {"base_name": name, "parts": sorted(parts)}
        for name, parts in sorted(patterns.items(), key=lambda x: -len(x[1]))[:10]
    ]

    # Compute suitability flags
    profile["suitability"] = {
        "v0.3_ingestion": (
            profile["file_types"]["stl"] > 0 or
            profile["file_types"]["3mf"] > 0 or
            profile["design_detection"]["messages_with_archives"] > 0
        ),
        "v0.3_thangs": profile["external_links"]["thangs"]["count"] > 0,
        "v0.4_multipart": (
            profile["multipart_detection"]["split_archives"]["count"] > 0 or
            profile["multipart_detection"]["image_file_pairs"]["count"] > 0
        ),
        "v0.6_active": (
            profile["activity"]["days_since_last_post"] is not None and
            profile["activity"]["days_since_last_post"] <= 30
        ),
        "v0.6_discovery": (
            profile["channel_references"]["forwarded_from"]["count"] > 0 or
            profile["channel_references"]["mentioned_channels"]["count"] > 0 or
            profile["channel_references"]["linked_channels"]["count"] > 0
        ),
        "v0.7_previews": profile["file_types"]["images"] > 0,
        "v0.7_3mf": profile["file_types"]["3mf"] > 0,
    }

    return profile


def generate_markdown_summary(profiles: list[dict]) -> str:
    """Generate a markdown summary of all profiles."""
    lines = [
        "# Channel Profiles Summary",
        "",
        f"Generated: {datetime.now().isoformat()}",
        f"Channels analyzed: {len(profiles)}",
        "",
        "## Suitability Matrix",
        "",
        "| Channel | v0.3 Ingest | v0.3 Thangs | v0.4 Multi | v0.6 Active | v0.6 Disc | v0.7 Prev |",
        "|---------|-------------|-------------|------------|-------------|-----------|-----------|",
    ]

    for p in profiles:
        if "error" in p:
            continue
        s = p.get("suitability", {})
        title = p["channel"]["title"][:20]
        lines.append(
            f"| {title} | "
            f"{'✅' if s.get('v0.3_ingestion') else '❌'} | "
            f"{'✅' if s.get('v0.3_thangs') else '❌'} | "
            f"{'✅' if s.get('v0.4_multipart') else '❌'} | "
            f"{'✅' if s.get('v0.6_active') else '❌'} | "
            f"{'✅' if s.get('v0.6_discovery') else '❌'} | "
            f"{'✅' if s.get('v0.7_previews') else '❌'} |"
        )

    lines.extend([
        "",
        "## Discovered Channels (via references)",
        "",
        "Channels referenced by monitored channels that could be added:",
        "",
    ])

    # Aggregate all discovered channels
    discovered: Counter = Counter()
    for p in profiles:
        if "error" in p:
            continue
        refs = p.get("channel_references", {})
        for ref_type in ["forwarded_from", "mentioned_channels", "linked_channels"]:
            for ch in refs.get(ref_type, {}).get("channels", []):
                discovered[ch["name"]] += ch["count"]

    if discovered:
        lines.append("| Channel | Reference Count |")
        lines.append("|---------|-----------------|")
        for name, count in discovered.most_common(30):
            lines.append(f"| @{name} | {count} |")
    else:
        lines.append("No channel references found.")

    lines.extend([
        "",
        "## File Type Distribution",
        "",
        "| Channel | STL | 3MF | ZIP | RAR | Images |",
        "|---------|-----|-----|-----|-----|--------|",
    ])

    for p in profiles:
        if "error" in p:
            continue
        ft = p.get("file_types", {})
        title = p["channel"]["title"][:20]
        lines.append(
            f"| {title} | "
            f"{ft.get('stl', 0)} | "
            f"{ft.get('3mf', 0)} | "
            f"{ft.get('zip', 0)} | "
            f"{ft.get('rar', 0)} | "
            f"{ft.get('images', 0)} |"
        )

    lines.extend([
        "",
        "## External Links",
        "",
        "| Channel | Thangs | Printables | Thingiverse |",
        "|---------|--------|------------|-------------|",
    ])

    for p in profiles:
        if "error" in p:
            continue
        el = p.get("external_links", {})
        title = p["channel"]["title"][:20]
        lines.append(
            f"| {title} | "
            f"{el.get('thangs', {}).get('count', 0)} | "
            f"{el.get('printables', {}).get('count', 0)} | "
            f"{el.get('thingiverse', {}).get('count', 0)} |"
        )

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Profile Telegram channels for Printarr testing")
    parser.add_argument(
        "--channels-file",
        default="TEST_CHANNELS.md",
        help="Path to file with channel URLs (one per line)",
    )
    parser.add_argument(
        "--output-dir",
        default="channel_profiles",
        help="Output directory for profiles",
    )
    parser.add_argument(
        "--messages",
        type=int,
        default=100,
        help="Number of messages to sample per channel",
    )
    parser.add_argument(
        "--channels",
        help="Specific channel(s) to profile (comma-separated usernames)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip channels that already have profiles",
    )
    args = parser.parse_args()

    # Setup output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Read channels from file
    channels_file = Path(args.channels_file)
    if not channels_file.exists():
        print(f"Error: Channels file not found: {channels_file}")
        sys.exit(1)

    channel_inputs: list[str] = []
    with open(channels_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract username or full URL
                channel_inputs.append(line)

    # Filter to specific channels if requested
    if args.channels:
        specific = set(args.channels.lower().split(","))
        channel_inputs = [
            c for c in channel_inputs
            if any(s in c.lower() for s in specific)
        ]

    print(f"Found {len(channel_inputs)} channels to profile")

    # Initialize Telegram client
    # Use session from config directory
    config_dir = Path(__file__).parent.parent / "config"
    session_path = config_dir / "telegram_session"

    if not session_path.with_suffix(".session").exists():
        print("Error: No Telegram session found. Run the app first to authenticate.")
        print(f"Expected session at: {session_path}.session")
        sys.exit(1)

    # Read API credentials from environment or config
    import os
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        # Try to read from .env file
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("TELEGRAM_API_ID="):
                        api_id = line.split("=", 1)[1].strip()
                    elif line.startswith("TELEGRAM_API_HASH="):
                        api_hash = line.split("=", 1)[1].strip()

    if not api_id or not api_hash:
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH required")
        print("Set them in environment or .env file")
        sys.exit(1)

    client = TelegramClient(str(session_path), int(api_id), api_hash)

    print("Connecting to Telegram...")
    await client.connect()

    if not await client.is_user_authorized():
        print("Error: Telegram session not authorized. Run the app first.")
        await client.disconnect()
        sys.exit(1)

    print("Connected!")
    print()

    # Profile each channel
    profiles: list[dict] = []

    for i, channel_input in enumerate(channel_inputs):
        # Extract display name
        display_name = channel_input.split("/")[-1] if "/" in channel_input else channel_input

        # Check if profile exists
        profile_path = output_dir / f"{display_name}.json"
        if args.skip_existing and profile_path.exists():
            print(f"[{i+1}/{len(channel_inputs)}] Skipping {display_name} (profile exists)")
            with open(profile_path) as f:
                profiles.append(json.load(f))
            continue

        print(f"[{i+1}/{len(channel_inputs)}] Profiling: {display_name}")

        try:
            profile = await profile_channel(client, channel_input, args.messages)
            profiles.append(profile)

            # Save individual profile
            with open(profile_path, "w") as f:
                json.dump(profile, f, indent=2, default=str)
            print(f"  Saved to {profile_path}")

        except Exception as e:
            print(f"  Error: {e}")
            profiles.append({"error": str(e), "channel_input": channel_input})

        # Small delay between channels
        await asyncio.sleep(1)

    # Generate summary
    summary_path = output_dir / "SUMMARY.md"
    summary = generate_markdown_summary(profiles)
    with open(summary_path, "w") as f:
        f.write(summary)
    print(f"\nSummary saved to {summary_path}")

    # Save all profiles
    all_profiles_path = output_dir / "all_profiles.json"
    with open(all_profiles_path, "w") as f:
        json.dump(profiles, f, indent=2, default=str)
    print(f"All profiles saved to {all_profiles_path}")

    await client.disconnect()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
