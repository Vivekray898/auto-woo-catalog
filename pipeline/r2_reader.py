from __future__ import annotations

import logging
import re
from typing import Iterable

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from config import Settings
from utils import PipelineError

logger = logging.getLogger("auto_woo_catalog.r2")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".avif")


def list_r2_images(settings: Settings) -> list[str]:
    """List public URLs for all image objects in the configured R2 bucket.

    Raises PipelineError on connectivity or configuration issues.
    """
    endpoint = settings.r2_endpoint
    access_key = settings.r2_access_key
    secret_key = settings.r2_secret_key
    bucket = settings.r2_bucket
    public_base = settings.r2_public_url.rstrip("/")

    if not all((endpoint, access_key, secret_key, bucket, public_base)):
        raise PipelineError("Incomplete R2 configuration; please set R2_* variables.")

    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    s3 = session.client(
        "s3",
        endpoint_url=endpoint,
        config=BotoConfig(signature_version="s3v4", s3={'addressing_style': 'path'}),
    )

    paginator = s3.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(Bucket=bucket)

    urls: list[str] = []
    pattern = re.compile(r".*(\.[jJ][pP][gG]|\.[jJ][pP][eE][gG]|\.[pP][nN][gG]|\.[wW][eE][bB][pP]|\.[aA][vV][iI][fF])$")

    try:
        for page in page_iterator:
            contents = page.get("Contents", [])
            for obj in contents:
                key = obj.get("Key", "")
                if not key or not pattern.match(key):
                    continue
                urls.append(f"{public_base}/{key}")
    except (BotoCoreError, ClientError) as exc:
        raise PipelineError(f"Error listing R2 bucket: {exc}") from exc

    logger.info("Found %s images in R2 bucket %s", len(urls), bucket)
    return urls
