"""Schema-aware transport minimization; authored text is never pattern-redacted.

Raw means source-shaped recovery data, not an exact HTTP capture. Unknown fields
are excluded. Invalid structures fail closed instead of becoming diagnostic text.
"""
import json


def scalar(value):
    return value if value is None or type(value) in (str, int, float, bool) else None


def project(value, schema):
    if value is None:
        return None
    if isinstance(schema, list):
        if not isinstance(value, list):
            raise ValueError('Invalid source list')
        return [project(item, schema[0]) for item in value]
    if isinstance(schema, dict):
        if not isinstance(value, dict):
            raise ValueError('Invalid source object')
        return {key: project(value[key], shape) for key, shape in schema.items() if key in value}
    return scalar(value)


def fields(names):
    return dict.fromkeys(names.split())


PERSON = fields('id nickName')
MEDIA = fields('fileId mediaUrl mediaName')
COMMENT = fields('commentId toCommentId comments createTime fromName toName type voiceLength likeCount tag') | {
    'fromUser': PERSON, 'toUser': PERSON}
DIARY = fields('dairyId noteType noteDate dairy dairy2 audioUrl voiceDuration vedioUrl emotion emotionIdentity weather weatherIdentity date openTime parallelShowStatus commentCount dairyLeafCount audioCount') | {
    'user': PERSON,
    'noteInfo2': {'richTextInfo': [fields('type text') | {'fileList': [MEDIA]}]},
    'commentList': [fields('bundleId') | {'detail': [COMMENT]}],
}
CAPSULE = fields('id title keywords hopeInfo createDate openDate userOpenDate updateDate openStatus user2OpenStatus canOpen status user2Status type hopeType openDateStatus openLocationStatus daysBeforeSeal tapeDuration tapeStatus videoUrl hopeImgUrl hopeImgUrl2 hopeImgUrl3 audioUrl tapeUrl videoPreviewUrl videoPreviewUrl2 videoPreviewUrl3') | {
    'user': PERSON, 'user2': PERSON, 'clientImg': fields('imageUrl'), 'mediaUrlList': [None]}


def minimized_response(body, kind='diary'):
    """Never persist server error bodies, status messages or unknown envelopes."""
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError()
        schema = {'status': None, 'datas': fields('total') | {'list': [DIARY]}}
        if kind == 'capsule':
            data = payload.get('datas')
            shape = (fields('total totalCount') | {'list': [CAPSULE], 'datas': [CAPSULE]}
                     if isinstance(data, dict) and ('list' in data or 'datas' in data) else CAPSULE)
            schema = {'status': None, 'datas': shape}
        if 'status' in payload and (type(payload['status']) is not int or payload['status'] != 1):
            return {'privacy_schema': 1, 'response': 'unsuccessful'}
        return project(payload, schema) | {'privacy_schema': 1}
    except (ValueError, TypeError, UnicodeError):
        return {'privacy_schema': 1, 'response': 'invalid-or-unrecognized'}
