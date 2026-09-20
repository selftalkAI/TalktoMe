from __future__ import annotations

import json

from ..config import settings
from .base import ModelProviderUnavailable


class BedrockProvider:
    """Talks to AWS Bedrock. Uses standard AWS credential resolution (env vars,
    ~/.aws/credentials, or an instance/role profile) — no secrets live in this file.

    Request/response shape below targets the Anthropic Claude message API as
    exposed through Bedrock; a different BEDROCK_MODEL_ID family (e.g. Titan,
    Llama) would need its own request/response mapping.
    """

    def __init__(
        self,
        region: str | None = None,
        model_id: str | None = None,
        embedding_model_id: str | None = None,
    ) -> None:
        self.region = region or settings.aws_region
        self.model_id = model_id or settings.bedrock_model_id
        self.embedding_model_id = embedding_model_id or settings.bedrock_embedding_model_id
        self._client = None  # created lazily so importing this module never requires boto3/AWS creds

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:
                raise ModelProviderUnavailable(
                    "boto3 is not installed. Run `pip install boto3` to use MODEL_PROVIDER=bedrock."
                ) from exc
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def chat(self, messages: list[dict[str, str]], *, system: str | None = None) -> str:
        client = self._get_client()
        body: dict[str, object] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": messages,
        }
        if system:
            body["system"] = system

        try:
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
        except Exception as exc:  # botocore raises many distinct exception types
            raise ModelProviderUnavailable(
                f"Bedrock invoke_model failed for '{self.model_id}' in {self.region}: {exc}. "
                "Check AWS credentials, region, and that model access is enabled in the Bedrock console."
            ) from exc

        payload = json.loads(response["body"].read())
        return payload["content"][0]["text"]

    def embed(self, text: str) -> list[float]:
        client = self._get_client()
        try:
            response = client.invoke_model(
                modelId=self.embedding_model_id,
                body=json.dumps({"inputText": text}),
                contentType="application/json",
                accept="application/json",
            )
        except Exception as exc:
            raise ModelProviderUnavailable(
                f"Bedrock invoke_model failed for embedding model '{self.embedding_model_id}' "
                f"in {self.region}: {exc}."
            ) from exc

        payload = json.loads(response["body"].read())
        return payload["embedding"]
