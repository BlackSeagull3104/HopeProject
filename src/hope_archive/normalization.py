"""Offline, loss-conscious mapping of Hope diary fields. No network or file I/O."""

from copy import deepcopy


def object_or_empty(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected an object or null")
    return value


def list_or_empty(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Expected a list or null")
    return value


def normalize_person(value):
    user = object_or_empty(value)
    # Allowlist: never copy the backend account object into the archive model.
    return {"id": user.get("id"), "name": user.get("nickName")}


def normalize_content(value):
    content = []
    for block in list_or_empty(value):
        if not isinstance(block, dict):
            raise ValueError("Each rich text block must be an object")
        media = []
        for file in list_or_empty(block.get("fileList")):
            if not isinstance(file, dict):
                raise ValueError("Each media reference must be an object")
            media.append({"file_id": file.get("fileId"), "url": file.get("mediaUrl"),
                          "media_name": file.get("mediaName")})
        source_type = block.get("type")
        # Observed locally: 1=text, 2=JPEG references, 3=MP4 reference.
        # Preserve source_type because these observations are not a full enum.
        kind = {1: "text", 2: "image", 3: "video"}.get(source_type, "unknown") if type(source_type) is int else "unknown"
        content.append({"kind": kind, "source_type": source_type,
                        "text": block.get("text"), "media": media})
    return content


def normalize_comments(value):
    groups = []
    for group in list_or_empty(value):
        if not isinstance(group, dict):
            raise ValueError("Each comment group must be an object")
        items = []
        for comment in list_or_empty(group.get("detail")):
            if not isinstance(comment, dict):
                raise ValueError("Each comment must be an object")
            items.append({
                "id": comment.get("commentId"), "reply_to_id": comment.get("toCommentId"),
                "text": comment.get("comments"), "created_at": comment.get("createTime"),
                "author": normalize_person(comment.get("fromUser")),
                "recipient": normalize_person(comment.get("toUser")),
                "from_name": comment.get("fromName"), "to_name": comment.get("toName"),
                "source_type": comment.get("type"), "voice_length": comment.get("voiceLength"),
                "like_count": comment.get("likeCount"), "tag": comment.get("tag"),
            })
        groups.append({"bundle_id": group.get("bundleId"), "items": items})
    return groups


def normalize_diary(entry):
    if not isinstance(entry, dict):
        raise ValueError("Each diary must be an object")
    diary_id = entry.get("dairyId")
    # A missing identity must not silently become an invented stable identity.
    if type(diary_id) not in (str, int) or diary_id == "":
        raise ValueError("Diary requires a nonempty string or integer dairyId")
    note = object_or_empty(entry.get("noteInfo2"))
    result = {
        "id": diary_id, "note_date": entry.get("noteDate"), "created_at": None,
        "original_text": entry.get("dairy"), "original_text_secondary": entry.get("dairy2"),
        "author": normalize_person(entry.get("user")),
        # No fallback text block: keep absent rich content distinct from dairy.
        "content": normalize_content(note.get("richTextInfo")),
        "legacy_media": {"audio_url": entry.get("audioUrl"),
                         "voice_duration": entry.get("voiceDuration"),
                         "video_url": entry.get("vedioUrl")},
        "emotion": {"value": entry.get("emotion"), "identity": entry.get("emotionIdentity")},
        "weather": {"value": entry.get("weather"), "identity": entry.get("weatherIdentity")},
        "comments": normalize_comments(entry.get("commentList")),
        "metadata": {"source_date": entry.get("date"), "source_open_time": entry.get("openTime"),
                     "note_type": entry.get("noteType"),
                     "parallel_show_status": entry.get("parallelShowStatus"),
                     "comment_count": entry.get("commentCount"),
                     "leaf_count": entry.get("dairyLeafCount"), "audio_count": entry.get("audioCount")},
    }
    return deepcopy(result)


def normalize_diaries(entries):
    if not isinstance(entries, list):
        raise ValueError("Input must be the combined diary list")
    # Preserve duplicates and order; normalization is not deduplication.
    return {"schema_version": 1, "source": "hope", "diaries": [normalize_diary(e) for e in entries]}
