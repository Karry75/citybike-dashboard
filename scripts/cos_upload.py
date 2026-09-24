# -*- coding: utf-8 -*-
"""将本地文件 PUT 到 ima 的 COS（使用 create_media 返回的临时凭证）。
用法：python cos_upload.py <creds.json> <local_file> [content_type]
"""
import sys, json
from qcloud_cos import CosConfig, CosS3Client

cred = json.load(open(sys.argv[1], encoding='utf-8'))
local = sys.argv[2]
ctype = sys.argv[3] if len(sys.argv) > 3 else 'application/octet-stream'

config = CosConfig(
    Region=cred['region'],
    SecretId=cred['secret_id'],
    SecretKey=cred['secret_key'],
    Token=cred['token'],
)
client = CosS3Client(config)
with open(local, 'rb') as f:
    resp = client.put_object(
        Bucket=cred['bucket_name'],
        Body=f,
        Key=cred['cos_key'],
        ContentType=ctype,
    )
print('ETag:', resp.get('ETag'))
print('HTTP Code:', resp.get('x-cos-request-id') or 'ok')
print('UPLOAD_OK')
