import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8001"))
SLACK_INFO_PATH = Path(os.environ.get("SLACK_INFO_PATH", "/app/env/slack_info.json"))


def load_slack_info() -> dict:
    if not SLACK_INFO_PATH.exists():
        raise FileNotFoundError(f"Slack info file not found: {SLACK_INFO_PATH}")

    with SLACK_INFO_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    slack_id = str(data.get("slack_id") or "").strip()
    token = str(data.get("SLACK_USER_TOKEN") or "").strip()
    if not slack_id or not token:
        raise ValueError("slack_id or SLACK_USER_TOKEN is missing")

    return {"slack_id": slack_id, "token": token}


def slack_api(method: str, payload: dict, token: str) -> dict:
    request = Request(
        url=f"https://slack.com/api/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def send_slack_dm(payload: dict) -> None:
    slack_info = load_slack_info()

    channel_result = slack_api(
        "conversations.open",
        {"users": slack_info["slack_id"]},
        slack_info["token"],
    )
    if not channel_result.get("ok"):
        raise RuntimeError(channel_result.get("error", "failed_to_open_dm"))

    channel_id = (((channel_result.get("channel") or {})).get("id") or "").strip()
    if not channel_id:
        raise RuntimeError("missing_channel_id")

    lines = [
        "*ETLERS Portal 슬랙 문의*",
        f"- 이름: {payload['name']}",
        f"- 연락처: {payload['contact']}",
        f"- 서비스: {payload['service']}",
        "- 문의 내용:",
        payload["message"],
    ]
    message = "\n".join(lines)

    message_result = slack_api(
        "chat.postMessage",
        {"channel": channel_id, "text": message},
        slack_info["token"],
    )
    if not message_result.get("ok"):
        raise RuntimeError(message_result.get("error", "failed_to_send_message"))


class Handler(BaseHTTPRequestHandler):
    server_version = "ETLERSContactAPI/1.0"

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health" or self.path == "/api/contact/health":
            self._json_response(200, {"status": "ok"})
            return
        self._json_response(404, {"detail": "Not found"})

    def do_POST(self) -> None:
        if self.path != "/api/contact/slack":
            self._json_response(404, {"detail": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            self._json_response(400, {"detail": "요청 본문이 비어 있습니다."})
            return

        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            self._json_response(400, {"detail": "JSON 형식이 올바르지 않습니다."})
            return

        payload = {
            "name": str(data.get("name") or "").strip(),
            "contact": str(data.get("contact") or "").strip(),
            "service": str(data.get("service") or "").strip() or "포털 문의",
            "message": str(data.get("message") or "").strip(),
        }

        if not payload["name"]:
            self._json_response(400, {"detail": "이름을 입력해주세요."})
            return
        if not payload["contact"]:
            self._json_response(400, {"detail": "연락처를 입력해주세요."})
            return
        if not payload["message"]:
            self._json_response(400, {"detail": "문의 내용을 입력해주세요."})
            return

        try:
            send_slack_dm(payload)
        except FileNotFoundError:
            self._json_response(500, {"detail": "슬랙 설정 파일을 찾을 수 없습니다."})
        except ValueError:
            self._json_response(500, {"detail": "슬랙 설정이 올바르지 않습니다."})
        except HTTPError:
            self._json_response(502, {"detail": "슬랙 API 호출 중 오류가 발생했습니다."})
        except URLError:
            self._json_response(502, {"detail": "슬랙 서버에 연결할 수 없습니다."})
        except RuntimeError as exc:
            self._json_response(502, {"detail": f"슬랙 전송 실패: {exc}"})
        except Exception:
            self._json_response(500, {"detail": "문의 전송 중 알 수 없는 오류가 발생했습니다."})
        else:
            self._json_response(200, {"message": "슬랙 문의가 전송되었습니다."})

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Contact API listening on {HOST}:{PORT}", flush=True)
    httpd.serve_forever()
