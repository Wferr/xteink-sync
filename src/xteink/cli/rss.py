"""RSS command handler."""

import json
import sys
from typing import Any

from xteink.client import XteinkClient


def rss(args: Any, client: XteinkClient) -> None:
    """Handle RSS commands."""

    # We are calling the conversion endpoint
    # Note: Currently client doesn't have a specific RSS method, so we use _request directly
    # or we can assume we should add one. For now I'll implement it here using client internals
    # or assume we add it to client.

    # Actually, let's just use requests for now if client doesn't have it,
    # but clean way is to add it to client.

    # If no device_id, we just parse and list (Standard API flow)
    if not args.device_id:
        if not args.json:
            print(f"Fetching RSS feed info: {args.feed_url}")

        url = f"{client.BASE_URL}/api/v1/rss/parse"
        payload = {"rss_url": args.feed_url}

        headers = {}
        if client.access_token:
            headers["Authorization"] = f"Bearer {client.access_token}"

        try:
            response = client._request("POST", url, json_data=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if args.json:
                    print(json.dumps(data, indent=2))
                    return

                feed_info = data.get("feed_info", {})
                articles = data.get("articles", [])

                print(f"\nFeed: {feed_info.get('title', 'Unknown')}")
                print(f"Description: {feed_info.get('description', '')}")
                print(f"Found {len(articles)} articles:\n")

                for i, art in enumerate(articles[: args.limit]):
                    print(f"{i + 1}. {art.get('title')}")
                    print(f"   Date: {art.get('published')}")
                    print(f"   Link: {art.get('link')}")
                    print("")
            else:
                print(f"Error ({response.status_code}): {response.text}")
                sys.exit(1)
        except Exception as e:
            print(f"Error fetching feed: {e}")
            sys.exit(1)

        return

    # If device_id provided, use the Custom Convert Endpoint (Legacy/Custom Server Feature)
    print(f"Fetching and converting RSS feed: {args.feed_url}")
    print(f"Target Device: {args.device_id}")
    print(f"Format: {args.format}, Max Articles: {args.limit}")

    try:
        # Construct the payload
        payload = {
            "feed_url": args.feed_url,
            "device_id": args.device_id,
            "format": args.format,
            "max_articles": args.limit,
        }

        # dither isn't supported by the server endpoint yet, but user asked for it.
        # I should probably update server first?
        # The user's request "where/how can I use the rss stuff?" was about CLI.
        # But they also asked about dithering.
        # Sending dither param even if server ignores it for now won't hurt,
        # but to make it work I need to update server too.
        # I'll update server in next step.

        if args.dithering:
            payload["dither"] = args.dithering.lower() != "none"

        # Make request
        # We need to manually construct the request URL since it's a custom endpoint
        # mapped in server.py: @app.post("/api/v1/rss/convert")

        url = f"{client.BASE_URL}/api/v1/rss/convert"

        headers = {}
        if client.access_token:
            headers["Authorization"] = f"Bearer {client.access_token}"

        # Use client's internal request helper to avoid extra dependencies
        response = client._request("POST", url, json_data=payload, headers=headers, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                print("\nSuccess!")
                print(f"Title: {payload['feed_url']}")  # RSS title not returned in simple response?
                # Actually response has filename
                print(f"File: {data.get('filename')}")
                print(f"Size: {data.get('file_size')} bytes")
                print(f"Articles: {data.get('article_count')}")
                print(f"Pages: {data.get('page_count')}")
                print(f"Download URL: {data.get('download_url')}")
                print("\nTask created? No, this endpoint just converts.")
                print("To send to device, run:")
                print(f"  xteink send {data.get('filename')} {args.device_id}")
                # Wait, does the server create a task?
                # The implementation of rss_convert_route returns download_url
                # but DOES NOT create a task.
                # It just saves the file.
                # So we might want to auto-create a task if requested?

        else:
            print(f"Error ({response.status_code}): {response.text}")
            sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
