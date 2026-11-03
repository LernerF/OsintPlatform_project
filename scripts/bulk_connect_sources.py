#!/usr/bin/env python3
"""Bulk connect Telegram channels to the running backend.

This script reads a list of Telegram channel usernames from a text file
and connects them as monitoring sources via the API.

Usage:
    python scripts/bulk_connect_sources.py --file channels.txt --city "Moscow" --region "Moscow"
    python scripts/bulk_connect_sources.py --dry-run  # Preview without connecting
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def load_channels(path: Path) -> list[str]:
    """Load and validate channel usernames from a text file.
    
    Each line should contain a channel username (with or without @)
    or a t.me URL.
    """
    channels = []
    seen = set()
    
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = line.strip()
        
        # Skip empty lines and comments
        if not value or value.startswith("#"):
            continue
        
        # Normalize the value to just the username
        value = value.removeprefix("https://").removeprefix("http://")
        value = value.removeprefix("www.").removeprefix("t.me/").lstrip("@")
        
        if not USERNAME_PATTERN.fullmatch(value):
            print(f"Warning: {path}:{line_number}: invalid channel format: {line!r}", file=sys.stderr)
            continue
        
        key = value.casefold()
        if key in seen:
            continue
        
        seen.add(key)
        channels.append(f"@{value}")
    
    if not channels:
        raise ValueError(f"No valid channels found in {path}")
    
    return channels


def connect(api_base: str, channels: list[str], city: str, region: str) -> dict:
    """Connect channels via the bulk-connect API endpoint."""
    body = json.dumps(
        {"channels": channels, "city": city, "region": region},
        ensure_ascii=False,
    ).encode("utf-8")
    
    request = Request(
        f"{api_base.rstrip('/')}/telegram/bulk-connect",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    with urlopen(request, timeout=300) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bulk connect Telegram channels as monitoring sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s --file channels.txt --city "Moscow" --region "Moscow"
    %(prog)s --file channels.txt --city "Moscow" --region "Moscow" --dry-run
    %(prog)s --api http://localhost:8000/api --file channels.txt --city "Moscow" --region "Moscow"

The channels file should contain one channel per line:
    @channel_name
    @another_channel
    https://t.me/yet_another
        """
    )
    parser.add_argument(
        "--file", 
        type=Path, 
        default=PROJECT_ROOT / "channels.txt",
        help="Path to file with channel list (default: channels.txt in project root)"
    )
    parser.add_argument(
        "--api", 
        default="http://127.0.0.1:8000/api",
        help="Backend API URL (default: http://127.0.0.1:8000/api)"
    )
    parser.add_argument(
        "--city", 
        required=True,
        help="Default city for all channels"
    )
    parser.add_argument(
        "--region", 
        required=True,
        help="Region/oblast for all channels"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Preview channels without connecting"
    )
    
    args = parser.parse_args()
    
    try:
        channels = load_channels(args.file)
        print(f"Found {len(channels)} channels in {args.file}")
        
        if args.dry_run:
            print("\nChannels to connect:")
            for channel in channels:
                print(f"  {channel}")
            print(f"\nCity: {args.city}")
            print(f"Region: {args.region}")
            return 0
        
        print(f"Connecting to {args.api}...")
        result = connect(args.api, channels, args.city, args.region)
        
        print(f"\nResults:")
        print(f"  Connected: {result['connected']}")
        print(f"  Updated: {result['updated']}")
        print(f"  Failed: {result['failed']}")
        
        for item in result["items"]:
            if item["status"] == "failed":
                print(f"  FAILED {item['channel']}: {item.get('detail') or 'unknown error'}")
        
        return 1 if result["failed"] else 0
        
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, HTTPError, URLError) as exc:
        if isinstance(exc, HTTPError):
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"API error {exc.code}: {detail}", file=sys.stderr)
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
