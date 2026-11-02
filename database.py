"""
Persistent JSON Database for Telegram Bot & Backend API.
Manages Channels, Categories, Channel APIs (PHP JSON & M3U), App Updates, Maintenance Mode, and Admins.
"""

import json
import os
import re
import time
import threading
from datetime import datetime
from urllib.request import Request, urlopen
from config import DB_FILE, ADMIN_ID

_lock = threading.Lock()

# Initial defaults are empty as channels and categories are loaded exclusively from the Bot
DEFAULT_CATEGORIES = []
DEFAULT_CHANNELS = []

class Database:
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with _lock:
            if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
                data = {
                    "categories": [],
                    "channels": [],
                    "channel_apis": [],
                    "maintenance": {
                        "enabled": False,
                        "message": "التطبيق يخضع لصيانة دورية لتحسين الأداء وتحديث السيرفرات، سنعود قريباً!",
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    },
                    "app_update": {
                        "enabled": False,
                        "version_code": 2,
                        "version_name": "1.1",
                        "download_url": "",
                        "release_notes": "إصلاحات عامة وإضافة قنوات جديدة وسرعة أعلى في البث",
                        "is_force": False,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    },
                    "admins": {}
                }
                if ADMIN_ID and ADMIN_ID != 0:
                    data["admins"][str(ADMIN_ID)] = {
                        "id": ADMIN_ID,
                        "name": "المدير العام (Super Admin)",
                        "role": "super_admin",
                        "permissions": ["all"],
                        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                self._save_raw(data)

    def _load_raw(self):
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "categories": [],
                "channels": [],
                "channel_apis": [],
                "maintenance": {"enabled": False, "message": "صيانة دورية", "updated_at": ""},
                "app_update": {"enabled": False, "version_code": 2, "version_name": "1.1", "download_url": "", "release_notes": "", "is_force": False},
                "admins": {}
            }

    def _save_raw(self, data):
        temp_file = f"{self.db_path}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, self.db_path)

    # ------------------ Categories ------------------
    def get_categories(self):
        with _lock:
            data = self._load_raw()
            return data.get("categories", [])

    def add_category(self, cat_id, name, icon="📺"):
        with _lock:
            data = self._load_raw()
            cats = data.setdefault("categories", [])
            for c in cats:
                if c["id"] == cat_id:
                    c["name"] = name
                    c["icon"] = icon
                    self._save_raw(data)
                    return c
            new_cat = {"id": cat_id, "name": name, "icon": icon}
            cats.append(new_cat)
            self._save_raw(data)
            return new_cat

    def delete_category(self, cat_id):
        with _lock:
            data = self._load_raw()
            cats = data.get("categories", [])
            data["categories"] = [c for c in cats if c["id"] != cat_id]
            self._save_raw(data)
            return True

    def clear_categories(self):
        with _lock:
            data = self._load_raw()
            data["categories"] = []
            self._save_raw(data)
            return True

    # ------------------ Channels ------------------
    def get_channels(self, category=None):
        with _lock:
            data = self._load_raw()
            channels = data.get("channels", [])
            if category and category != "all":
                return [c for c in channels if c.get("category") == category]
            return channels

    def get_channel(self, channel_id):
        with _lock:
            data = self._load_raw()
            for ch in data.get("channels", []):
                if ch.get("id") == channel_id:
                    return ch
            return None

    def add_channel(self, ch_dict):
        with _lock:
            data = self._load_raw()
            channels = data.setdefault("channels", [])
            if not ch_dict.get("id"):
                ch_dict["id"] = f"ch-{int(time.time())}-{len(channels)}"
            for i, c in enumerate(channels):
                if c["id"] == ch_dict["id"]:
                    channels[i] = ch_dict
                    self._save_raw(data)
                    return ch_dict
            channels.insert(0, ch_dict)
            self._save_raw(data)
            return ch_dict

    def add_single_channel(self, name, url, category_id="general", category_name=None, logo="📺", quality="FHD", referer="", useragent="", origin="", cookie="", key="", scheme=""):
        with _lock:
            data = self._load_raw()
            categories = data.setdefault("categories", [])
            channels = data.setdefault("channels", [])

            cat_id_clean = str(category_id or "general").strip()
            cat_match = next((c for c in categories if c["id"] == cat_id_clean or c["name"] == cat_id_clean), None)
            if not cat_match:
                if not category_name:
                    category_name = "قنوات رياضية" if "sport" in cat_id_clean.lower() or "رياض" in cat_id_clean else (cat_id_clean if cat_id_clean != "general" else "منوعات عامة")
                icon = "⚽" if "رياض" in str(category_name) or "sport" in str(category_name).lower() else "📺"
                cat_match = {"id": cat_id_clean.lower().replace(" ", "_"), "name": str(category_name), "icon": icon}
                categories.append(cat_match)
            cat_id = cat_match["id"]
            cat_name = cat_match["name"]

            clean_url = str(url).strip()
            lower_url = clean_url.lower()

            # Auto-detect Ostora / Uruk / Maziika headers
            if any(k in lower_url for k in ["maziika", "sa037", "sa047", "ostora", "uruk", "optikl"]):
                if not referer:
                    referer = "https://www.w2.maziikaaaaa.shop/"
                if not useragent:
                    useragent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"

            stream_type = "hls"
            if ".mpd" in lower_url:
                stream_type = "dash"
            elif ".mp4" in lower_url:
                stream_type = "mp4"
            elif ".ts" in lower_url:
                stream_type = "ts"
            elif ".m3u8" in lower_url or ".php" in lower_url or ".js" in lower_url:
                stream_type = "hls"

            ch_id = f"ch-{int(time.time())}-{len(channels)}"
            new_ch = {
                "id": ch_id,
                "name": str(name).strip(),
                "category": cat_id,
                "categoryName": cat_name,
                "currentShow": "بث مباشر حصري عبر الإنترنت",
                "logo": str(logo).strip() if logo else "📺",
                "quality": str(quality).strip() if quality else "FHD",
                "url": clean_url,
                "streamUrl": clean_url,
                "referer": str(referer).strip() if referer else "",
                "useragent": str(useragent).strip() if useragent else "",
                "origin": str(origin).strip() if origin else "",
                "cookie": str(cookie).strip() if cookie else "",
                "key": str(key).strip() if key else "",
                "scheme": str(scheme).strip() if scheme else "",
                "badge": "مباشر",
                "servers": [
                    {"name": f"سيرفر البث ({quality or 'FHD'})", "url": clean_url, "type": stream_type}
                ]
            }

            for idx, c in enumerate(channels):
                if c.get("url") == clean_url or (c.get("name") == new_ch["name"] and c.get("category") == cat_id):
                    new_ch["id"] = c.get("id", ch_id)
                    channels[idx] = new_ch
                    self._save_raw(data)
                    return new_ch

            channels.insert(0, new_ch)
            self._save_raw(data)
            return new_ch

    def update_channel(self, channel_id, ch_dict):
        with _lock:
            data = self._load_raw()
            channels = data.get("channels", [])
            for i, c in enumerate(channels):
                if c["id"] == channel_id:
                    ch_dict["id"] = channel_id
                    channels[i] = ch_dict
                    self._save_raw(data)
                    return ch_dict
            return None

    def delete_channel(self, channel_id):
        with _lock:
            data = self._load_raw()
            channels = data.get("channels", [])
            initial_len = len(channels)
            data["channels"] = [c for c in channels if c["id"] != channel_id]
            self._save_raw(data)
            return len(data["channels"]) < initial_len

    def delete_all_channels(self):
        with _lock:
            data = self._load_raw()
            count = len(data.get("channels", []))
            data["channels"] = []
            data["categories"] = []
            self._save_raw(data)
            return count

    # ------------------ Channel APIs (PHP JSON & M3U) ------------------
    def get_channel_apis(self):
        with _lock:
            data = self._load_raw()
            return data.get("channel_apis", [])

    def add_channel_api(self, name, url, api_type="php_json"):
        with _lock:
            data = self._load_raw()
            apis = data.setdefault("channel_apis", [])
            api_id = f"api-{int(time.time())}"
            new_api = {
                "id": api_id,
                "name": name,
                "url": url,
                "type": api_type,
                "status": "نشط",
                "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            apis.append(new_api)
            self._save_raw(data)
            return new_api

    def delete_channel_api(self, api_id):
        with _lock:
            data = self._load_raw()
            apis = data.get("channel_apis", [])
            data["channel_apis"] = [a for a in apis if a["id"] != api_id]
            self._save_raw(data)
            return True

    # ------------------ PHP API JSON Universal Importer ------------------
    def sync_php_json(self, url_or_raw):
        """
        Universal importer for PHP API JSON endpoints and raw JSON data.
        Supports all common PHP IPTV structures:
        1. Dict with 'categories' and 'channels'
        2. Array of category objects containing channels
        3. Flat array of channels with category fields
        4. Xtream codes / custom PHP output formats
        """
        try:
            raw_str = url_or_raw.strip()
            # If it's a URL, fetch it via HTTP
            if raw_str.startswith("http://") or raw_str.startswith("https://"):
                req = Request(
                    raw_str,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                        "Accept": "application/json, text/plain, */*"
                    }
                )
                with urlopen(req, timeout=14) as response:
                    raw_str = response.read().decode("utf-8", errors="ignore")

            parsed = json.loads(raw_str)
            return self._process_parsed_json(parsed)
        except Exception as e:
            return {"success": False, "error": str(e), "channels_count": 0, "categories_count": 0}

    def _process_parsed_json(self, parsed):
        with _lock:
            data = self._load_raw()
            categories = data.setdefault("categories", [])
            channels = data.setdefault("channels", [])

            # Helper to find or create category
            cat_map = {c["id"]: c["name"] for c in categories}
            name_to_id = {c["name"].lower(): c["id"] for c in categories}

            def ensure_category(raw_name_or_id):
                if not raw_name_or_id:
                    cat_name = "منوعات"
                    cat_id = "general"
                else:
                    cat_name = str(raw_name_or_id).strip()
                    cat_id = cat_name.lower().replace(" ", "_")
                    # Clean special characters for ID
                    cat_id = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '', cat_id) or f"cat_{int(time.time())}"

                if cat_name.lower() in name_to_id:
                    return name_to_id[cat_name.lower()], cat_map.get(name_to_id[cat_name.lower()], cat_name)
                if cat_id in cat_map:
                    return cat_id, cat_map[cat_id]

                # Choose an icon
                icon = "📺"
                lower_name = cat_name.lower()
                if "رياض" in cat_name or "sport" in lower_name: icon = "⚽"
                elif "خبر" in cat_name or "أخبار" in cat_name or "news" in lower_name: icon = "🔴"
                elif "سينما" in cat_name or "فيلم" in cat_name or "movie" in lower_name: icon = "🎬"
                elif "دين" in cat_name or "قرآن" in cat_name or "إسلام" in cat_name: icon = "🕋"
                elif "أطفال" in cat_name or "كرتون" in cat_name or "kid" in lower_name: icon = "🦁"

                new_cat = {"id": cat_id, "name": cat_name, "icon": icon}
                categories.append(new_cat)
                cat_map[cat_id] = cat_name
                name_to_id[cat_name.lower()] = cat_id
                return cat_id, cat_name

            # Pre-populate categories if explicitly present in JSON
            if isinstance(parsed, dict) and "categories" in parsed and isinstance(parsed["categories"], list):
                for c in parsed["categories"]:
                    if isinstance(c, dict):
                        cid = c.get("id") or c.get("category_id") or c.get("slug")
                        cname = c.get("name") or c.get("category_name") or c.get("title") or cid
                        if cid and cname:
                            ensure_category(cname)

            raw_channel_list = []

            # 1. Dict with 'channels' or 'streams' or 'data'
            if isinstance(parsed, dict):
                if "channels" in parsed and isinstance(parsed["channels"], list):
                    raw_channel_list = parsed["channels"]
                elif "streams" in parsed and isinstance(parsed["streams"], list):
                    raw_channel_list = parsed["streams"]
                elif "data" in parsed:
                    if isinstance(parsed["data"], list):
                        raw_channel_list = parsed["data"]
                    elif isinstance(parsed["data"], dict) and "channels" in parsed["data"]:
                        raw_channel_list = parsed["data"]["channels"]
            # 2. List of items directly
            elif isinstance(parsed, list):
                # Check if it's a list of category objects containing channels
                if len(parsed) > 0 and isinstance(parsed[0], dict) and ("channels" in parsed[0] or "items" in parsed[0]):
                    for group in parsed:
                        group_cat = group.get("category") or group.get("category_name") or group.get("name") or "منوعات"
                        group_chans = group.get("channels") or group.get("items") or []
                        for ch in group_chans:
                            if isinstance(ch, dict):
                                ch["_forced_category"] = group_cat
                                raw_channel_list.append(ch)
                else:
                    raw_channel_list = parsed

            imported_count = 0
            for item in raw_channel_list:
                if not isinstance(item, dict):
                    continue

                # Channel Name
                name = (
                    item.get("name") or item.get("title") or item.get("channel_name")
                    or item.get("stream_name") or item.get("label") or item.get("tvg-name")
                )
                if not name:
                    continue

                # Stream URL
                url = (
                    item.get("url") or item.get("stream_url") or item.get("link")
                    or item.get("stream") or item.get("play_url") or item.get("source")
                    or item.get("direct_source") or item.get("server_url")
                )
                if not url:
                    # Check in servers list if present
                    if "servers" in item and isinstance(item["servers"], list) and len(item["servers"]) > 0:
                        url = item["servers"][0].get("url")
                if not url:
                    continue

                # Category
                raw_cat = item.get("_forced_category") or item.get("category") or item.get("category_name") or item.get("cat") or item.get("group") or "منوعات"
                cat_id, cat_name = ensure_category(raw_cat)

                # Logo
                logo = (
                    item.get("logo") or item.get("icon") or item.get("stream_icon")
                    or item.get("image") or item.get("poster") or "📺"
                )

                # Quality
                quality = item.get("quality") or ("4K / FHD" if "4k" in str(name).lower() else "HD")

                ch_id = item.get("id") or f"ch-php-{int(time.time())}-{imported_count}"

                # Servers
                if "servers" in item and isinstance(item["servers"], list) and len(item["servers"]) > 0:
                    servers = item["servers"]
                else:
                    stream_type = "hls" if ".m3u8" in str(url).lower() else "mp4"
                    servers = [{"name": "سيرفر البث الرئيسي", "url": str(url).strip(), "type": stream_type}]

                new_ch = {
                    "id": str(ch_id),
                    "name": str(name).strip(),
                    "category": cat_id,
                    "categoryName": cat_name,
                    "currentShow": item.get("currentShow") or item.get("epg") or "بث مباشر عبر الإنترنت",
                    "logo": logo,
                    "quality": quality,
                    "badge": "مباشر",
                    "servers": servers
                }

                # Avoid exact duplicate channel ID
                existing_idx = next((i for i, c in enumerate(channels) if c["id"] == new_ch["id"]), None)
                if existing_idx is not None:
                    channels[existing_idx] = new_ch
                else:
                    channels.append(new_ch)
                imported_count += 1

            self._save_raw(data)
            return {
                "success": True,
                "channels_count": imported_count,
                "categories_count": len(categories),
                "total_channels": len(channels)
            }

    # ------------------ M3U Importer ------------------
    def sync_m3u_from_url(self, url, category="sports", category_name="رياضة"):
        """Fetch and parse M3U playlist and add discovered channels to database."""
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=12) as response:
                content = response.read().decode("utf-8", errors="ignore")

            lines = content.splitlines()
            imported_count = 0
            current_name = ""
            current_logo = "📺"
            current_cat = category
            current_cat_name = category_name

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#EXTINF:"):
                    name_match = re.search(r',([^,]+)$', line)
                    current_name = name_match.group(1).strip() if name_match else "قناة بث مباشر"

                    logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                    current_logo = logo_match.group(1).strip() if logo_match else "📺"

                    group_match = re.search(r'group-title="([^"]+)"', line)
                    if group_match:
                        current_cat_name = group_match.group(1).strip()
                        current_cat = current_cat_name.lower().replace(" ", "_")

                elif not line.startswith("#") and (line.startswith("http://") or line.startswith("https://")):
                    if current_name:
                        self.add_category(current_cat, current_cat_name)
                        ch_id = f"m3u-{int(time.time())}-{imported_count}"
                        ch_data = {
                            "id": ch_id,
                            "name": current_name,
                            "category": current_cat,
                            "categoryName": current_cat_name,
                            "currentShow": "بث مباشر عبر الإنترنت",
                            "logo": current_logo,
                            "quality": "HD",
                            "badge": "مباشر",
                            "servers": [
                                {"name": "سيرفر البث", "url": line, "type": "hls" if ".m3u8" in line else "mp4"}
                            ]
                        }
                        self.add_channel(ch_data)
                        imported_count += 1
                        current_name = ""
                        if imported_count >= 150:
                            break
            return imported_count
        except Exception:
            return -1

    def _parse_m3u_text(self, content, default_cat="sports", default_cat_name="قنوات رياضية"):
        lines = content.splitlines()
        imported_count = 0
        current_name = ""
        current_logo = "📺"
        current_cat = default_cat
        current_cat_name = default_cat_name

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF:"):
                name_match = re.search(r',([^,]+)$', line)
                current_name = name_match.group(1).strip() if name_match else "قناة بث مباشر"

                logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                current_logo = logo_match.group(1).strip() if logo_match else "📺"

                group_match = re.search(r'group-title="([^"]+)"', line)
                if group_match:
                    current_cat_name = group_match.group(1).strip()
                    current_cat = current_cat_name.lower().replace(" ", "_")
                    current_cat = re.sub(r'[^a-zA-Z0-9_\u0600-\u06FF]', '', current_cat) or "general"

            elif not line.startswith("#") and (line.startswith("http://") or line.startswith("https://")):
                if current_name:
                    self.add_single_channel(
                        name=current_name,
                        url=line,
                        category_id=current_cat,
                        category_name=current_cat_name,
                        logo=current_logo,
                        quality="HD"
                    )
                    imported_count += 1
                    current_name = ""
        return {
            "success": True,
            "type": "playlist_imported",
            "format": "m3u",
            "channels_count": imported_count,
            "total_channels": len(self.get_channels())
        }

    def process_universal_link(self, input_text, channel_name=None, category_id=None, category_name=None, logo="📺", quality="FHD"):
        """
        Universal link and raw code processor supporting:
        - m3u8 (HLS stream)
        - ts (MPEG-TS stream)
        - js (JavaScript stream link or API)
        - php (Ostora/PHP stream link or PHP API JSON)
        - json (JSON API endpoint or pasted JSON data)
        - m3u (M3U playlist link or pasted M3U text)
        """
        raw = input_text.strip()
        lower_raw = raw.lower()

        # 1. Pasted raw JSON code
        if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
            res = self.sync_php_json(raw)
            res["type"] = "api_json_imported"
            res["format"] = "json"
            return res

        # 2. Pasted raw M3U playlist text
        if "#EXTM3U" in raw or "#EXTINF:" in raw:
            return self._parse_m3u_text(raw, default_cat=category_id or "sports", default_cat_name=category_name or "قنوات رياضية")

        # 3. HTTP / HTTPS URL
        if raw.startswith("http://") or raw.startswith("https://"):
            # If channel_name is already provided, add directly as single channel
            if channel_name:
                ch = self.add_single_channel(
                    name=channel_name,
                    url=raw,
                    category_id=category_id or "general",
                    category_name=category_name,
                    logo=logo or "📺",
                    quality=quality or "FHD"
                )
                return {
                    "success": True,
                    "type": "single_channel_added",
                    "channel": ch,
                    "total_channels": len(self.get_channels()),
                    "message": f"تمت إضافة القناة {ch['name']} بنجاح في قسم {ch['categoryName']}!"
                }

            # Check if URL explicitly indicates M3U
            if ".m3u" in lower_raw and not ".m3u8" in lower_raw:
                count = self.sync_m3u_from_url(raw, category=category_id or "sports")
                return {
                    "success": True if count >= 0 else False,
                    "type": "playlist_imported",
                    "format": "m3u",
                    "channels_count": count,
                    "total_channels": len(self.get_channels())
                }

            # Attempt inspection of URL content
            try:
                req = Request(
                    raw,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                        "Accept": "*/*"
                    }
                )
                with urlopen(req, timeout=8) as resp:
                    ct = resp.headers.get("Content-Type", "").lower()
                    peek = resp.read(4096).decode("utf-8", errors="ignore")

                    if "#EXTM3U" in peek or "#EXTINF:" in peek:
                        count = self.sync_m3u_from_url(raw, category=category_id or "sports")
                        return {
                            "success": True if count >= 0 else False,
                            "type": "playlist_imported",
                            "format": "m3u",
                            "channels_count": count,
                            "total_channels": len(self.get_channels())
                        }

                    if "application/json" in ct or (peek.strip().startswith("{") or peek.strip().startswith("[")):
                        res = self.sync_php_json(raw)
                        res["type"] = "api_json_imported"
                        res["format"] = "json"
                        return res
            except Exception:
                pass

            # Detect format of single stream
            detected_fmt = "m3u8"
            if ".ts" in lower_raw:
                detected_fmt = "ts"
            elif ".php" in lower_raw:
                detected_fmt = "php"
            elif ".js" in lower_raw:
                detected_fmt = "js"
            elif ".mp4" in lower_raw:
                detected_fmt = "mp4"

            # Suggest channel name from URL if possible
            suggested_name = "قناة بث مباشر"
            if "id=" in raw:
                try:
                    qid = raw.split("id=")[1].split("&")[0]
                    suggested_name = f"قناة سبورت {qid}" if ("cat=4524" in raw or "cat=331" in raw) else f"قناة {qid}"
                except Exception:
                    pass

            return {
                "success": True,
                "type": "need_details",
                "url": raw,
                "format": detected_fmt,
                "suggested_name": suggested_name
            }

        return {
            "success": False,
            "error": "الرابط أو النص المدخل غير صالح. يرجى إرسال رابط يبدأ بـ http:// أو https:// أو لصق كود JSON أو M3U."
        }

    # ------------------ Maintenance Mode ------------------
    def get_maintenance(self):
        with _lock:
            data = self._load_raw()
            return data.get("maintenance", {
                "enabled": False,
                "message": "التطبيق يخضع لصيانة دورية، سنعود قريباً!",
                "updated_at": ""
            })

    def set_maintenance(self, enabled: bool, message=None):
        with _lock:
            data = self._load_raw()
            m = data.setdefault("maintenance", {})
            m["enabled"] = bool(enabled)
            if message:
                m["message"] = str(message).strip()
            m["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_raw(data)
            return m

    # ------------------ App Update ------------------
    def get_app_update(self):
        with _lock:
            data = self._load_raw()
            return data.get("app_update", {
                "enabled": False,
                "version_code": 2,
                "version_name": "1.1",
                "download_url": "",
                "release_notes": "تحديث جديد لتطبيق A2 TV",
                "is_force": False,
                "updated_at": ""
            })

    def set_app_update(self, version_code: int, version_name: str, download_url: str, release_notes: str, is_force: bool = False, enabled: bool = True):
        with _lock:
            data = self._load_raw()
            up = data.setdefault("app_update", {})
            up["enabled"] = bool(enabled)
            up["version_code"] = int(version_code)
            up["version_name"] = str(version_name).strip()
            up["download_url"] = str(download_url).strip()
            up["release_notes"] = str(release_notes).strip()
            up["is_force"] = bool(is_force)
            up["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_raw(data)
            return up

    def toggle_app_update(self, enabled: bool):
        with _lock:
            data = self._load_raw()
            up = data.setdefault("app_update", {})
            up["enabled"] = bool(enabled)
            up["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._save_raw(data)
            return up

    # ------------------ Admins & Permissions ------------------
    def get_admins(self):
        with _lock:
            data = self._load_raw()
            return data.get("admins", {})

    def is_admin(self, user_id):
        if ADMIN_ID and user_id == ADMIN_ID:
            return True
        with _lock:
            data = self._load_raw()
            return str(user_id) in data.get("admins", {})

    def has_permission(self, user_id, permission):
        if ADMIN_ID and user_id == ADMIN_ID:
            return True
        with _lock:
            data = self._load_raw()
            admin = data.get("admins", {}).get(str(user_id))
            if not admin:
                return False
            perms = admin.get("permissions", [])
            return "all" in perms or permission in perms

    def add_admin(self, user_id, name="مشرف", permissions=None):
        if permissions is None:
            permissions = ["all"]
        with _lock:
            data = self._load_raw()
            admins = data.setdefault("admins", {})
            admins[str(user_id)] = {
                "id": int(user_id),
                "name": str(name),
                "role": "admin",
                "permissions": permissions,
                "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            self._save_raw(data)
            return admins[str(user_id)]

    def delete_admin(self, user_id):
        if ADMIN_ID and int(user_id) == ADMIN_ID:
            return False
        with _lock:
            data = self._load_raw()
            admins = data.get("admins", {})
            if str(user_id) in admins:
                del admins[str(user_id)]
                self._save_raw(data)
                return True
            return False

# Global Database Instance
db = Database()
