"""DLKLAP client for Tapo DL-series locks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import aiohttp
from Crypto.Cipher import AES


Json = dict[str, Any]


class DlklapError(Exception):
    """Base error class."""


class DlklapAuthError(DlklapError):
    """Authentication error."""


def _sha(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for part in parts:
        h.update(part)
    return h.digest()


def _pkcs7_pad(data: bytes) -> bytes:
    pad = 16 - (len(data) % 16)
    return data + bytes([pad]) * pad


def _pkcs7_unpad(data: bytes) -> bytes:
    return data[: -data[-1]]


def _aes_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)


def _aes_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)


def _extract_json(data: bytes) -> Json:
    text = data.decode("utf-8")
    start = text.find("{")
    if start < 0:
        raise DlklapError("No JSON object start in response")
    depth = 0
    in_str = False
    esc = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_str:
            if esc:
                esc = False
            elif char == "\\":
                esc = True
            elif char == '"':
                in_str = False
        elif char == '"':
            in_str = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : idx + 1])
    raise DlklapError("No complete JSON object in response")


@dataclass
class DeviceInfo:
    """DL-series device state."""

    lock_status: int
    battery_percentage: int | None
    at_low_battery: bool | None
    raw: Json


class _Session:
    """A live DLKLAP session."""

    def __init__(
        self,
        ip: str,
        lsk: bytes,
        ldk: bytes,
        ivb: bytes,
        seq: int,
        cookie: str,
        websession: aiohttp.ClientSession,
    ) -> None:
        self._ip = ip
        self._lsk = lsk
        self._ldk = ldk
        self._ivb = ivb
        self._seq = seq
        self._cookie = cookie
        self._websession = websession

    async def call(self, requests: list[Json]) -> Json:
        return await self._request({"method": "multipleRequest", "params": {"requests": requests}})

    async def _request(self, plaintext: Json) -> Json:
        self._seq += 1
        seqb = self._seq.to_bytes(4, "big", signed=False)
        iv = self._ivb + seqb
        payload = json.dumps(plaintext).encode("utf-8")
        ciphertext = _aes_encrypt(self._lsk, iv, _pkcs7_pad(payload))
        mac = _sha(self._ldk, seqb, ciphertext)
        body = mac + ciphertext

        status, _, raw = await _post(
            self._websession,
            f"http://{self._ip}:80/app/request?seq={self._seq}",
            headers={
                "Referer": f"http://{self._ip}:80/",
                "Accept": "application/json",
                "requestByApp": "true",
                "Content-Type": "text/plain",
                "Cookie": self._cookie,
            },
            body=body,
        )
        if status != 200:
            raise DlklapError(f"/app/request HTTP {status} (seq={self._seq})")
        decrypted = _pkcs7_unpad(_aes_decrypt(self._lsk, iv, raw[32:]))
        return _extract_json(decrypted)


async def _post(
    websession: aiohttp.ClientSession,
    url: str,
    headers: dict[str, str],
    body: bytes | str,
    ssl: bool | None = None,
) -> tuple[int, aiohttp.typedefs.LooseHeaders, bytes]:
    kwargs: dict[str, Any] = {"headers": headers, "data": body}
    if ssl is not None:
        kwargs["ssl"] = ssl
    async with websession.post(url, **kwargs) as response:
        return response.status, response.headers, await response.read()


class DlklapApi:
    """Async client for TP-Link DLKLAP endpoints used by DL-series locks."""

    def __init__(
        self,
        ip: str,
        cloud_username: str,
        cloud_password: str,
        lock_name: str,
        websession: aiohttp.ClientSession,
        logger: logging.Logger,
        terminal_uuid: str | None = None,
        device_id: str | None = None,
    ) -> None:
        self.ip = ip
        self.cloud_username = cloud_username
        self.cloud_password = cloud_password
        self.lock_name = lock_name
        self.websession = websession
        self.log = logger

        self.terminal_uuid = terminal_uuid
        self.device_id = device_id
        self._token: str | None = None
        self._account_id: str | None = None
        self._session: _Session | None = None
        self._lock = asyncio.Lock()

    async def get_device_info(self) -> DeviceInfo:
        async def _do_call(session: _Session) -> DeviceInfo:
            result = await session.call([{"method": "getDeviceInfo"}])
            info = result["result"]["responses"][0]["result"]
            return DeviceInfo(
                lock_status=info["lock_status"],
                battery_percentage=info.get("battery_percentage"),
                at_low_battery=info.get("at_low_battery"),
                raw=info,
            )

        return await self._with_session(_do_call)

    async def set_lock(self, locked: bool) -> None:
        async def _do_call(session: _Session) -> None:
            response = await session.call(
                [
                    {
                        "method": "setLockStatus",
                        "params": {
                            "lock_status": 0 if locked else 1,
                            "sa_user_id": "local_1",
                        },
                    }
                ]
            )
            resp = response.get("result", {}).get("responses", [{}])[0]
            if resp.get("error_code") != 0:
                raise DlklapError(f"setLockStatus failed: {response}")

        await self._with_session(_do_call)

    async def _with_session(self, fn):
        async with self._lock:
            last_err: Exception | None = None
            for attempt in range(2):
                try:
                    await self._ensure_identifiers()
                    if self._session is None:
                        self._session = await self._handshake()
                        self.log.debug("New DLKLAP session established.")
                    return await fn(self._session)
                except Exception as err:  # noqa: BLE001
                    last_err = err
                    self._session = None
                    self._token = None
                    self.log.warning("Session attempt %s failed: %s", attempt + 1, err)
                    await asyncio.sleep(0.5)
            raise DlklapError(f"Session retries exhausted: {last_err}") from last_err

    async def _ensure_identifiers(self) -> None:
        if not self.terminal_uuid:
            self.terminal_uuid = str(uuid4()).upper()
            self.log.debug("Generated terminal_uuid: %s", self.terminal_uuid)
        if self.device_id:
            return

        await self._ensure_token()
        status, _, raw = await _post(
            self.websession,
            f"https://wap.tplinkcloud.com/?token={self._token}",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"method": "getDeviceList"}),
        )
        if status != 200:
            raise DlklapError(f"getDeviceList HTTP {status}")
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("error_code") != 0:
            raise DlklapError(f"getDeviceList failed: {payload}")
        devices = payload.get("result", {}).get("deviceList", [])
        dl_locks = [
            d
            for d in devices
            if str(d.get("deviceModel", "")).upper().startswith("DL")
        ]
        if not dl_locks:
            raise DlklapError("No DL-series lock devices found on this TP-Link account")
        if len(dl_locks) == 1:
            self.device_id = dl_locks[0]["deviceId"]
            return
        match = next((d for d in dl_locks if d.get("alias") == self.lock_name), None)
        if not match:
            aliases = ", ".join(d.get("alias", "<unknown>") for d in dl_locks)
            raise DlklapError(
                f"Multiple DL-series lock devices found ({aliases}). "
                "Set name to match alias in Tapo app exactly."
            )
        self.device_id = match["deviceId"]

    async def _ensure_token(self) -> None:
        if self._token:
            return
        if not self.terminal_uuid:
            self.terminal_uuid = str(uuid4()).upper()
        body = {
            "method": "login",
            "params": {
                "appType": "Tapo_Android",
                "cloudUserName": self.cloud_username,
                "cloudPassword": self.cloud_password,
                "terminalUUID": self.terminal_uuid,
                "refreshTokenNeeded": False,
            },
        }
        status, _, raw = await _post(
            self.websession,
            "https://wap.tplinkcloud.com/",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        if status != 200:
            raise DlklapAuthError(f"login HTTP {status}")
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("error_code") != 0:
            raise DlklapAuthError(f"login failed: {payload}")
        self._token = payload["result"]["token"]
        self._account_id = str(payload["result"]["accountId"])

    async def _handshake(self) -> _Session:
        if not self._account_id:
            await self._ensure_token()
        base = f"http://{self.ip}:80"
        local_headers = {"Content-Type": "text/plain", "Referer": f"{base}/"}

        random4 = b""
        control_key = None
        await self._ensure_token()
        for attempt in range(2):
            random4 = os.urandom(4)
            digest = _sha((random4.hex() + self._account_id).upper().encode("ascii"))
            hs0_body = digest[:32] + b"\x00"
            hs0_status, _, hs0_raw = await _post(
                self.websession,
                f"{base}/app/handshake0",
                headers=local_headers,
                body=hs0_body,
            )
            if hs0_status != 200:
                raise DlklapError(f"handshake0 HTTP {hs0_status}")
            secret = hs0_raw.decode("utf-8").strip()

            ck_status, _, ck_raw = await _post(
                self.websession,
                f"https://use1-app-server.iot.i.tplinknbu.com/v1/things/{self.device_id}/control-key",
                headers={
                    "Authorization": f"ut|{self._token}",
                    "app-cid": f"app:Tapo_Android:{self.terminal_uuid}",
                    "App-Type": "Tapo_Android",
                    "x-app-name": "Tapo_Android",
                    "UUID": self.terminal_uuid,
                    "Terminal-Id": self.terminal_uuid,
                    "x-term-id": self.terminal_uuid,
                    "Platform": "ANDROID",
                    "X-App-Os": "android",
                    "Content-Type": "application/json",
                },
                body=json.dumps(
                    {"secret": secret, "random": random4.hex().upper()}
                ),
                ssl=False,
            )
            if ck_status != 200:
                raise DlklapError(f"control-key HTTP {ck_status}")
            ck_payload = json.loads(ck_raw.decode("utf-8"))
            ck_code = int(
                ck_payload.get("code")
                or ck_payload.get("error_code")
                or ck_payload.get("result", {}).get("code")
                or 0
            )
            ck_obj = ck_payload.get("result") or ck_payload.get("data") or ck_payload
            control_key = ck_obj.get("controlKey") or ck_obj.get("control_key")
            if control_key:
                break
            if ck_code == 10000 and attempt == 0:
                self._token = None
                await self._ensure_token()
                continue
            raise DlklapError(f"control-key missing: {ck_payload}")

        if not control_key:
            raise DlklapError("control-key retry exhausted")

        control_key_bytes = control_key.upper().encode("ascii")
        lmk = _sha(control_key_bytes)
        local_random = os.urandom(16)
        hs1_body = local_random + _sha(local_random + control_key_bytes)
        hs1_status, hs1_headers, hs1_raw = await _post(
            self.websession,
            f"{base}/app/handshake1",
            headers=local_headers,
            body=hs1_body,
        )
        if hs1_status != 200:
            raise DlklapError(f"handshake1 HTTP {hs1_status}")

        cookie_token = ""
        for cookie_line in hs1_headers.getall("Set-Cookie", []):
            for part in cookie_line.split(";"):
                token = part.strip()
                if token.startswith("TP_SESSIONID="):
                    cookie_token = token
                    break
            if cookie_token:
                break
        if not cookie_token:
            raise DlklapError("No TP_SESSIONID cookie on handshake1")

        remote_random = hs1_raw[:16]
        server_proof = hs1_raw[16:48]
        expected_proof = _sha(local_random + remote_random + lmk)
        if expected_proof != server_proof:
            raise DlklapError("handshake1 server proof mismatch")

        hs2_status, _, _ = await _post(
            self.websession,
            f"{base}/app/handshake2",
            headers={**local_headers, "Cookie": cookie_token},
            body=_sha(remote_random + local_random + lmk),
        )
        if hs2_status != 200:
            raise DlklapError(f"handshake2 HTTP {hs2_status}")

        def kdf(tag: str) -> bytes:
            return _sha(tag.encode("ascii") + local_random + remote_random + lmk)

        lsk = kdf("lsk")[:16]
        ldk = kdf("ldk")[:28]
        iv_full = kdf("iv")
        ivb = iv_full[:12]
        seq0 = int.from_bytes(iv_full[28:32], "big") & 0x7FFFFFFF

        return _Session(
            ip=self.ip,
            lsk=lsk,
            ldk=ldk,
            ivb=ivb,
            seq=seq0,
            cookie=cookie_token,
            websession=self.websession,
        )
