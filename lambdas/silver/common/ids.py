import hashlib
import json
import uuid


USER_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def user_id_for(platform, username):
    return str(uuid.uuid5(USER_ID_NAMESPACE, f"{platform}:{username}"))


def hash_csv_row(row_dict):
    canonical = json.dumps(row_dict, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
